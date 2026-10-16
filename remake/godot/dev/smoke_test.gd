extends Node
## Scripted check of the combat loop (`-- --smoke`): puts the player next to Dummy 1, plays a
## 3-hit combo, checks the result and quits with exit code 0 or 1. Prints only RESULT lines; `-- --verbose` also prints every state change.
##
## - With Aaron's real style (assets_ripped/moves/aaron.tres): Triple Snake Fang, →P P P
##   (actions 1807 -> 1808 -> 1809). Each press is made a few frames into the previous move, so
##   it is the "last input" its cancel point matches. Checks the chain happens exactly at each
##   cancel point, that all three hits land as a combo, and the damage against the MECHANICS
##   formula (base x combo scaling 0.7, 0.6; the dummy has 3000 HP, so no low-HP factor).
## - Without it (fresh clone, placeholder style): P P P = jab, jab, straight for 50 damage.
##
## `--shot=<file.png>` also saves a screenshot during the last hit's hitstop.
## `--press=<code>` (with Aaron's style) presses one input code instead ("P" Blade Cut, "→K"...) and
## passes when it hits Dummy 1; with `--shot=` the screenshot is taken on the hit's first hitstop
## frame, or on frame `--shot-frame=N` of the move. Prints where each hit sphere was.
## `--shot-down=<file.png>` (the combo) saves a side view of Dummy 1 knocked down.

const AARON := [["→", "P", "a1807"], ["", "P", "a1808"], ["", "P", "a1809"]]

var arena: Node
var _frame := 0
var _log_last := {}
var _shot := ""
var _shot_taken := false
var _step := 0          # Aaron: presses made so far
var _chains: Array[String] = []
var _errors: Array[String] = []
var _press := ""
var _shot_down := ""
var _shot_frame := -1


func _ready() -> void:
	process_physics_priority = 100   # after the fighters
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--shot="):
			_shot = a.substr(7)
		elif a.begins_with("--shot-down="):
			_shot_down = a.substr(12)
		elif a.begins_with("--press="):
			_press = a.substr(8)
		elif a.begins_with("--shot-frame="):
			_shot_frame = int(a.substr(13))


func _physics_process(_delta: float) -> void:
	if not Dev.tick:
		return
	_frame += 1
	var p: Fighter = arena.player
	var d: Fighter = _dummy()
	var real := p.real_style()
	if _frame == 1:
		p.global_position = Vector3(0, 0, 2.2)
		p.rotation.y = 0.0
		print("style: %s" % p.move_set.style_name)
	if real and _press != "":
		_one_move(p, d)
		return
	if real:
		_drive_aaron(p)
	elif _frame in [20, 30, 42]:
		# Press each button a few frames early: the buffer holds it until the combo window.
		(p.brain as PlayerBrain).press("P")
	for f in [p, d]:
		var line: String = f.debug_text()
		var key: String = "%s %s %s" % [f.display_name, f.state, f.move_id]
		if _log_last.get(f.display_name, "") != key:
			_log_last[f.display_name] = key
			if "--verbose" in OS.get_cmdline_user_args():
				print("frame %d: %s" % [Dev.frame, line])
	var last_id: String = AARON[-1][2] if real else "straight"
	if _shot != "" and not _shot_taken and p.move_id == last_id and p.hitstop > 0:
		_shot_taken = true
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png(_shot)
		print("screenshot saved: %s" % _shot)
	if _shot_down != "" and _frame == 2:
		_side_camera()
	if _shot_down != "" and d.state == Fighter.State.KNOCKDOWN and d.state_frame == 50:
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png(_shot_down)
		print("screenshot saved: %s" % _shot_down)
	if _frame == 260:
		var ok := false
		if real:
			var want := _expected_damage(p)
			ok = p.combo_hits == 3 and d.hp == d.max_hp - want and _errors.is_empty() and _chains.size() == 2
			print("RESULT %s: combo %d hits, %d damage (expected %d), dummy hp %d/%d, chains %s %s -> %s" % [
				"→P P P", p.combo_hits, p.combo_damage, want, d.hp, d.max_hp, _chains, _errors, "PASS" if ok else "FAIL"])
		else:
			ok = p.combo_hits == 3 and d.hp == d.max_hp - 50
			print("RESULT combo %d hits, %d damage, dummy hp %d -> %s" % [p.combo_hits, p.combo_damage, d.hp, "PASS" if ok else "FAIL"])
		get_tree().quit(0 if ok else 1)


