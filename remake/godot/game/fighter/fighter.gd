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
##
## Hits as the game takes them (Combat_ResolveHit / Combat_TakeHit, docs/ANIMATION.md "Hit reactions"):
## the reaction action comes from the game's tables by hit kind, reaction set (heavier below 1000 HP or
## when hit while attacking) and the attacker's direction (front / behind / left / right of the victim's
## facing; the victim doesn't turn). Hitstun is that action's release frame (op 0x3C) or its end, a
## knockdown lasts until its clips end, and the knockback is the reaction's own hip travel (root motion):
## the game has no separate push. A guarding fighter facing the attacker (within 45°) blocks high and mid
## hits: no damage, no reaction. After control returns the rest of the animation plays out (the "tail")
## unless the fighter does something else.

enum State { IDLE, MOVE, ATTACK, GUARD, HITSTUN, BLOCKSTUN, KNOCKDOWN, GETUP, HOLD, HELD }

const DT := 1.0 / 60.0
const GRAVITY := 20.0
const WALK_FRICTION := 30.0     ## m/s² of slow-down when not walking
const KNOCK_FRICTION := 14.0    ## m/s² while sliding from a hit
const DOWN_FRAMES := 45         ## frames lying on the floor after a knockdown (remake: the game's lying loop isn't timed by data)
const GETUP_FRAMES := 24        ## invulnerable frames getting up
const BUFFER := 10              ## frames a press made late in a move is kept for the next one
const LAYER_WORLD := 1
const LAYER_BODIES := 2
const LAYER_HURTBOXES := 4
const RIPPED_MOVES := "res://assets_ripped/moves/%s.tres"
## g_AttackRankMul 0x005D04D0 (docs/MECHANICS.md): attack multiplier by attack rank 0-6
const ATTACK_RANK_MUL := [0.5, 1.0, 1.3, 1.6, 1.8, 1.9, 2.0]
## Reaction table entries in the game's order (g_ReactionSets rows): index = Combat_TakeHit's direction
const DIRECTIONS := ["behind", "front", "left", "right"]
const DIR_BEHIND := 0
const DIR_FRONT := 1
const DIR_LEFT := 2
const DIR_RIGHT := 3
const LOCK_RANGE := 5.0         ## remake: walking within this distance of an enemy locks on (the game is locked in every battle)
const UNIT := 0.1               ## metres per game unit
const HOLD_FRAMES := 150        ## remake: how long a hold lasts without a throw before letting go (the game's escape isn't traced)
const WALL_RANGE := 1.1         ## Combat_TakeHit's wall test radius, 11 units

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
var holding: Fighter = null          ## the fighter this one holds (grab, throw)
var held_by: Fighter = null          ## the fighter holding this one
var _hold_rear := false              ## the hold was taken from behind (throws use REAR GRAB P / K)
var _held_action := 0                ## held: the partner action being played (catch, hold, a throw's victim side)
var _held_loop := false
var _walk_frame := 0.0              ## walk clip frame (advances at the rate that keeps the feet planted)
var _walk_rate := 1.0
var _walk_action := 2                ## the walk action shown (g_WalkModes direction, or the run)
var walk_mode := 0                   ## g_WalkModes mode: 0 unarmed, 2 afraid and hurt (FUN_003155D0)
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
var _react := {}                     ## its info from the anim set (clips per frame, frames, release, then)
var _react_count := 0                ## hits taken so far (a new hit restarts the reaction)
var _down_action := 20               ## lying action the knockdown continues with (19 face down, 20 face up)
var _getup_action := 22              ## getup after lying (the lying action's goto: 20 -> 22, 19 -> 21)
var _getup_frames := GETUP_FRAMES
var _tail := {}                      ## the rest of an animation after control returned: key, move or action, from
var _block_action := 822            ## guard-hit action being played (blocked hit)
var last_reaction := ""              ## the last reaction picked (overlay, tests), e.g. "a703 front kind 0 set 0" 
var posture := 1                     ## +0x4390, set by timeline op 0x35: 1 standing, 2 crouching, 4 down, 8 face up, 0x10 face down, 0x20 in the air
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
	# Fighters push each other apart with the game's body spheres (_push_apart), not the fat capsules.
	collision_mask &= ~LAYER_BODIES
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
		State.HOLD:
			_tick_hold()
		State.HELD:
			_tick_held()

	_animate()
	if model and _root_motion_state():
		# The clip's hip travel moves the body (moves, reactions, knockdowns, getups); collision stops it.
		velocity.x = model.root_delta.x / DT
		velocity.z = model.root_delta.z / DT
	velocity.y -= GRAVITY * DT
	move_and_slide()
	_push_apart()


