class_name PlayerBrain
extends Node
## Turns keyboard, mouse and gamepad into what the fighter wants: a direction to walk,
## guard, and button presses.
##
## Presses go into a short buffer (BUFFER frames) instead of being used at once, so a
## press made a little before the combo window opens still counts. Without it, combos
## would demand frame-perfect timing; with it they feel "responsive".

const BUFFER := 10

var camera: ThirdPersonCamera   ## for camera-relative movement
var presses: Array[Dictionary] = []   ## {button, frame}, oldest first


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and Input.mouse_mode != Input.MOUSE_MODE_CAPTURED:
		return   # that click captures the mouse, it isn't a punch
	if event.is_action_pressed("attack_p"):
		press("P")
	elif event.is_action_pressed("attack_k"):
		press("K")


func press(button: String) -> void:
	presses.append({"button": button, "frame": Dev.frame})


func think(_f: Fighter) -> void:
	while presses.size() > 0 and Dev.frame - int(presses[0]["frame"]) > BUFFER:
		presses.pop_front()   # too old: forget it


## Uses up the oldest buffered press of one of these buttons; "" if there is none.
func take_press(buttons: Array) -> String:
	for i in presses.size():
		var b: String = presses[i]["button"]
		if b in buttons:
			presses.remove_at(i)
			return b
	return ""


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
		parts.append("%s@%d" % [p["button"], p["frame"]])
	return " ".join(parts) if parts.size() > 0 else "-"
