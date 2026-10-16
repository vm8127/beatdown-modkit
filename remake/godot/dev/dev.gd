extends Node
## Developer state shared by everything (autoload "Dev"): pause, frame step, slow motion,
## hitbox drawing, and the dev keys (F1-F7, Tab).
##
## Game logic never reads real time. Every physics frame (60 per second) Dev decides
## whether the game advances one frame (`tick`); fighters skip their logic when it's false.
## That gives pause, single-frame stepping and slow motion for free, and keeps the logic
## deterministic: frame 120 is always the same, whatever the frame rate.

const SLOW_SCALES := [1.0, 0.5, 0.25, 0.1]

var tick := true          ## true when this physics frame runs game logic
var frame := 0            ## game frames run so far
var paused := false
var time_scale := 1.0
var show_boxes := true
var show_hurtboxes := true  ## screenshots of the model turn these off (the hit spheres stay)

var _step := false
var _acc := 0.0
var _slow_index := 0


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	process_physics_priority = -1000   # run before every fighter
	_setup_input()


func _physics_process(_delta: float) -> void:
	if paused:
		tick = _step
		_step = false
	else:
		_acc += time_scale
		tick = _acc >= 1.0
		if tick:
			_acc -= 1.0
	if tick:
		frame += 1


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("dev_pause"):
		paused = not paused
	elif event.is_action_pressed("dev_step"):
		paused = true
		_step = true
	elif event.is_action_pressed("dev_slow"):
		_slow_index = (_slow_index + 1) % SLOW_SCALES.size()
		time_scale = SLOW_SCALES[_slow_index]
	elif event.is_action_pressed("dev_boxes"):
		show_boxes = not show_boxes


func status_text() -> String:
	var s := "frame %d" % frame
	if paused:
		s += "   [PAUSED: F4 steps one frame]"
	if time_scale < 1.0:
		s += "   [slow x%s]" % time_scale
	return s


# Dev keys only. The game's controls (move, attacks, camera, pads, rebinding) are the autoload
# GameInput (game/input/game_input.gd), which loads before this one.
func _setup_input() -> void:
	_bind("dev_boxes", [KEY_F1])
	_bind("dev_slow", [KEY_F2])
	_bind("dev_pause", [KEY_F3])
	_bind("dev_step", [KEY_F4])
	_bind("dev_spawn", [KEY_F5])
	_bind("dev_dummy_mode", [KEY_F6])
	_bind("dev_reset", [KEY_F7])
	_bind("dev_overlay", [KEY_TAB])


func _bind(action: String, keys: Array, mouse: Array = [], joy: Array = [], axes: Array = []) -> void:
	if not InputMap.has_action(action):
		InputMap.add_action(action, 0.25)
	for k in keys:
		var e := InputEventKey.new()
		e.physical_keycode = k
		InputMap.action_add_event(action, e)
	for m in mouse:
		var e := InputEventMouseButton.new()
		e.button_index = m
		InputMap.action_add_event(action, e)
	for j in joy:
		var e := InputEventJoypadButton.new()
		e.button_index = j
		InputMap.action_add_event(action, e)
	for a in axes:
		var e := InputEventJoypadMotion.new()
		e.axis = a[0]
		e.axis_value = a[1]
		InputMap.action_add_event(action, e)
