extends Node
## The game's controls (autoload "GameInput"): the input map, laid out like Beat Down on the PS2
## (docs/CONTROLS.md), on Xbox / PlayStation / Switch pads, keyboard and mouse; the CONTROL CONFIG
## TYPE 1-6 face-button layouts, rebinding saved in user://controls.cfg, analog dead zones,
## vibration like the game's, and which glyphs to show for the device in use.
##
## Pad buttons are Godot's positional ones: South = × (Xbox A), East = ○ (B), West = □ (X),
## North = △ (Y). Default (TYPE 1): □ punch, △ kick, × guard, ○ special, L1 run, R1 grab / use,
## L2 / R2 items, R3 taunt, START menu, SELECT select. Keyboard: WASD, J punch, K kick, L / Space
## guard, I special, Shift run, E grab / use, Q / R items, T taunt; mouse: left punch, right kick.
##
## Other code asks for the actions by name (Input.is_action_pressed("guard")) or uses the helpers
## here: move_vector(), full_tilt(), device_kind(), button_for(action), text_button(token), vibrate(kind).

signal device_changed(kind: String)   ## "keyboard", "playstation", "xbox", "nintendo" or "generic"
signal bindings_changed

const CONFIG_PATH := "user://controls.cfg"
const MOVE := ["move_left", "move_right", "move_forward", "move_back"]
const CAM := ["cam_left", "cam_right", "cam_up", "cam_down"]

## g_PadLayouts (0x005CF7C0): TYPE 1-6 -> the face button of punch, kick, guard, special.
const LAYOUTS := [
	["square", "triangle", "cross", "circle"],
	["square", "cross", "triangle", "circle"],
	["cross", "square", "triangle", "circle"],
	["cross", "circle", "square", "triangle"],
	["triangle", "circle", "square", "cross"],
	["triangle", "cross", "square", "circle"],
]
const LAYOUT_ACTIONS := ["attack_p", "attack_k", "guard", "special"]
const FACE := {"cross": JOY_BUTTON_A, "circle": JOY_BUTTON_B, "square": JOY_BUTTON_X, "triangle": JOY_BUTTON_Y}

## Every game action: [label for the controls screen, default keys, mouse buttons, pad buttons, pad axes].
## A pad button is a JoyButton or a name in FACE; an axis is [JoyAxis, direction].
const ACTIONS := {
	"move_left": ["Move left", [KEY_A, KEY_LEFT], [], [JOY_BUTTON_DPAD_LEFT], [[JOY_AXIS_LEFT_X, -1.0]]],
	"move_right": ["Move right", [KEY_D, KEY_RIGHT], [], [JOY_BUTTON_DPAD_RIGHT], [[JOY_AXIS_LEFT_X, 1.0]]],
	"move_forward": ["Move forward", [KEY_W, KEY_UP], [], [JOY_BUTTON_DPAD_UP], [[JOY_AXIS_LEFT_Y, -1.0]]],
	"move_back": ["Move back", [KEY_S, KEY_DOWN], [], [JOY_BUTTON_DPAD_DOWN], [[JOY_AXIS_LEFT_Y, 1.0]]],
	"cam_left": ["Camera left", [], [], [], [[JOY_AXIS_RIGHT_X, -1.0]]],
	"cam_right": ["Camera right", [], [], [], [[JOY_AXIS_RIGHT_X, 1.0]]],
	"cam_up": ["Camera up", [], [], [], [[JOY_AXIS_RIGHT_Y, -1.0]]],
	"cam_down": ["Camera down", [], [], [], [[JOY_AXIS_RIGHT_Y, 1.0]]],
	"attack_p": ["Punch", [KEY_J], [MOUSE_BUTTON_LEFT], ["square"], []],
	"attack_k": ["Kick", [KEY_K], [MOUSE_BUTTON_RIGHT], ["triangle"], []],
	"guard": ["Guard", [KEY_L, KEY_SPACE], [], ["cross"], []],
	"special": ["Special (Devastator, threaten)", [KEY_I], [MOUSE_BUTTON_MIDDLE], ["circle"], []],
	"run": ["Run / free move (L1)", [KEY_SHIFT], [], [JOY_BUTTON_LEFT_SHOULDER], []],
	"grab": ["Grab, pick up, use, doors (R1)", [KEY_E], [], [JOY_BUTTON_RIGHT_SHOULDER], []],
	"item_1": ["Item 1 (L2)", [KEY_Q], [], [], [[JOY_AXIS_TRIGGER_LEFT, 1.0]]],
	"item_2": ["Item 2 (R2)", [KEY_R], [], [], [[JOY_AXIS_TRIGGER_RIGHT, 1.0]]],
	"taunt": ["Taunt (R3)", [KEY_T], [], [JOY_BUTTON_RIGHT_STICK], []],
	"menu": ["Menu (START)", [KEY_ENTER], [], [JOY_BUTTON_START], []],
	"select": ["Select", [KEY_BACKSPACE], [], [JOY_BUTTON_BACK], []],
	"controls_menu": ["Controls screen", [KEY_F8], [], [], []],
}
## Actions that always share another's bindings: doors (levels/level.gd) use "interact" = grab (R1).
const LINKED := {"interact": "grab"}
## Fighter_Vibrate kinds (g_VibrationStrength / g_VibrationTime): large motor 0-1, seconds.
const VIBRATION := [[64.0 / 255.0, 0.05], [128.0 / 255.0, 0.08], [1.0, 0.09]]

