extends Node3D
## Model viewer (M1, M2/M3): shows every .glb in res://assets_ripped/models side by side on a turntable, and plays
## the clips of res://assets_ripped/anims/*.glb on every rigged model (same Skeleton3D bone names).
##
## Run: Godot --path remake/godot res://dev/model_viewer.tscn
## Keys: Left/Right turn, Up/Down zoom, Space pauses the turntable.
## Tab / Shift+Tab next / previous clip, P play/pause, Comma / Period step one game frame (1/60 s) back / forward.
## `-- --shot=<file.png>` saves a screenshot after a few frames and quits; `--dist=` and `--height=` place the camera;
## `--clip=<name>` and `--frame=<n>` (60 Hz) pose the models paused on that frame; `--yaw=<deg>` turns them.

const MODEL_DIR := "res://assets_ripped/models"
const ANIM_DIR := "res://assets_ripped/anims"
const SPACING := 2.0
const LOOPING := ["stance", "walk"]   # the in-game looping motions (docs/ANIMATION.md)
const FRAME := 1.0 / 60.0

var _turn := true
var _shot := ""
var _frames := 0
var _pivot: Node3D
var _cam: Camera3D
var _dist := 4.5
var _height := 1.0
var _players: Array[AnimationPlayer] = []
var _clips: PackedStringArray = []
var _clip := 0
var _playing := true
var _hud: Label
var _yaw := 0.0
var _start_clip := ""
var _start_frame := -1


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--shot="):
			_shot = a.substr(7)
		elif a.begins_with("--dist="):
			_dist = float(a.substr(7))
		elif a.begins_with("--height="):
			_height = float(a.substr(9))
		elif a.begins_with("--clip="):
			_start_clip = a.substr(7)
		elif a.begins_with("--frame="):
			_start_frame = int(a.substr(8))
		elif a.begins_with("--yaw="):
			_yaw = float(a.substr(6))
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
	var libs := _load_anims()
	var x := -SPACING * (files.size() - 1) / 2.0
	for f in files:
		var scene := load(MODEL_DIR + "/" + f) as PackedScene
		if scene == null:
			push_error("could not load " + f)
			continue
		var m := scene.instantiate() as Node3D
		m.position.x = x
		m.rotation_degrees.y = _yaw
		_pivot.add_child(m)
		_add_player(m, libs)
		var label := Label3D.new()
		label.text = f.get_basename()
		label.position = Vector3(x, -0.15, 0)
		label.pixel_size = 0.002
		add_child(label)
		print("loaded %s" % f)
		x += SPACING
	_build_stage()
	_hud = Label.new()
	_hud.position = Vector2(10, 10)
	add_child(_hud)
	_clips.sort()
	if _start_clip != "" and _start_clip in _clips:
		_clip = _clips.find(_start_clip)
	if _start_frame >= 0:
		_playing = false
		_turn = false
	_play_clip()
	if _start_frame >= 0:
		_seek(_start_frame * FRAME)


## Every AnimationLibrary of ANIM_DIR's files, keyed by file name ("aaron"); the first one's clips are the clip list.
func _load_anims() -> Dictionary:
	var libs := {}
	var dir := DirAccess.open(ANIM_DIR)
	if dir == null:
		return libs
	var files := Array(dir.get_files()).filter(func(f): return f.ends_with(".glb"))
	files.sort()
	for f in files:
		var n := (load(ANIM_DIR + "/" + f) as PackedScene).instantiate()
		var ap := n.find_child("AnimationPlayer", true, false) as AnimationPlayer
		if ap:
			var lib := AnimationLibrary.new()
			for a in ap.get_animation_list():
				var anim := ap.get_animation(a).duplicate() as Animation
				anim.loop_mode = Animation.LOOP_LINEAR if a in LOOPING else Animation.LOOP_NONE
				lib.add_animation(a, anim)
				if libs.is_empty():
					_clips.append(a)
			libs[f.get_basename()] = lib
		n.free()
	return libs


## A player on a rigged model (it has a Skeleton3D) with every animation library; tracks are "Skeleton3D:bone".
func _add_player(m: Node3D, libs: Dictionary) -> void:
	if libs.is_empty() or m.get_node_or_null("Skeleton3D") == null:
		return
	var ap := AnimationPlayer.new()
	m.add_child(ap)
	ap.root_node = NodePath("..")
	for k in libs:
		ap.add_animation_library(k, libs[k])
	_players.append(ap)


func _clip_name() -> String:
	return "" if _clips.is_empty() else _clips[_clip]


func _play_clip() -> void:
	for ap in _players:
		var lib_name: StringName = ap.get_animation_library_list()[0]
		ap.play("%s/%s" % [lib_name, _clip_name()])
		if not _playing:
			ap.pause()


func _seek(t: float) -> void:
	for ap in _players:
		if not ap.has_animation(ap.assigned_animation):
			continue
		var length := ap.get_animation(ap.assigned_animation).length
		ap.seek(clampf(t, 0.0, length), true)


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
	if _hud and not _players.is_empty():
		var ap := _players[0]
		_hud.text = "%s  frame %d / %d  %s   [Tab clip, P play/pause, , . step]" % [_clip_name(),
			roundi(ap.current_animation_position / FRAME), roundi(ap.get_animation(ap.assigned_animation).length / FRAME),
			"playing" if _playing else "paused"]
	_frames += 1
	if _shot != "" and _frames == 10:
		get_viewport().get_texture().get_image().save_png(_shot)
		print("screenshot saved: %s" % _shot)
		get_tree().quit()


func _unhandled_input(event: InputEvent) -> void:
	if not (event is InputEventKey and event.pressed):
		return
	match event.physical_keycode:
		KEY_SPACE:
			_turn = not _turn
		KEY_TAB:
			if not _clips.is_empty():
				_clip = (_clip + (-1 if event.shift_pressed else 1) + _clips.size()) % _clips.size()
				_play_clip()
		KEY_P:
			_playing = not _playing
			for ap in _players:
				if _playing:
					ap.play()
				else:
					ap.pause()
		KEY_COMMA, KEY_PERIOD:
			_playing = false
			for ap in _players:
				ap.pause()
			if not _players.is_empty():
				_seek(_players[0].current_animation_position + (FRAME if event.physical_keycode == KEY_PERIOD else -FRAME))
