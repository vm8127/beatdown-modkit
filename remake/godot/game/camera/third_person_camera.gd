class_name ThirdPersonCamera
extends Node3D
## Orbit camera behind the target: yaw node (this) -> pitch node -> SpringArm3D -> Camera3D.
## The spring arm pulls the camera in when a wall is between it and the player.
## It's purely visual, so it runs in _process (every rendered frame) and smooths with
## exponential decay, which looks the same at any frame rate.

var target: Node3D
var yaw := 0.0
var pitch := -0.35
var distance := 5.0
var mouse_sensitivity := 0.0025
var stick_speed := 2.5
var camera: Camera3D

var _pitch_node: Node3D
var _arm: SpringArm3D
var _trauma := 0.0


func _ready() -> void:
	top_level = true
	add_to_group("camera")
	_pitch_node = Node3D.new()
	add_child(_pitch_node)
	_arm = SpringArm3D.new()
	_arm.collision_mask = 1   # world only, not the fighters
	_arm.margin = 0.2
	var probe := SphereShape3D.new()
	probe.radius = 0.2
	_arm.shape = probe
	_pitch_node.add_child(_arm)
	camera = Camera3D.new()
	camera.fov = 65
	_arm.add_child(camera)
	camera.make_current()


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		yaw -= event.relative.x * mouse_sensitivity
		pitch -= event.relative.y * mouse_sensitivity
	elif event is InputEventMouseButton and event.pressed:
		if event.button_index == MOUSE_BUTTON_WHEEL_UP:
			distance = maxf(2.0, distance - 0.5)
		elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			distance = minf(12.0, distance + 0.5)


func _process(delta: float) -> void:
	var look := Input.get_vector("cam_left", "cam_right", "cam_up", "cam_down")
	yaw -= look.x * stick_speed * delta
	pitch -= look.y * stick_speed * delta
	pitch = clampf(pitch, -1.3, 0.35)
	if target:
		var goal := target.global_position + Vector3(0, 1.5, 0)
		global_position = global_position.lerp(goal, 1.0 - exp(-12.0 * delta))
	rotation = Vector3(0, yaw, 0)
	_pitch_node.rotation.x = pitch
	_arm.spring_length = distance
	# Screen shake: "trauma" decays over time, shake grows with its square.
	_trauma = maxf(0.0, _trauma - delta * 2.5)
	var s := _trauma * _trauma
	camera.h_offset = randf_range(-1, 1) * 0.15 * s
	camera.v_offset = randf_range(-1, 1) * 0.15 * s


func snap_to_target() -> void:
	if target:
		global_position = target.global_position + Vector3(0, 1.5, 0)


func add_shake(amount: float) -> void:
	_trauma = minf(1.0, _trauma + amount)
