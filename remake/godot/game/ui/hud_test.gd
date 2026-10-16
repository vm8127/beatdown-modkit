extends Node
## Fight HUD check (headless): the dev arena with its FightHud; the player attacks Dummy 1 and the HUD must
## follow: the target, HP and the damage trail (above HP right after a hit, back to HP once drained), the
## enemy's Pride falling, TIRED = the costs of the moves started (draining 1 every 30 frames), the combo
## counter. Exit code 0 = pass.
##
##     Godot_console.exe --headless --path remake/godot res://game/ui/hud_test.tscn
##     Godot.exe --path remake/godot res://game/ui/hud_test.tscn -- --shots=<folder>
##
## `--shots=<folder>` (not headless) saves hud_fight.png mid-combo, hud_lowhp.png (the low-HP pulse, enemy
## Pride empty: NEGOTIATION OK!) and hud_text.png (the game's font: colours, button icons, MOVE LIST arrows).

const ARENA := preload("res://dev/dev_arena.tscn")

var arena: Node
var hud: FightHud
var _frame := 0
var _errors: PackedStringArray = []
var _shots := ""
var _presses := {20: "P", 34: "P", 48: "P", 90: "P", 104: "P", 118: "P"}
var _costs := 0
var _last_move: MoveData
var _last_frame := 0
var _saw_trail := false
var _saw_combo := false
var _hp_at_hit := -1
var _trail_back := -1
var _phase := 0


func _ready() -> void:
	process_physics_priority = 300   # after the fighters and the HUD
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--shots="):
			_shots = a.substr(8)
	arena = ARENA.instantiate()
	add_child(arena)
	hud = arena.get_node("FightHud")
	var ov := arena.get_node_or_null("DebugOverlay")
	if ov:
		ov.visible = false


func _physics_process(_delta: float) -> void:
	if not Dev.tick:
		return
	_frame += 1
	var p: Fighter = arena.player
	var d: Fighter = arena.get_node("Dummy1")
	if _frame == 1:
		p.global_position = Vector3(0, 0, 2.2)
		p.rotation.y = 0.0
		print("style: %s, font: %s" % [p.move_set.style_name if p.move_set else "?", GameFont.available()])
	if _presses.has(_frame):
		(p.brain as PlayerBrain).press(_presses[_frame])
	# The costs of every move the player starts (what TIRED must add up).
	if p.state == Fighter.State.ATTACK and p.move and (p.move != _last_move or p.state_frame < _last_frame):
		_costs += p.move.cost
	_last_move = p.move if p.state == Fighter.State.ATTACK else null
	_last_frame = p.state_frame
	if _frame < 3:
		return
	var right := hud.hp_right
	if hud.target == d and right.trail > right.hp:
		if not _saw_trail:
			if "--verbose" in OS.get_cmdline_user_args():
				print("frame %d: trail %d above HP %d" % [_frame, right.trail, right.hp])
		_saw_trail = true
		_hp_at_hit = right.hp
	if _saw_trail and _trail_back < 0 and right.trail == right.hp and right.hp == _hp_at_hit:
		_trail_back = _frame
	if hud.combo.visible_now():
		if not _saw_combo:
			if "--verbose" in OS.get_cmdline_user_args():
				print("frame %d: combo %d HITS" % [_frame, hud.combo.count])
			if _shots != "":
				_shot("hud_fight.png")
		_saw_combo = true
	if _frame % 30 == 0:
		if "--verbose" in OS.get_cmdline_user_args():
			print("frame %d: %s" % [_frame, hud.debug_text()])
	if _frame == 320:
		_check(p, d)
	if _frame == 325:
		_low_hp(d)
	if _frame == 350:
		_check_low(d)
		if _shots != "":
			await _shot("hud_lowhp.png")
			await _text_panel()
		_finish()


