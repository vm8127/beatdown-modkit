class_name FighterModel
extends Node3D
## The animated look of a fighter (M4): a rigged model from res://assets_ripped/models/ posed by the
## clips of res://assets_ripped/anims/<set>.glb, plus that set's JSON (clip lengths and loops, the
## generic actions, the hit reaction tables, the attack spheres' bones), all made by
## remake/tools/conv_anims.py. Clips are named by anim id: "a34" is anim 34 (Blade Cut).
##
## No AnimationPlayer: the Fighter tells this node every game frame which clip to show, at which
## animation frame, with how many blend frames (`show_clip`), and the pose is sampled from the
## Animation resources directly. So the animation follows the fighter's fixed-frame state exactly
## (pause, frame step, slow motion and hitstop freeze it), like the game's motion update.
##
## Blending is the game's (docs/ANIMATION.md, "Playing a motion"): when the clip changes, the pose at
## that moment is frozen and the new clip is blended in from it over the blend frames (linear weight,
## slerp per bone). Blend 0 snaps.
##
## Root motion: in the game the hips carry the travel of moves and hit reactions (a stagger pushes the
## victim 0.33 m back, a knockdown up to 4 m: that is the game's knockback, there is no separate push).
## Each shown frame, `root_delta` is how far the clip's hips moved on the floor (x/z) since the last
## frame of the same clip, in world space; the Fighter turns it into velocity so the capsule carries it
## (and collision stops it). The model pins the hips' floor position to the body (this node shifts by
## it), so the hips stay over the capsule. Vertical hip motion stays in the animation.

const MODEL_DIR := "res://assets_ripped/models/%s.glb"
const ANIM_DIR := "res://assets_ripped/anims/%s"
const MOVING := ["hips", "spine"]   ## the only bones with translation keys (docs/ANIMATION.md)

var meta: Dictionary = {}           ## the anim set's JSON
var skeleton: Skeleton3D

var _anims := {}                    ## clip name -> Animation
var _tracks := {}                   ## clip name -> [[bone index, rotation track, position track]]
var _key := ""                      ## what's shown now (changes start a blend)
var _clip := ""
var _blend := 0
var _since := 0                     ## game frames since the key changed
var _from_rot: Array[Quaternion] = []
var _from_pos: Array[Vector3] = []
var _hips := -1
var _hips_ref := Vector3.ZERO       ## hips' floor position (x, z) in the stance's first frame
var _root_prev := Vector3.ZERO      ## this clip's raw hips floor position on the last shown frame
var _root_frame := -1.0
var _shown_tick := -1               ## physics frame of the last show_clip (a second call in a frame changes nothing)
var root_delta := Vector3.ZERO      ## world-space floor travel of the hips on the last shown frame
var _strides := {}                  ## stride_speed cache
var _body := []                    ## g_BodySpheres: [bone index, offset, radius] (fighters push apart with these)
var _parts := {}                    ## attack part -> {"bone": index, "offset": Vector3, "radius": float}


## True when the model and the animation set exist (run remake_assets.py), so a fighter can use them.
static func available(model_name: String, anim_set: String) -> bool:
	return model_name != "" and anim_set != "" and ResourceLoader.exists(MODEL_DIR % model_name) \
		and ResourceLoader.exists(ANIM_DIR % anim_set + ".glb") and FileAccess.file_exists(ANIM_DIR % anim_set + ".json")


## Loads everything; false if something is missing or unusable (the fighter keeps its capsule).
func setup(model_name: String, anim_set: String) -> bool:
	var f := FileAccess.open(ANIM_DIR % anim_set + ".json", FileAccess.READ)
	if f == null:
		return false
	var m = JSON.parse_string(f.get_as_text())
	if not (m is Dictionary):
		return false
	meta = m
	var model := (load(MODEL_DIR % model_name) as PackedScene).instantiate() as Node3D
	skeleton = model.get_node_or_null("Skeleton3D") as Skeleton3D
	if skeleton == null:
		model.free()
		return false
	add_child(model)
	rotation.y = PI   # the models face +Z; a fighter's forward is -Z
	var lib_root := (load(ANIM_DIR % anim_set + ".glb") as PackedScene).instantiate()
	var ap := lib_root.find_child("AnimationPlayer", true, false) as AnimationPlayer
	if ap:
		for a in ap.get_animation_list():
			_anims[String(a)] = ap.get_animation(a)
	lib_root.free()
	for i in skeleton.get_bone_count():
		_from_rot.append(skeleton.get_bone_pose_rotation(i))
		_from_pos.append(skeleton.get_bone_pose_position(i))
	_hips = skeleton.find_bone("hips")
	for p in meta.get("attack_parts", []):
		var o: Array = p["offset"]
		_parts[int(p["part"])] = {"bone": skeleton.find_bone(p["bone"]), "offset": Vector3(o[0], o[1], o[2]),
			"radius": float(p["radius"])}
	for p in meta.get("body_parts", []):
		var o: Array = p["offset"]
		var b := skeleton.find_bone(p["bone"])
		if b >= 0:
			_body.append([b, Vector3(o[0], o[1], o[2]), float(p["radius"])])
	var stance := clip_for_action(int(meta.get("generic", {}).get("stance", 1)))
	if has_clip(stance) and _hips >= 0:
		_hips_ref = _sample_pos(stance, _hips, 0.0)
		_hips_ref.y = 0.0
	return not _anims.is_empty()


