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
## Root motion: the fighter's body moves by the move's hip travel (MoveData.root_z), so the model
## pins the hips' forward travel to the body (this node shifts back by it): the hips stay over the
## capsule, and the capsule's collision decides where the fighter really is. Sideways and vertical
## hip motion stays in the animation.

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
var _hips_ref := 0.0                ## hips' forward position in the stance's first frame
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
	var stance := clip_for_action(int(meta.get("generic", {}).get("stance", 1)))
	if has_clip(stance) and _hips >= 0:
		_hips_ref = _sample_pos(stance, _hips, 0.0).z
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


## The reaction action for a reaction set (0 normal, 1 heavy) and kind, hit from the front.
func reaction_action(reaction_set: int, kind: int) -> int:
	var s: Dictionary = meta.get("reactions", {}).get(str(reaction_set), {})
	var k: Dictionary = s.get(str(kind), {})
	return int(k.get("front", 0))


## Shows `clip` at animation frame `frame`. A new `key` (move, clip index, reaction...) freezes the
## current pose and blends into the clip over `blend` game frames. Called once per game frame.
func show_clip(key: String, clip: String, frame: float, blend: int) -> void:
	if not _anims.has(clip):
		return
	if key != _key:
		for i in skeleton.get_bone_count():
			_from_rot[i] = skeleton.get_bone_pose_rotation(i)
			_from_pos[i] = skeleton.get_bone_pose_position(i)
		_key = key
		_clip = clip
		_blend = blend
		_since = 0
	else:
		_since += 1
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
	# Pin the hips' forward travel to the body (the capsule carries it; see the header).
	if _hips >= 0:
		position.z = skeleton.get_bone_pose_position(_hips).z - _hips_ref


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


func _sample_pos(clip: String, bone: int, t: float) -> Vector3:
	for tr in _tracks_of(clip):
		if tr[0] == bone and tr[2] >= 0:
			return (_anims[clip] as Animation).position_track_interpolate(tr[2], t)
	return skeleton.get_bone_pose_position(bone)
