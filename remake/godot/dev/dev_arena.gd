extends Node3D
## Developer arena: a flat test level to try features without real stages or the story.
## The level, the player, the dummies, the camera and the overlay are nodes in
## dev_arena.tscn (edit them in the editor); this script adds the dev keys and spawns
## extra dummies.
##
## Command line (after `--`): `--smoke` runs a scripted combo and prints what happened,
## `--shot=<file.png>` saves a screenshot at the end of it and quits. remake/README.md.

const FIGHTER_SCENE := preload("res://game/fighter/fighter.tscn")

var dummy_mode := DummyBrain.Mode.STAND
var _dummies := 3

@onready var player: Fighter = $Player
@onready var overlay: CanvasLayer = $DebugOverlay


func _ready() -> void:
	if "--smoke" in OS.get_cmdline_user_args():
		var test := preload("res://dev/smoke_test.gd").new()
		test.arena = self
		add_child(test)


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed and Input.mouse_mode != Input.MOUSE_MODE_CAPTURED:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	elif event.is_action_pressed("ui_cancel"):
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	elif event.is_action_pressed("dev_spawn"):
		_spawn_dummy(player.global_position + player.forward() * 2.0)
	elif event.is_action_pressed("dev_dummy_mode"):
		dummy_mode = (dummy_mode + 1) % DummyBrain.Mode.size() as DummyBrain.Mode
		for n in get_tree().get_nodes_in_group("fighters"):
			if n.brain is DummyBrain:
				n.brain.mode = dummy_mode
	elif event.is_action_pressed("dev_reset"):
		get_tree().reload_current_scene()
	elif event.is_action_pressed("dev_overlay"):
		overlay.visible = not overlay.visible


## Spawns a dummy from the same fighter scene the ones in the editor use.
func _spawn_dummy(pos: Vector3) -> Fighter:
	_dummies += 1
	var f: Fighter = FIGHTER_SCENE.instantiate()
	f.name = "Dummy%d" % _dummies
	f.display_name = "Dummy %d" % _dummies
	f.color = Color(0.3, 0.5, 0.85)
	var brain := DummyBrain.new()
	brain.name = "Brain"
	brain.mode = dummy_mode
	f.add_child(brain)
	add_child(f)
	f.global_position = pos
	var to := player.global_position - pos
	f.rotation.y = atan2(-to.x, -to.z)
	return f
