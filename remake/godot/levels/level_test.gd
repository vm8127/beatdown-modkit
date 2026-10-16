extends Node
## Level test (`-- --test` on levels/subway.tscn; exit code 0 = pass). Checks, in the subway and DOWNTOWN STREET:
## - the area has its props (PB placements), battle spots and doors;
## - walking into every wall direction keeps the player inside (wall bounds + floor under them);
## - the camera is never behind a wall: a ray from the player's head to the camera hits no world collision
##   for more than CAM_STREAK frames in a row (the spring arm smooths a few frames);
## - walking up to a street fighter starts a fight at a battle spot and blows land;
## - every door between the subway and Downtown works both ways and lands at the right arrival point inside.

const CAM_STREAK := 6

var level: Level
var _fails: Array[String] = []
var _cam_streak := 0
var _cam_worst := 0
var _cam_frames := 0


func _ready() -> void:
	_run.call_deferred()


func _check(ok: bool, what: String) -> void:
	if not ok:
		print("  FAIL  " + what)
	if not ok:
		_fails.append(what)


func _frames(n: int) -> void:
	for i in n:
		await get_tree().physics_frame
		_camera_check()


func _camera_check() -> void:
	if level._fade != 0:
		_cam_streak = 0
		return
	var p := level.player.global_position + Vector3(0, 1.5, 0)
	var c := level.cam.camera.global_position
	var q := PhysicsRayQueryParameters3D.create(p, c, GameArea.LAYER_WORLD)
	var hit := level.get_world_3d().direct_space_state.intersect_ray(q)
	_cam_frames += 1
	if hit.is_empty():
		_cam_streak = 0
	else:
		_cam_streak += 1
		_cam_worst = maxi(_cam_worst, _cam_streak)


## Holds "forward" with the camera turned to the game angle `angle_deg` for `n` frames (`until_fight`: stop
## when a fight starts).
func _walk(angle_deg: float, n: int, until_fight := false) -> void:
	level.cam.yaw = GameArea.yaw_from_game(angle_deg)
	Input.action_press("move_forward")
	for i in n:
		await _frames(1)
		if until_fight and not level.fight.is_empty():
			break
		if not level.area.is_inside(level.player.global_position) and level._fade == 0:
			_check(false, "player left the area at %s" % level.player.global_position)
			break
	Input.action_release("move_forward")


func _run() -> void:
	await _frames(10)
	var a := level.area
	print("level test: %s" % a.info["name"])
	_check(a.area_id == 5, "starts in the subway (area 5)")
	_check(a.props_placed == 18, "subway: 18 props placed (PB), got %d" % a.props_placed)
	_check(a.battle_spots.size() == 4, "subway: 4 battle spots")
	_check(a.doors.size() == 2, "subway: 2 doors")
	_check(a.get_node("Markers").get_child_count() >= 6, "subway: battle spot and door markers")
	_check(level.dummies.size() >= 2, "subway: street fighters at the spots (3 spots, none by the way in), got %d" % level.dummies.size())
	_check(a.is_inside(level.player.global_position), "spawned inside")
	# Walls: back (-z = 180), front (+z = 0), ends (-x = -90, +x = 90); park the street fighters out of the way
	for d in level.dummies:
		d.global_position += Vector3(1000, 0, 0)
		d.set_physics_process(false)
	for leg in [180.0, 0.0, -90.0, 90.0]:
		await _walk(leg, 300)
		print("    walk %.0f: stopped at %s" % [leg, level.player.global_position])
	_check(a.is_inside(level.player.global_position), "walls hold the player in")
	await _fight_test()
	await _door_test()
	_check(_cam_worst <= CAM_STREAK, "camera never behind a wall (worst streak %d frames of %d)" % [_cam_worst, _cam_frames])
	print("level test: %s" % ("PASS" if _fails.is_empty() else "FAIL (%d)" % _fails.size()))
	get_tree().quit(0 if _fails.is_empty() else 1)


