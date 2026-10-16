class_name GameText
extends RefCounted
## The game's own text, by text id (Text_Get's ids), from res://assets_ripped/text/ (remake/tools/conv_text.py).
##
## Strings are in the converter's markup (docs/FORMATS.md, "Text"): "\n" new lines, {c0}..{c9} colours,
## placeholders {person} {person2} {area} {item} {item1} {item2} {money} {num1} {num2} {text1} {text2},
## buttons {btn:punch} {btn:kick} {btn:guard} {btn:special} (+ "_on" = pressed), {btn:ok} {btn:back} {btn:third},
## {btn:circle} ... and icons {icon:N}. text() returns the markup; render() fills it in for a Label or RichTextLabel.
## Without assets_ripped every lookup returns "#<id>" (and available() is false), so scenes still run.
##
##     GameText.text(11069)                     # "Aaron"
##     GameText.render(30747, {"person": "Gina"}) # "Add Gina to the party."
##     GameText.move_list(0x13)[0]              # ["Blade Cut", "□"]

const DIR := "res://assets_ripped/text/"

## Face-button glyphs per action for the game's default controller layout 0 (g_PadLayouts 0x005CF7C0).
const BUTTONS := {
	"punch": "□", "kick": "△", "guard": "×", "special": "○",
	"punch_on": "■", "kick_on": "▲", "guard_on": "Ⅹ", "special_on": "●",
	"ok": "×", "back": "△", "third": "□",
	"circle": "○", "triangle": "△", "square": "□", "cross": "×",
	"circle_on": "●", "triangle_on": "▲", "square_on": "■", "cross_on": "Ⅹ",
}
## Icon glyphs per {icon:...} token (GameFont draws them as the game's button pictures: docs/HUD.md).
const ICONS := {
	"1": "①", "2": "②", "3": "③", "4": "④", "5": "⑤", "6": "⑥", "17": "⑰", "18": "⑱",
	"rapid": "∬", "alpha": "α", "beta": "β",
}

static var language := "en"
static var _text := {}
static var _dialogue := {}
static var _index := {}
static var _loaded := ""


static func _load() -> void:
	if _loaded == language:
		return
	_loaded = language
	_text = _read(DIR + language + ".json").get("text", {})
	_dialogue = _read(DIR + "dialogue_" + language + ".json").get("scripts", {})
	_index = _read(DIR + "index.json")


static func _read(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var data = JSON.parse_string(FileAccess.get_file_as_string(path))
	return data if data is Dictionary else {}


## True when the converted text is there (remake_assets.py was run).
static func available() -> bool:
	_load()
	return not _text.is_empty()


## The markup of text id `id`, or "#id" when it is missing.
static func text(id: int) -> String:
	_load()
	return _text.get(str(id), "#%d" % id)


static func has(id: int) -> bool:
	_load()
	return _text.has(str(id))


## A script's strings (SCRIPT.XAF entry: 0-999 dialogue, 1000 + n mission n).
static func dialogue(entry: int) -> PackedStringArray:
	_load()
	return PackedStringArray(_dialogue.get(str(entry), []))


## Name of person / fighter `n` (text 11001 + n; the game uses Person +0x3E, the hero their hero def).
static func person_name(n: int) -> String:
	return text(11001 + n)


## Name of item `n` (text 11999 + n, from 108 on 17316 + n).
static func item_name(n: int) -> String:
	return text((11999 if n < 108 else 17316) + n)


## Name of area `area` (Area_Current numbering; g_AreaDefs name text). short = the short name.
static func area_name(area: int, short := false) -> String:
	_load()
	var a: Array = _index.get("areas", {}).get(str(area), [])
	return text(int(a[1 if short else 0])) if a.size() == 2 else "#area%d" % area


## A style's MOVE LIST: [[name, input], ...] with the inputs rendered as button glyphs.
static func move_list(style: int) -> Array:
	_load()
	var v: Array = _index.get("move_lists", {}).get(str(style), [])
	var out := []
	if v.size() == 4:
		for i in range(int(v[1]) - int(v[0]) + 1):
			out.append([render_markup(text(int(v[2]) + i)).strip_edges(), render_markup(text(int(v[0]) + i))])
	return out


## text(id) with placeholders filled from `vars` ({"person": "Gina", "money": 500, ...}); see render_markup.
static func render(id: int, vars := {}, bbcode := false) -> String:
	return render_markup(text(id), vars, bbcode)


## Fill markup: placeholders from `vars` (missing ones stay as {name}), buttons and icons as their glyphs
## (GameFont draws them as the game's pictures), {lb}/{rb} as braces, colours as [color] BBCode with the game's
## palette (g_TextPalette, GameFont.color) when `bbcode` is true, else dropped. In BBCode, buttons and icons
## are forced white like the game draws them (Text_Encode gives them colour 1).
static func render_markup(s: String, vars := {}, bbcode := false) -> String:
	var out := ""
	var i := 0
	var open_color := false
	while i < s.length():
		var c := s[i]
		if c != "{":
			out += c
			i += 1
			continue
		var j := s.find("}", i)
		if j < 0:
			out += s.substr(i)
			break
		var tok := s.substr(i + 1, j - i - 1)
		i = j + 1
		if tok == "lb":
			out += "{"
		elif tok == "rb":
			out += "}"
		elif tok.length() == 2 and tok[0] == "c" and tok[1].is_valid_int():
			if bbcode:
				if open_color:
					out += "[/color]"
					open_color = false
				var n := int(tok[1])
				if n > 0:
					out += "[color=#%s]" % GameFont.color(n).to_html()
					open_color = true
		elif tok.begins_with("btn:"):
			out += _glyph(BUTTONS.get(tok.substr(4), "?"), bbcode)
		elif tok.begins_with("icon:"):
			var k := tok.substr(5)
			out += _glyph(ICONS.get(k, char(k.hex_to_int()) if k.length() == 4 else "?"), bbcode)
		elif tok == "money" and vars.has(tok):   # "$" (text 10202) + amount; German puts the amount first
			out += (str(vars[tok]) + text(10202)) if language == "de" else (text(10202) + str(vars[tok]))
		elif vars.has(tok):
			out += str(vars[tok])
		else:
			out += "{%s}" % tok
	if open_color:
		out += "[/color]"
	return out


static func _glyph(g: String, bbcode: bool) -> String:
	return "[color=#ffffff]%s[/color]" % g if bbcode else g
