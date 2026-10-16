class_name DebugOverlay
extends CanvasLayer
## Text overlay for the dev arena, like the PS2 developer overlay (TASK / MOT):
## frame counter, every fighter's state and move frame, the input buffer, combo count.

const KEYS := """WASD / left stick move · mouse / right stick camera (click to capture, Esc frees it, wheel zooms)
%s · F8 controls (rebind, TYPE 1-6, vibration)
F1 boxes · F2 slow-mo · F3 pause · F4 step one frame · F5 spawn dummy · F6 dummy mode · F7 reset · Tab hide"""


## The game buttons on the device in use (GameInput), e.g. "□ punch · △ kick · × guard ...".
static func _buttons() -> String:
	var parts: Array[String] = []
	for a in [["attack_p", "punch"], ["attack_k", "kick"], ["guard", "guard"], ["special", "special"],
			["run", "run"], ["grab", "grab/use"], ["taunt", "taunt"]]:
		parts.append("%s %s" % [GameInput.button_for(a[0])["label"], a[1]])
	return " · ".join(parts)

@export var arena: Node

@onready var _label: Label = $Label


func _process(_delta: float) -> void:
	var lines: Array[String] = []
	lines.append("BEAT DOWN REMAKE · dev arena    fps %d    %s" % [Engine.get_frames_per_second(), Dev.status_text()])
	var player: Fighter = arena.player
	lines.append("")
	lines.append(player.debug_text())
	lines.append("  buffer %s" % (player.brain as PlayerBrain).buffer_text())
	lines.append("  combo %d hits, %d damage    last: %s" % [player.combo_hits, player.combo_damage, player.last_event])
	lines.append("")
	lines.append("dummies: %s (F6)" % DummyBrain.MODE_NAMES[arena.dummy_mode])
	for n in get_tree().get_nodes_in_group("fighters"):
		if n != player:
			lines.append((n as Fighter).debug_text())
	lines.append("")
	lines.append(KEYS % _buttons())
	_label.text = "\n".join(lines)