func has_clip(clip: String) -> bool:
	return _anims.has(clip)


## Length of a clip in animation frames (60 per second).
func clip_frames(clip: String) -> int:
	return int(meta["clips"][clip]["frames"]) if meta.get("clips", {}).has(clip) else 0


func clip_loops(clip: String) -> bool:
	return meta.get("clips", {}).get(clip, {}).get("loop", false)


## The clip an action plays first (its motion script's first play op), "" if unknown.
func clip_for_action(action: int) -> String:
	var a: Dictionary = meta.get("actions", {}).get(str(action), {})
	return ("a%d" % int(a["anim"])) if a.has("anim") and int(a["anim"]) >= 0 else ""


## {anim, blend, then, loop} of a generic or reaction action (conv_anims.py), {} if unknown.
func action_info(action: int) -> Dictionary:
	return meta.get("actions", {}).get(str(action), {})


## The reaction action from the game's tables (conv_anims.py): `table` "0" / "1" (reaction sets by kind),
## "knockdown" (rows 0 down, 1 KO, 2 KO while lying) or "wall" (rows 0, 1), `row` the kind or row, and the
## direction entry "behind", "front", "left" or "right". 0 if unknown.
func reaction_action(table: String, row: int, direction: String = "front") -> int:
	var s: Dictionary = meta.get("reactions", {}).get(table, {})
	var k: Dictionary = s.get(str(row), {})
	return int(k.get(direction, 0))


## Shows `clip` at animation frame `frame`. A new `key` (move, clip index, reaction...) freezes the
## current pose and blends into the clip over `blend` game frames. Called every game frame; a second call
## in the same physics frame re-poses without advancing the blend or adding root motion.
func show_clip(key: String, clip: String, frame: float, blend: int) -> void:
	if not _anims.has(clip):
		return
	var tick := Engine.get_physics_frames()
	var again := tick == _shown_tick and key == _key
	_shown_tick = tick
	var raw := _floor_pos(clip, frame)
	if key != _key:
		_root_prev = raw
		_root_frame = frame
		for i in skeleton.get_bone_count():
			_from_rot[i] = skeleton.get_bone_pose_rotation(i)
			_from_pos[i] = skeleton.get_bone_pose_position(i)
		_key = key
		_clip = clip
		_blend = blend
		_since = 0
	elif not again:
		_since += 1
	# Floor travel of the clip's own hips since its last shown frame (none when a loop wraps).
	var d := Vector3.ZERO if frame < _root_frame else raw - _root_prev
	if not again:
		root_delta = skeleton.global_transform.basis * d if skeleton else Vector3.ZERO
		root_delta.y = 0.0
	_root_prev = raw
	_root_frame = frame
	var anim: Animation = _anims[clip]
	var t := frame / 60.0
	if clip_loops(clip) and anim.length > 0.0:
		t = fmod(t, anim.length)
	t = clampf(t, 0.0, anim.length)
	var w := 1.0 if _blend <= 0 else clampf(float(_since) / _blend, 0.0, 1.0)
	for tr in _tracks_of(clip):
		var b: int = tr[0]
		if tr[1] >= 0:
			var q := anim.rotation_track_interpolate(tr[1], t)
			skeleton.set_bone_pose_rotation(b, _from_rot[b].slerp(q, w) if w < 1.0 else q)
		if tr[2] >= 0:
			var p := anim.position_track_interpolate(tr[2], t)
			skeleton.set_bone_pose_position(b, _from_pos[b].lerp(p, w) if w < 1.0 else p)
	# Pin the hips' floor position to the body (the capsule carries it; see the header). The model is
	# turned 180° (rotation.y = PI), so its local x/z offsets go the other way in the parent.
	if _hips >= 0:
		var hp := skeleton.get_bone_pose_position(_hips) - _hips_ref
		position.x = hp.x
		position.z = hp.z