## The game's body collision between fighters (FUN_003072C0, every frame, every pair): where a body sphere of this
## fighter (g_BodySpheres on the posed bones: hips and chest 0.22 m, head, limbs) overlaps the other's, both move
## apart along the floor line between them, half each (each fighter moves itself by its half here). Remake: the
## deepest overlap of the pair, moved with collision so walls still stop it; held pairs are skipped.
func _push_apart() -> void:
	if model == null:
		return
	var mine := model.body_spheres()
	for n in get_tree().get_nodes_in_group("fighters"):
		var o := n as Fighter
		if o == self or o.model == null or o == holding or o == held_by:
			continue
		if global_position.distance_to(o.global_position) > 2.5:
			continue
		var depth := 0.0
		for a in mine:
			for b in o.model.body_spheres():
				var d := float(a[0].distance_to(b[0]))
				depth = maxf(depth, float(a[1]) + float(b[1]) - d)
		if depth <= 0.0:
			continue
		var away := global_position - o.global_position
		away.y = 0
		away = away.normalized() if away.length() > 0.001 else -forward()
		move_and_collide(away * depth * 0.5)


func _enter(new_state: State) -> void:
	state = new_state
	state_frame = 0
	_landed = -1
	if new_state != State.IDLE:
		_tail = {}
	if new_state in [State.IDLE, State.MOVE, State.ATTACK, State.GUARD, State.HOLD]:
		posture = 1   # every move and the stance start with op 0x35 1 (standing); the remake has no crouch yet


## Applies an action's timeline posture (op 0x35) and MATCHLESS ranges at game frame `f` (reactions, falls, getups):
## the game lets a falling or launched fighter be hit (no MATCHLESS: kinds 5 in the air, 9 / 10 down), only the real
## knockdowns (649-652, the KOs) and the getups are invincible.
func _track_status(action: int, f: int) -> void:
	if model == null:
		return
	var info := model.action_info(action)
	for p in info.get("posture", []):
		if int(p[0]) <= f:
			posture = int(p[1])
	var inv := false
	for r in info.get("invincible", []):
		if f >= int(r[0]) and f < int(r[1]):
			inv = true
	_set_invulnerable(inv)


## States whose animation carries the body (root motion); idle only while a tail plays.
func _root_motion_state() -> bool:
	match state:
		State.ATTACK, State.HITSTUN, State.BLOCKSTUN, State.KNOCKDOWN, State.GETUP, State.HOLD, State.HELD:
			return true
		State.IDLE:
			return not _tail.is_empty()
	return false


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
		var v := _walk_velocity(dir.normalized())
		velocity.x = v.x
		velocity.z = v.z
		if state != State.MOVE:
			_enter(State.MOVE)
	else:
		_apply_friction(WALK_FRICTION)
		if state != State.IDLE:
			_enter(State.IDLE)
		_face_target_smoothly()


## Fighter_TaskWalk 0x0030CA90: locked on an enemy, the fighter keeps facing it and steps in one of 8 directions
## (g_WalkModes: each its own action and speed, so the feet match); running (L1 or the stick at full tilt) faces
## the way it goes, action 3 at 54 units/s; with nobody near, a plain walk forward. Sets the walk action.
func _walk_velocity(dir: Vector3) -> Vector3:
	var row: Dictionary = model.meta.get("walk_modes", {}).get(str(walk_mode), {}) if model else {}
	if row.is_empty():
		_turn_toward(dir)
		return dir * walk_speed
	var run: bool = brain.has_method("wants_run") and brain.wants_run(self)
	var target := _lock_target()
	if run or target == null:
		_turn_toward(dir)
		if run:
			var r: Dictionary = model.meta.get("run", {})
			_walk_action = int(r.get("action", 3))
			return _walk_at(dir, float(r.get("speed", 54.0)) * UNIT, 0)
		_walk_action = int(row["actions"][0])
		return _walk_at(dir, float(row["speeds"][0]) * 60.0 * UNIT, 0)
	var to := target.global_position - global_position
	_turn_toward(Vector3(to.x, 0, to.z))
	var i := walk_direction(dir)
	_walk_action = int(row["actions"][i])
	return _walk_at(dir, float(row["speeds"][i]) * 60.0 * UNIT, i)


