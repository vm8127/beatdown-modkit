class_name GameArea
extends Node3D
## One area (a free-roam place, which is also where its fights happen) built from what
## remake/tools/conv_stages.py extracted (docs/STAGES.md): the render world and its props, the three
## collision meshes, the area's lights, its doors, battle spots and the items of a story stage.
##
##   stages/area_NN[_eMM].glb            world + props at their PB placements (unlit, prelit vertex colours)
##   stages/area_NN[_eMM]_spare.glb      props no PB placement uses (g_AreaObjects type-1 records use them)
##   stages/area_NN[_eMM]_collision.glb  walls, floor, camera, door panels -> trimesh StaticBody3Ds
##   stages/area_NN[_eMM].json           lights, music, battle spots, doors (game order), items
##
## area.tscn holds the fixed nodes (environment, two lights, empty groups); load_area() fills them, and
## can be called again to swap areas (a door). The level scene (res://levels/) owns the player and camera.

const LAYER_WORLD := 1        ## walls, floor, door panels: fighters and the camera collide with them
const LAYER_CAMERA := 16      ## the area's separate camera-collision mesh: only the camera arm uses it
const STAGES := "res://assets_ripped/stages/"
const DOOR_FACING_DEG := 90.0 ## 0x002E2930: the player must face the door within 90 degrees to use it

@export var area_id := 5
## FSTAGE entry for areas with random variants (DOWNTOWN STREET: 1, 2, 3, 24). -1 = the first one; the game
## picks one at random, never the same twice in a row (Area_Load).
@export var variant := -1
## Story stage (1-11; chapter): which g_AreaObjects items and props are placed. 2 = Chapter 2.
@export var story_stage := 2
@export var show_markers := true   ## battle spots, door zones and item markers (debug drawing)

var info := {}                 ## the area's JSON
var entry := 0                 ## the FSTAGE entry loaded
var doors: Array = []          ## info.doors: {index, bonetag, dest_area, entrance, into_deg, arrival, zone_tris...}
var battle_spots: Array = []   ## {pos: Vector3, angle_deg}
var walls_aabb := AABB()       ## bounds of the wall mesh: the area's playable outline (no separate bounds box)
var props_placed := 0          ## PB placements + g_AreaObjects props shown
var items_placed: Array = []   ## markers for the items of the story stage

@onready var _env: WorldEnvironment = $WorldEnvironment
@onready var _lights: Array[DirectionalLight3D] = [$Light1, $Light2]
@onready var _world: Node3D = $World
@onready var _collision: Node3D = $Collision
@onready var _markers: Node3D = $Markers


## The asset base path for an area (and FSTAGE entry), or "" when it wasn't converted.
static func base_path(id: int, fstage := -1) -> String:
	var b := STAGES + "area_%02d" % id
	if fstage > 0 and fstage != id:
		b += "_e%02d" % fstage
	return b if ResourceLoader.exists(b + ".glb") else ""


static func available(id: int) -> bool:
	return base_path(id) != ""


## Game angle (degrees; 0 = facing +z, 90 = +x: atan2(x, z)) -> Godot yaw for a node whose forward is -Z
## (Fighter, the camera).
static func yaw_from_game(angle_deg: float) -> float:
	return deg_to_rad(angle_deg) + PI


static func dir_from_game(angle_deg: float) -> Vector3:
	var a := deg_to_rad(angle_deg)
	return Vector3(sin(a), 0, cos(a))


