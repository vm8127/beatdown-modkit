extends Control
## The controls screen (controls_menu.tscn, F8 anywhere): CONTROL CONFIG TYPE 1-6, vibration,
## stick dead zone, camera X / Y reverse, and rebinding: pick an action's keyboard or pad slot and
## press the new key / button. Pauses the game while open; saves to user://controls.cfg on close.

const LISTEN_DELAY := 0.25   ## seconds before a slot listens, so the press that opened it isn't taken

@onready var _layout: OptionButton = %Layout
@onready var _vibration: CheckBox = %Vibration
@onready var _deadzone: HSlider = %Deadzone
@onready var _deadzone_label: Label = %DeadzoneValue
@onready var _invert_x: CheckBox = %InvertX
@onready var _invert_y: CheckBox = %InvertY
@onready var _rows: GridContainer = %Rows
@onready var _hint: Label = %Hint

var _listen_action := ""
var _listen_pad := false
var _listen_at := 0.0
var _was_paused := false
var _was_mouse := Input.MOUSE_MODE_VISIBLE


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	_was_paused = Dev.paused
	Dev.paused = true
	_was_mouse = Input.mouse_mode
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	for i in GameInput.LAYOUTS.size():
		var l: Array = GameInput.LAYOUTS[i]
		_layout.add_item("TYPE %d   P %s  K %s  G %s  S %s" % [i + 1, GameInput.PS_NAMES[l[0]],
			GameInput.PS_NAMES[l[1]], GameInput.PS_NAMES[l[2]], GameInput.PS_NAMES[l[3]]])
	_layout.item_selected.connect(func(i: int) -> void: GameInput.set_layout(i))
	_vibration.toggled.connect(func(on: bool) -> void: GameInput.vibration = on)
	_deadzone.value_changed.connect(_on_deadzone)
	_invert_x.toggled.connect(func(on: bool) -> void: GameInput.invert_x = on)
	_invert_y.toggled.connect(func(on: bool) -> void: GameInput.invert_y = on)
	%Reset.pressed.connect(func() -> void:
		GameInput.reset_defaults()
		_refresh())
	%Close.pressed.connect(close)
	GameInput.bindings_changed.connect(_refresh)
	GameInput.device_changed.connect(func(_k: String) -> void: _refresh())
	_refresh()
	_layout.grab_focus()


func _exit_tree() -> void:
	Dev.paused = _was_paused
	Input.mouse_mode = _was_mouse


func close() -> void:
	GameInput.save_config()
	GameInput.toggle_controls_menu()


func _on_deadzone(v: float) -> void:
	GameInput.deadzone = v
	_deadzone_label.text = "%.2f" % v


func _refresh() -> void:
	_layout.select(GameInput.layout)
	_vibration.set_pressed_no_signal(GameInput.vibration)
	_deadzone.set_value_no_signal(GameInput.deadzone)
	_deadzone_label.text = "%.2f" % GameInput.deadzone
	_invert_x.set_pressed_no_signal(GameInput.invert_x)
	_invert_y.set_pressed_no_signal(GameInput.invert_y)
	var focused := get_viewport().gui_get_focus_owner()
	var focus_name := focused.name if focused and _rows.is_ancestor_of(focused) else ""
	for c in _rows.get_children():
		c.queue_free()
	var pad_kind := GameInput.device_kind() if GameInput.using_pad() else "playstation"
	for action: String in GameInput.ACTIONS:
		if action in GameInput.CAM:
			continue
		var label := Label.new()
		label.text = GameInput.ACTIONS[action][0]
		_rows.add_child(label)
		for pad in [false, true]:
			var b := Button.new()
			b.name = "%s_%s" % [action, "pad" if pad else "key"]
			b.custom_minimum_size = Vector2(150, 0)
			var info := GameInput.button_for(action, pad_kind if pad else "keyboard")
			b.text = "..." if action == _listen_action and pad == _listen_pad else info["label"]
			b.pressed.connect(_listen.bind(action, pad))
			_rows.add_child(b)
			if b.name == focus_name:
				b.call_deferred("grab_focus")
	_hint.text = "Device: %s.  Click a slot, then press the new key or pad button (Esc cancels).  F8 closes." % GameInput.device_kind()


func _listen(action: String, pad: bool) -> void:
	_listen_action = action
	_listen_pad = pad
	_listen_at = Time.get_ticks_msec() / 1000.0 + LISTEN_DELAY
	_refresh()


func _input(event: InputEvent) -> void:
	if _listen_action == "":
		return
	if Time.get_ticks_msec() / 1000.0 < _listen_at:
		return
	var take := false
	if event is InputEventKey and event.pressed and not event.echo:
		if event.physical_keycode == KEY_ESCAPE:
			_listen_action = ""
			_refresh()
			get_viewport().set_input_as_handled()
			return
		take = not _listen_pad
	elif event is InputEventMouseButton and event.pressed:
		take = not _listen_pad
	elif event is InputEventJoypadButton and event.pressed:
		take = _listen_pad
	elif event is InputEventJoypadMotion and absf(event.axis_value) > 0.6:
		take = _listen_pad
	if take:
		var action := _listen_action
		_listen_action = ""
		GameInput.rebind(action, event)
		get_viewport().set_input_as_handled()
