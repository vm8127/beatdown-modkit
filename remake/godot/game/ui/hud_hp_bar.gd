class_name HudHpBar
extends Control
## One HP bar of the fight HUD, drawn like HpBar_LayerQuads (docs/HUD.md, "HP bars"): four layers of three
## quads (cap, stretched middle, cap) whose length follows max HP (1.4 x value x 0.018 px), a red damage trail
## that drains 1/60 of the gap per frame, and a pulsing colour at 20 % HP or less. Side 1 is mirrored.
## Lives in a 640 x 448 parent (FightHud's Screen) and covers it; set_values() once per game frame.
## Without assets_ripped/ui/ it draws plain rectangles in the same place.

@export_range(0, 1) var side := 0
@export_range(0, 2) var member := 0       ## party row: 0 the fighter, 1-2 drawn at 0.7 scale
@export var enemy_named := true            ## side 1: magenta bar (PersonDef +0xB = 0) or orange
@export var show_tired := true             ## remake-only TIRED strip under the bar (the game has none)

var max_hp := 0
var hp := 0
var trail := 0            ## g_HpBars +4: the shown value
var _drain_left := 0      ## +0x14: damage still to drain into the trail
var pride_offset := 0.0   ## members 1-2 move down while the Pride gauge shows (HpBar_SetPrideOffset)
var tired_ratio := 0.0    ## 0..1 of tired_max
var tired_max := 0

static var _cfg := {}
static var _frame_tex: Texture2D
static var _fill_tex: Texture2D
static var _pulse_n := 0
static var _pulse_up := true
static var _pulse_frame := -1


static func config() -> Dictionary:
	if _cfg.is_empty():
		var p := GameFont.DIR + "hud.json"
		var d = JSON.parse_string(FileAccess.get_file_as_string(p)) if FileAccess.file_exists(p) else null
		_cfg = d if d is Dictionary else {"none": true}
		_frame_tex = GameFont.texture("hp_frame.png")
		_fill_tex = GameFont.texture("hp_fill.png")
	return _cfg


func _ready() -> void:
	config()
	mouse_filter = Control.MOUSE_FILTER_IGNORE


## Once per game frame: the fighter's HP. Tracks the trail the way HpBar_TrackHP / HpBar_Drain do.
func set_values(new_hp: int, new_max: int) -> void:
	new_hp = maxi(new_hp, 0)
	if new_max != max_hp:   # HpBar_SyncMax
		max_hp = new_max
		hp = new_hp
		trail = new_hp
		_drain_left = 0
	elif new_hp != hp:
		_drain_left += hp - new_hp
		hp = new_hp
	if _drain_left > 0:
		var step := maxi(1, (trail - hp) / int(_hp().get("drain_div", 60)))
		_drain_left -= step
		trail -= step
	else:
		trail = hp
	trail = maxi(trail, hp)
	_step_pulse()
	queue_redraw()


func _hp() -> Dictionary:
	return config().get("hp_bar", {})


## The low-HP pulse counter (HpBar_BuildQuads): 0 -> 7 -> 0, one step per game frame, shared by all bars.
static func _step_pulse() -> void:
	var f := Engine.get_physics_frames()
	if f == _pulse_frame:
		return
	_pulse_frame = f
	if _pulse_up:
		_pulse_n += 1
		if _pulse_n >= 7:
			_pulse_up = false
	else:
		_pulse_n -= 1
		if _pulse_n <= 0:
			_pulse_up = true


func scale_k() -> float:
	return float(_hp().get("k", 0.018)) * (1.0 if member == 0 else float(_hp().get("party_scale", 0.7)))


## Pixel length of the stretched middle for a value.
func length(value: float) -> float:
	return 1.4 * value * scale_k()


func row_y() -> float:
	var ys: Array = _hp().get("row_y", [47.0, 81.0, 109.0])
	return float(ys[member]) + float(_hp().get("row_y_add", 40.0)) + (pride_offset if member > 0 else 0.0)


func _col(key: String) -> Color:
	var c: Array = _hp().get("colours", {}).get(key, [255, 255, 255, 255])
	return Color8(int(c[0]), int(c[1]), int(c[2]), int(c[3]))


