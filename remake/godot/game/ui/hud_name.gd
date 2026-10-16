class_name HudName
extends Control
## A fighter's name over its HP bar (HpBar_Build): SYSFONT02's cells (16 columns x 14 rows of 16 x 18.3 px,
## gold metal, codes from 0x20; rows 6-7 unused, Latin-1 from row 8)
## drawn 22 x 30 each. Spacing is each glyph's own ink width + 1 (remake choice: the game's spacing isn't
## traced). Side 0 starts at the node's left edge, side 1 ends at its right edge. Default font without assets.

@export_range(0, 1) var side := 0
@export var text := "":
	set(v):
		if v != text:
			text = v
			queue_redraw()
@export var tint := Color.WHITE

static var _tex: Texture2D
static var _ink := {}            ## code -> Vector2i(first, last) ink column in the cell
static var _rows: Array = []
static var _cell := Vector2(16, 256.0 / 14.0)
static var _loaded := false

const DRAW := Vector2(22, 30)


static func _load() -> void:
	if _loaded:
		return
	_loaded = true
	GameFont.available()
	var p := GameFont.DIR + "font.json"
	var d = JSON.parse_string(FileAccess.get_file_as_string(p)) if FileAccess.file_exists(p) else null
	if not d is Dictionary or not d.has("name_font"):
		return
	var nf: Dictionary = d["name_font"]
	var img := GameFont.image(nf["texture"])
	if img == null:
		return
	_tex = ImageTexture.create_from_image(img)
	var c: Array = nf.get("cell", [16, 256.0 / 14.0])
	_cell = Vector2(float(c[0]), float(c[1]))
	_rows = nf.get("rows", [])
	for r: Array in _rows:
		for row in range(int(r[0]), int(r[1])):
			for col in range(16):
				var code := int(r[2]) + (row - int(r[0])) * 16 + col
				var lo := int(_cell.x)
				var hi := -1
				for x in range(int(_cell.x)):
					for y in range(int(_cell.y)):
						if img.get_pixel(int(col * _cell.x) + x, int(row * _cell.y) + y).a > 0.1:
							lo = mini(lo, x)
							hi = maxi(hi, x)
							break
				_ink[code] = Vector2i(lo, hi)


static func _cell_of(code: int) -> Vector2i:
	for r: Array in _rows:
		var first := int(r[2])
		var n := (int(r[1]) - int(r[0])) * 16
		if code >= first and code < first + n:
			return Vector2i((code - first) % 16, int(r[0]) + (code - first) / 16)
	return Vector2i(-1, -1)


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_load()


func text_width() -> float:
	var w := 0.0
	for c in text:
		w += _advance(c.unicode_at(0))
	return w


func _advance(code: int) -> float:
	var ink: Vector2i = _ink.get(code, Vector2i(0, -1))
	if ink.y < ink.x:
		return DRAW.x * 0.45   # space
	return (ink.y - ink.x + 1) * DRAW.x / _cell.x + 1.0


func _draw() -> void:
	if _tex == null:
		var f := ThemeDB.fallback_font
		var w := f.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, 26).x
		draw_string(f, Vector2(size.x - w if side == 1 else 0.0, 24), text, HORIZONTAL_ALIGNMENT_LEFT, -1, 26, tint)
		return
	var x := size.x - text_width() if side == 1 else 0.0
	var sx := DRAW.x / _cell.x
	for c in text:
		var code := c.unicode_at(0)
		var cell := _cell_of(code)
		var ink: Vector2i = _ink.get(code, Vector2i(0, -1))
		if cell.x >= 0 and ink.y >= ink.x:
			var src := Rect2(cell.x * _cell.x + ink.x, cell.y * _cell.y, ink.y - ink.x + 1, _cell.y)
			draw_texture_rect_region(_tex, Rect2(x, 0, src.size.x * sx, DRAW.y), src, tint)
		x += _advance(code)
