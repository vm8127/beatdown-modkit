class_name Fighter
extends CharacterBody3D
## One fighter: the player or a dummy. The same code runs both; who controls it is its
## "brain" child (PlayerBrain reads the pad, DummyBrain is a tiny AI).
##
## Game logic runs in fixed frames (60 per second) in _physics_process, like the PS2 game.
## Everything that only looks nice (limbs, colours, labels) runs in _process, every
## rendered frame, and never changes the game state.
##
## The fighter is a state machine: exactly one State at a time, with `state_frame` counting
## the frames spent in it. A move (MoveData) has hit windows (MoveHit) where its hit sphere is
## out, a cancel point, and a frame where control returns.
##
## Moves come from the style (MoveSet). With the assets extracted, every fighter loads Aaron's
## real style (res://assets_ripped/moves/aaron.tres, made by remake/tools/conv_moves.py from the
## game's tables); without them, the placeholder style of M0 (game/moves/).
##
## Input works like the game's (docs/ANIMATION.md, "Frame data"; docs/MECHANICS.md, "Damage"):
## - From neutral, one input code ("P", "→P", "→→P") starts the command that is exactly that
##   code, or its fallback (→→P, then →P, then P). The history becomes [that code].
## - During a move, the last input pressed since the move started is kept (`last_input`). At
##   the move's cancel point, history + last input must match a whole command ("P P ↓P"); if
##   it does the next move starts at once (a chain), else the move plays out.
## - At the release frame (or the end) the fighter is free again; a press made in the last
##   BUFFER frames of the move still starts the next move from neutral (remake choice).
##
## The body, limbs, hurtbox and debug views are nodes in fighter.tscn; this script only
## moves and colours them.
##
## Animated look (M4): when the assets are extracted, `model_name` and `anim_set` load a rigged
## model and its clips (FighterModel); the capsule body and box limbs hide, the collision capsule
## and the hurtbox stay. Every game frame the state picks the clip and its animation frame
## (`_animate`): stance when idle, walk when moving, guard, each move's clips in order at its
## speeds with its blend frames, the game's hit reaction for the hit taken, knockdown, lying and
## getting up. Hit spheres then sit on the bones of each hit window's attack parts (MoveHit.parts,
## g_AttackSpheres); the capsule's fixed sphere is the fallback.

enum State { IDLE, MOVE, ATTACK, GUARD, HITSTUN, BLOCKSTUN, KNOCKDOWN, GETUP }

const DT := 1.0 / 60.0
const GRAVITY := 20.0
const WALK_FRICTION := 30.0     ## m/s² of slow-down when not walking
const KNOCK_FRICTION := 14.0    ## m/s² while sliding from a hit
const DOWN_FRAMES := 45         ## frames lying on the floor after a knockdown
const GETUP_FRAMES := 24        ## invulnerable frames getting up
const BUFFER := 10              ## frames a press made late in a move is kept for the next one
const LAYER_WORLD := 1
const LAYER_BODIES := 2
const LAYER_HURTBOXES := 4
const RIPPED_MOVES := "res://assets_ripped/moves/%s.tres"
## g_AttackRankMul 0x005D04D0 (docs/MECHANICS.md): attack multiplier by attack rank 0-6
const ATTACK_RANK_MUL := [0.5, 1.0, 1.3, 1.6, 1.8, 1.9, 2.0]

@export var move_set: MoveSet       ## the fighting style (placeholder; replaced by `ripped_style`)
@export var ripped_style := "aaron" ## style to load from assets_ripped/moves/ when present ("" keeps move_set)
@export var display_name := "Fighter"
@export var color := Color(0.85, 0.3, 0.2)
@export var max_hp := 300
@export var walk_speed := 4.5
@export var turn_speed := 14.0
@export var model_name := "fighter_aaron_078"   ## assets_ripped/models/<name>.glb ("" = capsule)
@export var anim_set := "aaron"                  ## assets_ripped/anims/<set>.glb + .json

