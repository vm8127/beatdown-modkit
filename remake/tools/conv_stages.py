"""Converter: stages (areas) -> stages/area_NN.glb (render world + props), area_NN_collision.glb, area_NN.json.

The decoding is in tools/stagekit.py (area packs, RpWorld, collision clumps, doors, spots; docs/STAGES.md) and
tools/ps2tex.py (PS2-native textures; docs/FORMATS.md). This module only writes glTF and JSON, in metres (x 0.1).

- area_NN.glb: node "world" (the RpWorld, one primitive per material) and node "props" (the props at their PB
  placements). Lighting is baked into the prelit vertex colours, so the materials are unlit (KHR_materials_unlit)
  with COLOR_0 = prelit colour x material colour. Materials named "... [add]" should blend additively.
- area_NN_collision.glb: nodes "walls", "floor", "camera" (the three collision meshes) and "door_panels"; Godot
  turns them into concave (trimesh) shapes.
- area_NN.json: name, lights, music and sound banks, far clip, battle spots, doors in the game's order (destination,
  entrance, arrival point, zone triangles, lock flag), spawn point, items per story stage, unplaced props.
- Areas with random variants (DOWNTOWN STREET: FSTAGE 1, 2, 3, 24) get one set per entry: area_01.* is the first,
  area_01_eNN.* the others.
- area_NN_spare.glb: props no PB placement uses (the subway's drums), each at the origin.
"""
import json
import math
import os
import struct
import types

import ps2tex
import rwkit
import stagekit
from gltf_writer import Gltf

SCALE = 0.1          # RenderWare units are about 10 cm
# PS2 convention (guess, picked by eye in Godot): vertex colour 0x80 = full texture brightness
PRELIT_SCALE = 2.0

ITEM_KINDS = 0x00589C40   # pickup kinds, 0x84 bytes each (0x00347FC0); +0x54 lift above the floor
AREAS = [5, 1]       # ABANDONED SUBWAY STATION, DOWNTOWN STREET (every FSTAGE variant of each)


def _srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _vcolor(prelit, matcol):
    rgb = tuple(_srgb_to_linear(min(1.0, prelit[i] / 255 * PRELIT_SCALE * matcol[i] / 255)) for i in range(3))
    return rgb + (prelit[3] / 255 * matcol[3] / 255,)


def _alpha_kind(tex):
    """'blend' for soft alpha, 'mask' for cut-outs (grates), 'add' for opaque glows on black (sparks, light
    covers: mostly black pixels; the game sets their additive blending in code, not in the data, so this is a
    guess by look), None when opaque."""
    a = tex.rgba[3::4]
    if all(x == 255 for x in a):
        r = tex.rgba
        n = len(a)
        black = sum(1 for i in range(n) if r[4 * i] + r[4 * i + 1] + r[4 * i + 2] < 24)
        return "add" if black > n // 2 else None
    soft = sum(1 for x in a if 16 < x < 240)
    return "blend" if soft > len(a) * 0.05 else "mask"


class _Materials:
    def __init__(self, g, texs):
        self.g, self.texs, self.cache = g, texs, {}

    def get(self, texname, color):
        key = (texname, tuple(color))
        if key not in self.cache:
            t = self.texs.get(texname) if texname else None
            if t is None:
                self.cache[key] = self.g.material(texname or "untextured", unlit=True)
            else:
                kind = _alpha_kind(t)
                # Additive has no glTF alpha mode: the name ends with " [add]" and the loader sets the blend mode
                name = texname + (" [add]" if kind == "add" else "")
                self.cache[key] = self.g.material(name, self.g.texture(texname, t.png()), unlit=True,
                                                  alpha_mask=kind == "mask", alpha_blend=kind == "blend")
        return self.cache[key]


def _primitives(mats, verts, colors, uvs, tris, matdefs):
    """Split triangles by material, compact the vertices; tris are (v0, v1, v2, material)."""
    by = {}
    for a, b, c, m in tris:
        if a != b and b != c and a != c:
            by.setdefault(m, []).extend((a, b, c))
    prims = []
    for m in sorted(by):
        md = matdefs[m]
        used = sorted(set(by[m]))
        remap = {v: i for i, v in enumerate(used)}
        pos = [tuple(x * SCALE for x in verts[v]) for v in used]
        col = [_vcolor(colors[v] if colors else (128, 128, 128, 255), md["color"]) for v in used]
        uv = [tuple(uvs[v]) for v in used] if uvs and md["texture"] else None
        prims.append((pos, None, uv, [remap[v] for v in by[m]], mats.get(md["texture"], md["color"]),
                      None, None, col))
    return prims


def _quat(q):
    l = math.sqrt(sum(x * x for x in q)) or 1.0
    return [x / l for x in q]