## Moves at the game's speed and sets the clip's playback rate so its feet keep up (remake: the game moves 2.16 m/s
## with a front walk whose stride is about 1.35 m/s at speed 1.0, docs/ANIMATION.md "Locomotion").
const WALK_DIRS := [Vector3(0, 0, 1), Vector3(0, 0, -1), Vector3(1, 0, 0), Vector3(-1, 0, 0),
	Vector3(0.707, 0, 0.707), Vector3(-0.707, 0, 0.707), Vector3(0.707, 0, -0.707), Vector3(-0.707, 0, -0.707)]


func _walk_at(dir: Vector3, speed: float, i: int) -> Vector3:
	var natural := model.stride_speed(model.clip_for_action(_walk_action), WALK_DIRS[i])
	_walk_rate = clampf(speed / natural, 0.5, 2.5) if natural > 0.05 else 1.0
	return dir * speed


## The walk task's 8 directions from the game angle of the move against the facing: 0 front (-25..25), 4 (25..65),
## 2 (65..115), 6 (115..155), 5 (-65..-25), 3 (-115..-65), 7 (-155..-115), 1 back.
func walk_direction(dir: Vector3) -> int:
	var l := global_transform.basis.inverse() * dir
	var a := rad_to_deg(atan2(-l.x, -l.z))
	if a >= -25.0 and a < 25.0:
		return 0
	if a >= 25.0 and a < 65.0:
		return 4
	if a >= 65.0 and a < 115.0:
		return 2
	if a >= 115.0 and a < 155.0:
		return 6
	if a >= -65.0 and a < -25.0:
		return 5
	if a >= -115.0 and a < -65.0:
		return 3
	if a >= -155.0 and a < -115.0:
		return 7
	return 1


## The nearest other fighter within LOCK_RANGE that can still fight, any direction.
func _lock_target() -> Fighter:
	var best: Fighter = null
	var best_d := LOCK_RANGE
	for n in get_tree().get_nodes_in_group("fighters"):
		var f := n as Fighter
		if f == self or f.state == State.KNOCKDOWN:
			continue
		var d := global_position.distance_to(f.global_position)
		if d < best_d:
			best = f
			best_d = d
	return best


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
	if model:
		pass   # root motion from the clips (_physics_process)
	elif move.root_z.size() > 1:
		# Capsule only: the hips' forward travel in the animation moves the capsule.
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
	for th in move.throw_hits:
		if (th as MoveHit).start == f and holding:
			holding.take_throw(self, th)   # timeline op 0x2B: the hit record lands on the held fighter
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
		_let_go()
		_leftover = last_input   # pressed too late for the chain: may start a move from neutral
		var tail := {"move": move, "key": move_id, "from": f} if f < move.frames else {}
		_enter(State.IDLE)
		_tail = tail


func _tick_stun() -> void:
	if model == null:
		_apply_friction(KNOCK_FRICTION)
	elif state == State.HITSTUN:
		_track_status(_react_action, state_frame)
	stun -= 1
	if stun <= 0:
		combo_taken = 0
		var tail := {}
		if model and state == State.HITSTUN and state_frame < int(_react.get("frames", 0)):
			tail = {"action": _react_action, "key": "hit%d" % _react_count, "from": state_frame}
		_enter(State.GUARD if brain.wants_guard(self) else State.IDLE)
		if state == State.IDLE:
			_tail = tail


## On the floor after a knockdown (the fall is over).
func _is_lying() -> bool:
	if state != State.KNOCKDOWN:
		return false
	if model:
		return state_frame >= int(_react.get("frames", 0))
	return _landed >= 0


