extends SceneTree
## Headless check of a generated MoveSet against the frame data `codemap.py framedata` prints.
## Run by remake/tools/test_moves.py, which writes the expected values:
##   godot --headless --path remake/godot --script res://dev/move_check.gd -- --expect=<file.json>
## Prints one line per mismatch and a summary; exit code 0 = all match.

var _fails: Array[String] = []
var _notes: Array[String] = []
var _checked := 0


func _initialize() -> void:
	var path := ""
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--expect="):
			path = a.substr(9)
	var want = JSON.parse_string(FileAccess.get_file_as_string(path))
	if want == null:
		print("cannot read %s" % path)
		quit(2)
		return
	var res := "res://assets_ripped/moves/%s.tres" % want["style"]
	var ms := load(res) as MoveSet
	if ms == null:
		print("cannot load %s (run remake/tools/remake_assets.py first)" % res)
		quit(2)
		return
	var by_action := {}
	for c in ms.commands:
		by_action[(c["move"] as MoveData).action_id] = c["move"]
	# Commands: every input sequence names the same action.
	for c in want["commands"]:
		var m := ms.match_sequence(PackedStringArray(c["seq"]))
		_eq("command %s" % " ".join(c["seq"]), m.action_id if m else -1, int(c["action"]))
	for key in want["actions"]:
		var e: Dictionary = want["actions"][key]
		var m: MoveData = by_action.get(int(key))
		if m == null:
			_fails.append("action %s: missing" % key)
			continue
		var t := "action %s (%s)" % [key, m.move_name]
		_eq(t + " anim", m.anim_id, int(e["anim"]))
		_eq(t + " blend", m.blend, int(e["blend"]))
		if e["end"] != null:
			_eq(t + " anim end", m.anim_end, int(e["end"]))
			_near(t + " end (game frames)", m.frames, int(e["end_g"]))
		var sp := []
		for v in m.speeds:
			sp.append([int(v.x), snappedf(v.y, 0.001)])
		var sw := []
		for v in e["speeds"]:
			sw.append([int(v[0]), snappedf(float(v[1]), 0.001)])
		_eq(t + " speeds", str(sp), str(sw))
		_eq(t + " cancel (anim)", m.anim_cancel, int(e["cancel"]))
		_near(t + " cancel (game)", m.cancel_start, int(e["cancel_g"]))
		_eq(t + " release (anim)", m.anim_release, int(e["release"]))
		_near(t + " release (game)", m.release_frame, int(e["release_g"]))
		var hits := m.get_hits() if m.hits.size() > 0 else []
		_eq(t + " hit windows", hits.size(), (e["hits"] as Array).size())
		for i in mini(hits.size(), (e["hits"] as Array).size()):
			var h: MoveHit = hits[i]
			var w: Dictionary = e["hits"][i]
			_eq(t + " hit %d anim start" % i, h.anim_start, int(w["start"]))
			_eq(t + " hit %d anim end" % i, h.anim_end, int(w["end"]))
			_near(t + " hit %d start (game)" % i, h.start, int(w["start_g"]))
			_eq(t + " hit %d parts" % i, str(Array(h.parts)), str(w["parts"].map(func(x): return int(x))))
			_eq(t + " hit %d damage" % i, h.damage, int(w["damage"]))
	for n in _notes:
		print("note " + n)
	for f in _fails:
		print("MISMATCH " + f)
	print("RESULT %d checks, %d mismatches, %d game-frame values 1-2 frames off -> %s" % [
		_checked, _fails.size(), _notes.size(), "PASS" if _fails.is_empty() else "FAIL"])
	quit(0 if _fails.is_empty() else 1)


func _eq(what: String, got, expected) -> void:
	_checked += 1
	if got != expected:
		_fails.append("%s: got %s, framedata %s" % [what, got, expected])


## Game frames: within 2 of framedata's (it switches speed at the exact frame, the converter at
## the first whole frame that reaches it).
func _near(what: String, got: int, expected: int) -> void:
	_checked += 1
	if got == expected:
		return
	if absi(got - expected) <= 2:
		_notes.append("%s: %d, framedata %d" % [what, got, expected])
	else:
		_fails.append("%s: got %s, framedata %s" % [what, got, expected])
