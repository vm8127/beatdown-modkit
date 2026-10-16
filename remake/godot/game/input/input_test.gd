extends Node
## Headless check of the controls (input_test.tscn = the dev arena + this node): injects joypad,
## keyboard and stick events with Input.parse_input_event and checks the input codes PlayerBrain
## buffers and the moves the player starts. Exit code 0 = pass.
##
##   godot --headless --path remake/godot res://game/input/input_test.tscn
##
## Checks: the default TYPE 1 map (□ P, △ K, × guard, ○ special, L1 run, R1 grab + interact, L2/R2
## items, R3 taunt); □ / △ / ○ / J start P / K / special; × held guards; stick toward / away from the
## opponent + □ = →P / ←P; → n → + □ within 19 frames = →→P, too slow = →P; TYPE 2 makes × kick;
## rebinding punch to L3; the dead zone and full tilt; glyph names for PlayStation / Xbox / keys;
## a landed hit rumbles. Never saves user://controls.cfg.

var arena: Node
var _errors: Array[String] = []
var _checks := 0


func _ready() -> void:
	arena = get_parent()
	process_physics_priority = -500   # after Dev (-1000), before the fighters: sees fresh presses
	GameInput.reset_defaults()        # the user's own config must not change the test
	_run.call_deferred()


func _check(ok: bool, what: String) -> void:
	_checks += 1
	if not ok:
		print("FAIL  " + what)
	if not ok:
		_errors.append(what)


func _frames(n: int) -> void:
	for i in n:
		await get_tree().physics_frame


func _player() -> Fighter:
	return arena.player


func _dummy() -> Fighter:
	for n in get_tree().get_nodes_in_group("fighters"):
		if (n as Fighter).display_name == "Dummy 1":
			return n
	return null


func _brain() -> PlayerBrain:
	return _player().brain as PlayerBrain


func _button(index: JoyButton, pressed: bool) -> void:
	var e := InputEventJoypadButton.new()
	e.device = 0
	e.button_index = index
	e.pressed = pressed
	e.pressure = 1.0 if pressed else 0.0
	Input.parse_input_event(e)


func _axis(axis: JoyAxis, value: float) -> void:
	var e := InputEventJoypadMotion.new()
	e.device = 0
	e.axis = axis
	e.axis_value = value
	Input.parse_input_event(e)


func _stick(v: Vector2) -> void:
	_axis(JOY_AXIS_LEFT_X, v.x)
	_axis(JOY_AXIS_LEFT_Y, v.y)


func _key(k: Key, pressed: bool) -> void:
	var e := InputEventKey.new()
	e.physical_keycode = k
	e.keycode = k
	e.pressed = pressed
	Input.parse_input_event(e)


## The stick vector that walks the player toward (sign 1) or away from (-1) Dummy 1 with the
## camera's yaw (PlayerBrain.move_dir turns the stick by the camera).
func _stick_toward(sign: float) -> Vector2:
	var w := _dummy().global_position - _player().global_position
	w.y = 0
	w = w.normalized() * sign
	var cam: ThirdPersonCamera = _brain().camera
	var yaw := cam.yaw if cam else 0.0
	var v := Basis(Vector3.UP, -yaw) * w
	return Vector2(v.x, v.z)


## Puts both fighters back: player 1.2 m in front of Dummy 1, both free, full HP.
func _reset_fighters() -> void:
	var p := _player()
	var d := _dummy()
	for i in 400:
		var busy := false
		for f in [p, d]:
			busy = busy or f.state not in [Fighter.State.IDLE, Fighter.State.MOVE, Fighter.State.GUARD]
		if not busy:
			break
		await _frames(1)
	d.global_position = Vector3(0, 0, 1)   # where the arena puts it: 1.2 m apart, like the smoke test
	d.velocity = Vector3.ZERO
	d.hp = d.max_hp
	p.global_position = Vector3(0, 0, 2.2)
	p.velocity = Vector3.ZERO
	p.rotation.y = 0.0
	_brain().presses.clear()
	await _frames(3)


## Presses `index` (optionally after holding the stick at `stick`), checks the buffered code is
## `want` and that the move the style has for it starts. Releases everything afterwards.
func _press_expect(index: JoyButton, want: String, what: String, stick := Vector2.ZERO) -> void:
	await _reset_fighters()
	if stick != Vector2.ZERO:
		_stick(stick)
		await _frames(3)
	_button(index, true)
	var codes := await _codes()
	_check(want in codes, "%s: buffered %s (want %s)" % [what, codes, want])
	await _expect_move(want, what)
	_button(index, false)
	_stick(Vector2.ZERO)
	await _frames(2)


