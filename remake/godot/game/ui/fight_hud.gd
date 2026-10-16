class_name FightHud
extends CanvasLayer
## The fight HUD the way Beat Down draws it (docs/HUD.md): the player's HP bar and name top left, the current
## target's top right (mirrored), both Pride gauges (a lighter with a burning fuse) under them, the combo
## counter, and a thin TIRED strip under each HP bar (remake-only; the game has no TIRED display).
##
## Drop fight_hud.tscn into any scene with fighters: it finds the player (group "player") and picks the target
## among group "fighters" (the last enemy the player hit or was hit by, else the nearest within `target_range`).
## Layout is the game's 640 x 448 screen, scaled to the window height and stretched sideways so the bars
## stay in the corners. Reads the fighters' state only; Pride and TIRED come from FighterMeters.

static var screen_w := 640.0     ## the virtual screen's width (640 at 4:3, wider on wide windows)

@export var target_range := 8.0       ## metres: an enemy this close becomes the target
@export var player_person := 68       ## the player's name: text 11001 + person (68 = Aaron); -1 = display_name
@export var player_pride := 300       ## Pride max (person +0x3A6): heroes 300
@export var enemy_pride := 200        ## template 77 (Wendel, Eggusz's stats) 200

var player: Fighter
var target: Fighter
var meters := {}                      ## Fighter -> FighterMeters

@onready var screen: Control = $Screen
@onready var hp_left: HudHpBar = $Screen/HpLeft
@onready var hp_right: HudHpBar = $Screen/HpRight
@onready var name_left: HudName = $Screen/NameLeft
@onready var name_right: HudName = $Screen/NameRight
@onready var pride_left: HudPrideGauge = $Screen/PrideLeft
@onready var pride_right: HudPrideGauge = $Screen/PrideRight
@onready var combo: HudCombo = $Screen/Combo
@onready var negotiation: RichTextLabel = $Screen/Negotiation

var _last_hp := {}
var _last_combo := 0


func _ready() -> void:
	process_physics_priority = 200   # after the fighters (and test drivers) moved this frame
	negotiation.add_theme_font_override("normal_font", GameFont.font())
	negotiation.add_theme_font_size_override("normal_font_size", int(GameFont.SIZE * 0.8))   # drawn at 0.8 (PrideGauge_Build)
	pride_right.negotiation_label = negotiation
	get_viewport().size_changed.connect(_fit)
	_fit()


## Scale the 448-line screen to the window height; widen it to the window's aspect.
func _fit() -> void:
	var vp := get_viewport().get_visible_rect().size
	var s := vp.y / 448.0
	screen_w = maxf(vp.x / s, 640.0)
	screen.scale = Vector2(s, s)
	screen.size = Vector2(screen_w, 448.0)


func meters_of(f: Fighter) -> FighterMeters:
	if not meters.has(f):
		meters[f] = FighterMeters.new(f, player_pride if f.is_in_group("player") else enemy_pride)
	return meters[f]


func _physics_process(_delta: float) -> void:
	if not Dev.tick:
		return
	var fighters := get_tree().get_nodes_in_group("fighters")
	if player == null or not is_instance_valid(player):
		var ps := get_tree().get_nodes_in_group("player")
		player = ps[0] as Fighter if ps.size() > 0 else null
	if player == null:
		visible = false
		return
	visible = true
	for f in fighters:
		if f is Fighter:
			meters_of(f).update(fighters)
	_pick_target(fighters)
	# Left: the player.
	var pm := meters_of(player)
	hp_left.set_values(player.hp, player.max_hp)
	hp_left.tired_max = pm.tired_max
	hp_left.tired_ratio = float(pm.tired) / maxf(pm.tired_max, 1)
	name_left.text = _name(player)
	# Right: the target.
	var has_target := target != null and is_instance_valid(target)
	for n: CanvasItem in [hp_right, name_right, pride_left, pride_right]:
		n.visible = has_target
	if has_target:
		var tm := meters_of(target)
		hp_right.set_values(target.hp, target.max_hp)
		hp_right.tired_max = tm.tired_max
		hp_right.tired_ratio = float(tm.tired) / maxf(tm.tired_max, 1)
		name_right.text = _name(target)
		pride_left.set_ratio(pm.ratio())
		pride_right.set_ratio(tm.ratio())
	else:
		negotiation.visible = false
	# Combo counter: the player's running hit count (Hud_ComboWatch).
	if player.combo_hits != _last_combo:
		_last_combo = player.combo_hits
		combo.show_count(player.combo_hits)
	combo.tick()
	for f in fighters:
		if f is Fighter:
			_last_hp[f] = f.hp


func _name(f: Fighter) -> String:
	if f == player and player_person >= 0 and GameText.available():
		return GameText.person_name(player_person)
	return f.display_name


## The target: whoever the player just hit or was hit by; kept while in range, else the nearest enemy.
func _pick_target(fighters: Array) -> void:
	for f in fighters:
		var o := f as Fighter
		if o == null or o == player:
			continue
		var was: int = _last_hp.get(o, o.hp)
		if o.hp < was and player.state == Fighter.State.ATTACK:
			target = o
		elif player.hp < int(_last_hp.get(player, player.hp)) and o.state == Fighter.State.ATTACK and \
				o.global_position.distance_to(player.global_position) < 3.0:
			target = o
	if target and is_instance_valid(target) and target.global_position.distance_to(player.global_position) <= target_range * 1.5:
		return
	target = null
	var best := target_range
	for f in fighters:
		var o := f as Fighter
		if o == null or o == player:
			continue
		var d := o.global_position.distance_to(player.global_position)
		if d < best:
			best = d
			target = o


## Text the test and the overlay can print.
func debug_text() -> String:
	var s := "HUD %s %d/%d trail %d pride %.0f tired %d" % [name_left.text, hp_left.hp, hp_left.max_hp, hp_left.trail,
		meters_of(player).pride, meters_of(player).tired]
	if target and is_instance_valid(target):
		var tm := meters_of(target)
		s += " | %s %d/%d trail %d pride %.0f/%d tired %d" % [name_right.text, hp_right.hp, hp_right.max_hp,
			hp_right.trail, tm.pride, tm.pride_max, tm.tired]
	if combo.visible_now():
		s += " | %d HITS (f%d)" % [combo.count, combo.frame]
	return s
