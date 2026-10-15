extends Node3D
## Developer arena: a flat test level to try features without real stages or the story.
## Everything is built in code, so there is no scene file to keep in sync.
##
## Command line (after `--`): `--smoke` runs a scripted combo and prints what happened,
## `--shot=<file.png>` saves a screenshot at the end of it and quits. remake/README.md.

var player: Fighter
var camera: ThirdPersonCamera
var overlay: DebugOverlay
var dummy_mode := DummyBrain.Mode.STAND
var _dummies := 0


func _ready() -> void:
	_build_environment()
	_build_level()
	camera = ThirdPersonCamera.new()
	add_child(camera)
	var brain := PlayerBrain.new()
	brain.camera = camera
	player = _spawn("Player", Color(0.85, 0.25, 0.2), Vector3(0, 0, 5), brain)
	player.add_to_group("player")
	camera.target = player
	camera.snap_to_target()
	for p in [Vector3(0, 0, 1), Vector3(3, 0, -1), Vector3(-3, 0, -1)]:
		_spawn_dummy(p)
	overlay = DebugOverlay.new()
	overlay.arena = self
	add_child(overlay)
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


func _spawn(fighter_name: String, c: Color, pos: Vector3, brain: Node) -> Fighter:
	var f := Fighter.new()
	f.display_name = fighter_name
	f.color = c
	f.add_child(brain)
	add_child(f)
	f.global_position = pos
	return f


func _spawn_dummy(pos: Vector3) -> Fighter:
	_dummies += 1
	var brain := DummyBrain.new()
	brain.mode = dummy_mode
	var f := _spawn("Dummy %d" % _dummies, Color(0.3, 0.5, 0.85), pos, brain)
	f.rotation.y = atan2(-(player.global_position.x - pos.x), -(player.global_position.z - pos.z))
	return f


func _build_environment() -> void:
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	var sky := Sky.new()
	sky.sky_material = ProceduralSkyMaterial.new()
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.ssao_enabled = true
	var world_env := WorldEnvironment.new()
	world_env.environment = env
	add_child(world_env)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-55, -30, 0)
	sun.shadow_enabled = true
	add_child(sun)


func _build_level() -> void:
	var floor_mat := _checker(Color(0.42, 0.42, 0.45), Color(0.32, 0.32, 0.35))
	var wall_mat := _checker(Color(0.55, 0.5, 0.45), Color(0.47, 0.42, 0.38))
	_box(Vector3(40, 1, 40), Vector3(0, -0.5, 0), floor_mat)
	for side in [Vector3(0, 1.5, -20), Vector3(0, 1.5, 20)]:
		_box(Vector3(40, 3, 1), side, wall_mat)
	for side in [Vector3(-20, 1.5, 0), Vector3(20, 1.5, 0)]:
		_box(Vector3(1, 3, 40), side, wall_mat)
	_box(Vector3(4, 0.5, 8), Vector3(11, 0.9, 2), wall_mat, Vector3(-14, 0, 0))   # ramp
	_box(Vector3(6, 1, 4), Vector3(11, 0.5, -4), wall_mat)                        # platform at its top
	_box(Vector3(1, 3, 1), Vector3(-8, 1.5, -6), wall_mat)                        # pillars
	_box(Vector3(1, 3, 1), Vector3(8, 1.5, -10), wall_mat)
	for i in 4:
		_box(Vector3(3, 0.25 * (i + 1), 1), Vector3(-11, 0.125 * (i + 1), 4 - i), wall_mat)   # stairs
	_box(Vector3(12, 3, 1), Vector3(-6, 1.5, -14), wall_mat)                      # wall to test the camera


func _box(size: Vector3, pos: Vector3, mat: Material, rot_deg := Vector3.ZERO) -> void:
	var body := StaticBody3D.new()
	body.collision_layer = Fighter.LAYER_WORLD
	body.position = pos
	body.rotation_degrees = rot_deg
	var col := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = size
	col.shape = shape
	body.add_child(col)
	var mi := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = size
	mi.mesh = bm
	mi.material_override = mat
	body.add_child(mi)
	add_child(body)


## 1 m checker squares, projected in world space so every box gets the same scale.
func _checker(a: Color, b: Color) -> StandardMaterial3D:
	var img := Image.create_empty(64, 64, false, Image.FORMAT_RGB8)
	img.fill(a)
	img.fill_rect(Rect2i(0, 0, 32, 32), b)
	img.fill_rect(Rect2i(32, 32, 32, 32), b)
	var m := StandardMaterial3D.new()
	m.albedo_texture = ImageTexture.create_from_image(img)
	m.uv1_triplanar = true
	m.uv1_world_triplanar = true
	m.uv1_scale = Vector3(0.5, 0.5, 0.5)
	m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST_WITH_MIPMAPS
	return m