## The codes PlayerBrain buffered within 6 frames (parse_input_event reaches the brain on the next
## frame or the one after, depending on where in the frame it was called), or already used to start
## a move this frame.
func _codes() -> Array:
	var out := []
	for i in 6:
		await _frames(1)
		for p in _brain().presses:
			if not p["code"] in out:
				out.append(p["code"])
		var f := _player()   # a press the fighter already used: the history of the move it started
		if f.state == Fighter.State.ATTACK and f.state_frame <= 6 and f.history.size() == 1 and not f.history[0] in out:
			out.append(f.history[0])
		if not out.is_empty():
			break
	return out


func _expect_move(code: String, what: String) -> void:
	var found: Array = _player().move_set.match_single(code)
	await _frames(2)
	var p := _player()
	if found.is_empty():
		_check(p.state != Fighter.State.ATTACK, "%s: the style has no move for %s, none started" % [what, code])
		return
	var m: MoveData = found[0]
	var started := p.state == Fighter.State.ATTACK and p.move == m
	_check(started, "%s: started %s (%s), history %s" % [what, m.move_name, p.move_id, p.history])


func _has_joy(action: String, button: JoyButton) -> bool:
	for e in InputMap.action_get_events(action):
		if e is InputEventJoypadButton and e.button_index == button:
			return true
	return false


func _has_axis(action: String, axis: JoyAxis, value: float) -> bool:
	for e in InputMap.action_get_events(action):
		if e is InputEventJoypadMotion and e.axis == axis and signf(e.axis_value) == signf(value):
			return true
	return false


