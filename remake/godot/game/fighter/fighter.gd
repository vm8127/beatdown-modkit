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
## the frames spent in it. A move (MoveData, game/moves/*.tres) is split into startup,
## active and recovery frames; the hitbox only exists on the active frames.
##
## The body, limbs, hurtbox and debug views are nodes in fighter.tscn; this script only
## moves and colours them.

enum State { IDLE, MOVE, ATTACK, GUARD, HITSTUN, BLOCKSTUN, KNOCKDOWN, GETUP }

const DT := 1.0 / 60.0
const GRAVITY := 20.0
const WALK_FRICTION := 30.0     ## m/s² of slow-down when not walking
const KNOCK_FRICTION := 14.0    ## m/s² while sliding from a hit
const DOWN_FRAMES := 45         ## frames lying on the floor after a knockdown
const GETUP_FRAMES := 24        ## invulnerable frames getting up
const LAYER_WORLD := 1
const LAYER_BODIES := 2
const LAYER_HURTBOXES := 4

@export var move_set: MoveSet       ## the fighting style: which move each button starts
@export var display_name := "Fighter"
@export var color := Color(0.85, 0.3, 0.2)
@export var max_hp := 300
@export var walk_speed := 4.5
@export var turn_speed := 14.0

var hp := 0
var state := State.IDLE
var state_frame := 0
var move: MoveData                   ## current move while attacking
var move_id := ""                    ## its file name, e.g. "jab1"
var hitstop := 0                     ## frames left frozen by an impact
var stun := 0                        ## hitstun / blockstun frames left
var pending_knockback := Vector3.ZERO  ## applied when the hitstop ends
var hit_targets: Array[Fighter] = []   ## already hit by the current move
var brain: Node

# For the overlay
var combo_hits := 0
var combo_damage := 0
var last_event := ""

var _landed := -1
var _hit_shape := SphereShape3D.new()
var _flash := 0
var _flash_color := Color.WHITE

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
	hp = max_hp
	add_to_group("fighters")
	for child in get_children():
		if child.has_method("take_press"):
			brain = child


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


func _enter(new_state: State) -> void:
	state = new_state
	state_frame = 0
	_landed = -1


func _tick_free() -> void:
	if brain.wants_guard(self):
		_enter(State.GUARD)
		return
	var press: String = brain.take_press(move_set.root.keys())
	if press != "":
		_start_move(move_set.root[press])
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
	if not brain.wants_guard(self):
		_enter(State.IDLE)


func _start_move(m: MoveData) -> void:
	move = m
	move_id = m.resource_path.get_file().get_basename()
	hit_targets.clear()
	_enter(State.ATTACK)
	# Soft lock-on: snap to face the nearest enemy in front, else the stick direction.
	var target := nearest_enemy(3.5)
	if target:
		_face_now(target.global_position - global_position)
	else:
		var dir: Vector3 = brain.move_dir(self)
		if dir.length() > 0.1:
			_face_now(dir)


func _tick_attack() -> void:
	var f := state_frame
	if f < move.active_start:
		var fwd := forward() * move.lunge
		velocity.x = fwd.x
		velocity.z = fwd.z
	else:
		_apply_friction(WALK_FRICTION)
	if move.is_active(f):
		_do_hits()
	# Combo: during the cancel window, a buffered press starts the next move.
	if move.cancel_open(f):
		var press: String = brain.take_press(move.next.keys())
		if press != "":
			_start_move(move.next[press])
			return
	if f >= move.frames:
		_enter(State.IDLE)


func _tick_stun() -> void:
	_apply_friction(KNOCK_FRICTION)
	stun -= 1
	if stun <= 0:
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
	if state_frame >= GETUP_FRAMES:
		_set_invulnerable(false)
		_enter(State.IDLE)


# --- Hits ----------------------------------------------------------------------------

func hitbox_center() -> Vector3:
	return global_position + Vector3.UP * move.height + forward() * move.reach


## Checks the hit sphere against every hurtbox this frame. A direct shape query is
## exact on the frame it runs (an Area3D's overlaps lag one physics frame behind).
func _do_hits() -> void:
	_hit_shape.radius = move.radius
	var q := PhysicsShapeQueryParameters3D.new()
	q.shape = _hit_shape
	q.transform = Transform3D(Basis(), hitbox_center())
	q.collide_with_areas = true
	q.collide_with_bodies = false
	q.collision_mask = LAYER_HURTBOXES
	q.exclude = [_hurtbox.get_rid()]
	for r in get_world_3d().direct_space_state.intersect_shape(q, 8):
		var other := (r["collider"] as Node).get_parent() as Fighter
		if other == null or other == self or other in hit_targets:
			continue
		hit_targets.append(other)   # one hit per move and target
		var result := other.take_hit(self, move)
		hitstop = maxi(hitstop, other.hitstop)   # attacker freezes as long as the victim
		match result:
			"combo":
				combo_hits += 1
				combo_damage += move.damage
			"hit":
				combo_hits = 1
				combo_damage = move.damage
		last_event = "%s %s %s" % [move.move_name, result, other.display_name]


