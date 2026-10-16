extends Node
## Plays every chain of the loaded style against Dummy 1 (`-- --probe`, dev arena) and prints, per command, each
## hit's move, frame, damage and the victim's reaction (Fighter.last_reaction), and FELL-EARLY when the victim went
## down before the chain's last move and a later move whiffed (the game keeps hitting a launched fighter). `--probe=P,P,P` plays one sequence; `--gap=N` presses N frames into each move (default 3).
## Prints one line per command, then a RESULT line; for comparing with the game's numbers (docs/ANIMATION.md).

var arena: Node
var _seqs: Array = []
var _gap := 3


func _ready() -> void:
	process_physics_priority = 100
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--probe="):
			_seqs = [PackedStringArray(a.substr(8).split(","))]
		elif a.begins_with("--gap="):
			_gap = int(a.substr(6))
	_run.call_deferred()


func _frames(n: int) -> void:
	for i in n:
		await get_tree().physics_frame


func _dummy() -> Fighter:
	for n in get_tree().get_nodes_in_group("fighters"):
		if (n as Fighter).display_name == "Dummy 1":
			return n
	return null


func _run() -> void:
	var p: Fighter = arena.player
	for n in get_tree().get_nodes_in_group("fighters"):
		if n.brain is DummyBrain:
			n.brain.mode = DummyBrain.Mode.STAND
			if (n as Fighter).display_name != "Dummy 1":
				(n as Fighter).global_position = Vector3(20, 0, 20 + randf())   # out of the way
	await _frames(5)
	if _seqs.is_empty():
		for c in p.move_set.get_commands():
			var s: PackedStringArray = c["seq"]
			if s.size() >= 2 and not "GRAB" in s[0]:
				_seqs.append(s)
	var falls := 0
	for s in _seqs:
		var line := await _play(p, _dummy(), s)
		if "FELL-EARLY" in line:
			falls += 1
		print(line)
	print("RESULT probe: %d sequences, %d with an early fall" % [_seqs.size(), falls])
	get_tree().quit(0)


func _reset(p: Fighter, d: Fighter) -> void:
	for i in 600:
		if p.state in [Fighter.State.IDLE, Fighter.State.MOVE] and d.state in [Fighter.State.IDLE, Fighter.State.MOVE]:
			break
		await _frames(1)
	await _frames(30)
	d.global_position = Vector3(0, 0, 1)
	d.rotation.y = PI   # facing the player
	d.velocity = Vector3.ZERO
	d.hp = d.max_hp
	p.global_position = Vector3(0, 0, 2.0)
	p.rotation.y = 0.0
	p.velocity = Vector3.ZERO
	(p.brain as PlayerBrain).presses.clear()
	await _frames(3)


func _press(p: Fighter, code: String) -> void:
	var b := code.right(1)
	(p.brain as PlayerBrain).press(b, code.left(code.length() - 1))


func _play(p: Fighter, d: Fighter, seq: PackedStringArray) -> String:
	await _reset(p, d)
	var hits := []
	var moves := []
	var fell_at := -1
	var step := 0
	_press(p, seq[0])
	var last_hp := d.hp
	var last_react := 0
	for f in 400:
		await _frames(1)
		if p.state == Fighter.State.ATTACK and (moves.is_empty() or moves[-1] != p.move_id):
			moves.append(p.move_id)
			step = moves.size()
		# press the next code a few frames into each move
		if p.state == Fighter.State.ATTACK and p.state_frame == _gap and step < seq.size() and moves.size() == step:
			_press(p, seq[step])
			step += 1   # one press per move
		if d.hp < last_hp or d._react_count != last_react:
			if d.hp < last_hp:
				hits.append("%s f%d -%d %s" % [p.move_id, p.state_frame, last_hp - d.hp, d.last_reaction])
			last_hp = d.hp
			last_react = d._react_count
			if d.state == Fighter.State.KNOCKDOWN and fell_at < 0:
				fell_at = moves.size()
		if p.state in [Fighter.State.IDLE, Fighter.State.MOVE] and f > 10 and p._tail.is_empty():
			break
	var early := fell_at > 0 and fell_at < seq.size() and hits.size() < moves.size()   # fell, and a later move whiffed
	return "%-22s moves %s | %d hits: %s%s" % [" ".join(seq), ",".join(moves), hits.size(), "; ".join(hits),
		"  FELL-EARLY after move %d" % fell_at if early else ""]
