class_name GameFont
extends RefCounted
## The game's text font, built at run time from res://assets_ripped/ui/ (remake/tools/conv_ui.py; docs/HUD.md,
## "The text font"): UNICODEFONT's glyphs keyed by Unicode code point, the BUTTON icon sheet and the crime icons
## as glyphs of the same font (so "○", "①", "←" in a string draw the game's pictures), and the @N colour palette.
##
##     label.add_theme_font_override("font", GameFont.font())
##     label.add_theme_font_size_override("font_size", GameFont.SIZE)
##
## Like the game: glyphs advance 0.95 x their width (the game also draws them 0.95 wide; a Godot bitmap font
## can't squeeze a glyph, so they overlap by that 5 %), lines are 24 high, icons keep their own sizes and the
## game's small vertical nudges. Without the assets font() returns the default theme
## font and color() a placeholder palette, so scenes still run.

const DIR := "res://assets_ripped/ui/"
const SIZE := 24                 ## the font's pixel size (glyph cells are 24 high)
const ASCENT := 19.0             ## baseline inside the 24-pixel cell (remake choice: looks right for Latin)
## Placeholder palette (no assets): same hues as g_TextPalette.
const FALLBACK_PALETTE := [Color.WHITE, Color.WHITE, Color.RED, Color.GREEN, Color.BLUE,
	Color8(241, 95, 93), Color8(255, 255, 95), Color8(233, 166, 214), Color8(113, 238, 200), Color(0, 0, 0, 0)]

static var _font: Font
static var _data := {}
static var _tried := false


static func _load() -> void:
	if _tried:
		return
	_tried = true
	var path := DIR + "font.json"
	if FileAccess.file_exists(path):
		var d = JSON.parse_string(FileAccess.get_file_as_string(path))
		if d is Dictionary:
			_data = d


## True when the converted font is there (remake_assets.py was run).
static func available() -> bool:
	_load()
	return not _data.is_empty() and FileAccess.file_exists(DIR + "font_page0.png")


## An image from assets_ripped/ui/ (read from the PNG, so no import step is needed), or null.
static func image(file: String) -> Image:
	var p := DIR + file
	if not FileAccess.file_exists(p):
		return null
	return Image.load_from_file(ProjectSettings.globalize_path(p))


## A texture from assets_ripped/ui/, or null.
static func texture(file: String) -> Texture2D:
	var img := image(file)
	return ImageTexture.create_from_image(img) if img else null


## Text colour `n` of the @N / $N codes (g_TextPalette); 0 = the box's own colour (white here).
static func color(n: int) -> Color:
	_load()
	var pal: Array = _data.get("palette", [])
	if n <= 0:
		return Color.WHITE
	if n < pal.size():
		var c: Array = pal[n]
		return Color8(int(c[0]), int(c[1]), int(c[2]), int(c[3]))
	return FALLBACK_PALETTE[n] if n < FALLBACK_PALETTE.size() else Color.WHITE


## The text font (a bitmap FontFile), or the default theme font without the assets.
static func font() -> Font:
	if _font:
		return _font
	if not available():
		_font = ThemeDB.fallback_font
		return _font
	var f := FontFile.new()
	f.fixed_size = SIZE
	f.fixed_size_scale_mode = TextServer.FIXED_SIZE_SCALE_ENABLED
	f.antialiasing = TextServer.FONT_ANTIALIASING_GRAY
	var size := Vector2i(SIZE, 0)
	var pages: Dictionary = _data.get("pages", {})
	var tex_index := {}
	for page in pages:
		var img := image(pages[page]["texture"])
		if img == null:
			continue
		tex_index[page] = tex_index.size()
		f.set_texture_image(0, size, tex_index[page], img)
	var adv: float = _data.get("advance", 0.95)
	var glyphs: Dictionary = _data.get("glyphs", {})
	for key in glyphs:
		var g: Array = glyphs[key]
		var page := str(int(g[0]))
		if not tex_index.has(page):
			continue
		var code := int(key)
		var w := float(g[3])
		var h := float(g[4])
		f.set_glyph_texture_idx(0, size, code, tex_index[page])
		f.set_glyph_uv_rect(0, size, code, Rect2(g[1], g[2], w, h))
		f.set_glyph_size(0, size, code, Vector2(w, h))   # must equal the UV size (Godot samples by it)
		# Icons are taller or shorter than the 24-pixel cell: centre them on the line, plus the game's nudge.
		var top := -ASCENT if int(g[0]) == 0 else -ASCENT + (24.0 - h) * 0.5
		f.set_glyph_offset(0, size, code, Vector2(0, top + float(g[5])))
		f.set_glyph_advance(0, SIZE, code, Vector2(w * adv, 0))
	f.set_cache_ascent(0, SIZE, ASCENT)
	f.set_cache_descent(0, SIZE, 24.0 - ASCENT)
	f.fallbacks = [ThemeDB.fallback_font]
	_font = f
	return _font


## BBCode for a RichTextLabel from the game's markup: GameText.render_markup with the palette's colours;
## button and icon glyphs come out as their characters, which this font draws as the game's pictures
## (always white, like Text_Encode gives icons colour 1).
static func bbcode(markup: String, vars := {}) -> String:
	return GameText.render_markup(markup, vars, true)