func _fight_test() -> void:
	level.enter_area(5, 0, -1)
	await _frames(5)
	var d: Fighter = level.dummies[0]
	var to := d.global_position - level.player.global_position
	await _walk(rad_to_deg(atan2(to.x, to.z)), 200, true)
	var started := not level.fight.is_empty()
	_check(started, "walking up to a street fighter starts a fight")
	if not started:
		return
	var s: Dictionary = level.area.battle_spots[level.fight["spot"]]
	_check(level.player.global_position.distance_to(s["pos"]) < 0.3, "the player stands on battle spot %d" % level.fight["spot"])
	var foe: Fighter = level.fight["dummy"]
	var brain := level.player.brain as PlayerBrain
	for i in 12:
		brain.press("P", "")
		await _frames(25)
	_check(foe.hp < foe.max_hp or level.player.hp < level.player.max_hp,
		"blows landed (opponent %d/%d, player %d/%d)" % [foe.hp, foe.max_hp, level.player.hp, level.player.max_hp])
	level._end_fight()


## Uses `door` of the current area by walking into it from its own arrival point and waits for the new area.
func _through(door: Dictionary) -> bool:
	var arr: Dictionary = door["arrival"]
	var p: Array = arr["pos"]
	level.place(level.player, Vector3(p[0], p[1], p[2]), float(door["into_deg"]))
	level.cam.yaw = level.player.rotation.y
	level.cam.snap_to_target()
	var before := level.transitions
	level.cam.yaw = GameArea.yaw_from_game(float(door["into_deg"]))
	Input.action_press("move_forward")
	for i in 240:
		await _frames(1)
		if level.transitions > before:
			break
	Input.action_release("move_forward")
	await _frames(25)   # the fade in
	return level.transitions > before


func _door_test() -> void:
	# subway door n -> Downtown entrance e -> back through Downtown door e -> subway entrance n
	for n in [1, 2]:
		level.enter_area(5, 0, -1)
		await _frames(3)
		var d: Dictionary = level.area.doors[n - 1]
		var e := int(d["entrance"])
		var ok := await _through(d)
		_check(ok and level.area_id == 1, "subway door %d (tag %d) -> DOWNTOWN STREET" % [n, int(d["bonetag"])])
		if not ok or level.area_id != 1:
			continue
		var want: Dictionary = level.area.doors[e - 1]
		var wp: Array = want["arrival"]["pos"]
		var at := level.player.global_position
		_check(at.distance_to(Vector3(wp[0], wp[1], wp[2])) < 0.5, "  arrives at Downtown entrance %d (door %d) %s" % [e, int(want["bonetag"]), at])
		_check(level.area.is_inside(at), "  inside Downtown's walls")
		_check(level.area.door_at(at).is_empty() or not GameArea.facing_door(level.area.door_at(at), level.player.forward()), "  not facing back into the door")
		await _frames(30)
		_check(level.area_id == 1, "  stays in Downtown while standing still")
		var back_to := int(want["entrance"])
		ok = await _through(want)
		_check(ok and level.area_id == 5, "Downtown door %d (tag %d) -> subway" % [e, int(want["bonetag"])])
		if ok and level.area_id == 5:
			var bp: Array = level.area.doors[back_to - 1]["arrival"]["pos"]
			at = level.player.global_position
			_check(back_to == n and at.distance_to(Vector3(bp[0], bp[1], bp[2])) < 0.5, "  back at subway entrance %d %s" % [back_to, at])
			_check(level.area.is_inside(at), "  inside the subway's walls")
	# Walk Downtown a little: the street in four directions
	level.enter_area(1, 0, -1)
	await _frames(5)
	_check(level.area.props_placed > 30, "Downtown: props placed (%d)" % level.area.props_placed)
	_check(level.area.battle_spots.size() == 11 and level.area.doors.size() == 7, "Downtown: 11 battle spots, 7 doors")
	for d in level.dummies:
		d.global_position += Vector3(1000, 0, 0)
		d.set_physics_process(false)
	for leg in [0.0, 90.0, 180.0, -90.0]:
		await _walk(leg, 240)
	_check(level.area.is_inside(level.player.global_position), "Downtown: walls hold the player in")
