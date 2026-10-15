extends Node3D
## Model viewer (M1): shows every .glb in res://assets_ripped/models side by side on a turntable.
##
## Run: Godot --path remake/godot res://dev/model_viewer.tscn
## Keys: Left/Right turn, Up/Down zoom, Space pauses the turntable.
## `-- --shot=<file.png>` saves a screenshot after a few frames and quits; `--dist=` and `--height=` place the camera.

const MODEL_DIR := "res://assets_ripped/models"
const SPACING := 2.0

var _turn := true
var _shot := ""
var _frames := 0
var _pivot: Node3D
var _cam: Camera3D
var _dist := 4.5
var _height := 1.0


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--shot="):
			_shot = a.substr(7)
		elif a.begins_with("--dist="):
			_dist = float(a.substr(7))
		elif a.begins_with("--height="):
			_height = float(a.substr(9))
	_pivot = Node3D.new()
	add_child(_pivot)
	var files := []
	var dir := DirAccess.open(MODEL_DIR)
	if dir == null:
		push_error("no %s: run python remake/tools/remake_assets.py ISO remake/godot/assets_ripped" % MODEL_DIR)
	else:
		for f in dir.get_files():
			if f.ends_with(".glb"):
				files.append(f)
	files.sort()
	var x := -SPACING * (files.size() - 1) / 2.0
	for f in files:
		var scene := load(MODEL_DIR + "/" + f) as PackedScene
		if scene == null:
			push_error("could not load " + f)
			continue
		var m := scene.instantiate() as Node3D
		m.position.x = x
		_pivot.add_child(m)
		var label := Label3D.new()
		label.text = f.get_basename()
		label.position = Vector3(x, -0.15, 0)
		label.pixel_size = 0.002
		add_child(label)
		print("loaded %s" % f)
		x += SPACING
	_build_stage()


func _build_stage() -> void:
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.background_mode = Environment.BG_COLOR
	env.environment.background_color = Color(0.25, 0.27, 0.3)
	env.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_color = Color(0.6, 0.6, 0.6)
	add_child(env)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-40, 30, 0)
	add_child(sun)
	var floor_mesh := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(6, 6)
	floor_mesh.mesh = plane
	add_child(floor_mesh)
	_cam = Camera3D.new()
	add_child(_cam)
	_place_camera()


func _place_camera() -> void:
	_cam.position = Vector3(0, _height, _dist)
	_cam.look_at(Vector3(0, _height - 0.1, 0))


func _process(delta: float) -> void:
	if Input.is_physical_key_pressed(KEY_LEFT):
		_pivot.rotate_y(-2.0 * delta)
	elif Input.is_physical_key_pressed(KEY_RIGHT):
		_pivot.rotate_y(2.0 * delta)
	elif _turn and _shot == "":
		for c in _pivot.get_children():
			(c as Node3D).rotate_y(0.6 * delta)
	if Input.is_physical_key_pressed(KEY_UP):
		_dist = max(1.0, _dist - 3.0 * delta)
		_place_camera()
	elif Input.is_physical_key_pressed(KEY_DOWN):
		_dist = min(12.0, _dist + 3.0 * delta)
		_place_camera()
	_frames += 1
	if _shot != "" and _frames == 10:
		get_viewport().get_texture().get_image().save_png(_shot)
		print("screenshot saved: %s" % _shot)
		get_tree().quit()


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and event.physical_keycode == KEY_SPACE:
		_turn = not _turn