func hp_color() -> Color:
	if max_hp > 0 and hp <= max_hp * float(_hp().get("low_hp", 0.2)):
		var p: Array = _hp().get("pulse", [255, 180, 50, 255])
		var st: Array = _hp().get("pulse_step", [22.5, 6.25])
		return Color8(int(p[0]), clampi(int(p[1] - st[0] * _pulse_n), 0, 255), clampi(int(p[2] - st[1] * _pulse_n), 0, 255))
	if side == 0:
		return _col("hp_side0")
	return _col("hp_side1") if enemy_named else _col("hp_side1_other")


func trail_color() -> Color:
	if side == 0:
		return _col("trail_side0" if member == 0 else "trail_side0_party")
	return _col("trail_side1")


func _draw() -> void:
	if max_hp <= 0:
		return
	if side == 1:
		draw_set_transform(Vector2(FightHud.screen_w, 0), 0.0, Vector2(-1, 1))   # mirrored about the screen
	var h := 32.0 * (1.0 if member == 0 else float(_hp().get("party_scale", 0.7)))
	var y := row_y()
	var fx: Array = _hp().get("fill_x", [37, 39])
	# back (black), trail, HP, frame: g_HpBarLayerOrder
	_fill(float(fx[0]), y, h, max_hp, _col("back"))
	if trail > hp:
		_fill(float(fx[0]), y, h, trail, trail_color())
	if hp > 0:
		_fill(float(fx[0]), y, h, hp, hp_color())
	_frame(y, h)
	if show_tired and member == 0 and tired_max > 0:
		var tl := length(tired_max) * tired_ratio
		var ty := y + h * 0.78
		draw_rect(Rect2(float(fx[1]), ty, length(tired_max), 2.0), Color(0, 0, 0, 0.6))
		draw_rect(Rect2(float(fx[1]), ty, tl, 2.0), Color(1.0, 0.82, 0.3, 0.9))
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)


## One fill layer: GD_HPG_02 tinted, caps 2 px, middle stretched (u 20-90 of a 111-wide UV space).
func _fill(x0: float, y: float, h: float, value: float, c: Color) -> void:
	var mid := length(value)
	if _fill_tex == null:
		draw_rect(Rect2(x0, y + h * 0.3, mid + 4.0, h * 0.4), c)
		return
	var tw: Array = _hp().get("tex_wh", [128, 32, 111, 32])
	var su := _fill_tex.get_width() / float(tw[2])
	var u: Array = _hp().get("fill_u", [[0, 2], [20, 70], [109, 2]])
	var parts := [[x0, float(u[0][1]), u[0]], [x0 + float(u[0][1]), mid, u[1]], [x0 + float(u[0][1]) + mid, float(u[2][1]), u[2]]]
	for p in parts:
		var src := Rect2(float(p[2][0]) * su, 0, float(p[2][1]) * su, _fill_tex.get_height())
		draw_texture_rect_region(_fill_tex, Rect2(p[0], y, p[1], h), src, c)


## The frame: GD_HPG_01, caps 10 / 11 px, middle stretched to the max HP length minus 2 x 1.4 px.
func _frame(y: float, h: float) -> void:
	var mid := 1.4 * (max_hp * scale_k() - 2.0)
	var fx: Array = _hp().get("frame_x", [30, 40])
	if _frame_tex == null:
		draw_rect(Rect2(float(fx[0]), y + h * 0.25, mid + 21.0, h * 0.5), Color(0.8, 0.8, 0.8), false, 2.0)
		return
	var u: Array = _hp().get("frame_u", [[0, 10], [20, 70], [117, 11]])
	var x0 := float(fx[0])
	var parts := [[x0, float(u[0][1]), u[0]], [float(fx[1]), mid, u[1]], [float(fx[1]) + mid, float(u[2][1]), u[2]]]
	for p in parts:
		draw_texture_rect_region(_frame_tex, Rect2(p[0], y, p[1], h), Rect2(float(p[2][0]), 0, float(p[2][1]), 32), Color.WHITE)