## Builds area `id` (replacing the current one). False if it wasn't converted.
func load_area(id: int, fstage := -1) -> bool:
	var base := base_path(id)
	if base == "":
		push_error("area %d not converted: run python remake/tools/remake_assets.py ISO remake/godot/assets_ripped" % id)
		return false
	info = JSON.parse_string(FileAccess.get_file_as_string(base + ".json"))
	if fstage > 0 and base_path(id, fstage) != "":
		base = base_path(id, fstage)
		info = JSON.parse_string(FileAccess.get_file_as_string(base + ".json"))
	area_id = id
	entry = int(info.get("fstage_entry", id))
	_clear()
	var stage := (load(base + ".glb") as PackedScene).instantiate()
	_world.add_child(stage)
	fix_materials(stage)
	var props := stage.find_child("props", true, false)
	props_placed = props.get_child_count() if props else 0
	_add_collision(load(base + "_collision.glb") as PackedScene)
	_setup_lights()
	doors = info.get("doors", [])
	battle_spots = []
	for s in info.get("battle_spots", []):
		var p: Array = s["pos"]
		battle_spots.append({"pos": Vector3(p[0], p[1], p[2]), "angle_deg": float(s["angle_deg"])})
	_place_objects(base)
	if show_markers:
		_draw_markers()
	return true


func _clear() -> void:
	for group in [_world, _collision, _markers]:
		for c in group.get_children():
			group.remove_child(c)
			c.queue_free()
	items_placed.clear()


## glTF has no additive blending: conv_stages.py names those materials "... [add]" (sparks, light glows).
static func fix_materials(root: Node) -> void:
	for mi in root.find_children("*", "MeshInstance3D", true, false):
		var mesh: Mesh = (mi as MeshInstance3D).mesh
		for i in mesh.get_surface_count():
			var mat := mesh.surface_get_material(i) as BaseMaterial3D
			if mat and mat.resource_name.ends_with("[add]"):
				mat.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
				mat.depth_draw_mode = BaseMaterial3D.DEPTH_DRAW_DISABLED
				mat.cull_mode = BaseMaterial3D.CULL_DISABLED


## Each collision mesh becomes a StaticBody3D with a concave (trimesh) shape. The game's meshes are open
## (single walls, a floor sheet), so backface collision is on: they block from both sides.
func _add_collision(scene: PackedScene) -> void:
	var root := scene.instantiate()
	for mi in root.find_children("*", "MeshInstance3D", true, false):
		var m := mi as MeshInstance3D
		var faces := m.mesh.get_faces()
		var shape := ConcavePolygonShape3D.new()
		shape.set_faces(faces)
		shape.backface_collision = true
		var body := StaticBody3D.new()
		body.name = String(m.name)
		body.collision_layer = LAYER_CAMERA if String(m.name).begins_with("camera") else LAYER_WORLD
		body.collision_mask = 0
		var cs := CollisionShape3D.new()
		cs.shape = shape
		body.add_child(cs)
		_collision.add_child(body)
		if String(m.name) == "walls":
			walls_aabb = AABB(faces[0], Vector3.ZERO)
			for v in faces:
				walls_aabb = walls_aabb.expand(v)
	root.free()   # the collision glb's nodes sit at the origin (vertices are in area space)


## The area's two directional lights and ambient colour (AreaDef, docs/STAGES.md) light the fighters;
## the world itself is unlit. Angle convention (x pitch, y yaw in degrees) is a guess.
func _setup_lights() -> void:
	var env := _env.environment
	var amb: Array = info["ambient_light"]
	env.ambient_light_color = Color(amb[0], amb[1], amb[2])
	var lights: Array = info["lights"]
	for i in _lights.size():
		var l := _lights[i]
		l.visible = i < lights.size()
		if not l.visible:
			continue
		var ang: Array = lights[i]["angles_deg"]
		var c: Array = lights[i]["color"]
		l.rotation_degrees = Vector3(-float(ang[0]), float(ang[1]), 0)
		l.light_color = Color(c[0], c[1], c[2])