@export_group("Stats (placeholders with the real style)")
@export var ripped_hp := 3000       ## max HP when the real style loads (template 77, Wendel: 3000)
@export var attack_rank := 1        ## g_AttackRankMul index: 1 = x1.0 (Attack ability 0)
@export var attack_percent := 100   ## person +0x380
@export var defense_mul := 1.0      ## fighter +0x4418
@export var combo_limit := 5        ## chains allowed: person +0x384 + 1 (stat not identified)

var hp := 0
var state := State.IDLE
var state_frame := 0
var move: MoveData                   ## current move while attacking
var move_id := ""                    ## its id: "a1805" (action) or the placeholder file name
var hitstop := 0                     ## frames left frozen by an impact
var stun := 0                        ## hitstun / blockstun frames left
var pending_knockback := Vector3.ZERO  ## applied when the hitstop ends
var brain: Node

var history := PackedStringArray()   ## input codes of the current chain (the game's command history)
var last_input := ""                 ## last code pressed since the current move started (+0x4510)
var combo_count := 0                 ## chains done (+0x450C)
var combo_taken := 0                 ## hits taken in the current combo (+0x450E, damage scaling)
var last_damage := 0

# For the overlay
var combo_hits := 0
var combo_damage := 0
var last_event := ""

var _landed := -1
var _hit_shape := SphereShape3D.new()
var _hit_done := {}                  ## hit window index -> fighters it already hit
var _leftover := ""                  ## a press from the end of the last move
var _leftover_frame := 0
var _flash := 0
var _flash_color := Color.WHITE
var model: FighterModel              ## the animated look, null with the capsule
var _react_action := 0               ## hit reaction action being played (Combat_TakeHit's choice)
var _react_count := 0                ## hits taken so far (a new hit restarts the reaction)
var _down_action := 20               ## lying action the knockdown continues with (19 or 20)
var _getup_frames := GETUP_FRAMES
var _hit_views: Array[MeshInstance3D] = []

@onready var _pivot: Node3D = $Pivot
@onready var _arms: Array[Node3D] = [$Pivot/ArmR, $Pivot/ArmL]
@onready var _leg: Node3D = $Pivot/Leg
@onready var _shield: MeshInstance3D = $Pivot/Shield
@onready var _mat: StandardMaterial3D = $Pivot/Body.material_override
@onready var _hurtbox: Area3D = $Hurtbox
@onready var _hurtbox_view: MeshInstance3D = $HurtboxView
@onready var _hitbox_view: MeshInstance3D = $HitboxView
@onready var _hp_label: Label3D = $HpLabel


func _ready() -> void:
	if ripped_style != "" and ResourceLoader.exists(RIPPED_MOVES % ripped_style):
		move_set = load(RIPPED_MOVES % ripped_style)
		max_hp = ripped_hp
	hp = max_hp
	add_to_group("fighters")
	for child in get_children():
		if child.has_method("take_input"):
			brain = child
	_setup_model()


## Loads the animated model when the assets exist; otherwise the capsule stays.
func _setup_model() -> void:
	if not FighterModel.available(model_name, anim_set):
		return
	var m := FighterModel.new()
	m.name = "Model"
	_pivot.add_child(m)
	if not m.setup(model_name, anim_set):
		m.queue_free()
		return
	model = m
	for n in ["Body", "Visor", "ArmR", "ArmL", "Leg"]:
		(_pivot.get_node(n) as Node3D).visible = false
	_animate()


## True when the real style from the disc is loaded (the damage formula applies).
func real_style() -> bool:
	return move_set != null and move_set.commands.size() > 0


# --- Game logic (fixed frames) -------------------------------------------------------

func _physics_process(_delta: float) -> void:
	if not Dev.tick:
		return
	brain.think(self)
	if _flash > 0:
		_flash -= 1
	if hitstop > 0:
		# Frozen by an impact. The victim shakes so the hit reads clearly.
		hitstop -= 1
		var shaking := state in [State.HITSTUN, State.BLOCKSTUN, State.KNOCKDOWN]
		_pivot.position = Vector3(randf_range(-0.05, 0.05), 0, randf_range(-0.05, 0.05)) if shaking else Vector3.ZERO
		if state == State.ATTACK:
			_read_inputs()   # presses during the freeze count for the cancel
		return
	_pivot.position = Vector3.ZERO
	if pending_knockback != Vector3.ZERO:
		velocity = pending_knockback
		pending_knockback = Vector3.ZERO

	state_frame += 1
	match state:
		State.IDLE, State.MOVE:
			_tick_free()
		State.GUARD:
			_tick_guard()
		State.ATTACK:
			_tick_attack()
		State.HITSTUN, State.BLOCKSTUN:
			_tick_stun()
		State.KNOCKDOWN:
			_tick_knockdown()
		State.GETUP:
			_tick_getup()

	velocity.y -= GRAVITY * DT
	move_and_slide()
	_animate()


