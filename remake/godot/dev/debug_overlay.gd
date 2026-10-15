class_name DebugOverlay
extends CanvasLayer
## Text overlay for the dev arena, like the PS2 developer overlay (TASK / MOT):
## frame counter, every fighter's state and move frame, the input buffer, combo count.

const KEYS := """WASD / left stick move · mouse / right stick camera (click to capture, Esc frees it, wheel zooms)
J or LMB / X punch · K or RMB / Y kick · L or Shift / RB guard
F1 boxes · F2 slow-mo · F3 pause · F4 step one frame · F5 spawn dummy · F6 dummy mode · F7 reset · Tab hide"""

var arena: Node
var _label: Label


func _ready() -> void:
	_label = Label.new()
	_label.position = Vector2(12, 10)
	var font := SystemFont.new()
	font.font_names = PackedStringArray(["Consolas", "DejaVu Sans Mono", "Courier New", "monospace"])
	_label.add_theme_font_override("font", font)
	_label.add_theme_font_size_override("font_size", 15)
	var bg := StyleBoxFlat.new()
	bg.bg_color = Color(0, 0, 0, 0.55)
	bg.set_content_margin_all(8)
	_label.add_theme_stylebox_override("normal", bg)
	add_child(_label)


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
	lines.append(KEYS)
	_label.text = "\n".join(lines)
