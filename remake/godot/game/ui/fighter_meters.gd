class_name FighterMeters
extends RefCounted
## Pride Gauge and TIRED meter of one fighter, for the HUD (docs/MECHANICS.md, "Pride Gauge"; docs/HUD.md, "TIRED").
##
## Fighter doesn't keep these yet (the fight-feel work owns fighter.gd), so this follows the fighter from the
## outside once per game frame: a drop in HP is a landed hit (Pride damage from the attacker's active hit
## record, Fighter_PrideDamage), a move starting adds its cost to TIRED (Fighter_StartAction), and TIRED drains
## by 1 every 0.5 s down to its rising floor (Fighter_TaskAction). Move these into Fighter when negotiation
## (M7) needs them; the formulas stay the same.

const STYLE_PRIDE_MUL := 100     ## g_StylePrideMul percent (Aaron's style: 100; Boxer 120, Negotiator 150...)

var fighter: Fighter
var pride := 300.0
var pride_max := 300             ## person +0x3A6: heroes 300, template 77 (Wendel) 200, bosses 500-800
var tired := 0
var tired_max := 0               ## 1.5 x max HP
var tired_total := 0             ## +0x442E: every cost ever added
var tired_floor_f := 1.0         ## +0x44E0: the floor is tired_max x (1 - f); f drops by 0.1 to 0.5
var technique := 0               ## player's Technique ability level (Pride damage x (1 + 0.2 n))
var last_pride_damage := 0
var rng := RandomNumberGenerator.new()

var _hp := -1
var _max_hp := -1
var _move: MoveData
var _move_frame := 0
var _drain := 0


func _init(f: Fighter, max_pride := 300) -> void:
	fighter = f
	pride_max = max_pride
	rng.seed = 0x5CA320   # deterministic (tests)
	reset()


func reset() -> void:
	pride = pride_max
	tired = 0
	tired_total = 0
	tired_floor_f = 1.0
	_max_hp = fighter.max_hp
	_hp = fighter.hp
	tired_max = int(fighter.max_hp * 1.5)


func ratio() -> float:
	return clampf(pride / pride_max, 0.0, 1.0) if pride_max > 0 else 0.0


## Once per game frame, after the fighters moved. `others` are the fighters that could have hit this one.
func update(others: Array) -> void:
	if not is_instance_valid(fighter):
		return
	if fighter.max_hp != _max_hp or fighter.hp > _hp and fighter.hp == fighter.max_hp:
		reset()   # new fight / reset (F7) / revived
	elif fighter.hp < _hp:
		var att := _attacker(others)
		var base := 0
		if att and att.move:
			for h: MoveHit in att.move.hits:
				if h.is_active(att.state_frame):
					base = h.pride
					break
		sub_pride(pride_damage(base, att))
	_hp = fighter.hp
	# A move starting adds its cost (Fighter_StartAction: hit table header +4).
	if fighter.state == Fighter.State.ATTACK and fighter.move and (fighter.move != _move or fighter.state_frame < _move_frame):
		add_cost(fighter.move.cost)
	_move = fighter.move if fighter.state == Fighter.State.ATTACK else null
	_move_frame = fighter.state_frame
	# Drain: 1 every 0.5 s (30 frames), not below the floor.
	_drain += 1
	if _drain > 30:
		_drain = 0
		tired = maxi(tired - 1, floor_value())
		tired = maxi(tired, floor_value())


func floor_value() -> int:
	return tired_max - int(tired_max * tired_floor_f)


func add_cost(cost: int) -> void:
	if cost <= 0:
		return
	tired += cost
	var before := tired_total
	tired_total += cost
	if tired_max > 0 and before / tired_max != tired_total / tired_max:
		tired_floor_f = maxf(tired_floor_f - 0.1, 0.5)


## Fighter_PrideDamage (defender = this fighter): base + random 30-39, x style %, + 10 - 20 x HP%, >= 0,
## x (1 + 0.2 Technique) for the player.
func pride_damage(base: int, attacker: Fighter) -> int:
	var p := base + rng.randi_range(30, 39)
	p = int(p * STYLE_PRIDE_MUL / 100.0)
	var hp_ratio := float(maxi(fighter.hp, 0)) / maxf(fighter.max_hp, 1)
	p += int(10.0 - 20.0 * hp_ratio)
	p = maxi(p, 0)
	if attacker and attacker.is_in_group("player"):
		p += int(p * 0.2 * technique)
	return p


func sub_pride(amount: int) -> void:
	last_pride_damage = amount
	pride = maxf(pride - amount, 0.0)


func _attacker(others: Array) -> Fighter:
	var best: Fighter
	var best_d := INF
	for o in others:
		var f := o as Fighter
		if f == null or f == fighter or f.state != Fighter.State.ATTACK:
			continue
		var d := f.global_position.distance_squared_to(fighter.global_position)
		if d < best_d:
			best_d = d
			best = f
	return best