## g_AreaObjects records of the story stage (Stage_PlaceObjects): type 1 = a prop (a spare prop model),
## 4 = an item pickup (a marker for now), 3 weapons and 2 specials are markers too. Placed at floor height
## (+ the item kind's lift), turned by rot y.
func _place_objects(base: String) -> void:
	var spare: Node = null
	if ResourceLoader.exists(base + "_spare.glb"):
		spare = (load(base + "_spare.glb") as PackedScene).instantiate()
		fix_materials(spare)
	var holder := Node3D.new()
	holder.name = "StoryObjects"
	_world.add_child(holder)
	for r in info.get("items", []):
		var stages: Array = r["stages"]
		if not stages.has(float(story_stage)) and not stages.has(story_stage):
			continue
		var p: Array = r["pos"]
		var pos := Vector3(p[0], p[1], p[2])
		var fy = floor_height(pos)
		if fy != null:
			pos.y = float(fy) + float(r.get("lift", 0.0))
		var t := int(r["type"])
		if t == 1 and spare and spare.has_node("prop_%02d" % int(r.get("prop", -1))):
			var prop: Node3D = spare.get_node("prop_%02d" % int(r["prop"])).duplicate()
			prop.position = pos
			prop.rotation.y = deg_to_rad(float(r["rot_y"]))
			holder.add_child(prop)
			props_placed += 1
		elif t != 1:
			var m := _item_marker(r)
			m.position = pos
			holder.add_child(m)
			items_placed.append(m)
	if spare:
		spare.free()


func _item_marker(r: Dictionary) -> Node3D:
	var n := Node3D.new()
	n.name = "Item_%d_%d" % [int(r["type"]), int(r["sub"])]
	n.set_meta("record", r)
	var mi := MeshInstance3D.new()
	var box := BoxMesh.new()
	box.size = Vector3(0.25, 0.25, 0.25)
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(1.0, 0.85, 0.2)
	mat.emission_enabled = true
	mat.emission = Color(0.6, 0.45, 0.05)
	box.material = mat
	mi.mesh = box
	mi.position.y = 0.15
	mi.rotation_degrees = Vector3(0, 45, 35)
	n.add_child(mi)
	var l := Label3D.new()
	l.text = "%s %d" % [r.get("kind", "?"), int(r["sub"])]
	l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	l.font_size = 28
	l.pixel_size = 0.004
	l.position.y = 0.55
	l.no_depth_test = true
	n.add_child(l)
	return n


func _draw_markers() -> void:
	var spot_mat := _marker_mat(Color(1.0, 0.3, 0.2, 0.5))
	for i in battle_spots.size():
		var s: Dictionary = battle_spots[i]
		var ring := MeshInstance3D.new()
		ring.name = "BattleSpot%d" % i
		var cyl := CylinderMesh.new()
		cyl.top_radius = 0.4
		cyl.bottom_radius = 0.4
		cyl.height = 0.03
		cyl.material = spot_mat
		ring.mesh = cyl
		ring.position = s["pos"] + Vector3(0, 0.02, 0)
		_markers.add_child(ring)
		var arrow := MeshInstance3D.new()
		var bm := BoxMesh.new()
		bm.size = Vector3(0.08, 0.03, 0.5)
		bm.material = spot_mat
		arrow.mesh = bm
		arrow.position = Vector3(0, 0.02, 0.25)
		ring.add_child(arrow)
		ring.rotation.y = deg_to_rad(float(s["angle_deg"]))
	var zone_mat := _marker_mat(Color(0.2, 0.7, 1.0, 0.35))
	for d in doors:
		var st := SurfaceTool.new()
		st.begin(Mesh.PRIMITIVE_TRIANGLES)
		for tri in d["zone_tris"]:
			for v in tri:
				st.add_vertex(Vector3(v[0], v[1] + 0.03, v[2]))
		var mi := MeshInstance3D.new()
		mi.name = "DoorZone%d" % int(d["index"])
		mi.mesh = st.commit()
		mi.material_override = zone_mat
		_markers.add_child(mi)
		var l := Label3D.new()
		l.text = "%d -> %s (%s)" % [int(d["index"]), d["dest_name"], "entrance %d" % int(d["entrance"]) if d["entrance"] != null else "its door"]
		l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		l.font_size = 32
		l.pixel_size = 0.005
		l.no_depth_test = true
		var zb: Dictionary = d["zone_box"]
		var mn: Array = zb["min"]
		var mx: Array = zb["max"]
		l.position = Vector3((mn[0] + mx[0]) * 0.5, mn[1] + 1.2, (mn[2] + mx[2]) * 0.5)
		_markers.add_child(l)


func _marker_mat(c: Color) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.albedo_color = c
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	return m


# --- Queries ---------------------------------------------------------------------------------------