const PS_NAMES := {"cross": "×", "circle": "○", "square": "□", "triangle": "△", "l1": "L1", "r1": "R1",
	"l2": "L2", "r2": "R2", "l3": "L3", "r3": "R3", "start": "START", "select": "SELECT"}
const XBOX_NAMES := {"cross": "A", "circle": "B", "square": "X", "triangle": "Y", "l1": "LB", "r1": "RB",
	"l2": "LT", "r2": "RT", "l3": "LS", "r3": "RS", "start": "Menu", "select": "View"}
const NINTENDO_NAMES := {"cross": "B", "circle": "A", "square": "Y", "triangle": "X", "l1": "L", "r1": "R",
	"l2": "ZL", "r2": "ZR", "l3": "LS", "r3": "RS", "start": "+", "select": "-"}
const DIR_NAMES := {"up": "↑", "down": "↓", "left": "←", "right": "→", "lstick": "L stick", "rstick": "R stick"}
## The game's text icons (docs/CONTROLS.md, "Icons in the text") -> the action they stand for.
const ICON_ACTIONS := {"1": "run", "2": "item_1", "4": "grab", "5": "item_2", "6": "taunt", "alpha": "menu"}

# Options (CONTROL CONFIG). The game's own dead zone is half the stick (docs/CONTROLS.md); modern
# sticks are tighter, so the remake starts at 0.2 (the config file can say 0.5 for the PS2 feel).
var layout := 0                 ## TYPE 1-6 as 0-5
var vibration := true
var deadzone := 0.2             ## radial, rescaled, like Pad_Update
var invert_x := false           ## CAMERA TYPE (X): REVERSE
var invert_y := false           ## CAMERA TYPE (Y): REVERSE
var pad_device := 0             ## the pad that moved last
var rumble_count := 0           ## rumbles started (tests check it; headless pads don't shake)
var _kind := "keyboard"
var _custom := {}               ## action -> {"keys": [...], "pad": [...]} overrides (rebinding)
var _menu: CanvasLayer


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	process_priority = -2000
	load_config()
	apply()
	if Input.get_connected_joypads().size() > 0:
		pad_device = Input.get_connected_joypads()[0]
	Input.joy_connection_changed.connect(_on_joy_connection)


