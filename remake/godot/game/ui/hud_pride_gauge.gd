class_name HudPrideGauge
extends Control
## One Pride gauge of the fight HUD (docs/HUD.md, "Pride gauge"): a lighter with a burning fuse. The flames
## are the gauge: drawn ratio x 1.3 wide and ratio x 1.8 high, cycling 8 frames, faster when Pride is high
## (PrideGauge_Flames). Slides in from the side over 10 frames. Side 1 (the enemy) is mirrored and shows
## "NEGOTIATION OK!" + the special button when its Pride is empty. set_ratio() once per game frame.

@export_range(0, 1) var side := 0
@export var negotiation_label: RichTextLabel   ## side 1: the NEGOTIATION OK! prompt (optional)

var ratio := 1.0
var _shown := 0.0          ## slide-in 0..1
var _flame := 0
var _flame_t := 0.0
var _blink := 0
var _tex := {}


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	for k in ["hud_tex02", "hud_tex03"]:
		_tex[k] = GameFont.texture(k + ".png")


func _pride() -> Dictionary:
	return HudHpBar.config().get("pride", {})


func set_ratio(r: float) -> void:
	ratio = clampf(r, 0.0, 1.0)
	_shown = minf(_shown + 0.1, 1.0)
	# PrideGauge_Flames: next frame after (1 - ratio) x 0.05 + 0.05 s
	var ft: Array = _pride().get("flame_time", [0.05, 0.05])
	_flame_t += 1.0 / 60.0
	if _flame_t >= (1.0 - ratio) * float(ft[0]) + float(ft[1]):
		_flame_t = 0.0
		_flame = (_flame + 1) % 8
	_blink += 1
	if negotiation_label:
		var empty := side == 1 and ratio <= 0.0 and _shown >= 1.0
		negotiation_label.visible = empty
		if empty:
			var p: Dictionary = _pride().get("negotiation", {})
			var id := int(p.get("text_on", 10447)) if (_blink / 10) % 2 else int(p.get("text", 10446))
			var t := "[right]%s[/right]" % GameFont.bbcode(GameText.text(id))
			if negotiation_label.text != t:
				negotiation_label.text = t
	queue_redraw()


func _draw() -> void:
	var lay: Array = _pride().get("layout", [[20, 105, 10, -1, 29, 15, 123, 16, 29, 5]])
	var l: Array = lay[0]
	var slide := (1.0 - _shown) * -200.0
	if side == 1:
		draw_set_transform(Vector2(FightHud.screen_w, 0), 0.0, Vector2(-1, 1))
	var base := Vector2(float(l[0]) + slide, float(l[1]))
	for piece: Array in _pride().get("pieces", []):
		var oi := int(piece[5])
		var off := Vector2.ZERO if oi < 0 else Vector2(float(l[2 + oi * 2]), float(l[3 + oi * 2]))
		_sprite(piece[0], Rect2(piece[1], piece[2], piece[3], piece[4]), Rect2(base + off, Vector2(piece[3], piece[4])))
	# Flames from the fuse's left end, scaled by the ratio.
	if ratio > 0.0:
		var fi := int(_pride().get("flame_offset", 3))
		var at := base + Vector2(float(l[2 + fi * 2]), float(l[3 + fi * 2]))
		var fs: Array = _pride().get("flame_size", [77, 16])
		var sc: Array = _pride().get("flame_scale", [1.3, 1.8])
		var fr: Array = _pride().get("flame_frames", [["hud_tex02", 102, 96]])[_flame % 8]
		var size := Vector2(float(fs[0]) * ratio * float(sc[0]), float(fs[1]) * ratio * float(sc[1]))
		# Remake choice: grow upward from the fuse (the game's anchor isn't checked on screen).
		var dst := Rect2(at + Vector2(0, float(fs[1]) - size.y), size)
		_sprite(fr[0], Rect2(fr[1], fr[2], fs[0], fs[1]), dst)
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)


func _sprite(tex: String, src: Rect2, dst: Rect2) -> void:
	var t: Texture2D = _tex.get(tex)
	if t:
		draw_texture_rect_region(t, dst, src)
	else:
		draw_rect(dst, Color(1.0, 0.55, 0.1, 0.8) if tex == "hud_tex02" else Color(0.3, 0.3, 0.3, 0.8))