func _enter(new_state: State) -> void:
	state = new_state
	state_frame = 0
	_landed = -1


## The next input code from neutral: a press left over from the last move, or the brain's.
func _next_input() -> String:
	if _leftover != "":
		var code := _leftover
		_leftover = ""
		if Dev.frame - _leftover_frame <= BUFFER:
			return code
	return brain.take_input(self)


## Starts the one-input command for `code` (or its fallback). False if the style has none.
func _try_neutral(code: String) -> bool:
	var found := move_set.match_single(code)
	if found.is_empty():
		return false
	history = PackedStringArray([code])   # the game stores the pressed code, not the fallback
	combo_count = 0
	_start_move(found[0])
	return true


func _tick_free() -> void:
	if brain.wants_guard(self):
		_enter(State.GUARD)
		return
	var code := _next_input()
	if code != "" and _try_neutral(code):
		return
	var dir: Vector3 = brain.move_dir(self)
	if dir.length() > 0.1:
		velocity.x = dir.x * walk_speed
		velocity.z = dir.z * walk_speed
		_turn_toward(dir)
		if state != State.MOVE:
			_enter(State.MOVE)
	else:
		_apply_friction(WALK_FRICTION)
		if state != State.IDLE:
			_enter(State.IDLE)
		_face_target_smoothly()


func _tick_guard() -> void:
	_apply_friction(WALK_FRICTION)
	_face_target_smoothly()
	var code := _next_input()
	if code.ends_with("G") and _try_neutral(code):   # →G Weaving, ←G Sway Back...
		return
	if not brain.wants_guard(self):
		_enter(State.IDLE)


func _start_move(m: MoveData) -> void:
	move = m
	move_id = ("a%d" % m.action_id) if m.action_id > 0 else m.resource_path.get_file().get_basename()
	last_input = ""
	_hit_done.clear()
	if m.combo_window:
		combo_count = maxi(combo_count, 1)
	_enter(State.ATTACK)
	# Soft lock-on: snap to face the nearest enemy in front, else the stick direction.
	var target := nearest_enemy(3.5)
	if target:
		_face_now(target.global_position - global_position)
	else:
		var dir: Vector3 = brain.move_dir(self)
		if dir.length() > 0.1:
			_face_now(dir)


## Presses during a move: the last one is what the cancel point matches.
func _read_inputs() -> void:
	var code: String = brain.take_input(self)
	while code != "":
		last_input = code
		_leftover_frame = Dev.frame
		code = brain.take_input(self)


func _tick_attack() -> void:
	var f := state_frame
	_animate()   # this frame's pose first: the hit spheres sit on its bones
	if move.root_z.size() > 1:
		# Root motion: the hips' forward travel in the animation moves the capsule.
		var v := forward() * move.root_step(f) / DT
		velocity.x = v.x
		velocity.z = v.z
	elif f < move.active_start:
		var fwd := forward() * move.lunge
		velocity.x = fwd.x
		velocity.z = fwd.z
	else:
		_apply_friction(WALK_FRICTION)
	var windows := move.get_hits()
	for i in windows.size():
		if (windows[i] as MoveHit).is_active(f):
			_do_hits(i, windows[i])
	_read_inputs()
	# Cancel point: history + the last press must be a whole command of the style.
	if move.cancel_open(f) and last_input != "" and combo_count < combo_limit:
		history.append(last_input)
		var nxt := move_set.match_sequence(history)
		if nxt:
			combo_count += 1
			_start_move(nxt)
			return
		history.remove_at(history.size() - 1)   # (the game leaves it; it checks only once)
	if f >= move.control_frame():
		_leftover = last_input   # pressed too late for the chain: may start a move from neutral
		_enter(State.IDLE)