func _input(event: InputEvent) -> void:
	var kind := _kind
	if event is InputEventJoypadButton or (event is InputEventJoypadMotion and absf(event.axis_value) > 0.5):
		pad_device = event.device
		kind = pad_kind(event.device)
	elif event is InputEventKey or event is InputEventMouseButton:
		kind = "keyboard"
	if kind != _kind:
		_kind = kind
		device_changed.emit(kind)
	if event.is_action_pressed("controls_menu"):
		toggle_controls_menu()


func _on_joy_connection(device: int, connected: bool) -> void:
	if connected:
		pad_device = device
	elif device == pad_device and _kind != "keyboard":
		_kind = "keyboard"
		device_changed.emit(_kind)


# --- reading --------------------------------------------------------------------------------

## The movement stick (or WASD / d-pad), camera-free: x right, y down, length 0-1 with the radial
## dead zone rescaled away (so 0 just past the dead zone, 1 at full tilt).
func move_vector() -> Vector2:
	return Input.get_vector("move_left", "move_right", "move_forward", "move_back", deadzone)


## Stick pushed all the way: the game runs at full tilt (Fighter_TaskWalk: > 0.998 after its rescale).
func full_tilt() -> bool:
	return move_vector().length() > 0.95


func camera_vector() -> Vector2:
	var v := Input.get_vector("cam_left", "cam_right", "cam_up", "cam_down", deadzone)
	return Vector2(-v.x if invert_x else v.x, -v.y if invert_y else v.y)


## "keyboard" or the kind of pad used last.
func device_kind() -> String:
	return _kind


func using_pad() -> bool:
	return _kind != "keyboard"


## A pad's glyph family from its name (SDL names: "PS4 Controller", "Xbox Series Controller"...).
static func pad_kind(device: int) -> String:
	var n := Input.get_joy_name(device).to_lower()
	for k in ["ps3", "ps4", "ps5", "playstation", "dualshock", "dualsense", "sony"]:
		if k in n:
			return "playstation"
	for k in ["xbox", "xinput", "x-box", "microsoft"]:
		if k in n:
			return "xbox"
	for k in ["nintendo", "switch", "pro controller", "joy-con"]:
		if k in n:
			return "nintendo"
	return "generic"   # shown with Xbox names (SDL's standard layout)


# --- glyphs ---------------------------------------------------------------------------------

## The physical control of `action` on the device in use: {"set": device kind, "button": canonical
## PS2 name ("square", "l1", "r2", "up", "lstick"...) or a key's name, "label": text to print}.
## For the HUD's icons: draw `button` from the `set`'s icon sheet, or print `label`.
func button_for(action: String, kind := "") -> Dictionary:
	if kind == "":
		kind = _kind
	action = LINKED.get(action, action)
	if not InputMap.has_action(action):
		return {"set": kind, "button": "", "label": "?"}
	var events := InputMap.action_get_events(action)
	if kind == "keyboard":
		for e in events:
			if e is InputEventKey:
				var s := OS.get_keycode_string(e.physical_keycode)
				return {"set": kind, "button": s, "label": s}
		for e in events:
			if e is InputEventMouseButton:
				var s: String = ["", "LMB", "RMB", "MMB"][e.button_index] if e.button_index <= 3 else "Mouse %d" % e.button_index
				return {"set": kind, "button": s, "label": s}
		return {"set": kind, "button": "", "label": "-"}
	for e in events:
		var b := pad_button_name(e)
		if b != "":
			return {"set": kind, "button": b, "label": glyph_label(b, kind)}
	return {"set": kind, "button": "", "label": "-"}


## GameText's tokens ("btn:punch", "btn:guard_on", "btn:circle", "icon:4", "icon:alpha") -> button_for.
## The layout tokens follow the bindings; fixed face glyphs (btn:circle) map through the pad family.
func text_button(token: String, kind := "") -> Dictionary:
	if kind == "":
		kind = _kind
	var t := token.trim_suffix("_on")
	var name := t.get_slice(":", 1)
	if t.begins_with("btn:"):
		var act: String = {"punch": "attack_p", "kick": "attack_k", "guard": "guard", "special": "special"}.get(name, "")
		if act != "":
			return button_for(act, kind)
		if FACE.has(name):
			if kind == "keyboard":
				kind = "playstation"
			return {"set": kind, "button": name, "label": glyph_label(name, kind)}
	elif t.begins_with("icon:") and ICON_ACTIONS.has(name):
		return button_for(ICON_ACTIONS[name], kind)
	return {"set": kind, "button": "", "label": name}


