class_name HudCombo
extends Control
## The combo counter (docs/HUD.md, "Combo counter"): when the player's hit count in a combo changes and is
## 2 or more (Hud_ComboWatch), "N HITS" shows for 40 frames: the digits slide in at 1.333 scale, then from
## frame 15 everything grows (1 + 0.025 f) and fades (255 - 6 f), over a fade of the whole (1 - 0.025 f).
## FONT_TEX_03's cyan digits (25 x 32) and HITS (81 x 22). show_count() when the count changes.

@export_range(0, 1) var side := 0
@export var party_rows := 0          ## extra party members shown: 25 px lower each

var count := 0
var frame := 40                      ## frames since the count changed (40 = hidden)
var _tex: Texture2D


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_tex = GameFont.texture("hud_tex03.png")


func _combo() -> Dictionary:
	return HudHpBar.config().get("combo", {})


## Combo_Show: a new count (shown only from min_count = 2 on, capped at 99).
func show_count(n: int) -> void:
	if n == count:
		return
	count = n
	if n >= int(_combo().get("min_count", 2)):
		frame = 0
		count = mini(n, int(_combo().get("max", 99)))


func tick() -> void:
	if frame < int(_combo().get("frames", 40)):
		frame += 1
		queue_redraw()


func visible_now() -> bool:
	return frame < int(_combo().get("frames", 40))


func _draw() -> void:
	if not visible_now():
		return
	var f := float(frame)
	var a := clampf(1.0 - 0.025 * f, 0.0, 1.0)
	var sc := 1.333
	if frame >= 15:
		sc = 1.0 + 0.025 * f
		a = minf(a, clampf((255.0 - 6.0 * f) / 255.0, 0.0, 1.0))
	var y := 160.0 + 25.0 * party_rows
	var digits := str(count)
	var dw := 25.0 * sc
	var slide := -float(maxi(10 - frame, 0)) * 8.0       # digits slide in from the left over 10 frames
	var right := 100.0 + slide
	for i in range(digits.length()):
		var n := int(digits[i])
		var x := right - dw * (digits.length() - i)
		_sprite(_combo_digit(n), Rect2(x, y - 16.0 * sc, dw, 32.0 * sc), Color(1, 1, 1, a))
	var hits: Dictionary = _combo().get("hits", {})
	var huv: Array = hits.get("uv", [175, 42, 81, 22])
	var hx := 104.0
	var hs := 1.0 if frame < 15 else sc
	_sprite(Rect2(huv[0], huv[1], huv[2], huv[3]), Rect2(hx, y - 11.0 * hs, 81.0 * hs, 22.0 * hs), Color(1, 1, 1, a))


func _combo_digit(n: int) -> Rect2:
	var d: Array = _combo().get("digits", [])
	if n < d.size():
		var uv: Array = d[n]["uv"]
		return Rect2(uv[0], uv[1], uv[2], uv[3])
	return Rect2(25 * n, 64, 25, 32)


## Side 1 mirrors the layout but not the pictures (the digits stay readable).
func _sprite(src: Rect2, dst: Rect2, c: Color) -> void:
	if side == 1:
		dst.position.x = FightHud.screen_w - dst.position.x - dst.size.x
	if _tex:
		draw_texture_rect_region(_tex, dst, src, c)
	else:
		draw_rect(dst, Color(0.4, 1.0, 1.0, c.a * 0.6))