func _tick_knockdown() -> void:
	if model:
		# The fall plays the reaction's clips (MATCHLESS in the game), then the lying loop.
		var n := int(_react.get("frames", 0))
		if state_frame < n:
			_track_status(_react_action, state_frame)   # the fall: launched (0x20) or down (4), MATCHLESS only for real knockdowns
		elif state_frame == n:
			_set_invulnerable(false)   # lying: low hits still connect (take_hit)
		if state_frame >= n + DOWN_FRAMES:
			if hp <= 0:
				hp = max_hp
				last_event = "KO! hp refilled"
			_enter(State.GETUP)
			_set_invulnerable(true)   # the getups set MATCHLESS (status bit 1) from their first frame
		return
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
	if model == null:
		_apply_friction(WALK_FRICTION)
	if state_frame >= _getup_frames:
		_set_invulnerable(false)
		combo_taken = 0
		var info := model.action_info(_getup_action) if model else {}
		var tail := {}
		if state_frame < int(info.get("frames", 0)):
			tail = {"action": _getup_action, "key": "getup%d" % _react_count, "from": state_frame}
		_enter(State.IDLE)
		_tail = tail


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
	if move.attack_kind & 4 and holding == null:
		# A grab attempt (category HOLD, Combat_ResolveHit's HOLD branch): the window catches instead of hitting.
		for other: Fighter in found:
			if other != self and other.can_be_grabbed():
				_catch(other)
				return
		return
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


## Lying face down (posture 0x10, or the face-down lying action 19).
func _face_down() -> bool:
	return posture & 0x10 != 0 if posture & 4 else _down_action == 19


func _in_damage_state() -> bool:
	return state == State.HITSTUN or (state == State.KNOCKDOWN and not _is_lying())


## Called by the attacker. Returns "blocked", "hit" (fresh hit), "combo" (the victim was
## still reeling from an earlier hit, so it couldn't have escaped) or "miss" (invincible).
func take_hit(attacker: Fighter, h: MoveHit) -> String:
	if state == State.ATTACK and move.is_invincible(state_frame):
		return "miss"
	if state == State.HELD or held_by:
		return "miss"   # remake: a held fighter only takes its holder's throw damage
	_let_go()   # hit while holding: the hold breaks
	var lying := _is_lying() or (model != null and posture & 4 != 0)   # Fighter_IsDown: posture bit 4
	if lying and not (h.level & 8):
		return "miss"   # remake: the hurtbox is a standing capsule, so on the floor only low hits connect
	var entry := hit_direction(attacker)
	var push := attacker.forward()
	var real := attacker.real_style()
	var dmg := damage_from(attacker, h) if real else h.damage
	var guarding := state in [State.GUARD, State.BLOCKSTUN]
	if guarding and entry == DIR_FRONT and not (h.level & 8):
		# Combat_ResolveHit: guarding (state 0x400) with the attacker within 45° in front blocks high and
		# mid hits: no damage and no hit reaction; a standing guard doesn't stop low hits. The guard task
		# (0x0030FF20) then plays a guard-hit action (g_GuardActions) that returns to the guard loop.
		last_damage = 0
		hitstop = int(h.get_hitstop() * 0.75)
		stun = 1
		pending_knockback = Vector3.ZERO if model else push * h.get_knockback() * 0.6
		if model:
			_react_count += 1
			_block_action = guard_hit_action(h)
			stun = maxi(1, int(model.action_info(_block_action).get("frames", 1)))
		_start_flash(Color(0.6, 0.8, 1.0))
		_enter(State.BLOCKSTUN)
		_shake_camera(0.15)
		last_reaction = "blocked"
		return "blocked"

	var combo := _in_damage_state()
	var heavy := hp < 1000 or state == State.ATTACK   # before the damage, like Combat_SituationFactor
	hp -= dmg
	last_damage = dmg
	combo_taken += 1
	hitstop = h.get_hitstop()
	_start_flash(Color.WHITE)
	if model:
		_react_to(attacker, h, heavy, entry, lying)
		return "combo" if combo else "hit"
	# Capsule only (no animations): placeholder stun and push.
	_face_now(attacker.global_position - global_position)
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


## Where the attacker stands, as Combat_TakeHit's table entry (FUN_00308ec0 keeps it every frame at +0x4393):
## the game angle atan2(x, z) of the attacker in the victim's own frame (forward +Z): -45..45 front,
## 45..135 entry 3, -135..-45 entry 2, else behind.
func hit_direction(attacker: Fighter) -> int:
	var l := global_transform.basis.inverse() * (attacker.global_position - global_position)
	var ang := rad_to_deg(atan2(-l.x, -l.z))   # the fighter's forward is -Z: turn 180° into the game's frame
	if ang > -45.0 and ang <= 45.0:
		return DIR_FRONT
	if ang > 45.0 and ang <= 135.0:
		return DIR_RIGHT
	if ang > -135.0 and ang <= -45.0:
		return DIR_LEFT
	return DIR_BEHIND