## Floor height under `pos` (a ray from 2 m above down to 20 m below on the world layer), or null.
func floor_height(pos: Vector3) -> Variant:
	var space := get_world_3d().direct_space_state
	var q := PhysicsRayQueryParameters3D.create(pos + Vector3(0, 2.0, 0), pos + Vector3(0, -20.0, 0), LAYER_WORLD)
	var hit := space.intersect_ray(q)
	return null if hit.is_empty() else (hit["position"] as Vector3).y


## Where a player coming through `entrance` from area `from_area` arrives (Door_ArrivalPoint 0x002E7B10 via
## Door_FindArrival 0x00351CF0): entrance n >= 1 = the n-th door of this area (game order); otherwise the door
## leading back to `from_area`; else door 1, else the spawn point. {pos: Vector3, angle_deg, door}.
func arrival(entrance: int, from_area := -1) -> Dictionary:
	var door: Dictionary = {}
	if entrance >= 1 and entrance <= doors.size():
		door = doors[entrance - 1]
	else:
		for d in doors:
			if int(d["dest_area"]) == from_area:
				door = d
				break
		if door.is_empty() and doors.size() > 0:
			door = doors[0]
	if not door.is_empty() and door["arrival"] != null:
		var p: Array = door["arrival"]["pos"]
		return {"pos": Vector3(p[0], p[1], p[2]), "angle_deg": float(door["arrival"]["angle_deg"]), "door": door}
	var s: Dictionary = info.get("spawn", {"pos": [0, 0, 0], "angle_deg": 0})
	var sp: Array = s["pos"]
	return {"pos": Vector3(sp[0], sp[1], sp[2]), "angle_deg": float(s["angle_deg"]), "door": {}}


## The door whose zone `pos` stands on, or {}. The game casts a short vertical ray (2 m above to 1.5 m
## below the point) at each door's zone quad (0x00351A70); here: point in triangle (x, z) and the zone's
## height within that range.
func door_at(pos: Vector3) -> Dictionary:
	for d in doors:
		for tri in d["zone_tris"]:
			var a := Vector3(tri[0][0], tri[0][1], tri[0][2])
			var b := Vector3(tri[1][0], tri[1][1], tri[1][2])
			var c := Vector3(tri[2][0], tri[2][1], tri[2][2])
			var y := (a.y + b.y + c.y) / 3.0
			if y > pos.y + 2.0 or y < pos.y - 1.5:
				continue
			if Geometry2D.point_is_inside_triangle(Vector2(pos.x, pos.z), Vector2(a.x, a.z), Vector2(b.x, b.z), Vector2(c.x, c.z)):
				return d
	return {}


## True when a fighter facing `forward` may use `door`: within 90 degrees of the door's way in.
static func facing_door(door: Dictionary, forward: Vector3) -> bool:
	var into := dir_from_game(float(door["into_deg"]))
	return forward.normalized().dot(into) >= cos(deg_to_rad(DOOR_FACING_DEG)) - 0.0001


## Battle_PlaceFighters / Area_PickBattleSpot mode 0: the spot nearest `pos` among spots 1..n-1
## (spot 0 is for story fights); a single spot is used as it is.
func nearest_battle_spot(pos: Vector3) -> int:
	if battle_spots.is_empty():
		return -1
	var best := 0 if battle_spots.size() == 1 else 1
	for i in range(1, battle_spots.size()):
		if (battle_spots[i]["pos"] as Vector3).distance_to(pos) < (battle_spots[best]["pos"] as Vector3).distance_to(pos):
			best = i
	return best


## True when `pos` is inside the area: within the wall mesh's bounds and over a floor.
func is_inside(pos: Vector3) -> bool:
	var box := walls_aabb.grow(0.3)
	if pos.x < box.position.x or pos.x > box.end.x or pos.z < box.position.z or pos.z > box.end.z:
		return false
	var fy = floor_height(pos + Vector3(0, 0.5, 0))
	return fy != null and absf(float(fy) - pos.y) < 1.0


func far_clip() -> float:
	return float(info.get("far_clip", 150.0))
