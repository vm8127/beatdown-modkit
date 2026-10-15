class_name PlayerBrain
extends Node
## Turns keyboard, mouse and gamepad into what the fighter wants: a direction to walk,
## guard, and input codes ("P", "→P", "→→P", "↓→K", "→G"...).
##
## The direction in a code is relative to the opponent, like the game's Pad_ReadCommand
## (0x002A42E0), which measures the stick's angle against the line to the target: toward it
## is →, away is ←. The remake adds ↑ / ↓ for the stick to the fighter's left / right (the game's
## rule for those isn't traced: an open question). Motions (→→, ↓→, →↓→) are read from the
## recent stick history when the button is pressed.
##
## Presses go into a short buffer (BUFFER frames) instead of being used at once, so a press
## made a little before the fighter is free still counts.

const BUFFER := 10
const MOTION_FRAMES := 18       ## a motion (→→, ↓→, →↓→) must be done within this many frames
const ANGLE_FWD := 45.0         ## within this many degrees of the opponent: →
const ANGLE_BACK := 135.0       ## beyond this: ←; in between: ↑ (left) or ↓ (right)

@export var camera: ThirdPersonCamera   ## for camera-relative movement
var presses: Array[Dictionary] = []     ## {code, frame}, oldest first
var _dirs: Array[Dictionary] = []       ## stick history: {dir ("" neutral, "→", ...), frame} on each change
var _guard_was := false


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and Input.mouse_mode != Input.MOUSE_MODE_CAPTURED:
		return   # that click captures the mouse, it isn't a punch
	if event.is_action_pressed("attack_p"):
		press("P")
	elif event.is_action_pressed("attack_k"):
		press("K")


## Buffers a button press as an input code. `dir` forces the direction (scripted tests);
## otherwise it's read from the stick, with motions.
func press(button: String, dir := "?") -> void:
	var code := button
	if dir != "?":
		code = dir + button
	else:
		code = _motion() + button
	presses.append({"code": code, "frame": Dev.frame})


func think(f: Fighter) -> void:
	while presses.size() > 0 and Dev.frame - int(presses[0]["frame"]) > BUFFER:
		presses.pop_front()   # too old: forget it
	var d := direction_code(f, move_dir(f))
	if _dirs.is_empty() or _dirs[-1]["dir"] != d:
		_dirs.append({"dir": d, "frame": Dev.frame})
		if _dirs.size() > 8:
			_dirs.pop_front()
	# Guard tapped with a direction: a directional guard move (→G Weaving, ←G Sway Back).
	var g := Input.is_action_pressed("guard")
	if g and not _guard_was and d != "":
		presses.append({"code": d + "G", "frame": Dev.frame})
	_guard_was = g


## Stick direction relative to the opponent (or to the fighter's facing when there is none).
static func direction_code(f: Fighter, dir: Vector3) -> String:
	if dir.length() < 0.5:
		return ""
	var ref := f.forward()
	var t := f.nearest_enemy(6.0)
	if t:
		var to := t.global_position - f.global_position
		to.y = 0
		if to.length() > 0.01:
			ref = to.normalized()
	var a := rad_to_deg(Vector2(ref.x, ref.z).angle_to(Vector2(dir.x, dir.z)))
	if absf(a) <= ANGLE_FWD:
		return "→"
	if absf(a) >= ANGLE_BACK:
		return "←"
	return "↑" if a < 0.0 else "↓"   # stick to the fighter's left / right


## The direction part of a code: the motion that ends with the current stick, if any.
func _motion() -> String:
	if _dirs.is_empty():
		return ""
	var now: String = _dirs[-1]["dir"]
	if now == "":
		return ""
	var recent := PackedStringArray()   # non-neutral directions within the motion time, newest last
	var neutral_gap := false         # a neutral between the last two non-neutral ones (for →→)
	for i in range(_dirs.size() - 1, -1, -1):
		var e: Dictionary = _dirs[i]
		if Dev.frame - int(e["frame"]) > MOTION_FRAMES and i < _dirs.size() - 1:
			break
		if e["dir"] == "":
			if recent.size() == 1:
				neutral_gap = true
			continue
		recent.insert(0, e["dir"])
	var n := recent.size()
	var last3 := "".join(recent.slice(maxi(0, n - 3)))
	var last2 := "".join(recent.slice(maxi(0, n - 2)))
	if n >= 3 and last3 == "→↓→":
		return "→↓→"
	if n >= 2 and last2 == "↓→":
		return "↓→"
	if n >= 2 and last2 == "→→" and neutral_gap:
		return "→→"
	return now


## Uses up the oldest buffered input code; "" if there is none.
func take_input(_f: Fighter) -> String:
	if presses.is_empty():
		return ""
	return presses.pop_front()["code"]


func move_dir(_f: Fighter) -> Vector3:
	var v := Input.get_vector("move_left", "move_right", "move_forward", "move_back")
	var yaw := camera.yaw if camera else 0.0
	return Basis(Vector3.UP, yaw) * Vector3(v.x, 0, v.y)


func wants_guard(_f: Fighter) -> bool:
	return Input.is_action_pressed("guard")


func face_target(f: Fighter) -> Variant:
	return f.nearest_enemy(4.0) if f.state == Fighter.State.GUARD else null


func buffer_text() -> String:
	var parts: Array[String] = []
	for p in presses:
		parts.append("%s@%d" % [p["code"], p["frame"]])
	return " ".join(parts) if parts.size() > 0 else "-"
