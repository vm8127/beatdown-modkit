extends Node3D
## Stage test (M6): walk around a real area converted from the disc.
## remake_assets.py writes three files per area (remake/tools/conv_stages.py):
##   stages/area_NN.glb            the render world + props (unlit: the lighting is baked into vertex colours)
##   stages/area_NN_collision.glb  walls, floor, camera and door-panel meshes -> trimesh StaticBody3Ds here
##   stages/area_NN.json           lights, battle spots, doors, spawn point
## The player is the M0 fighter scene with a PlayerBrain and the third-person camera (stage_test.tscn).
##
## Keys: as the dev arena (WASD / stick, mouse camera); F7 resets; Tab hides the text.
## Command line (after `--`): `--area=N` (default 5), `--shot=<file.png>` saves a screenshot after a moment and
## quits, `--view=overview|player|stairs` picks the screenshot camera, `--walk` walks into the walls and prints
## where the player stops (exit code 1 if it falls through the floor or walks out of the walls).

const LAYER_WORLD := 1        ## walls, floor, door panels: fighters and the camera collide with them
const LAYER_CAMERA := 16      ## the area's separate camera-collision mesh: only the camera arm uses it

@export var area := 5

var info := {}
var _shot := ""
var _view := "player"
var _walk := false
var _frames := 0
var _log: Array[String] = []

@onready var player: Fighter = $Player
@onready var cam: ThirdPersonCamera = $Camera
@onready var _label: Label = $Overlay/Label


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--area="):
			area = int(a.substr(7))
		elif a.begins_with("--shot="):
			_shot = a.substr(7)
		elif a.begins_with("--view="):
			_view = a.substr(7)
		elif a == "--walk":
			_walk = true
	var base := "res://assets_ripped/stages/area_%02d" % area
	if not ResourceLoader.exists(base + ".glb"):
		push_error("%s.glb missing: run python remake/tools/remake_assets.py ISO remake/godot/assets_ripped" % base)
		get_tree().quit(1)
		return
	info = JSON.parse_string(FileAccess.get_file_as_string(base + ".json"))
	var stage := (load(base + ".glb") as PackedScene).instantiate()
	$Stage.add_child(stage)
	_fix_materials(stage)
	_add_collision(load(base + "_collision.glb") as PackedScene)
	_setup_lights()
	cam.get_node("Pitch/SpringArm3D").collision_mask = LAYER_WORLD | LAYER_CAMERA
	var spawn: Dictionary = info["spawn"]
	var p: Array = spawn["pos"]
	player.global_position = Vector3(p[0], p[1] + 0.1, p[2])
	player.rotation.y = deg_to_rad(float(spawn["angle_deg"]))
	cam.yaw = player.rotation.y
	cam.snap_to_target()


## glTF has no additive blending: conv_stages.py names those materials "... [add]" (sparks, light glows).
func _fix_materials(root: Node) -> void:
	for mi in root.find_children("*", "MeshInstance3D", true, false):
		var mesh: Mesh = (mi as MeshInstance3D).mesh
		for i in mesh.get_surface_count():
			var mat := mesh.surface_get_material(i) as BaseMaterial3D
			if mat and mat.resource_name.ends_with("[add]"):
				mat.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
				mat.depth_draw_mode = BaseMaterial3D.DEPTH_DRAW_DISABLED
				mat.cull_mode = BaseMaterial3D.CULL_DISABLED


## Each collision mesh becomes a StaticBody3D with a concave (trimesh) shape. The game's meshes are open
## (single walls, a floor sheet), so backface collision is on: they block from both sides.
func _add_collision(scene: PackedScene) -> void:
	var root := scene.instantiate()
	add_child(root)   # in the tree only to read the meshes' global transforms
	for mi in root.find_children("*", "MeshInstance3D", true, false):
		var m := mi as MeshInstance3D
		var shape := ConcavePolygonShape3D.new()
		shape.set_faces(m.mesh.get_faces())
		shape.backface_collision = true
		var body := StaticBody3D.new()
		body.name = String(m.name)
		body.collision_layer = LAYER_CAMERA if String(m.name).begins_with("camera") else LAYER_WORLD
		body.collision_mask = 0
		var cs := CollisionShape3D.new()
		cs.shape = shape
		body.add_child(cs)
		$Collision.add_child(body)
		body.global_transform = m.global_transform
	root.queue_free()