## Picks and starts the game's reaction (Combat_TakeHit 0x0030DFD0): a knockdown hit (reaction 0x20) or a
## KO uses the knockdown rows; otherwise the kind from the hit, in the heavier set when `heavy`, or the wall
## rows when a wall is right behind the victim. The action's goto decides: lying (19/20) = knockdown.
func _react_to(attacker: Fighter, h: MoveHit, heavy: bool, entry: int, lying: bool) -> void:
	var ko := hp <= 0
	var action := 0
	var e := entry
	if ko or (h.reaction & 0x20 and not lying):
		var row := (2 if lying else 1) if ko else 0
		if row == 2:
			e = DIR_LEFT if _face_down() else DIR_BEHIND   # KO on the floor: face down 231, face up 230
		action = model.reaction_action("knockdown", row, DIRECTIONS[e])
		last_reaction = "a%d %s knockdown row %d" % [action, DIRECTIONS[e], row]
	else:
		var kind := reaction_kind(h, lying, _face_down(), posture)
		e = turned_entry(kind, entry, h.reaction_detail)
		if not lying and not kind in [8, 0x15, 0xE, 0x14, 6, 0xB] and _wall_behind(attacker):
			var row := 1 if hp <= max_hp / 2 else 0
			action = model.reaction_action("wall", row, DIRECTIONS[e])
			last_reaction = "a%d %s wall row %d" % [action, DIRECTIONS[e], row]
		else:
			action = model.reaction_action(str(1 if heavy else 0), kind, DIRECTIONS[e])
			last_reaction = "a%d %s kind %d set %d" % [action, DIRECTIONS[e], kind, 1 if heavy else 0]
	_react_action = action
	_react = model.action_info(action)
	_react_count += 1
	var then := int(_react.get("then", 1))
	pending_knockback = Vector3.ZERO   # the knockback is the reaction's own hip travel
	if then in [19, 20]:
		_down_action = then
		_getup_action = int(model.action_info(then).get("then", 22))
		var g := model.action_info(_getup_action)
		_getup_frames = int(g["release"]) if int(g.get("release", -1)) > 0 else int(g.get("frames", GETUP_FRAMES))
		stun = 0
		_enter(State.KNOCKDOWN)
		_track_status(action, 0)   # the knockdowns 649-652 and KOs set MATCHLESS on frame 0; launches and big staggers don't
		_shake_camera(0.6)
	else:
		var rel := int(_react.get("release", -1))
		stun = rel if rel > 0 else int(_react.get("frames", 30))
		_enter(State.HITSTUN)
		_track_status(action, 0)
		_shake_camera(0.25)


## Combat_TakeHit's wall test: a wall within 11 units (1.1 m) of the victim, facing the attacker (the game
## compares the wall's normal with the attacker's facing within 60°). Remake: one ray along the push.
func _wall_behind(attacker: Fighter) -> bool:
	var from := global_position + Vector3.UP
	var q := PhysicsRayQueryParameters3D.create(from, from + attacker.forward() * WALL_RANGE, LAYER_WORLD, [get_rid()])
	var r := get_world_3d().direct_space_state.intersect_ray(q)
	if r.is_empty():
		return false
	return -(r["normal"] as Vector3).dot(attacker.forward()) >= 0.5


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

	_shield.visible = model == null and state in [State.GUARD, State.BLOCKSTUN]
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

## Reaction kind for a hit, in Combat_TakeHit 0x0030DFD0's order (docs/ANIMATION.md, "Hit reactions"): hit on the
## floor (9 face up, 10 face down), the big reaction bits (0x10 -> 8, 0x100 -> 0xE: checked in the sandbox PCSX2, Double
## Whip's 0x100 plays 340), crouching hit by a mid / low (6), in the air (5: posture 0x20, a launched fighter hit again
## re-launches), then the hit level, then the stagger detail bits. Knockdowns (reaction 0x20) and KOs use the knockdown
## rows instead (_react_to). Not modelled: kinds 4, 7, 0x12, 0x13 (same team, special states, weapon hits) and the
## class-row reactions 0x3E3-0x3E6 (reaction 0x40).
static func reaction_kind(h: MoveHit, lying := false, face_down := false, pose := 1) -> int:
	if lying:
		return 10 if face_down else 9
	for pair in [[0x800, 0x14], [0x1000, 0x15], [0x100, 0xE], [0x10, 8], [0x200, 0xD], [0x400, 0xF]]:
		if h.reaction & pair[0]:
			return pair[1]
	if pose & 2 and h.level & 0xC:
		return 6
	if pose & 0x20:
		return 5
	if h.level & 4:
		return 3
	if h.level & 8:
		return 0xB
	for pair in [[0x10, 1], [0x20, 2], [8, 0x10], [4, 0x11]]:
		if h.reaction_detail & pair[0]:
			return pair[1]
	return 0


