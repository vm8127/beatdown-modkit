class_name MoveData
extends Resource
## One move (in the game: one action). The placeholder moves are .tres files in game/moves/;
## the real ones are generated from the game's tables by remake/tools/conv_moves.py into
## res://assets_ripped/moves/<style>.tres (docs/ANIMATION.md, docs/MECHANICS.md).
##
## Times are in game frames (60 per second) from the start of the move. Distances in metres,
## speeds in m/s.

@export var move_name := "Move"
@export_enum("arm", "leg") var limb := "arm"
@export_range(0, 1) var side := 0   ## which arm: 0 right, 1 left

@export_group("Timing")
@export var frames := 30            ## total length (the animation's end); back to stance after it
@export var active_start := 8       ## placeholder moves: first frame the hitbox is out
@export var active_end := 10        ## placeholder moves: last frame (real moves use `hits`)
@export var cancel_start := -1      ## combo window: a press made during the move is matched against
@export var cancel_end := -1        ## the command list in [start, end] (the game: one frame, op 0x16)
@export var next: Dictionary = {}   ## placeholder moves: button ("P", "K") -> MoveData
@export var release_frame := -1     ## control returns here, before `frames` (op 0x3C; -1: at the end)
@export var combo_window := false   ## timeline op 0x15: starts the combo count at 1
@export var invincible := PackedVector2Array()   ## (first, last) frame ranges that take no damage (MATCHLESS)

@export_group("Hit")
@export var hits: Array = []        ## MoveHit windows; empty for placeholder moves (built from the fields below)
@export var damage := 10
@export var hitstop := 6            ## frames both fighters freeze on contact
@export var hitstun := 18           ## frames the victim can't act
@export var knockback := 2.0        ## push speed
@export var knockdown := false
@export var launch := 5.0           ## upward speed of a knockdown

@export_group("Hitbox")
@export var reach := 0.9            ## sphere centre: this far in front of the fighter
@export var height := 1.35          ## and this high (placeholder moves)
@export var radius := 0.4
@export var lunge := 1.0            ## forward speed during startup (placeholder moves)
@export var root_z := PackedFloat32Array()   ## real moves: hip forward offset per frame (root motion, m)

@export_group("Game data")          ## where it came from; the clip fields are for the animated fighter (M3/M4)
@export var action_id := 0
@export var anim_id := -1
@export var anim_group := -1
@export var anim_start := 0         ## animation frames played (the motion script's play op)
@export var anim_end := -1
@export var blend := 8              ## blend frames into this clip
@export var anim_cancel := -1       ## cancel point, animation frames
@export var anim_release := -1
@export var speeds := PackedVector2Array()   ## (animation frame, playback speed) changes
@export var clips: Array = []       ## every play op: PackedInt32Array(anim id, start, end, blend)
@export var frame_clip := PackedInt32Array()     ## per game frame: index in `clips` (action_sim.py: every clip, in order)
@export var frame_anim := PackedFloat32Array()   ## per game frame: animation frame shown
@export var throws := PackedInt32Array()         ## game frames of timeline op 0x2B (throw damage on the held target)
@export var then_action := -1       ## the action the motion script continues with (1 = stance)
@export var throw_hits: Array = []  ## MoveHit per throw-damage op (0x2B): `start` = game frame, the hit record then current
@export var pair_action := 0        ## the partner's action (g_ActionEvents +8): what the held victim plays during this throw
@export var place := PackedFloat32Array()   ## op 0x17 REVISION POS: x, y, z (game units), angle (degrees), frames
@export var attack_kind := 0        ## hit table header kind bits
@export var cost := 0               ## TIRED meter cost (hit table header +4)
@export var notes := PackedStringArray()

var _legacy_hits: Array = []
var _anim_frames := PackedFloat32Array()


## The hit windows: `hits`, or one built from the placeholder fields.
func get_hits() -> Array:
	if hits.size() > 0:
		return hits
	if _legacy_hits.is_empty():
		var h := MoveHit.new()
		h.start = active_start
		h.end = active_end
		h.damage = damage
		h.hitstop = hitstop
		h.hitstun = hitstun
		h.knockback = knockback
		h.knockdown = knockdown
		h.launch = launch
		h.radius = radius
		_legacy_hits = [h]
	return _legacy_hits


func is_active(f: int) -> bool:
	for h in get_hits():
		if (h as MoveHit).is_active(f):
			return true
	return false


func cancel_open(f: int) -> bool:
	return cancel_start >= 0 and f >= cancel_start and f <= cancel_end


func is_invincible(f: int) -> bool:
	for r in invincible:
		if f >= r.x and f <= r.y:
			return true
	return false


## Frame on which the fighter is free again (release point or the end).
func control_frame() -> int:
	return release_frame if release_frame >= 0 else frames


## Height of the capsule's hit sphere for a window.
func hit_height(h: MoveHit) -> float:
	return h.height() if hits.size() > 0 else height


## Animation frame shown on game frame `f` of the move: the timeline's speed ops (`speeds`) step it
## like conv_moves.Timing (a speed op at animation frame n applies once the whole frame reaches n).
func anim_frame_at(f: int) -> float:
	if _anim_frames.is_empty():
		var a := 0.0
		var sp := 1.0
		for g in frames + 1:
			_anim_frames.append(a)
			for s in speeds:
				if s.x <= floorf(a + 1e-6):
					sp = s.y
			a += sp
	return _anim_frames[clampi(f, 0, _anim_frames.size() - 1)]


## [clip index, animation frame] on game frame `f` (every clip of the motion script, in order); placeholder
## moves and old resources fall back to the first clip at the timeline's speeds.
func clip_frame(f: int) -> Array:
	if frame_clip.size() > 0:
		var i := clampi(f, 0, frame_clip.size() - 1)
		return [frame_clip[i], frame_anim[i]]
	return [0, anim_start + anim_frame_at(f)]


## Forward root motion between two frames (metres); 0 for placeholder moves.
func root_step(f: int) -> float:
	if root_z.size() < 2 or f <= 0:
		return 0.0
	var a := mini(f - 1, root_z.size() - 1)
	var b := mini(f, root_z.size() - 1)
	return root_z[b] - root_z[a]