func _tick_stun() -> void:
	_apply_friction(KNOCK_FRICTION)
	stun -= 1
	if stun <= 0:
		combo_taken = 0
		_enter(State.GUARD if brain.wants_guard(self) else State.IDLE)


func _tick_knockdown() -> void:
	if state_frame > 3 and is_on_floor():
		_apply_friction(KNOCK_FRICTION * 1.5)
		if _landed < 0:
			_landed = state_frame
			_set_invulnerable(true)   # no hitting a fighter on the floor
		if state_frame - _landed >= DOWN_FRAMES:
			if hp <= 0:
				hp = max_hp
				last_event = "KO! hp refilled"
			_enter(State.GETUP)


func _tick_getup() -> void:
	_apply_friction(WALK_FRICTION)
	if state_frame >= _getup_frames:
		_set_invulnerable(false)
		combo_taken = 0
		_enter(State.IDLE)


# --- Hits ----------------------------------------------------------------------------

## Centre of a hit window's capsule sphere: a fixed distance in front of the body (the fallback).
func hitbox_center(h: MoveHit = null) -> Vector3:
	if h == null:
		h = move.get_hits()[0]
	return global_position + Vector3.UP * move.hit_height(h) + forward() * move.reach


func _hit_radius(h: MoveHit) -> float:
	return maxf(h.radius, 0.3)   # the real hand spheres are 0.16-0.18 m: too small for a capsule


## The hit window's spheres as [centre, radius] pairs: with the animated model, one per attack part
## on its bone (g_AttackSpheres: node, offset, radius x 2, as Fighter_AttackCollide uses them); else
## the capsule's one fixed sphere.
func hit_spheres(h: MoveHit) -> Array:
	var out := []
	if model:
		for part in h.parts:
			var sp := model.part_sphere(part)
			if not sp.is_empty():
				out.append(sp)
	if out.is_empty():
		out.append([hitbox_center(h), _hit_radius(h)])
	return out


## Checks the hit sphere against every hurtbox this frame. A direct shape query is
## exact on the frame it runs (an Area3D's overlaps lag one physics frame behind).
func _do_hits(index: int, h: MoveHit) -> void:
	var found := []
	for sp in hit_spheres(h):
		_hit_shape.radius = sp[1]
		var q := PhysicsShapeQueryParameters3D.new()
		q.shape = _hit_shape
		q.transform = Transform3D(Basis(), sp[0])
		q.collide_with_areas = true
		q.collide_with_bodies = false
		q.collision_mask = LAYER_HURTBOXES
		q.exclude = [_hurtbox.get_rid()]
		for r in get_world_3d().direct_space_state.intersect_shape(q, 8):
			var o := (r["collider"] as Node).get_parent() as Fighter
			if o and not o in found:
				found.append(o)
	var done: Array = _hit_done.get(index, [])
	for other: Fighter in found:
		if other == self or other in done:
			continue
		done.append(other)   # one hit per window and target
		_hit_done[index] = done
		var result := other.take_hit(self, h)
		if result == "miss":
			continue
		hitstop = maxi(hitstop, other.hitstop)   # attacker freezes as long as the victim
		match result:
			"combo":
				combo_hits += 1
				combo_damage += other.last_damage
			"hit":
				combo_hits = 1
				combo_damage = other.last_damage
		last_event = "%s %s %s (%d)" % [move.move_name, result, other.display_name, other.last_damage]


## Attack multiplier (Fighter_Spawn): g_AttackRankMul[rank] x person +0x380 / 100.
func attack_mul() -> float:
	return ATTACK_RANK_MUL[clampi(attack_rank, 0, 6)] * attack_percent / 100.0


