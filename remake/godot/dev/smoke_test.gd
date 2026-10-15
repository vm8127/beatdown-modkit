extends Node
## Scripted check of the combat loop (`-- --smoke`): puts the player next to Dummy 1,
## presses P P P (jab, jab, straight: a 3-hit true combo ending in a knockdown),
## prints every state change, checks the result and quits with exit code 0 or 1.
## `--shot=<file.png>` also saves a screenshot during the straight's hitstop.

var arena: Node
var _frame := 0
var _log_last := {}
var _shot := ""
var _shot_taken := false


func _ready() -> void:
	process_physics_priority = 100   # after the fighters
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--shot="):
			_shot = a.substr(7)


func _physics_process(_delta: float) -> void:
	if not Dev.tick:
		return
	_frame += 1
	var p: Fighter = arena.player
	var d: Fighter = _dummy()
	if _frame == 1:
		p.global_position = Vector3(0, 0, 2.2)
		p.rotation.y = 0.0
	# Press each button a few frames early: the buffer holds it until the combo window.
	if _frame in [20, 30, 42]:
		(p.brain as PlayerBrain).press("P")
		print("frame %d: press P" % Dev.frame)
	for f in [p, d]:
		var line: String = f.debug_text()
		var key: String = "%s %s %s" % [f.display_name, f.state, f.move_id]
		if _log_last.get(f.display_name, "") != key:
			_log_last[f.display_name] = key
			print("frame %d: %s" % [Dev.frame, line])
	if _shot != "" and not _shot_taken and p.move_id == "straight" and p.hitstop > 0:
		_shot_taken = true
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png(_shot)
		print("screenshot saved: %s" % _shot)
	if _frame == 200:
		var ok := p.combo_hits == 3 and d.hp == d.max_hp - 50
		print("RESULT combo %d hits, %d damage, dummy hp %d -> %s" % [p.combo_hits, p.combo_damage, d.hp, "PASS" if ok else "FAIL"])
		get_tree().quit(0 if ok else 1)


func _dummy() -> Fighter:
	for n in get_tree().get_nodes_in_group("fighters"):
		if (n as Fighter).display_name == "Dummy 1":
			return n
	return null