## The area's two directional lights and ambient colour (AreaDef, docs/STAGES.md) light the fighters;
## the world itself is unlit. Angle convention (x pitch, y yaw in degrees) is a guess.
func _setup_lights() -> void:
	var env: Environment = $WorldEnvironment.environment
	var amb: Array = info["ambient_light"]
	env.ambient_light_color = Color(amb[0], amb[1], amb[2])
	var lights: Array = info["lights"]
	for i in lights.size():
		var l: DirectionalLight3D = get_node("Light%d" % (i + 1))
		var ang: Array = lights[i]["angles_deg"]
		var c: Array = lights[i]["color"]
		l.rotation_degrees = Vector3(-float(ang[0]), float(ang[1]), 0)
		l.light_color = Color(c[0], c[1], c[2])


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed and Input.mouse_mode != Input.MOUSE_MODE_CAPTURED:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	elif event.is_action_pressed("ui_cancel"):
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	elif event.is_action_pressed("dev_reset"):
		get_tree().reload_current_scene()
	elif event.is_action_pressed("dev_overlay"):
		_label.visible = not _label.visible


func _physics_process(_delta: float) -> void:
	_frames += 1
	if _walk:
		_walk_test()
	elif _shot != "" and _frames == 40:
		_take_shot()


func _process(_delta: float) -> void:
	var p := player.global_position
	_label.text = "%s (area %d)    fps %d\npos %.2f %.2f %.2f  on floor %s\n%s\nWASD / stick move · mouse camera · F7 reset · Tab hide" % [
		info.get("name", "?"), area, Engine.get_frames_per_second(), p.x, p.y, p.z, player.is_on_floor(),
		"\n".join(_log.slice(-4))]


## --walk: walk 6 s each way (camera yaw picks the direction) and log where the player stops. Subway walls
## (docs/STAGES.md, "The subway's collision"): back z 0.3 m, front z 12.8 m, ends x -10.7 / 15.5 m; the
## stairwells (x -10.6..-7.3 and 9.6..13) are closed at platform level by the door panels at z -0.96 m.
const WALK_LEGS := [["back (-z)", 0.0, null], ["front (+z)", PI, null], ["left end (-x)", PI / 2, null],
	["right end (+x)", -PI / 2, null], ["left stairwell door (-z)", 0.0, Vector3(-9.0, 0.1, 4.0)]]
const LEG_FRAMES := 360


func _walk_test() -> void:
	if _frames < 30:
		return
	var leg := (_frames - 30) / LEG_FRAMES
	var t := (_frames - 30) % LEG_FRAMES
	if leg >= WALK_LEGS.size():
		Input.action_release("move_forward")
		var ok := _check_inside()
		print("walk test: %s" % ("PASS" if ok else "FAIL"))
		_walk = false
		if _shot != "":
			_take_shot()
		else:
			get_tree().quit(0 if ok else 1)
		return
	if t == 0:
		if WALK_LEGS[leg][2] != null:
			player.global_position = WALK_LEGS[leg][2]
			player.velocity = Vector3.ZERO
		cam.yaw = WALK_LEGS[leg][1]
		Input.action_press("move_forward")
	if t == LEG_FRAMES - 1:
		var p := player.global_position
		var line := "%s: stopped at x %.2f y %.2f z %.2f, on floor %s" % [WALK_LEGS[leg][0], p.x, p.y, p.z, player.is_on_floor()]
		_log.append(line)
		print(line)
	if not _check_inside():
		print("walk test: FAIL at frame %d, position %s" % [_frames, player.global_position])
		get_tree().quit(1)
		_walk = false


func _check_inside() -> bool:
	var p := player.global_position
	return p.y > -0.5 and p.x > -11.0 and p.x < 15.8 and p.z > -4.0 and p.z < 13.1


func _take_shot() -> void:
	match _view:
		"overview":
			_shot_camera(Vector3(2.5, 17, 25), Vector3(2.5, 0, 5))
		"stairs":
			_shot_camera(Vector3(-4, 3.5, 8), Vector3(-9, 1.0, -1))
		"track":
			_shot_camera(Vector3(2, 2.5, 11), Vector3(2, 0.5, 20))
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(_shot)
	print("screenshot saved: %s" % _shot)
	get_tree().quit()


func _shot_camera(from: Vector3, at: Vector3) -> void:
	var c := Camera3D.new()
	add_child(c)
	c.global_position = from
	c.look_at(at)
	c.far = 200.0
	c.current = true
