extends Node
## Scripted checks of how hits land (`-- --fight`, with the assets extracted): the game's reactions
## (docs/ANIMATION.md, "Hit reactions"), hitstun from the reaction's release frame, knockback from the
## reaction's hip travel, a blocked hit, a knockdown with lying and getting up, and a grab (once grabs
## are in). Prints one line per check and quits with exit code 0 (all pass) or 1.
##
## `--shots=<folder>` (run without --headless) also saves fight_behind.png (a reaction from behind),
## fight_block.png (a blocked hit), fight_down.png (the knockdown) and fight_grab.png in that folder.

var arena: Node
var _shots := ""
var _fails: Array[String] = []
var _passes := 0


func _ready() -> void:
	process_physics_priority = 100   # after the fighters
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--shots="):
			_shots = a.substr(8)
	_run.call_deferred()


func _run() -> void:
	var p: Fighter = arena.player
	var d := _dummy("Dummy 1")
	for n in ["Dummy 2", "Dummy 3"]:   # out of the way
		_dummy(n).global_position += Vector3(0, 0, -20)
	await _frames(2)
	if p.model == null or not p.real_style():
		print("RESULT fight: needs the extracted assets (remake_assets.py) -> FAIL")
		get_tree().quit(1)
		return
	if _shots != "":
		_side_camera()
	await _test_reaction(p, d, "front", PI, "")
	await _test_reaction(p, d, "behind", 0.0, "fight_behind.png")
	await _test_reaction(p, d, "side", PI / 2, "")
	await _test_block(p, d)
	await _test_knockdown(p, d)
	var ok := _fails.is_empty()
	print("RESULT fight: %d checks passed, %d failed %s -> %s" % [_passes, _fails.size(), _fails, "PASS" if ok else "FAIL"])
	get_tree().quit(0 if ok else 1)


## Blade Cut (P) on Dummy 1 turned `yaw`: the reaction entry must match where the attacker stands, the
## hitstun must be the reaction's release frame (or its length), and the victim must slide away.
func _test_reaction(p: Fighter, d: Fighter, want: String, yaw: float, shot: String) -> void:
	_place(p, d, yaw, DummyBrain.Mode.STAND)
	await _frames(10)
	var start := d.global_position
	(p.brain as PlayerBrain).press("P", "")
	var got := await _until(func(): return d.state == Fighter.State.HITSTUN or d.state == Fighter.State.KNOCKDOWN, 60)
	_check(got, "%s: Blade Cut hits" % want)
	if not got:
		return
	var info := d.model.action_info(d._react_action)
	var rel := int(info.get("release", -1))
	var expect := rel if rel > 0 else int(info.get("frames", 0))
	var dir := d.last_reaction.split(" ")[1]
	if want == "side":
		_check(dir in ["left", "right"], "side: reaction entry %s is left/right (%s)" % [dir, d.last_reaction])
	else:
		_check(dir == want, "%s: reaction entry %s (%s)" % [want, dir, d.last_reaction])
	_check(d.stun == expect, "%s: hitstun %d = action %d release/length %d" % [want, d.stun, d._react_action, expect])
	var shot_at := 10
	var ticks := 0
	var n := 0
	while d.state == Fighter.State.HITSTUN and n < 300:
		await _frames(1)
		n += 1
		if d.hitstop == 0:
			ticks += 1
		if shot != "" and ticks == shot_at:
			await _shot(shot)
	_check(absi(ticks - expect) <= 1, "%s: in hitstun %d frames (want %d)" % [want, ticks, expect])
	await _frames(40)
	var moved := d.global_position - start
	moved.y = 0
	var away := (d.global_position - p.global_position).normalized()
	_check(moved.length() > 0.05 and moved.normalized().dot(Vector3(away.x, 0, away.z).normalized()) > 0.0,
		"%s: knocked back %.2f m, away from the attacker" % [want, moved.length()])


## Dummy 1 guarding, facing the player: Blade Cut is blocked (no damage, no reaction), the guard stays.
func _test_block(p: Fighter, d: Fighter) -> void:
	_place(p, d, PI, DummyBrain.Mode.GUARD)
	await _frames(30)
	_check(d.state == Fighter.State.GUARD, "block: dummy guards (%s)" % Fighter.State.keys()[d.state])
	var hp := d.hp
	(p.brain as PlayerBrain).press("P", "")
	var got := await _until(func(): return d.state == Fighter.State.BLOCKSTUN or d.state == Fighter.State.HITSTUN, 60)
	_check(got and d.state == Fighter.State.BLOCKSTUN, "block: blocked (%s, %s)" % [Fighter.State.keys()[d.state], d.last_reaction])
	var info := d.model.action_info(d._block_action)
	_check(got and float(d._block_action) in d.model.meta["guard"]["stand"] and d.stun == int(info.get("frames", -1)),
		"block: guard-hit action %d, blockstun %d = its length" % [d._block_action, d.stun])
	if got:
		await _frames(2)
		await _shot("fight_block.png")
	var back := await _until(func(): return d.state == Fighter.State.GUARD, 80)
	_check(d.hp == hp, "block: no damage (hp %d -> %d)" % [hp, d.hp])
	_check(back, "block: back in guard (%s)" % Fighter.State.keys()[d.state])