## Called by the attacker. Returns "blocked", "hit" (fresh hit) or "combo" (the victim was
## still reeling from an earlier hit, so it couldn't have escaped).
func take_hit(attacker: Fighter, m: MoveData) -> String:
	var to_attacker := attacker.global_position - global_position
	to_attacker.y = 0
	var push := attacker.forward()
	var guarding := state in [State.GUARD, State.BLOCKSTUN]
	if guarding and forward().dot(to_attacker.normalized()) > 0.3:
		hp = maxi(1, hp - m.damage / 10)   # chip damage
		hitstop = int(m.hitstop * 0.75)
		stun = int(m.hitstun * 0.7)
		pending_knockback = push * m.knockback * 0.6
		_start_flash(Color(0.6, 0.8, 1.0))
		_enter(State.BLOCKSTUN)
		_shake_camera(0.15)
		return "blocked"

	var combo := state in [State.HITSTUN, State.KNOCKDOWN]
	hp -= m.damage
	_face_now(to_attacker)
	hitstop = m.hitstop
	_start_flash(Color.WHITE)
	if m.knockdown or hp <= 0:
		stun = 0
		pending_knockback = push * m.knockback + Vector3.UP * m.launch
		_enter(State.KNOCKDOWN)
		_shake_camera(0.6)
	else:
		stun = m.hitstun
		pending_knockback = push * m.knockback
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
	var s := "%-8s %-9s hp %3d/%d" % [display_name, State.keys()[state], hp, max_hp]
	if state == State.ATTACK:
		var f := state_frame
		var phase := "startup" if f < move.active_start else ("ACTIVE" if f <= move.active_end else "recovery")
		s += "  %s f%d/%d %s" % [move.move_name, f, move.frames, phase]
		if move.cancel_start >= 0:
			var window := "OPEN" if move.cancel_open(f) else "[%d-%d]" % [move.cancel_start, move.cancel_end]
			s += "  combo %s %s" % [move.next.keys(), window]
	if stun > 0:
		s += "  stun %d" % stun
	if hitstop > 0:
		s += "  hitstop %d" % hitstop
	return s


# --- Visuals (every rendered frame, no game logic) ----------------------------------

func _process(delta: float) -> void:
	# Lie down after a knockdown, stand up during getup.
	var down := PI / 2 if state == State.KNOCKDOWN else 0.0
	_pivot.rotation.x = lerpf(_pivot.rotation.x, down, 1.0 - exp(-12.0 * delta))

	# Limbs: pull back in startup, extend on active frames, retract in recovery.
	for arm in _arms:
		_pose_limb(arm, 0.0, 1.3)
	_pose_limb(_leg, 0.0, 0.7)
	_leg.visible = false
	if state == State.ATTACK:
		var f := float(state_frame)
		var a0 := float(move.active_start)
		var a1 := float(move.active_end)
		var ext := 0.0
		if f < a0:
			ext = -0.3 * f / a0
		elif f <= a1:
			ext = 1.0
		else:
			ext = 1.0 - clampf((f - a1) / maxf(1.0, move.frames - a1) * 1.6, 0.0, 1.0)
		var limb: Node3D = _leg if move.limb == "leg" else _arms[move.side]
		_pose_limb(limb, ext, move.height)
		_leg.visible = move.limb == "leg"

	_shield.visible = state in [State.GUARD, State.BLOCKSTUN]
	_mat.albedo_color = _flash_color if _flash > 0 else color

	var active_now := state == State.ATTACK and move.is_active(state_frame)
	_hitbox_view.visible = Dev.show_boxes and active_now
	if active_now:
		_hitbox_view.global_position = hitbox_center()
		_hitbox_view.scale = Vector3.ONE * move.radius * 2.0
	_hurtbox_view.visible = Dev.show_boxes and _hurtbox.collision_layer != 0
	_hp_label.text = "%s\n%d" % [display_name, hp]


func _pose_limb(limb: Node3D, ext: float, height: float) -> void:
	limb.position.y = height
	limb.position.z = 0.25 * -minf(ext, 0.0)
	limb.scale.z = lerpf(0.35, 1.2, maxf(ext, 0.0))

