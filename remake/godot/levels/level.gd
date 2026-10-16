class_name Level
extends Node3D
## A playable level: one area from the disc (GameArea), the player, the third-person camera, street
## fighters (training dummies for now) at the area's battle spots, and the doors between areas.
## subway.tscn starts in the ABANDONED SUBWAY STATION (area 5), downtown.tscn in DOWNTOWN STREET (area 1);
## both are this scene with another start area. remake/README.md, "Levels".
##
## Doors (docs/STAGES.md, "Doors and exits"): stand on a door's zone facing it and press E (pad A), or keep
## walking into it, and the screen fades, the destination area loads and the player stands at the arrival
## point of the destination's door `entrance` (Door_ArrivalPoint), facing away from it. Doors to areas that
## aren't converted yet say so and stay shut.
##
## Fights: walk up to a street fighter and the fight starts like the game's Battle_PlaceFighters: the
## player moves to the nearest battle spot facing its angle, the opponent 2.5 m in front facing back.
##
## Command line (after `--`): `--area=N` and `--entrance=N` (`--from=A`) start elsewhere, `--variant=E` picks
## a FSTAGE variant, `--stage=N` the story stage, `--shot=<file.png>` saves a screenshot and quits
## (`--view=player|overview|door|fight`), `--test` runs levels/level_test.gd (exit code 0 = pass).

const FIGHTER_SCENE := preload("res://game/fighter/fighter.tscn")
const FADE_FRAMES := 20
const WALK_IN_FRAMES := 8       ## frames of walking into a door zone that count as using it
const FIGHT_RANGE := 3.0        ## a fight starts when the player comes this close to a street fighter
const OPPONENT_DISTANCE := 2.5  ## Battle_PlaceFighters: the opponent stands 25 units in front of the spot
const SPAWN_CLEAR := 6.0        ## no street fighter this close to where the player enters (remake choice)

@export var start_area := 5
@export var start_entrance := 0     ## 0 = the area's spawn point (its story-fight battle spot)
@export var story_stage := 2        ## Chapter 2 (g_AreaObjects items of that stage)
@export var max_dummies := 4

var area_id := -1
var previous_area := -1
var fight := {}                     ## {dummy, spot} while a fight is on
var transitions := 0                ## areas entered through doors (tests read it)
var last_message := ""
var dummies: Array[Fighter] = []

var _fade := 0                      ## > 0 fading out, < 0 fading in
var _pending := {}                  ## the door being used
var _walk_in := 0
var _variant := -1
var _from_arg := -1
var _shot := ""
var _view := "player"
var _frames := 0
var _message_frames := 0
var _fight_end := 0

@onready var area: GameArea = $Area
@onready var player: Fighter = $Player
@onready var cam: ThirdPersonCamera = $Camera
@onready var _label: Label = $Overlay/Info
@onready var _prompt: Label = $Overlay/Prompt
@onready var _black: ColorRect = $Overlay/Fade


func _ready() -> void:
	_ensure_interact_action()
	var test := false
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--area="):
			start_area = int(a.substr(7))
		elif a.begins_with("--entrance="):
			start_entrance = int(a.substr(11))
		elif a.begins_with("--from="):
			_from_arg = int(a.substr(7))
		elif a.begins_with("--variant="):
			_variant = int(a.substr(10))
		elif a.begins_with("--stage="):
			story_stage = int(a.substr(8))
		elif a.begins_with("--shot="):
			_shot = a.substr(7)
		elif a.begins_with("--view="):
			_view = a.substr(7)
		elif a == "--test":
			test = true
	area.story_stage = story_stage
	if not GameArea.available(start_area):
		push_error("area %d not converted: run python remake/tools/remake_assets.py ISO remake/godot/assets_ripped" % start_area)
		get_tree().quit(1)
		return
	cam.get_node("Pitch/SpringArm3D").collision_mask = GameArea.LAYER_WORLD | GameArea.LAYER_CAMERA
	enter_area(start_area, start_entrance, _from_arg)
	if test:
		var t: Node = load("res://levels/level_test.gd").new()
		t.level = self
		add_child(t)


## The interact button (doors; later talking): E / pad A. Added here so dev.gd's input map stays as it is.
func _ensure_interact_action() -> void:
	if InputMap.has_action("interact"):
		return
	InputMap.add_action("interact")
	var k := InputEventKey.new()
	k.physical_keycode = KEY_E
	InputMap.action_add_event("interact", k)
	var j := InputEventJoypadButton.new()
	j.button_index = JOY_BUTTON_A
	InputMap.action_add_event("interact", j)


## Loads area `id` and puts the player at `entrance` (0 with no `from` = the spawn point).
func enter_area(id: int, entrance: int, from := -1) -> void:
	_end_fight()
	area.load_area(id, _variant if id == start_area or _variant < 0 else -1)
	previous_area = area_id if from < 0 else from
	area_id = id
	cam.camera.far = maxf(area.far_clip(), 50.0)
	var at: Dictionary
	if entrance <= 0 and from < 0:
		var s: Dictionary = area.info.get("spawn", {"pos": [0, 0, 0], "angle_deg": 0})
		var p: Array = s["pos"]
		at = {"pos": Vector3(p[0], p[1], p[2]), "angle_deg": float(s["angle_deg"])}
	else:
		at = area.arrival(entrance, from)
	place(player, at["pos"], at["angle_deg"])
	cam.yaw = player.rotation.y
	cam.snap_to_target()
	_walk_in = 0
	_spawn_dummies()