## The guard-hit action for a blocked hit (the guard task 0x0030FF20): g_GuardActions' unarmed standing list,
## entry 2 / 3 when the target is to a side (never, while blocking needs it in front) or by the hit's detail bits
## (+0x4564 & 0x3C): 0x10 -> 2, 0x20 -> 3, 4 -> 4, 8 -> 5, else 1.
func guard_hit_action(h: MoveHit) -> int:
	var acts: Array = model.meta.get("guard", {}).get("stand", [821, 822, 826, 825, 823, 824])
	var i := 1
	match h.reaction_detail & 0x3C:
		0x10:
			i = 2
		0x20:
			i = 3
		4:
			i = 4
		8:
			i = 5
	return int(acts[i])


## Combat_TakeHit turns kinds 0xD, 0xF (big reactions) and 9, 10 (on the floor) sideways by the detail bits when
## hit from the front or behind: front 0x10 -> entry 2, 0x20 -> entry 3; behind the other way round. On the
## floor detail bit 4 means the front entry.
static func turned_entry(kind: int, entry: int, detail: int) -> int:
	if not kind in [0xD, 0xF, 9, 10]:
		return entry
	if kind in [9, 10] and detail & 4:
		return DIR_FRONT
	if entry == DIR_FRONT:
		return DIR_LEFT if detail & 0x10 else (DIR_RIGHT if detail & 0x20 else entry)
	if entry == DIR_BEHIND:
		return DIR_RIGHT if detail & 0x10 else (DIR_LEFT if detail & 0x20 else entry)
	return entry


## Poses the model for the current state and frame (every game frame, and before the hit checks of
## an attack frame). Animation frames advance with the game frames, at the move's speeds.
func _animate() -> void:
	if model == null:
		return
	var generic: Dictionary = model.meta.get("generic", {})
	match state:
		State.IDLE:
			if not _tail.is_empty() and _show_tail():
				return
			_show_action(int(generic.get("stance", 1)), "stance", state_frame)
		State.MOVE:
			_walk_frame += _walk_rate
			_show_action(_walk_action, "walk%d" % _walk_action, _walk_frame)
		State.GUARD:
			# The unarmed standing guard loop (action 821), blending in over its 10 frames.
			_show_action(int(generic.get("guard", 821)), "guard", state_frame)
		State.BLOCKSTUN:
			_show_track(_block_action, "block%d" % _react_count, state_frame)
		State.ATTACK:
			_show_move(move, move_id, state_frame)
		State.HITSTUN:
			_show_track(_react_action, "hit%d" % _react_count, state_frame)
		State.KNOCKDOWN:
			var n := int(_react.get("frames", 0))
			if state_frame < n:
				_show_track(_react_action, "hit%d" % _react_count, state_frame)
			else:
				_show_action(_down_action, "down%d" % _react_count, state_frame - n)
		State.GETUP:
			_show_track(_getup_action, "getup%d" % _react_count, state_frame)
		State.HOLD:
			var grab: Dictionary = model.meta.get("grab", {})
			var catch_a := int(grab.get("catch", [126])[0])
			var n := int(model.action_info(catch_a).get("frames", 0))
			if state_frame < n:
				_show_track(catch_a, "catch%d" % _react_count, state_frame)
			else:
				var hold_a := int(grab.get("hold", [124])[0])
				var m := maxi(1, int(model.action_info(hold_a).get("frames", 1)))
				_show_track(hold_a, "hold%d" % _react_count, (state_frame - n) % m)
		State.HELD:
			var info := model.action_info(_held_action)
			var m := maxi(1, int(info.get("frames", 1)))
			_show_track(_held_action, "held%d:%d" % [_react_count, _held_action], (state_frame % m) if _held_loop else state_frame)