## The current clip key (for the overlay).
func current() -> String:
	return "%s %s" % [_key, _clip]


## World centre and radius of an attack sphere (g_AttackSpheres part), or [] if unknown.
func part_sphere(part: int) -> Array:
	if not _parts.has(part) or _parts[part]["bone"] < 0:
		return []
	var p: Dictionary = _parts[part]
	var g := skeleton.global_transform * skeleton.get_bone_global_pose(p["bone"])
	return [g * (p["offset"] as Vector3), p["radius"]]


## A clip's own walking speed (m/s at playback 1.0) along `dir` (skeleton space, forward +Z): the median speed at
## which the lower foot moves backwards under the hips, sampled once per clip and cached. 0 if unknown.
func stride_speed(clip: String, dir: Vector3) -> float:
	var key := "%s %s" % [clip, dir]
	if _strides.has(key):
		return _strides[key]
	var feet := [skeleton.find_bone("foot_r"), skeleton.find_bone("foot_l")]
	if not _anims.has(clip) or feet.has(-1):
		return 0.0
	var anim: Animation = _anims[clip]
	var keep := []
	for i in skeleton.get_bone_count():
		keep.append([skeleton.get_bone_pose_rotation(i), skeleton.get_bone_pose_position(i)])
	var speeds := []
	var prev := []
	var n := clip_frames(clip)
	for f in n + 1:
		var t := minf(f / 60.0, anim.length)
		for tr in _tracks_of(clip):
			if tr[1] >= 0:
				skeleton.set_bone_pose_rotation(tr[0], anim.rotation_track_interpolate(tr[1], t))
			if tr[2] >= 0:
				skeleton.set_bone_pose_position(tr[0], anim.position_track_interpolate(tr[2], t))
		var hips := skeleton.get_bone_global_pose(_hips).origin if _hips >= 0 else Vector3.ZERO
		var pos := []
		for b in feet:
			var q := skeleton.get_bone_global_pose(b).origin - hips
			pos.append(q)
		if prev.size() == 2:
			var low := 0 if pos[0].y < pos[1].y else 1
			speeds.append(-((pos[low] - prev[low]) * 60.0).dot(dir.normalized()))
		prev = pos
	for i in keep.size():
		skeleton.set_bone_pose_rotation(i, keep[i][0])
		skeleton.set_bone_pose_position(i, keep[i][1])
	speeds.sort()
	var v: float = speeds[speeds.size() / 2] if speeds.size() > 0 else 0.0
	_strides[key] = v * skeleton.global_transform.basis.get_scale().x
	return _strides[key]


## The body spheres on the posed bones, as world [centre, radius] pairs ([] without the data).
func body_spheres() -> Array:
	var out := []
	for b in _body:
		var g := skeleton.global_transform * skeleton.get_bone_global_pose(b[0])
		out.append([g * (b[1] as Vector3), b[2]])
	return out


func _tracks_of(clip: String) -> Array:
	if _tracks.has(clip):
		return _tracks[clip]
	var anim: Animation = _anims[clip]
	var by_bone := {}
	for i in anim.get_track_count():
		var path := String(anim.track_get_path(i))
		var bone_name := path.get_slice(":", 1)
		var b := skeleton.find_bone(bone_name)
		if b < 0:
			continue
		var e: Array = by_bone.get(b, [b, -1, -1])
		match anim.track_get_type(i):
			Animation.TYPE_ROTATION_3D:
				e[1] = i
			Animation.TYPE_POSITION_3D:
				e[2] = i
		by_bone[b] = e
	_tracks[clip] = by_bone.values()
	return _tracks[clip]


## The clip's raw hips position on the floor (x, z; skeleton space) at an animation frame.
func _floor_pos(clip: String, frame: float) -> Vector3:
	if _hips < 0:
		return Vector3.ZERO
	var anim: Animation = _anims[clip]
	var p := _sample_pos(clip, _hips, clampf(frame / 60.0, 0.0, anim.length))
	p.y = 0.0
	return p


func _sample_pos(clip: String, bone: int, t: float) -> Vector3:
	for tr in _tracks_of(clip):
		if tr[0] == bone and tr[2] >= 0:
			return (_anims[clip] as Animation).position_track_interpolate(tr[2], t)
	return skeleton.get_bone_pose_position(bone)