## Canonical PS2 name of a pad event ("" for keys, mouse).
static func pad_button_name(e: InputEvent) -> String:
	if e is InputEventJoypadButton:
		match e.button_index:
			JOY_BUTTON_A: return "cross"
			JOY_BUTTON_B: return "circle"
			JOY_BUTTON_X: return "square"
			JOY_BUTTON_Y: return "triangle"
			JOY_BUTTON_LEFT_SHOULDER: return "l1"
			JOY_BUTTON_RIGHT_SHOULDER: return "r1"
			JOY_BUTTON_LEFT_STICK: return "l3"
			JOY_BUTTON_RIGHT_STICK: return "r3"
			JOY_BUTTON_START: return "start"
			JOY_BUTTON_BACK: return "select"
			JOY_BUTTON_DPAD_UP: return "up"
			JOY_BUTTON_DPAD_DOWN: return "down"
			JOY_BUTTON_DPAD_LEFT: return "left"
			JOY_BUTTON_DPAD_RIGHT: return "right"
		return "button %d" % e.button_index
	if e is InputEventJoypadMotion:
		match e.axis:
			JOY_AXIS_TRIGGER_LEFT: return "l2"
			JOY_AXIS_TRIGGER_RIGHT: return "r2"
			JOY_AXIS_LEFT_X, JOY_AXIS_LEFT_Y: return "lstick"
			JOY_AXIS_RIGHT_X, JOY_AXIS_RIGHT_Y: return "rstick"
		return "axis %d" % e.axis
	return ""


static func glyph_label(button: String, kind: String) -> String:
	if DIR_NAMES.has(button):
		return DIR_NAMES[button]
	var names: Dictionary = PS_NAMES
	if kind == "xbox" or kind == "generic":
		names = XBOX_NAMES
	elif kind == "nintendo":
		names = NINTENDO_NAMES
	return names.get(button, button)


# --- vibration ------------------------------------------------------------------------------

## Fighter_Vibrate: kind 0 = a hit lands (both sides), 1 = a wall / hazard hit, 2 = strong.
## Only when the player is on a pad and VIBRATION is on.
func vibrate(kind: int) -> void:
	if not vibration or not using_pad():
		return
	var v: Array = VIBRATION[clampi(kind, 0, VIBRATION.size() - 1)]
	rumble_count += 1
	Input.start_joy_vibration(pad_device, 1.0, v[0], v[1])


# --- the input map --------------------------------------------------------------------------

## Builds every action from the defaults, the TYPE layout and the rebinding overrides.
func apply() -> void:
	for action: String in ACTIONS:
		var d: Array = ACTIONS[action]
		if InputMap.has_action(action):
			InputMap.action_erase_events(action)
		else:
			InputMap.add_action(action, 0.2)
		var custom: Dictionary = _custom.get(action, {})
		for e in (custom["keys"] if custom.has("keys") else _default_keys(d)):
			InputMap.action_add_event(action, e)
		for e in (custom["pad"] if custom.has("pad") else _default_pad(action, d)):
			InputMap.action_add_event(action, e)
	for action: String in LINKED:
		if InputMap.has_action(action):
			InputMap.action_erase_events(action)
		else:
			InputMap.add_action(action, 0.2)
		for e in InputMap.action_get_events(LINKED[action]):
			InputMap.action_add_event(action, e)
	bindings_changed.emit()


func _default_keys(d: Array) -> Array:
	var out := []
	for k in d[1]:
		var e := InputEventKey.new()
		e.physical_keycode = k
		out.append(e)
	for m in d[2]:
		var e := InputEventMouseButton.new()
		e.button_index = m
		out.append(e)
	return out