func _run() -> void:
	for n in get_tree().get_nodes_in_group("fighters"):
		if n.brain is DummyBrain:
			n.brain.mode = DummyBrain.Mode.STAND
	await _frames(5)
	print("style: %s" % _player().move_set.style_name)

	# The map: TYPE 1 on Godot's positional buttons.
	_check(_has_joy("attack_p", JOY_BUTTON_X) and _has_joy("attack_k", JOY_BUTTON_Y)
		and _has_joy("guard", JOY_BUTTON_A) and _has_joy("special", JOY_BUTTON_B), "TYPE 1: □ P, △ K, × G, ○ S")
	_check(_has_joy("run", JOY_BUTTON_LEFT_SHOULDER) and _has_joy("grab", JOY_BUTTON_RIGHT_SHOULDER)
		and _has_joy("interact", JOY_BUTTON_RIGHT_SHOULDER) and _has_joy("taunt", JOY_BUTTON_RIGHT_STICK)
		and _has_axis("item_1", JOY_AXIS_TRIGGER_LEFT, 1) and _has_axis("item_2", JOY_AXIS_TRIGGER_RIGHT, 1)
		and _has_joy("menu", JOY_BUTTON_START), "shoulders: L1 run, R1 grab + interact, L2/R2 items, R3 taunt, START menu")

	# Face buttons -> codes -> moves.
	await _press_expect(JOY_BUTTON_X, "P", "□")
	_check(GameInput.device_kind() != "keyboard", "a pad press switches the glyphs to a pad (%s)" % GameInput.device_kind())
	await _press_expect(JOY_BUTTON_Y, "K", "△")
	await _press_expect(JOY_BUTTON_B, "#46", "○ (special)")
	await _press_expect(JOY_BUTTON_RIGHT_SHOULDER, "#1E", "R1 (grab)")

	# Directions relative to the opponent.
	await _press_expect(JOY_BUTTON_X, "→P", "stick toward + □", _stick_toward(1.0))
	await _press_expect(JOY_BUTTON_Y, "←K", "stick away + △", _stick_toward(-1.0))

	# →→P (two steps within 19 frames), and too slow.
	for slow in [false, true]:
		await _reset_fighters()
		var t := _stick_toward(1.0)
		_stick(t)
		await _frames(3)
		_stick(Vector2.ZERO)
		await _frames(3)
		_stick(t)
		await _frames(25 if slow else 3)
		_button(JOY_BUTTON_X, true)
		var codes := await _codes()
		var want := "→P" if slow else "→→P"
		_check(want in codes, "→ n → + □ %s: buffered %s (want %s)" % ["after 25 frames" if slow else "at once", codes, want])
		await _expect_move(want, "→→P" if not slow else "late →→P")
		_button(JOY_BUTTON_X, false)
		_stick(Vector2.ZERO)
		await _frames(2)

	# × held guards, released stops.
	await _reset_fighters()
	_button(JOY_BUTTON_A, true)
	await _frames(4)
	_check(_player().state == Fighter.State.GUARD, "× held: GUARD (%s)" % Fighter.State.keys()[_player().state])
	_button(JOY_BUTTON_A, false)
	await _frames(4)
	_check(_player().state != Fighter.State.GUARD, "× released: guard ends")

	# Keyboard still works.
	await _reset_fighters()
	_key(KEY_J, true)
	var kcodes := await _codes()
	_check("P" in kcodes and GameInput.device_kind() == "keyboard", "J key: P, glyphs back to keyboard")
	_key(KEY_J, false)
	await _expect_move("P", "J")

	# A landed hit rumbles (kind 0).
	await _reset_fighters()
	var before := GameInput.rumble_count
	_button(JOY_BUTTON_X, true)
	await _codes()
	_button(JOY_BUTTON_X, false)
	for i in 60:
		await _frames(1)
		if _dummy().hp < _dummy().max_hp:
			break
	await _frames(2)
	_check(_dummy().hp < _dummy().max_hp and GameInput.rumble_count > before,
		"□ hit lands (dummy hp %d/%d, %s): rumble %d -> %d" % [_dummy().hp, _dummy().max_hp,
		GameInput.device_kind(), before, GameInput.rumble_count])

	# TYPE 2 (□ P, × K, △ G, ○ S): × kicks.
	GameInput.set_layout(1)
	await _press_expect(JOY_BUTTON_A, "K", "TYPE 2 ×")
	GameInput.set_layout(0)

	# Rebinding punch to L3: L3 punches, □ no longer does.
	var l3 := InputEventJoypadButton.new()
	l3.button_index = JOY_BUTTON_LEFT_STICK
	l3.pressed = true
	GameInput.rebind("attack_p", l3)
	await _press_expect(JOY_BUTTON_LEFT_STICK, "P", "punch rebound to L3")
	await _reset_fighters()
	_button(JOY_BUTTON_X, true)
	await _codes()
	_check(_brain().presses.is_empty(), "□ after the rebind: no press (%s)" % _brain().buffer_text())
	_button(JOY_BUTTON_X, false)
	GameInput.reset_defaults()

	# Dead zone (0.2) and full tilt.
	_stick(Vector2(0.15, 0))
	await _frames(2)
	_check(GameInput.move_vector() == Vector2.ZERO, "stick 0.15: inside the dead zone")
	_stick(Vector2(0.6, 0))
	await _frames(2)
	var mv := GameInput.move_vector()
	_check(mv.x > 0.4 and mv.x < 0.6 and not GameInput.full_tilt(), "stick 0.6: rescaled to %.2f, walk" % mv.x)
	_stick(Vector2(1.0, 0))
	await _frames(2)
	_check(GameInput.full_tilt() and _brain().wants_run(_player()), "stick 1.0: full tilt = run")
	_stick(Vector2.ZERO)

	# Glyphs.
	var ps: String = GameInput.button_for("attack_p", "playstation")["label"]
	var xb: String = GameInput.button_for("attack_p", "xbox")["label"]
	var kb: String = GameInput.button_for("attack_p", "keyboard")["label"]
	_check(ps == "□" and xb == "X" and kb == "J", "punch glyph: PS %s, Xbox %s, keys %s" % [ps, xb, kb])
	var g := GameInput.text_button("btn:guard_on", "xbox")
	var i4 := GameInput.text_button("icon:4", "playstation")
	var i1 := GameInput.text_button("icon:1", "xbox")
	_check(g["button"] == "cross" and g["label"] == "A" and i4["label"] == "R1" and i1["label"] == "LB",
		"text tokens: btn:guard_on %s, icon:4 %s, icon:1 %s" % [g["label"], i4["label"], i1["label"]])

	print("RESULT input test: %d checks, %d failed %s -> %s" % [_checks, _errors.size(), _errors, "PASS" if _errors.is_empty() else "FAIL"])
	get_tree().quit(0 if _errors.is_empty() else 1)