## Puts a fighter at `pos` (on the floor) facing the game angle `angle_deg`.
func place(f: Fighter, pos: Vector3, angle_deg: float) -> void:
	var fy = area.floor_height(pos)
	if fy != null:
		pos.y = float(fy)
	f.global_position = pos + Vector3(0, 0.02, 0)
	f.velocity = Vector3.ZERO
	f.rotation.y = GameArea.yaw_from_game(angle_deg)


## One street fighter per battle spot (except the story spot 0, duplicates and spots by the player's way in),
## nearest to the player first,
## standing where Battle_PlaceFighters would put the opponent.
func _spawn_dummies() -> void:
	for d in dummies:
		d.queue_free()
	dummies.clear()
	var spots: Array = []
	for i in range(1 if area.battle_spots.size() > 1 else 0, area.battle_spots.size()):
		var p: Vector3 = area.battle_spots[i]["pos"]
		var dup := false
		for j in spots:
			if (area.battle_spots[j]["pos"] as Vector3).distance_to(p) < 0.5:
				dup = true
		if not dup:
			spots.append(i)
	var ppos := player.global_position
	spots.sort_custom(func(a, b): return (area.battle_spots[a]["pos"] as Vector3).distance_to(ppos) < (area.battle_spots[b]["pos"] as Vector3).distance_to(ppos))
	var placed := 0
	for k in spots.size():
		if placed >= max_dummies:
			break
		var s: Dictionary = area.battle_spots[spots[k]]
		var at: Vector3 = (s["pos"] as Vector3) + GameArea.dir_from_game(s["angle_deg"]) * OPPONENT_DISTANCE
		if Vector2(at.x - ppos.x, at.z - ppos.z).length() < SPAWN_CLEAR:
			continue
		placed += 1
		var f: Fighter = FIGHTER_SCENE.instantiate()
		f.name = "Street%d" % spots[k]
		f.display_name = "Street fighter %d" % spots[k]
		f.model_name = "street_089"
		f.color = Color(0.3, 0.5, 0.85)
		var brain := DummyBrain.new()
		brain.name = "Brain"
		brain.mode = DummyBrain.Mode.STAND
		f.add_child(brain)
		f.set_meta("spot", spots[k])
		$Dummies.add_child(f)
		place(f, at, float(s["angle_deg"]) + 180.0)
		dummies.append(f)


# --- Per frame ---------------------------------------------------------------------------------------

func _physics_process(_delta: float) -> void:
	_frames += 1
	if _message_frames > 0:
		_message_frames -= 1
	if _fade != 0:
		_tick_fade()
		return
	if fight.is_empty():
		_check_fight_start()
	else:
		_tick_fight()
	_check_doors()
	if _shot != "":
		_shot_tick()


func _check_doors() -> void:
	_prompt.text = ""
	if not fight.is_empty():
		_walk_in = 0
		return
	var d := area.door_at(player.global_position)
	if d.is_empty() or not GameArea.facing_door(d, player.forward()):
		_walk_in = 0
		return
	_prompt.text = "E / (A): %s" % d["dest_name"]
	var into := GameArea.dir_from_game(float(d["into_deg"]))
	var pushing := Vector3(player.velocity.x, 0, player.velocity.z).dot(into) > 0.5 or \
		(player.brain as PlayerBrain).move_dir(player).dot(into) > 0.5
	_walk_in = _walk_in + 1 if pushing else 0
	if Input.is_action_just_pressed("interact") or _walk_in >= WALK_IN_FRAMES:
		use_door(d)


## Starts the fade to the door's destination (or says it's shut).
func use_door(d: Dictionary) -> void:
	_walk_in = 0
	var dest := int(d["dest_area"]) if d["dest_area"] != null else -1
	if not GameArea.available(dest):
		_say("%s: not in the remake yet" % d["dest_name"])
		return
	_pending = d
	_fade = 1
	player.set_physics_process(false)


func _tick_fade() -> void:
	if _fade > 0:
		_fade += 1
		_black.color.a = clampf(float(_fade) / FADE_FRAMES, 0, 1)
		if _fade > FADE_FRAMES:
			var d := _pending
			var from := area_id
			enter_area(int(d["dest_area"]), int(d["entrance"]) if d["entrance"] != null else 0, from)
			transitions += 1
			_fade = -FADE_FRAMES
	else:
		_fade += 1
		_black.color.a = clampf(float(-_fade) / FADE_FRAMES, 0, 1)
		if _fade == 0:
			player.set_physics_process(true)
			_pending = {}