def write_render(secs, texs, path):
    g = Gltf()
    mats = _Materials(g, texs)
    w = stagekit.read_world(secs[1])
    prims = []
    for s in w["sectors"]:
        prims += _primitives(mats, s["verts"], s["colors"], s["uvs"][0] if s["uvs"] else None, s["tris"],
                             w["materials"])
    world = g.node("world", g.mesh("world", prims), root=False)
    # Props (section 7) at their PB placements (section 8); the clumps' frames are at the origin (seen)
    props = []
    p = secs[7]
    clumps = []
    for k in range(struct.unpack_from("<I", p, 0)[0]):
        o, s = struct.unpack_from("<II", p, 4 + 8 * k)
        clumps.append(rwkit.read_clumps(p[o:o + s]))
    meshes = {}
    placed = set()
    if len(secs) > 8 and secs[8][:2] == b"PB":
        for i in range(struct.unpack_from("<h", secs[8], 2)[0]):
            prop, x, y, z, qx, qy, qz, qw = struct.unpack_from("<i7f", secs[8], 4 + 32 * i)
            if prop not in meshes:
                pp = []
                for c in clumps[prop - 1]:
                    wm = rwkit.world_matrices(c.frames)
                    for fi, gi in c.atomics:
                        geo = c.geometries[gi]
                        verts = [rwkit.transform_point(v, wm[fi]) for v in geo.positions]
                        md = [{"color": m.color, "texture": m.texture} for m in geo.materials]
                        pp += _primitives(mats, verts, geo.colors, geo.uvs[0] if geo.uvs else None, geo.tris, md)
                meshes[prop] = g.mesh(f"prop_{prop:02d}", pp) if pp else None
            placed.add(prop)
            if meshes[prop] is not None:
                props.append(g.node(f"prop_{prop:02d}_{i:02d}", meshes[prop], root=False,
                                    translation=[x * SCALE, y * SCALE, z * SCALE], rotation=_quat([qx, qy, qz, qw])))
    kids = [world]
    if props:
        kids.append(g.node("props", children=props, root=False))
    g.node(os.path.splitext(os.path.basename(path))[0], children=kids)
    with open(path, "wb") as f:
        f.write(g.glb())
    _write_spare(clumps, placed, texs, path[:-4] + "_spare.glb")
    return w, len(clumps), placed


def _write_spare(clumps, placed, texs, path):
    """Props no PB placement uses (the subway's oil drums 12-14 and quad 15), each at the origin as node
    prop_NN, in their own file so a plain look at area_NN.glb doesn't show them; the loader can place them."""
    g = Gltf()
    mats = _Materials(g, texs)
    spare = []
    for k in range(1, len(clumps) + 1):
        if k in placed:
            continue
        pp = []
        for c in clumps[k - 1]:
            wm = rwkit.world_matrices(c.frames)
            for fi, gi in c.atomics:
                geo = c.geometries[gi]
                verts = [rwkit.transform_point(v, wm[fi]) for v in geo.positions]
                md = [{"color": m.color, "texture": m.texture} for m in geo.materials]
                pp += _primitives(mats, verts, geo.colors, geo.uvs[0] if geo.uvs else None, geo.tris, md)
        if pp:
            spare.append(g.node(f"prop_{k:02d}", g.mesh(f"prop_{k:02d}", pp), root=False))
    if os.path.exists(path):
        os.remove(path)
    if spare:
        g.node(os.path.splitext(os.path.basename(path))[0], children=spare)
        with open(path, "wb") as f:
            f.write(g.glb())


def write_collision(col, path):
    g = Gltf()
    kids = []
    groups = [(k, col[k]["vertices"], col[k]["triangles"]) for k in ("walls", "floor", "camera")]
    dv, dt = [], []
    for d in col["doors"]:
        if d["part"] == "panel":
            base = len(dv)
            dv += d["vertices"]
            dt += [[base + t[0], base + t[1], base + t[2], 0] for t in d["triangles"]]
    groups.append(("door_panels", dv, dt))
    for name, verts, tris in groups:
        if not tris:
            continue
        pos = [tuple(x * SCALE for x in v) for v in verts]
        idx = [i for t in tris for i in t[:3]]
        kids.append(g.node(name, g.mesh(name, [(pos, None, None, idx, None)]), root=False))
    g.node(os.path.splitext(os.path.basename(path))[0], children=kids)
    with open(path, "wb") as f:
        f.write(g.glb())


def _m(v):
    return [round(x * SCALE, 4) for x in v]