## A move whose hit knocks down (reaction 0x20) from neutral: the knockdown row's action plays to its end,
## then lying, then the getup until its release frame.
func _test_knockdown(p: Fighter, d: Fighter) -> void:
	var code := _knockdown_code(p)
	_check(code != "", "knockdown: Aaron has a one-input knockdown move")
	if code == "":
		return
	_place(p, d, PI, DummyBrain.Mode.STAND)
	await _frames(10)
	(p.brain as PlayerBrain).press(code.right(1), code.left(code.length() - 1))
	var got := await _until(func(): return d.state == Fighter.State.KNOCKDOWN, 120)
	_check(got, "knockdown: %s knocks Dummy 1 down (%s)" % [code, d.last_reaction])
	if not got:
		return
	_check("knockdown row 0" in d.last_reaction, "knockdown: from the knockdown rows (%s)" % d.last_reaction)
	var fall := int(d._react.get("frames", 0))
	var ticks := 0
	var n := 0
	while d.state == Fighter.State.KNOCKDOWN and n < 600:
		await _frames(1)
		n += 1
		if d.hitstop == 0:
			ticks += 1
		if ticks == fall + 10:
			await _shot("fight_down.png")
	_check(absi(ticks - (fall + Fighter.DOWN_FRAMES)) <= 1, "knockdown: fall %d + lying %d frames (took %d)" % [
		fall, Fighter.DOWN_FRAMES, ticks])
	var g := 0
	while d.state == Fighter.State.GETUP and g < 300:
		await _frames(1)
		g += 1
	_check(g == d._getup_frames, "knockdown: getup %d frames = action %d release %d" % [g, d._getup_action, d._getup_frames])


## The first one-input command of the style whose move has a knockdown hit (reaction 0x20).
func _knockdown_code(p: Fighter) -> String:
	for c in p.move_set.commands:
		var seq: PackedStringArray = c["seq"]
		if seq.size() != 1 or seq[0].begins_with("#") or seq[0].contains("GRAB") or seq[0].ends_with("G"):
			continue
		for h in (c["move"] as MoveData).get_hits():
			if (h as MoveHit).reaction & 0x20:
				return seq[0]
	return ""


func _place(p: Fighter, d: Fighter, yaw: float, mode: DummyBrain.Mode) -> void:
	for f in [p, d]:
		f._enter(Fighter.State.IDLE)
		f.hitstop = 0
		f.stun = 0
		f.velocity = Vector3.ZERO
		f._set_invulnerable(false)
	d.hp = d.max_hp
	d.turn_speed = 0.0   # the dummy keeps the yaw it's given (it normally turns to face the player)
	(d.brain as DummyBrain).mode = mode
	p.global_position = Vector3(0, 0, 2.2)
	p.rotation.y = 0.0
	d.global_position = Vector3(0, 0, 1.0)
	d.rotation.y = yaw


func _check(ok: bool, what: String) -> void:
	print(("  ok   " if ok else "  FAIL ") + what)
	if ok:
		_passes += 1
	else:
		_fails.append(what)


func _frames(n: int) -> void:
	for i in n:
		await get_tree().physics_frame


func _until(cond: Callable, limit: int) -> bool:
	for i in limit:
		await get_tree().physics_frame
		if cond.call():
			return true
	return false


func _shot(file: String) -> void:
	if _shots == "" or file == "":
		return
	await RenderingServer.frame_post_draw
	var path := _shots.path_join(file)
	get_viewport().get_texture().get_image().save_png(path)
	print("screenshot saved: %s" % path)


func _side_camera() -> void:
	Dev.show_hurtboxes = false
	if arena.get("overlay"):
		arena.overlay.visible = false
	var cam := Camera3D.new()
	arena.add_child(cam)
	cam.global_position = Vector3(3.2, 1.6, 1.4)
	cam.look_at(Vector3(0, 1.0, 1.4))
	cam.current = true


func _dummy(n: String) -> Fighter:
	for f in get_tree().get_nodes_in_group("fighters"):
		if (f as Fighter).display_name == n:
			return f
	return null