## Damage of a hit on this fighter, Combat_ResolveHit's formula (docs/MECHANICS.md, "Damage"):
## base x attacker multiplier x defense multiplier x situation factor, each step truncated.
## (No weapons and no Pride yet, so the weapon and empty-Pride terms are left out.)
func damage_from(attacker: Fighter, h: MoveHit) -> int:
	if h.damage <= 0:
		return 0
	var d := int(h.damage * attacker.attack_mul() + 0.01)
	d = int(d * defense_mul + 0.01)
	var factor := 1.0
	if hp < 300:
		factor *= 0.5
	elif hp < 1000:
		factor *= 0.8
	if state == State.ATTACK:
		factor *= 1.5   # counter hit
	if _in_damage_state():
		factor *= maxf(0.8 - 0.1 * combo_taken, 0.3)   # combo scaling
	d = int(d * factor + 0.01)
	return maxi(d, 1)


func _in_damage_state() -> bool:
	return state == State.HITSTUN or (state == State.KNOCKDOWN and _landed < 0)


## Called by the attacker. Returns "blocked", "hit" (fresh hit), "combo" (the victim was
## still reeling from an earlier hit, so it couldn't have escaped) or "miss" (invincible).
func take_hit(attacker: Fighter, h: MoveHit) -> String:
	if state == State.ATTACK and move.is_invincible(state_frame):
		return "miss"
	var to_attacker := attacker.global_position - global_position
	to_attacker.y = 0
	var push := attacker.forward()
	var real := attacker.real_style()
	var dmg := damage_from(attacker, h) if real else h.damage
	var guarding := state in [State.GUARD, State.BLOCKSTUN]
	if guarding and forward().dot(to_attacker.normalized()) > 0.3:
		last_damage = dmg / 10
		hp = maxi(1, hp - last_damage)   # chip damage (remake placeholder)
		hitstop = int(h.get_hitstop() * 0.75)
		stun = int(h.get_hitstun() * 0.7)
		pending_knockback = push * h.get_knockback() * 0.6
		_start_flash(Color(0.6, 0.8, 1.0))
		_enter(State.BLOCKSTUN)
		_shake_camera(0.15)
		return "blocked"

	var combo := _in_damage_state()
	var heavy := hp < 1000 or state == State.ATTACK   # before the damage, like Combat_SituationFactor
	hp -= dmg
	last_damage = dmg
	combo_taken += 1
	_face_now(to_attacker)
	hitstop = h.get_hitstop()
	_start_flash(Color.WHITE)
	_pick_reaction(h, heavy, h.knockdown or hp <= 0)
	if h.knockdown or hp <= 0:
		stun = 0
		pending_knockback = push * h.get_knockback() + Vector3.UP * h.launch
		_enter(State.KNOCKDOWN)
		_shake_camera(0.6)
	else:
		stun = h.get_hitstun()
		pending_knockback = push * h.get_knockback()
		_enter(State.HITSTUN)
		_shake_camera(0.25)
	return "combo" if combo else "hit"


func _set_invulnerable(on: bool) -> void:
	_hurtbox.collision_layer = 0 if on else LAYER_HURTBOXES


func _shake_camera(amount: float) -> void:
	get_tree().call_group("camera", "add_shake", amount)


# --- Helpers -------------------------------------------------------------------------

func forward() -> Vector3:
	var f := -global_transform.basis.z
	f.y = 0
	return f.normalized()


func nearest_enemy(max_range: float) -> Fighter:
	var best: Fighter = null
	var best_d := max_range
	for n in get_tree().get_nodes_in_group("fighters"):
		var f := n as Fighter
		if f == self:
			continue
		var to := f.global_position - global_position
		to.y = 0
		var d := to.length()
		if d < best_d and forward().dot(to.normalized()) > -0.2:
			best = f
			best_d = d
	return best


func _yaw_for(dir: Vector3) -> float:
	return atan2(-dir.x, -dir.z)   # forward is -Z in Godot


func _turn_toward(dir: Vector3) -> void:
	rotation.y = lerp_angle(rotation.y, _yaw_for(dir), minf(1.0, turn_speed * DT))


func _face_now(dir: Vector3) -> void:
	if Vector2(dir.x, dir.z).length() > 0.01:
		rotation.y = _yaw_for(dir)