def _door(rec, names, flags):
    """One door in the game's order (stagekit.door_records): `index` is the entrance number other areas' doors
    name; arrival = where a player coming in through it stands; zone = the floor quad that uses it."""
    bb = stagekit.bbox_of(rec["zone"]["verts"])
    pb = stagekit.bbox_of(rec["panel"]["verts"])
    tags = flags.get("tags") or []
    lock = flags["first_flag"] + tags.index(rec["bonetag"]) if rec["bonetag"] in tags else None
    return {"index": rec["index"], "bonetag": rec["bonetag"], "dest_area": rec["dest_area"],
            "dest_name": names.get(rec["dest_area"], ""), "entrance": rec["entrance"],
            "into_deg": rec["into_deg"],
            "arrival": {"pos": _m(rec["arrival"]["pos"]), "angle_deg": rec["arrival"]["angle_deg"]}
            if "arrival" in rec else None,
            "zone_box": {"min": _m(bb[:3]), "max": _m(bb[3:])}, "panel_box": {"min": _m(pb[:3]), "max": _m(pb[3:])},
            "zone_tris": [[_m(rec["zone"]["verts"][i]) for i in t] for t in rec["zone"]["tris"]],
            # Door_Locked (0x00351480): story flag first_flag + (index in the area's tag list) set = locked
            "lock_flag": lock}


def area_json(col, d, nprops, placed, door_recs, names, variants, items):
    doors = [_door(r, names, col["door_flags"]) for r in door_recs]
    spots = [{"pos": _m(s["pos"]), "angle_deg": s["angle"], "use": s["use"]} for s in col["battle_spots"]]
    return {
        "area": col["area"], "name": col["name"], "fstage_entry": col["fstage_entry"],
        "units": "metres (game units x 0.1), y up",
        "ambient_light": d["ambient_light"],
        "lights": [{"angles_deg": d["light1_angles"][:2], "color": d["light1_color"]},
                   {"angles_deg": d["light2_angles"][:2], "color": d["light2_color"]}],
        "bgm": d["bgm"], "ambience": d["ambience"], "ambience_flag_b": d["ambience_flag_b"],
        "sound_banks": d["sound_banks"], "far_clip": round(d["far_clip"] * SCALE, 2),
        "battle_spots": spots,
        # Where a test spawns the player: the story-fight battle spot (the real arrival point per door is open)
        "spawn": spots[0] if spots else {"pos": [0, 0, 0], "angle_deg": 0},
        "doors": doors,
        "variants": variants,   # FSTAGE entries Area_Load picks from (docs/STAGES.md); this file is fstage_entry
        "door_flags": col["door_flags"],
        "wall_kinds": [m.get("wall_kind") for m in col["walls"]["materials"]],
        "items": items,
        "props_unplaced": [k for k in range(1, nprops + 1) if k not in placed],
    }


def _items(ar, col):
    """g_AreaObjects records (pos in metres) + the pickup lift: Stage_PlaceObjects puts an item at floor height +
    the kind's +0x54 (table 0x00589C40, 0x84 bytes per kind) + 0.3 units."""
    pf = ar.objects(col["area"])["props_for"]
    use = {1: pf["type1_sub1"], 2: pf["type1_sub2"], 3: pf["type1_sub3"]}
    out = []
    for r in col["objects"]:
        e = dict(r, pos=_m(r["pos"]))
        if r["type"] == 1:      # a prop: which one comes from g_AreaObjects +0x10..+0x13 by sub
            e["prop"] = use.get(r["sub"], -1)
        elif r["type"] in (2, 3):   # specials and weapons ride on prop +0x11
            e["prop"] = pf["type2_3"]
        if r["type"] == 4:
            o = ar.e.v2o(ITEM_KINDS + 0x84 * r["sub"])
            e["lift"] = round((struct.unpack_from("<f", ar.e.d, o + 0x54)[0] + 0.3) * SCALE, 4)
        out.append(e)
    return out


def convert(iso, out, log=print):
    os.makedirs(os.path.join(out, "stages"), exist_ok=True)
    written = []
    ar = stagekit.Areas(iso)
    names = {i: ar.definition(i)["name"] for i in range(stagekit.AREA_COUNT)}
    for area in AREAS:
        d = ar.definition(area)
        for vi, entry in enumerate(d["entries"]):
            secs = stagekit.sections(stagekit.read_entry(iso, entry))
            texs = {t.name: t for t in ps2tex.textures(secs[0])}
            base = f"stages/area_{area:02d}" + ("" if vi == 0 else f"_e{entry:02d}")
            w, nprops, placed = write_render(secs, texs, os.path.join(out, base + ".glb"))
            col = stagekit.collision_data(types.SimpleNamespace(iso=iso, area=area, entry=entry))
            write_collision(col, os.path.join(out, base + "_collision.glb"))
            recs = stagekit.door_records(secs[5]) if len(secs) > 5 and secs[5] else []
            with open(os.path.join(out, base + ".json"), "w") as f:
                json.dump(area_json(col, d, nprops, placed, recs, names, d["entries"], _items(ar, col)), f,
                          indent=1, sort_keys=True)
            log(f"  {base}.glb: {d['name']} (FSTAGE {entry}), {w['triangles']} world triangles, {len(texs)} textures, "
                f"{len(placed)} of {nprops} props placed, {len(recs)} doors; _collision.glb, .json")
            written += [base + ".glb", base + "_collision.glb", base + ".json"]
    return written