func _check_fight_start() -> void:
	for d in dummies:
		var to := d.global_position - player.global_position
		to.y = 0
		if to.length() < FIGHT_RANGE and d.hp > 0:
			start_fight(d)
			return


## Battle_PlaceFighters: the player at the battle spot nearest to them, the opponent in front.
func start_fight(d: Fighter) -> void:
	var si := area.nearest_battle_spot(player.global_position)
	if si < 0:
		return
	var s: Dictionary = area.battle_spots[si]
	place(player, s["pos"], s["angle_deg"])
	place(d, (s["pos"] as Vector3) + GameArea.dir_from_game(s["angle_deg"]) * OPPONENT_DISTANCE, float(s["angle_deg"]) + 180.0)
	d.hp = d.max_hp
	(d.brain as DummyBrain).mode = DummyBrain.Mode.FIGHT
	fight = {"dummy": d, "spot": si, "frame": _frames}
	cam.yaw = player.rotation.y
	_fight_end = 0
	_say("FIGHT! (battle spot %d)" % si)


func _tick_fight() -> void:
	var d: Fighter = fight["dummy"]
	if not is_instance_valid(d):
		fight = {}
		return
	if d.hp <= 0 and _fight_end == 0:
		_fight_end = 120
		_say("K.O.")
	if _fight_end > 0:
		_fight_end -= 1
		if _fight_end == 0:
			_end_fight()
		return
	if d.global_position.distance_to(player.global_position) > 15.0:
		_say("fight abandoned")
		_end_fight()


func _end_fight() -> void:
	if fight.is_empty():
		return
	var d: Fighter = fight["dummy"]
	if is_instance_valid(d):
		(d.brain as DummyBrain).mode = DummyBrain.Mode.STAND
	fight = {}


func _say(s: String) -> void:
	last_message = s
	_message_frames = 150
	print(s)


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed and Input.mouse_mode != Input.MOUSE_MODE_CAPTURED:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	elif event.is_action_pressed("ui_cancel"):
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	elif event.is_action_pressed("dev_reset"):
		enter_area(area_id, 0, -1)
	elif event.is_action_pressed("dev_overlay"):
		_label.visible = not _label.visible
	elif event.is_action_pressed("dev_boxes"):
		area.get_node("Markers").visible = Dev.show_boxes


func _process(_delta: float) -> void:
	var p := player.global_position
	var lines: Array[String] = []
	lines.append("%s (area %d, FSTAGE %d) · story stage %d · fps %d · %s" % [area.info.get("name", "?"), area_id,
		area.entry, story_stage, Engine.get_frames_per_second(), Dev.status_text()])
	lines.append("pos %.2f %.2f %.2f  on floor %s  inside %s" % [p.x, p.y, p.z, player.is_on_floor(), area.is_inside(p)])
	lines.append(player.debug_text())
	if not fight.is_empty():
		var d: Fighter = fight["dummy"]
		lines.append("FIGHT at battle spot %d: %s" % [fight["spot"], d.debug_text()])
	else:
		lines.append("%d street fighters (walk up to one to fight) · %d doors · %d props · %d items" % [dummies.size(),
			area.doors.size(), area.props_placed, area.items_placed.size()])
	if _message_frames > 0:
		lines.append(">> " + last_message)
	lines.append("WASD / stick move · mouse camera · J/K punch/kick · L guard · E use door · F1 markers · F7 back to spawn · Tab hide")
	_label.text = "\n".join(lines)


# --- Screenshots -----------------------------------------------------------------------------------

func _shot_tick() -> void:
	if _view == "fight" and _frames == 5 and not dummies.is_empty():
		start_fight(dummies[0])
	if _frames == (100 if _view == "fight" else 45):
		_take_shot()


func _take_shot() -> void:
	Dev.show_hurtboxes = false
	var b := area.walls_aabb
	match _view:
		"overview":
			var c := b.get_center()
			var span := maxf(b.size.x, b.size.z)
			_shot_camera(c + Vector3(0, span * 0.55, span * 0.75), c)
		"door":
			if not area.doors.is_empty():
				var d: Dictionary = area.doors[0]
				var zb: Dictionary = d["zone_box"]
				var mn: Array = zb["min"]
				var mx: Array = zb["max"]
				var zc := Vector3((mn[0] + mx[0]) * 0.5, mn[1], (mn[2] + mx[2]) * 0.5)
				var out := -GameArea.dir_from_game(float(d["into_deg"]))
				_shot_camera(zc + out * 6.0 + Vector3(0, 2.5, 0), zc + Vector3(0, 1.2, 0))
		"fight":
			var p := player.global_position
			var side := player.global_transform.basis.x
			_shot_camera(p + side * 4.0 + player.forward() * 1.2 + Vector3(0, 1.8, 0), p + player.forward() * 1.25 + Vector3(0, 1.0, 0))
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(_shot)
	print("screenshot saved: %s" % _shot)
	get_tree().quit()


func _shot_camera(from: Vector3, at: Vector3) -> void:
	var c := Camera3D.new()
	add_child(c)
	c.global_position = from
	c.look_at(at)
	c.far = 400.0
	c.current = true