func _face_target_smoothly() -> void:
	var t = brain.face_target(self)
	if t is Fighter:
		_turn_toward((t as Fighter).global_position - global_position)


func _apply_friction(decel: float) -> void:
	var h := Vector2(velocity.x, velocity.z).move_toward(Vector2.ZERO, decel * DT)
	velocity.x = h.x
	velocity.z = h.y


func _start_flash(c: Color) -> void:
	_flash_color = c
	_flash = 8


func debug_text() -> String:
	var s := "%-8s %-9s hp %4d/%d" % [display_name, State.keys()[state], hp, max_hp]
	if state == State.ATTACK:
		var f := state_frame
		var phase := "ACTIVE" if move.is_active(f) else ("startup" if f < move.active_start else "recovery")
		s += "  %s f%d/%d %s" % [move.move_name, f, move.control_frame(), phase]
		if move.action_id > 0:
			s += "  [action %d anim %d]" % [move.action_id, move.anim_id]
		if move.cancel_start >= 0:
			var window := "OPEN" if move.cancel_open(f) else "@%d" % move.cancel_start
			s += "  cancel %s %s" % [window, " ".join(history)]
			if last_input != "":
				s += " +%s" % last_input
	if stun > 0:
		s += "  stun %d" % stun
	if hitstop > 0:
		s += "  hitstop %d" % hitstop
	return s


# --- Visuals (every rendered frame, no game logic) ----------------------------------

func _process(delta: float) -> void:
	# Lie down after a knockdown, stand up during getup.
	var down := PI / 2 if state == State.KNOCKDOWN and model == null else 0.0
	_pivot.rotation.x = lerpf(_pivot.rotation.x, down, 1.0 - exp(-12.0 * delta))

	# Limbs: pull back in startup, extend on active frames, retract in recovery.
	for arm in _arms:
		_pose_limb(arm, 0.0, 1.3)
	_pose_limb(_leg, 0.0, 0.7)
	_leg.visible = false
	var live: MoveHit = null
	var lives := []
	if state == State.ATTACK:
		for h in move.get_hits():
			if (h as MoveHit).is_active(state_frame):
				live = h
				lives.append(h)
		var f := float(state_frame)
		var a0 := float(move.active_start)
		var a1 := float(move.active_end)
		var ext := 0.0
		if live:
			ext = 1.0
		elif f < a0:
			ext = -0.3 * f / maxf(1.0, a0)
		elif f > a1:
			ext = 1.0 - clampf((f - a1) / maxf(1.0, move.frames - a1) * 1.6, 0.0, 1.0)
		var h0: MoveHit = live if live else (move.get_hits()[0] if move.get_hits().size() > 0 else null)
		var limb: Node3D = _leg if move.limb == "leg" else _arms[move.side]
		_pose_limb(limb, ext, move.hit_height(h0) if h0 else move.height)
		_leg.visible = move.limb == "leg" and model == null

	_shield.visible = state in [State.GUARD, State.BLOCKSTUN]
	_mat.albedo_color = _flash_color if _flash > 0 else color

	_show_hit_spheres(lives)
	_hurtbox_view.visible = Dev.show_boxes and Dev.show_hurtboxes and _hurtbox.collision_layer != 0
	_hp_label.text = "%s\n%d" % [display_name, hp]


## Draws every live hit sphere (F1 toggles), one view per sphere.
func _show_hit_spheres(lives: Array) -> void:
	var spheres := []
	if Dev.show_boxes:
		for h in lives:
			spheres.append_array(hit_spheres(h))
	while _hit_views.size() < spheres.size():
		var v := _hitbox_view.duplicate() as MeshInstance3D
		add_child(v)
		_hit_views.append(v)
	_hitbox_view.visible = false
	for i in _hit_views.size():
		var on := i < spheres.size()
		_hit_views[i].visible = on
		if on:
			_hit_views[i].global_position = spheres[i][0]
			_hit_views[i].scale = Vector3.ONE * float(spheres[i][1]) * 2.0


func _pose_limb(limb: Node3D, ext: float, height: float) -> void:
	limb.position.y = height
	limb.position.z = 0.25 * -minf(ext, 0.0)
	limb.scale.z = lerpf(0.35, 1.2, maxf(ext, 0.0))