## Presses the next input of the combo 3 frames into each move, and checks each chain starts
## on the previous move's cancel frame.
func _drive_aaron(p: Fighter) -> void:
	var brain := p.brain as PlayerBrain
	if _step == 0 and _frame == 20:
		brain.press(AARON[0][1], AARON[0][0])
		if "--verbose" in OS.get_cmdline_user_args():
			print("frame %d: press %s%s" % [Dev.frame, AARON[0][0], AARON[0][1]])
		_step = 1
		return
	if _step >= 1 and _step < AARON.size() and p.state == Fighter.State.ATTACK \
			and p.move_id == AARON[_step - 1][2] and p.state_frame == 3:
		brain.press(AARON[_step][1], AARON[_step][0])
		if "--verbose" in OS.get_cmdline_user_args():
			print("frame %d: press %s%s" % [Dev.frame, AARON[_step][0], AARON[_step][1]])
		_step += 1
	# A chain: the move changed while attacking. It must start on the previous move's cancel frame
	# (seen here one tick after the last frame we logged for the previous move).
	if p.state == Fighter.State.ATTACK:
		if _prev_id != "" and p.move_id != _prev_id and _chains.size() < AARON.size() - 1:
			var want: String = AARON[_chains.size() + 1][2]
			_chains.append("%s@%d" % [p.move_id, _prev_frame + 1])
			if p.move_id != want or _prev_frame + 1 != _prev_cancel:
				_errors.append("%s started on frame %d of %s (want %s on its cancel frame %d)" % [
					p.move_id, _prev_frame + 1, _prev_id, want, _prev_cancel])
		_prev_id = p.move_id
		_prev_frame = p.state_frame
		_prev_cancel = p.move.cancel_start


## `--press=`: one move on Dummy 1, screenshot on its hit (or a given frame of the move).
func _one_move(p: Fighter, d: Fighter) -> void:
	if _frame == 1 and _shot != "":
		_side_camera()
	if _frame == 20:
		var dir := ""
		var b := _press
		if _press.length() > 1:
			dir = _press.substr(0, _press.length() - 1)
			b = _press.substr(_press.length() - 1)
		(p.brain as PlayerBrain).press(b, dir)
		if "--verbose" in OS.get_cmdline_user_args():
			print("frame %d: press %s" % [Dev.frame, _press])
	if p.state == Fighter.State.ATTACK and p.move.is_active(p.state_frame):
		for h in p.move.get_hits():
			if (h as MoveHit).is_active(p.state_frame):
				for sp in p.hit_spheres(h):
					if "--verbose" in OS.get_cmdline_user_args():
						print("frame %d: %s f%d parts %s sphere at %s r %.2f (dummy at %s)" % [Dev.frame, p.move.move_name,
							p.state_frame, h.parts, sp[0], sp[1], d.global_position])
	var want_shot := _shot != "" and not _shot_taken and p.state == Fighter.State.ATTACK and (
		(p.state_frame == _shot_frame) if _shot_frame >= 0 else p.hitstop > 0)
	if want_shot:
		_shot_taken = true
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png(_shot)
		print("screenshot saved: %s" % _shot)
	if _frame == 160:
		var ok := d.hp < d.max_hp
		print("RESULT %s: dummy hp %d/%d -> %s" % [_press, d.hp, d.max_hp, "PASS" if ok else "FAIL"])
		get_tree().quit(0 if ok else 1)


## Screenshots of one move: a camera from the side, no hurtboxes, no overlay.
func _side_camera() -> void:
	Dev.show_hurtboxes = false
	if arena.get("overlay"):
		arena.overlay.visible = false
	var cam := Camera3D.new()
	arena.add_child(cam)
	cam.global_position = Vector3(2.2, 1.5, 1.8)
	cam.look_at(Vector3(0, 1.1, 1.6))
	cam.current = true


var _prev_id := ""
var _prev_frame := 0
var _prev_cancel := 0


## The MECHANICS formula by hand: first hit fresh, then combo scaling max(0.8 - 0.1 n, 0.3).
func _expected_damage(p: Fighter) -> int:
	var total := 0
	var n := 0
	for step in AARON:
		var m: MoveData = null
		for c in p.move_set.commands:
			if (c["move"] as MoveData).action_id == int(step[2].substr(1)):
				m = c["move"]
		var base: int = (m.get_hits()[0] as MoveHit).damage
		var factor := 1.0 if n == 0 else maxf(0.8 - 0.1 * n, 0.3)
		total += int(base * factor + 0.01)
		n += 1
	return total


func _dummy() -> Fighter:
	for n in get_tree().get_nodes_in_group("fighters"):
		if (n as Fighter).display_name == "Dummy 1":
			return n
	return null