func _default_pad(action: String, d: Array) -> Array:
	var out := []
	for b in d[3]:
		var e := InputEventJoypadButton.new()
		if b is String:   # a face button: the TYPE layout decides which
			var i := LAYOUT_ACTIONS.find(action)
			e.button_index = FACE[LAYOUTS[layout][i] if i >= 0 else b]
		else:
			e.button_index = b
		e.device = -1
		out.append(e)
	for a in d[4]:
		var e := InputEventJoypadMotion.new()
		e.axis = a[0]
		e.axis_value = a[1]
		e.device = -1
		out.append(e)
	return out


## Rebinds `action`: replaces its keyboard / mouse bindings (a key or mouse event) or its pad
## bindings (a pad event) with `event`. Saved by save_config().
func rebind(action: String, event: InputEvent) -> void:
	var pad := event is InputEventJoypadButton or event is InputEventJoypadMotion
	var custom: Dictionary = _custom.get(action, {})
	var e := event.duplicate() as InputEvent
	if e is InputEventJoypadMotion:
		e.axis_value = signf(e.axis_value)
	if pad:
		e.device = -1
	elif e is InputEventKey and e.physical_keycode == KEY_NONE:
		e.physical_keycode = e.keycode
	if e is InputEventWithModifiers:
		e.shift_pressed = false
		e.ctrl_pressed = false
		e.alt_pressed = false
		e.meta_pressed = false
	if e is InputEventKey or e is InputEventMouseButton or e is InputEventJoypadButton:
		e.pressed = false
	custom["pad" if pad else "keys"] = [e]
	_custom[action] = custom
	apply()


func set_layout(n: int) -> void:
	layout = clampi(n, 0, LAYOUTS.size() - 1)
	for a in LAYOUT_ACTIONS:   # a TYPE replaces the face buttons' own rebinding, like the game
		if _custom.has(a):
			_custom[a].erase("pad")
	apply()


func reset_defaults() -> void:
	_custom.clear()
	layout = 0
	vibration = true
	deadzone = 0.2
	invert_x = false
	invert_y = false
	apply()


func save_config() -> void:
	var c := ConfigFile.new()
	c.set_value("options", "layout", layout)
	c.set_value("options", "vibration", vibration)
	c.set_value("options", "deadzone", deadzone)
	c.set_value("options", "invert_x", invert_x)
	c.set_value("options", "invert_y", invert_y)
	for action: String in _custom:
		for side: String in _custom[action]:
			c.set_value(side, action, _custom[action][side])
	c.save(CONFIG_PATH)


func load_config(path := CONFIG_PATH) -> void:
	var c := ConfigFile.new()
	if c.load(path) != OK:
		return
	layout = clampi(int(c.get_value("options", "layout", 0)), 0, LAYOUTS.size() - 1)
	vibration = bool(c.get_value("options", "vibration", true))
	deadzone = clampf(float(c.get_value("options", "deadzone", 0.2)), 0.0, 0.9)
	invert_x = bool(c.get_value("options", "invert_x", false))
	invert_y = bool(c.get_value("options", "invert_y", false))
	_custom.clear()
	for side in ["keys", "pad"]:
		if not c.has_section(side):
			continue
		for action in c.get_section_keys(side):
			var v = c.get_value(side, action)
			if ACTIONS.has(action) and v is Array:
				var custom: Dictionary = _custom.get(action, {})
				custom[side] = v
				_custom[action] = custom


# --- controls screen ------------------------------------------------------------------------

func toggle_controls_menu() -> void:
	if is_instance_valid(_menu):
		_menu.queue_free()
		_menu = null
		return
	_menu = CanvasLayer.new()
	_menu.layer = 100
	_menu.add_child(load("res://game/input/controls_menu.tscn").instantiate())
	get_tree().root.add_child(_menu)


func controls_menu_open() -> bool:
	return is_instance_valid(_menu)
