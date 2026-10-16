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
	await _test_grab(p, d, false, "fight_grab.png")
	await _test_grab(p, d, true, "")
	await _test_walk(p, d)
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
	var closest := 99.0
	var got := false
	for i in 120:
		await _frames(1)
		var gap := Vector2(p.global_position.x - d.global_position.x, p.global_position.z - d.global_position.z).length()
		closest = minf(closest, gap)
		if d.state == Fighter.State.KNOCKDOWN:
			got = true
			break
	# FUN_003072C0: the body spheres (hips and chest 0.22 m) keep the bodies apart while the lunge's hips travel
	_check(closest >= 0.35, "body collision: %s's lunge keeps the bodies %.2f m apart (hips spheres 2 x 0.22)" % [code, closest])
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


## R1 (#1E, the grab attempt: action 10) on Dummy 1, then P: the catch and hold, then GRAB P (or REAR GRAB P from
## behind: Sleeper Hold) with the victim playing the throw's partner action, damage from the throw op, and the victim
## ends on the floor or standing as the partner action says.
func _test_grab(p: Fighter, d: Fighter, rear: bool, shot: String) -> void:
	var t := "rear grab" if rear else "grab"
	_place(p, d, 0.0 if rear else PI, DummyBrain.Mode.STAND)
	p.global_position = Vector3(0, 0, 1.9)
	await _frames(10)
	var hp := d.hp
	(p.brain as PlayerBrain).presses.append({"code": "#1E", "frame": Dev.frame})
	var got := await _until(func(): return p.state == Fighter.State.HOLD, 60)
	_check(got and d.state == Fighter.State.HELD and d.held_by == p, "%s: R1 catches Dummy 1 (%s / %s)" % [
		t, Fighter.State.keys()[p.state], Fighter.State.keys()[d.state]])
	if not got:
		return
	_check(p._hold_rear == rear, "%s: hold taken %s" % [t, "from behind" if p._hold_rear else "from the front"])
	await _frames(50)
	_check(p.state == Fighter.State.HOLD and d._held_loop, "%s: holding after the catch" % t)
	(p.brain as PlayerBrain).press("P", "")
	var thrown := await _until(func(): return p.state == Fighter.State.ATTACK, 20)
	var want := "REAR GRAB P" if rear else "GRAB P"
	var m: MoveData = p.move_set.match_single(want)[0]
	_check(thrown and p.move == m and d._held_action == m.pair_action, "%s: P throws (%s: action %d, victim %d)" % [
		t, want, p.move.action_id if p.move else -1, d._held_action])
	var n := 0
	var shot_done := false
	while d.state == Fighter.State.HELD and n < 400:
		await _frames(1)
		n += 1
		if shot != "" and not shot_done and n == 40:
			shot_done = true
			await _shot(shot)
	var dmg := 0
	for h in m.throw_hits:
		dmg += (h as MoveHit).damage
	_check(d.hp < hp or dmg == 0, "%s: throw damage %d (records %d)" % [t, hp - d.hp, dmg])
	var then := int(d.model.action_info(m.pair_action).get("then", 1))
	var end_state := Fighter.State.KNOCKDOWN if then in [19, 20] else Fighter.State.IDLE
	_check(d.state == end_state, "%s: victim ends %s after %d frames (partner goto %d)" % [
		t, Fighter.State.keys()[d.state], n, then])
	await _until(func(): return d.state == Fighter.State.IDLE and p.state == Fighter.State.IDLE, 400)
	_check(d.held_by == null and p.holding == null, "%s: both free again" % t)


## Walking (Fighter_TaskWalk, g_WalkModes): Dummy 1 walks at the player, locked on: the front walk action at the
## table's speed, and the lower foot barely slides (its floor speed is a small part of the walking speed). Then the
## 8-way choice and the back speed for a step backwards.
func _test_walk(p: Fighter, d: Fighter) -> void:
	_place(p, d, PI, DummyBrain.Mode.FIGHT)
	d.global_position = Vector3(0, 0, -1.6)
	var sk := d.model.skeleton
	var feet := [sk.find_bone("foot_r"), sk.find_bone("foot_l")]
	var row: Dictionary = d.model.meta["walk_modes"]["0"]
	var prev := []
	var slide := 0.0
	var n := 0
	var speed := 0.0
	var strides := []
	var slides := []
	var start := d.global_position
	var moved_frames := 0
	for i in 45:
		await _frames(1)
		if d.state != Fighter.State.MOVE:
			continue
		speed = Vector2(d.velocity.x, d.velocity.z).length()
		moved_frames += 1
		var pos := []
		for b in feet:
			pos.append(sk.global_transform * sk.get_bone_global_pose(b).origin)
		if prev.size() == 2 and i > 12:   # after the blend in
			var low := 0 if pos[0].y < pos[1].y else 1
			var v: Vector3 = (pos[low] - prev[low]) / Fighter.DT
			slide += Vector2(v.x, v.z).length()
			strides.append(-(v - d.velocity).dot(d.forward()))   # the lower foot against the body: the clip's own speed
			slides.append(absf(v.dot(d.forward())))   # along the walk: sideways ankle roll is not sliding
			n += 1
		prev = pos
	var want := float(row["speeds"][0]) * 60.0 * Fighter.UNIT
	_check(d._walk_action == int(row["actions"][0]) and absf(speed - want) < 0.05, "walk: front walk action %d at %.2f m/s (table %.2f)" % [
		d._walk_action, speed, want])
	print("  info walk: body moved %.2f m/s on average" % ((d.global_position - start).length() / maxf(moved_frames, 1) * 60.0))
	strides.sort()
	slides.sort()
	var avg: float = slides[slides.size() / 4] if slides.size() > 0 else 99.0   # lower quartile: the planted part of the step
	print("  info walk: the lower foot moves %.2f m/s backwards against the body (median; the clip's own walking speed)" % (strides[strides.size() / 2] if strides.size() > 0 else 0.0))
	_check(n > 10 and avg < 0.35 * want, "walk: planted foot slides %.2f m/s (lower quartile, walking %.2f m/s, %d frames)" % [avg, want, n])
	var back := p.walk_direction(p.global_transform.basis.z)
	var side := p.walk_direction(p.global_transform.basis.x)
	_check(back == 1 and side in [2, 3], "walk: back -> direction %d, side -> %d" % [back, side])


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
	Dev.show_boxes = false
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