func _check(p: Fighter, d: Fighter) -> void:
	var pm := hud.meters_of(p)
	var dm := hud.meters_of(d)
	_eq("target is Dummy 1", hud.target == d, true)
	_eq("right bar = Dummy 1 HP", hud.hp_right.hp, maxi(d.hp, 0))
	_eq("left bar = player HP", hud.hp_left.hp, p.hp)
	_eq("Dummy 1 was hurt", d.hp < d.max_hp, true)
	_eq("trail showed above HP after a hit", _saw_trail, true)
	_eq("trail drained back to HP", _trail_back > 0, true)
	_eq("Dummy 1 Pride fell", dm.pride < dm.pride_max, true)
	_eq("player Pride full", pm.pride == pm.pride_max, true)
	_eq("TIRED max = 1.5 x max HP", pm.tired_max, int(p.max_hp * 1.5))
	# TIRED: the costs added, minus 1 per 30 frames of drain (floor 0 while the total is under tired_max).
	_eq("TIRED within costs - drain", pm.tired <= _costs and pm.tired >= _costs - 320 / 30 - 1, true)
	print("costs %d, tired %d, Dummy 1 Pride %.0f/%d, combo seen %s" % [_costs, pm.tired, dm.pride, dm.pride_max, _saw_combo])
	if p.real_style():
		_eq("combo counter showed", _saw_combo, true)


## Puts Dummy 1 at 15 % HP and empty Pride: the bar must pulse and NEGOTIATION OK! show.
func _low_hp(d: Fighter) -> void:
	d.hp = int(d.max_hp * 0.15)
	hud.meters_of(d).pride = 0.0


func _check_low(d: Fighter) -> void:
	var c := hud.hp_right.hp_color()
	_eq("low HP colour is the pulse (red 255)", c.r8 == 255 and c.b8 <= 50, true)
	_eq("NEGOTIATION OK! shown", hud.negotiation.visible, true)
	print("negotiation text: %s" % hud.negotiation.text)


func _eq(what: String, got, want) -> void:
	if got != want:
		_errors.append("%s: got %s, want %s" % [what, got, want])
		print("  FAIL: %s: got %s, want %s" % [what, got, want])


func _shot(file: String) -> void:
	await RenderingServer.frame_post_draw
	var path := _shots.path_join(file)
	get_viewport().get_texture().get_image().save_png(path)
	print("screenshot saved: %s" % path)


## The game's font on a dark panel: colours, button and icon glyphs, a MOVE LIST line.
func _text_panel() -> void:
	var layer := CanvasLayer.new()
	layer.layer = 10
	add_child(layer)
	var bg := ColorRect.new()
	bg.color = Color(0.05, 0.05, 0.08)
	bg.size = get_viewport().get_visible_rect().size
	layer.add_child(bg)
	var r := RichTextLabel.new()
	r.bbcode_enabled = true
	r.position = Vector2(30, 20)
	r.size = bg.size - Vector2(60, 40)
	r.add_theme_font_override("normal_font", GameFont.font())
	r.add_theme_font_size_override("normal_font_size", 36)
	var lines := [
		GameText.text(30232),
		GameText.text(31151),
		GameText.render(60171, {"item1": GameText.item_name(1), "item2": GameText.item_name(2)}),
		GameText.text(19107),
		GameText.text(40678),
		GameText.text(10446),
	]
	var ml: Array = GameText.move_list(0x13)
	for i in range(mini(3, ml.size())):
		lines.append("{c8}%s{c0}  %s" % [ml[i][0], ml[i][1]])
	var pal := ""
	for n in range(1, 9):
		pal += "{c%d}@%d{c0} " % [n, n]
	lines.append(pal)
	lines.append("{icon:1}{icon:2}{icon:3}{icon:4}{icon:5}{icon:6} {icon:alpha} {icon:rapid} {icon:17}{icon:18} ←↑→↓ ㊧㊤㊨㊦ ○△□× ●▲■Ⅹ")
	var bb := ""
	for l in lines:
		bb += GameFont.bbcode(l) + "\n"
	r.text = bb
	layer.add_child(r)
	for i in 3:
		await get_tree().process_frame
	await _shot("hud_text.png")


func _finish() -> void:
	if _errors.is_empty():
		print("HUD TEST PASS")
		get_tree().quit(0)
	else:
		print("HUD TEST FAIL: %d" % _errors.size())
		get_tree().quit(1)
