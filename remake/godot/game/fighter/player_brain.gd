class_name PlayerBrain
extends Node
## Turns the controls (GameInput's actions: pad, keyboard, mouse) into what the fighter wants:
## a direction to walk, guard, run, and input codes ("P", "→P", "→→P", "↓→K", "→G", "#46"...).
##
## The direction in a code is relative to the opponent, like the game's Pad_ReadCommand
## (0x002A42E0), which measures the stick's angle against the line to the target: toward it
## is →, away is ←. The remake adds ↑ / ↓ for the stick to the fighter's left / right (the game's
## rule for those isn't traced: an open question). Motions (→→, ↓→, →↓→) are read from the
## recent stick history when the button is pressed, within the game's time limits
## (g_InputPatterns, docs/CONTROLS.md: 19 frames for two steps, 21 for three).
##
## Buttons -> codes (docs/CONTROLS.md, "Input patterns"; codes without a name in codemap.INPUTS keep
## the converter's "#XX" form so they match assets_ripped/moves/*.tres): punch P, kick K, special
## (○) S = #46 / →S #42 / ←S #43 / ↑S #44 / ↓S #45 / →→S #40, grab (R1) #1E, taunt (R3) #01,
## items (L2 / R2) #4C / #4D, guard tapped with a direction →G / ←G / ↑G / ↓G.
##
## Presses go into a short buffer (BUFFER frames) instead of being used at once, so a press
## made a little before the fighter is free still counts.

const BUFFER := 10
const MOTION2_FRAMES := 19      ## two-step motions (→→, ↓→): 316 ms in g_InputPatterns
const MOTION3_FRAMES := 21      ## three-step motions (→↓→): 350 ms
const ANGLE_FWD := 45.0         ## within this many degrees of the opponent: →
const ANGLE_BACK := 135.0       ## beyond this: ←; in between: ↑ (left) or ↓ (right)
const SPECIAL_CODES := {"": "#46", "→": "#42", "←": "#43", "↑": "#44", "↓": "#45", "→→": "#40"}
const BUTTON_CODES := {"grab": "#1E", "taunt": "#01", "item_1": "#4C", "item_2": "#4D"}

@export var camera: ThirdPersonCamera   ## for camera-relative movement
var presses: Array[Dictionary] = []     ## {code, frame}, oldest first
var _dirs: Array[Dictionary] = []       ## stick history: {dir ("" neutral, "→", ...), frame} on each change
var _guard_was := false
var _seen_hitstop := 0                  ## the fighter's hitstop last frame (a rise = an impact)
var _seen_hp := -1


func _unhandled_input(event: InputEvent) -> void:
	if GameInput.controls_menu_open():
		return
	if event is InputEventMouseButton and Input.mouse_mode != Input.MOUSE_MODE_CAPTURED:
		return   # that click captures the mouse, it isn't a punch
	if event.is_action_pressed("attack_p"):
		press("P")
	elif event.is_action_pressed("attack_k"):
		press("K")
	elif event.is_action_pressed("special"):
		press("S")
	else:
		for action: String in BUTTON_CODES:
			if event.is_action_pressed(action):
				presses.append({"code": BUTTON_CODES[action], "frame": Dev.frame})
				return


## Buffers a button press ("P", "K" or "S") as an input code. `dir` forces the direction
## (scripted tests); otherwise it's read from the stick, with motions.
func press(button: String, dir := "?") -> void:
	var d := dir if dir != "?" else _motion()
	var code := d + button
	if button == "S":
		code = SPECIAL_CODES.get(d, SPECIAL_CODES.get(d.right(1), "#46"))
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
	var g := Input.is_action_pressed("guard") and not GameInput.controls_menu_open()
	if g and not _guard_was and d != "":
		presses.append({"code": d + "G", "frame": Dev.frame})
	_guard_was = g
	_rumble(f)


## Fighter_Vibrate kind 0: a light rumble on every hit that lands, ours or on us (blocked hits
## don't rumble). Read from the fighter without touching it: our attack's hitstop starting (an
## impact) when last_event isn't a block, or lost HP outside a block.
func _rumble(f: Fighter) -> void:
	var landed := f.state == Fighter.State.ATTACK and f.hitstop > _seen_hitstop and not " blocked " in f.last_event
	var hurt := _seen_hp >= 0 and f.hp < _seen_hp and f.state != Fighter.State.BLOCKSTUN
	if landed or hurt:
		GameInput.vibrate(0)
	_seen_hitstop = f.hitstop
	_seen_hp = f.hp


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
	var recent: Array[Dictionary] = []   # non-neutral directions within the longest limit, newest last
	var neutral_gap := false             # a neutral between the last two non-neutral ones (for →→)
	for i in range(_dirs.size() - 1, -1, -1):
		var e: Dictionary = _dirs[i]
		if Dev.frame - int(e["frame"]) > MOTION3_FRAMES and i < _dirs.size() - 1:
			break
		if e["dir"] == "":
			if recent.size() == 1:
				neutral_gap = true
			continue
		recent.insert(0, e)
	var n := recent.size()
	if n >= 3 and _joined(recent, 3) == "→↓→" and Dev.frame - int(recent[n - 3]["frame"]) <= MOTION3_FRAMES:
		return "→↓→"
	if n >= 2 and Dev.frame - int(recent[n - 2]["frame"]) <= MOTION2_FRAMES:
		var two := _joined(recent, 2)
		if two == "↓→":
			return "↓→"
		if two == "→→" and neutral_gap:
			return "→→"
	return now


static func _joined(entries: Array[Dictionary], count: int) -> String:
	var s := ""
	for e in entries.slice(entries.size() - count):
		s += e["dir"]
	return s


## Uses up the oldest buffered input code; "" if there is none.
func take_input(_f: Fighter) -> String:
	if presses.is_empty():
		return ""
	return presses.pop_front()["code"]


func move_dir(_f: Fighter) -> Vector3:
	if GameInput.controls_menu_open():
		return Vector3.ZERO
	var v := GameInput.move_vector()
	var yaw := camera.yaw if camera else 0.0
	return Basis(Vector3.UP, yaw) * Vector3(v.x, 0, v.y)


func wants_guard(_f: Fighter) -> bool:
	return Input.is_action_pressed("guard") and not GameInput.controls_menu_open()


## RUN: L1 held, or the stick pushed all the way (Fighter_TaskWalk). For the fighter's locomotion
## (walk modes are the fight-feel work; Fighter doesn't ask for it yet).
func wants_run(_f: Fighter) -> bool:
	return Input.is_action_pressed("run") or GameInput.full_tilt()


## ESCAPE: L1 + R1 held (Battle_RequestEscape; the game needs a door zone during a battle).
func wants_escape(_f: Fighter) -> bool:
	return Input.is_action_pressed("run") and Input.is_action_pressed("grab")


func face_target(f: Fighter) -> Variant:
	return f.nearest_enemy(4.0) if f.state == Fighter.State.GUARD else null


func buffer_text() -> String:
	var parts: Array[String] = []
	for p in presses:
		parts.append("%s@%d" % [p["code"], p["frame"]])
	return " ".join(parts) if parts.size() > 0 else "-"