# --- Animation (M4): which clip the state shows -------------------------------------

## Reaction kind for a hit, in Combat_TakeHit 0x0030DFD0's order (docs/ANIMATION.md, "Hit reactions"):
## the big reaction bits first, then a knockdown, then the hit level, then the stagger detail bits.
static func reaction_kind(h: MoveHit, knocked_down: bool) -> int:
	for pair in [[0x800, 0x14], [0x1000, 0x15], [0x100, 8], [0x10, 0xE], [0x200, 0xD], [0x400, 0xF]]:
		if h.reaction & pair[0]:
			return pair[1]
	if knocked_down:
		return 9
	if h.level & 4:
		return 3
	if h.level & 8:
		return 0xB
	for pair in [[0x10, 1], [0x20, 2], [8, 0x10], [4, 0x11]]:
		if h.reaction_detail & pair[0]:
			return pair[1]
	return 0


## Picks the reaction action (set 1 when the victim was below 1000 HP or attacking: the set is
## Combat_SituationFactor's return value) and, for a knockdown, the lying action it continues with.
func _pick_reaction(h: MoveHit, heavy: bool, knocked_down: bool) -> void:
	_react_count += 1
	if model == null:
		return
	_react_action = model.reaction_action(1 if heavy else 0, reaction_kind(h, knocked_down))
	var then := int(model.action_info(_react_action).get("then", 1))
	_down_action = then if then in [19, 20] else 20
	var getup := int(model.action_info(_down_action).get("then", 22))
	var frames := model.clip_frames(model.clip_for_action(getup))
	_getup_frames = frames if frames > 0 else GETUP_FRAMES


## Poses the model for the current state and frame (every game frame, and before the hit checks of
## an attack frame). Animation frames advance with the game frames, at the move's speeds.
func _animate() -> void:
	if model == null:
		return
	var generic: Dictionary = model.meta.get("generic", {})
	match state:
		State.IDLE:
			_show_action(int(generic.get("stance", 1)), "stance", state_frame)
		State.MOVE:
			_show_action(int(generic.get("walk", 2)), "walk", state_frame)
		State.GUARD, State.BLOCKSTUN:
			# Action 10 plays frames 0-36 of its anim; the remake holds the last one while guarding.
			_show_action(int(generic.get("guard", 10)), "guard", mini(state_frame, 36))
		State.ATTACK:
			_show_move()
		State.HITSTUN:
			_show_action(_react_action, "hit%d" % _react_count, state_frame)
		State.KNOCKDOWN:
			var n := model.clip_frames(model.clip_for_action(_react_action))
			if state_frame < n:
				_show_action(_react_action, "hit%d" % _react_count, state_frame)
			else:
				_show_action(_down_action, "down%d" % _react_count, state_frame - n)
		State.GETUP:
			_show_action(int(model.action_info(_down_action).get("then", 22)), "getup%d" % _react_count, state_frame)


## Shows an action's first clip (stance, walk, a reaction...) with that action's blend.
func _show_action(action: int, key: String, frame: int) -> void:
	var clip := model.clip_for_action(action)
	if clip == "":
		clip = model.clip_for_action(1)
	var blend := int(model.action_info(action).get("blend", 8))
	model.show_clip(key, clip, frame, blend)


## A move's clips in order (its motion script's play ops): the animation frame runs at the
## timeline's speeds; each clip covers [start, end] (end -1 or past the clip = its length) and
## blends in with its own blend frames.
func _show_move() -> void:
	if move.clips.is_empty():
		_show_action(1, "stance", state_frame)
		return
	var a := move.anim_frame_at(state_frame)
	for i in move.clips.size():
		var c: PackedInt32Array = move.clips[i]
		var clip := "a%d" % c[0]
		var n := model.clip_frames(clip)
		var end := float(n if c[2] < 0 or c[2] > n else c[2])
		var length := maxf(end - c[1], 1.0)
		if a < length or i == move.clips.size() - 1:
			model.show_clip("%s:%d" % [move_id, i], clip, c[1] + minf(a, length), c[3])
			return
		a -= length