## The rest of a move, reaction or getup after control came back; false (and the tail ends) once it's over.
func _show_tail() -> bool:
	var f := int(_tail["from"]) + state_frame
	if _tail.has("move"):
		var m: MoveData = _tail["move"]
		if f >= m.frames:
			_tail = {}
			return false
		_show_move(m, _tail["key"], f)
		return true
	var info := model.action_info(int(_tail["action"]))
	if f >= int(info.get("frames", 0)):
		_tail = {}
		return false
	_show_track(int(_tail["action"]), _tail["key"], f)
	return true


## Shows an action's first clip (stance, walk, lying...) with that action's blend.
func _show_action(action: int, key: String, frame: float) -> void:
	var clip := model.clip_for_action(action)
	if clip == "":
		clip = model.clip_for_action(1)
	var blend := int(model.action_info(action).get("blend", 8))
	model.show_clip(key, clip, frame, blend)


## Shows game frame `f` of an action with every clip of its motion script (reactions, knockdowns, getups;
## conv_anims.py simulates them like the game with action_sim.py).
func _show_track(action: int, key: String, f: int) -> void:
	var info := model.action_info(action)
	var at: Array = info.get("clip_at", [])
	if at.is_empty():
		_show_action(action, key, f)
		return
	var i := clampi(f, 0, at.size() - 1)
	var k := int(at[i])
	var c: Array = info["clips"][k]
	model.show_clip("%s:%d" % [key, k], "a%d" % int(c[0]), float(info["frame_at"][i]), int(c[3]))


## A move's clips in order (its motion script's play ops, MoveData.clip_frame), each blending in with its
## own blend frames.
func _show_move(m: MoveData, id: String, f: int) -> void:
	if m.clips.is_empty():
		_show_action(1, "stance", f)
		return
	var cf := m.clip_frame(f)
	var k := clampi(int(cf[0]), 0, m.clips.size() - 1)
	var c: PackedInt32Array = m.clips[k]
	model.show_clip("%s:%d" % [id, k], "a%d" % c[0], float(cf[1]), c[3])


# --- Grabs (read from Fighter_HandleCommand, Fighter_PickWeaponMove, Combat_ResolveHit; docs/ANIMATION.md "Grabs") ---

## Standing and free to be caught: Combat_ResolveHit only lets a HOLD-category window catch a standing fighter
## (posture bit 1, Fighter_IsStandGuard counts) without NOT THROW (getting up), and in line of sight.
func can_be_grabbed() -> bool:
	return state in [State.IDLE, State.MOVE, State.ATTACK, State.GUARD, State.HITSTUN, State.BLOCKSTUN] \
		and holding == null and held_by == null and _hurtbox.collision_layer != 0


## The grab window touched `v`: the catch pair starts (attacker 126, victim 127), then the hold loop (124 / 125).
func _catch(v: Fighter) -> void:
	holding = v
	_hold_rear = v.hit_direction(self) == DIR_BEHIND
	v.held_by = self
	add_collision_exception_with(v)
	v.add_collision_exception_with(self)
	_react_count += 1
	_enter(State.HOLD)
	var grab: Dictionary = model.meta.get("grab", {}) if model else {}
	v._be_held(self, int(grab.get("catch", [126, 127])[1]), false)
	last_event = "%s grabs %s%s" % [display_name, v.display_name, " from behind" if _hold_rear else ""]


## Holding: the catch, then the hold loop; P / K throw (GRAB P / GRAB K, or REAR GRAB P / K from behind).
func _tick_hold() -> void:
	if holding == null or holding.held_by != self:
		_let_go()
		_enter(State.IDLE)
		return
	var grab: Dictionary = model.meta.get("grab", {}) if model else {}
	var catch_n := int(model.action_info(int(grab.get("catch", [126])[0])).get("frames", 30)) if model else 30
	if state_frame == catch_n:
		holding._be_held(self, int(grab.get("hold", [124, 125])[1]), _hold_rear, true)
	var code := _next_input()
	if code != "" and state_frame >= catch_n:
		var b := code.right(1)
		if b in ["P", "K"]:
			var found := move_set.match_single(("REAR GRAB " if _hold_rear else "GRAB ") + b)
			if not found.is_empty():
				var m: MoveData = found[0]
				var rear := _hold_rear
				var v := holding
				_start_move(m)
				v._be_held(self, m.pair_action, rear)
				return
	if state_frame >= catch_n + HOLD_FRAMES:
		_release_hold()


