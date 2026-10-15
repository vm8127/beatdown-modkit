class_name DummyBrain
extends Node
## A training dummy. Same interface as PlayerBrain, so the Fighter can't tell the
## difference: that's what lets one fighter class serve the player and every enemy.
## M5 replaces this with real enemy AI.

enum Mode { STAND, GUARD, COUNTER, FIGHT }
const MODE_NAMES := ["stand", "guard", "counter-jab", "fight"]

var mode := Mode.STAND
var _timer := 0
var _queue: Array[String] = []


func think(f: Fighter) -> void:
	_timer += 1
	if f.state in [Fighter.State.HITSTUN, Fighter.State.KNOCKDOWN, Fighter.State.GETUP]:
		_queue.clear()
		_timer = 0
		return
	var t := _target()
	if t == null:
		return
	var d := t.global_position.distance_to(f.global_position)
	match mode:
		Mode.COUNTER:
			if d < 2.2 and _timer >= 70 and f.state == Fighter.State.IDLE:
				_queue = ["P"]
				_timer = 0
		Mode.FIGHT:
			if d < 1.6 and _timer >= 50 and f.state == Fighter.State.IDLE:
				_queue = ["P", "P", "P"]   # jab, jab, straight
				_timer = 0


func take_press(buttons: Array) -> String:
	if _queue.size() > 0 and _queue[0] in buttons:
		return _queue.pop_front()
	return ""


func move_dir(f: Fighter) -> Vector3:
	var t := _target()
	if mode != Mode.FIGHT or t == null:
		return Vector3.ZERO
	var to := t.global_position - f.global_position
	to.y = 0
	return to.normalized() * 0.6 if to.length() > 1.3 else Vector3.ZERO


func wants_guard(_f: Fighter) -> bool:
	return mode == Mode.GUARD


func face_target(_f: Fighter) -> Variant:
	return _target()


func _target() -> Fighter:
	return get_tree().get_first_node_in_group("player") as Fighter