## Lets go without a throw: the remake's guess at the release pair (132 / 133).
func _release_hold() -> void:
	var v := holding
	_let_go()
	var grab: Dictionary = model.meta.get("grab", {}) if model else {}
	var pair: Array = grab.get("release", [132, 133])
	_enter(State.IDLE)
	if model:
		_tail = {"action": int(pair[0]), "key": "release%d" % _react_count, "from": 0}
	if v and v.held_by == self:
		v.held_by = null   # the victim is free again (it skips _end_held): no stale hold making it unhittable
	if v and v.model:
		v._react_action = int(pair[1])
		v._react = v.model.action_info(v._react_action)
		v._react_count += 1
		v.stun = int(v._react.get("frames", 30))
		v._enter(State.HITSTUN)


## Ends this fighter's hold (the victim keeps playing its side until its own end).
func _let_go() -> void:
	if holding:
		if holding.held_by == self and holding.state != State.HELD:
			holding.held_by = null
		remove_collision_exception_with(holding)
		holding.remove_collision_exception_with(self)
		holding = null


## Starts the partner action `action` for the holder `a`, placed like timeline op 0x17 (REVISION POS: x, y, z in game
## units relative to the holder, the angle added to its facing). A rear hold keeps the victim facing away.
func _be_held(a: Fighter, action: int, rear: bool, loop := false) -> void:
	held_by = a
	_held_action = action
	_held_loop = loop
	_react_count += 1
	_enter(State.HELD)
	_tail = {}
	var place: Array = model.action_info(action).get("place", []) if model else []
	if place == null or place.is_empty():
		place = [0.0, 0.0, 6.0, 180.0, 5]
	var ang := float(place[3])
	if rear and loop:
		ang = 0.0   # remake: no rear hold animation is loaded for Aaron's body, so the front hold faces away
	# The game's frame turned 180° into the fighter's (forward -Z): x -> -X, z -> -Z.
	var off := a.global_transform.basis * Vector3(-float(place[0]), 0.0, -float(place[2])) * 0.1
	global_position = Vector3(a.global_position.x + off.x, global_position.y, a.global_position.z + off.z)
	rotation.y = a.rotation.y + deg_to_rad(ang)


## Held: plays the partner action; a throw's side ends lying (its goto 19 / 20) or standing.
func _tick_held() -> void:
	if held_by == null or not is_instance_valid(held_by):
		_end_held(1)
		return
	if held_by.holding == self and held_by.state == State.HOLD:
		return   # the holder drives the catch and the hold loop
	var info := model.action_info(_held_action) if model else {}
	if _held_loop or held_by.holding != self and held_by.state == State.HOLD:
		_end_held(1)   # let go before a throw
	elif state_frame >= int(info.get("frames", 60)):
		_end_held(int(info.get("then", 1)))


func _end_held(then: int) -> void:
	var a := held_by
	held_by = null
	if a:
		remove_collision_exception_with(a)
		a.remove_collision_exception_with(self)
		if a.holding == self:
			a.holding = null
	if model and then in [19, 20]:
		# Thrown: lie down (the throw's clips were the fall), then get up like after a knockdown.
		_react_action = _held_action
		_react = {"frames": 0}
		_down_action = then
		_getup_action = int(model.action_info(then).get("then", 22))
		var g := model.action_info(_getup_action)
		_getup_frames = int(g["release"]) if int(g.get("release", -1)) > 0 else int(g.get("frames", GETUP_FRAMES))
		_enter(State.KNOCKDOWN)
		state_frame = 1
		return
	_enter(State.IDLE)


## Throw damage (timeline op 0x2B): the attacker's current hit record, through the damage formula.
func take_throw(attacker: Fighter, h: MoveHit) -> void:
	var dmg := damage_from(attacker, h) if attacker.real_style() else h.damage
	if dmg <= 0:
		return
	hp -= dmg
	last_damage = dmg
	combo_taken += 1
	_start_flash(Color.WHITE)
	_shake_camera(0.4)
	attacker.combo_hits += 1
	attacker.combo_damage += dmg
	attacker.last_event = "%s throws %s (%d)" % [attacker.move.move_name, display_name, dmg]
