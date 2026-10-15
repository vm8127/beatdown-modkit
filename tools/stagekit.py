#!/usr/bin/env python3
"""Stage (area) inspector for Beat Down: what an area is made of, and its collision (docs/STAGES.md).

An area id (0-56, the number Area_Current returns; not the "location" text numbering) picks
  * its area definition in the ELF, g_AreaDefs 0x005170F0 (0x104 bytes each: name, music, lights, battle spots,
    wall kinds per collision material),
  * FSTAGE.XAF entry = area id (+ a random variant for areas 1, 7, 19 and 47), a pack of 9 or 10 RenderWare
    streams: textures, the RpWorld render geometry, three collision clumps (walls, camera, floor), the doors clump
    and its animation, the props, the prop placements and prop animations,
  * the per-area object table g_AreaObjects 0x00422850 (items, weapons and props placed per story stage).

Read-only. Standard library only; the collision clumps are read with tools/rwkit.py (RenderWare clumps).
  python tools/stagekit.py areas ISO                     every area: id, name, FSTAGE entries, music, far clip
  python tools/stagekit.py pieces ISO 5                  the pieces of area 5 (ABANDONED SUBWAY STATION)
  python tools/stagekit.py collision ISO 5 [--json F] [--obj F]   walls, camera and floor triangles, doors, spots
  python tools/stagekit.py world ISO 5 --obj F           the render geometry (RpWorld) as an OBJ, for a quick look
  --entry N picks another FSTAGE entry for the area (a variant: 1, 2, 3, 24 for area 1).
Output files are converted game data: keep them out of git.
"""
import argparse
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bdkit  # noqa: E402

AREA_DEFS = 0x005170F0       # g_AreaDefs: 0x104 bytes per area id (Area_Def 0x0031CFC0)
AREA_DEF_SIZE = 0x104
AREA_COUNT = 57              # Area_Load clamps ids >= 0x39 (and 0) to 4
AREA_OBJECTS = 0x00422850    # g_AreaObjects: 0x28 bytes per area id
DOOR_FLAGS = 0x0058BDB4      # g_AreaDoorFlags: 0x14 bytes per area id
BATTLE_SPOT_DEFAULT = 0x00516980   # s16[4] per area: the spot used when the caller asks for -1
FIXED_BATTLE_POS = 0x00509930      # u32 per area: two fighter positions, used when the area has no spot list
NAME_TEXT = 386              # CDATA.XAF English text bank (area names are text 18000 + n)
SOUND_BANKS = 0x004337D0     # u32 per bank id: SOUND.XAF entry (def +4, +6)
# Area_Load's random variants (FSTAGE entry = area + offset); area 1 also loads entry 24 when a mission says so
VARIANTS = {1: [0, 1, 2, 23], 7: [0, 4], 19: [0, -1, 8], 47: [0, -19, -11]}
FAR_CLIP = {47: 2500.0, 46: 1800.0, 39: 1800.0, 19: 1800.0, 1: 1800.0, 8: 350.0}   # else 1500
SECTION_NAMES = ["textures", "world", "walls", "camera", "floor", "doors", "doors anim", "props", "prop placements",
                 "prop anims"]
COLLISION = {2: "walls", 3: "camera", 4: "floor"}


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------
def rw():
    try:
        import rwkit
    except ImportError:
        sys.exit("tools/rwkit.py (the RenderWare clump reader) is needed for collision and doors")
    return rwkit


def read_entry(iso, n):
    path = os.path.join(iso, "XAF", "FSTAGE.XAF")
    o, s = bdkit.xaf_entries(path)[n][1:3]
    with open(path, "rb") as f:
        f.seek(o)
        return f.read(s)


def sections(blob):
    """An area entry: u32 count, then count x {u32 offset, u32 size} from the entry start."""
    n = struct.unpack_from("<I", blob, 0)[0]
    out = []
    for k in range(n):
        o, s = struct.unpack_from("<II", blob, 4 + 8 * k)
        out.append(blob[o:o + s])
    return out


def chunks(data, off=0, end=None):
    end = len(data) if end is None else end
    out = []
    while off + 12 <= end:
        t, s, v = struct.unpack_from("<III", data, off)
        if v == 0 or off + 12 + s > end:
            break
        out.append((t, off + 12, s))
        off += 12 + s
    return out


def texture_names(sec):
    """TexDictionary (0x16) of PS2 native textures (0x15): each one's first String child is its name."""
    names = []
    for t, o, s in chunks(sec):
        if t != 0x16:
            continue
        for t2, o2, s2 in chunks(sec, o, o + s):
            if t2 == 0x15:
                for t3, o3, s3 in chunks(sec, o2, o2 + s2):
                    if t3 == 0x02:
                        names.append(sec[o3:o3 + s3].split(b"\0")[0].decode("latin1"))
                        break
    return names


def read_world(sec):
    """RpWorld (0x0B): Struct, MaterialList, then a tree of PlaneSectors (0x0A) and AtomicSectors (0x09)."""
    (t, o, s), = [c for c in chunks(sec) if c[0] == 0x0B][:1]
    kids = chunks(sec, o, o + s)
    st = sec[kids[0][1]:kids[0][1] + kids[0][2]]
    root_is_sector, ox, oy, oz, ntri, nvert, nplane, nsect, colsize, fmt = struct.unpack_from("<i3fiiiiiI", st, 0)
    bbox = struct.unpack_from("<6f", st, 40)
    mats = []
    mt, mo, ms = kids[1]
    for t2, o2, s2 in chunks(sec, mo, mo + ms):
        if t2 == 0x07:
            mk = chunks(sec, o2, o2 + s2)
            color = tuple(sec[mk[0][1] + 4:mk[0][1] + 8])
            tex = None
            for t3, o3, s3 in mk:
                if t3 == 0x06:
                    for t4, o4, s4 in chunks(sec, o3, o3 + s3):
                        if t4 == 0x02:
                            tex = sec[o4:o4 + s4].split(b"\0")[0].decode("latin1")
                            break
            mats.append({"color": color, "texture": tex})
    nuv = (fmt >> 16) & 0xFF or (1 if fmt & 4 else 0)
    sectors = []

    def atomic(o2, s2):
        sk = chunks(sec, o2, o2 + s2)
        so = sk[0][1]
        base, nt, nv = struct.unpack_from("<iii", sec, so)
        lo, hi = struct.unpack_from("<3f", sec, so + 12), struct.unpack_from("<3f", sec, so + 24)
        p = so + 44
        verts = [struct.unpack_from("<3f", sec, p + 12 * i) for i in range(nv)]
        p += 12 * nv
        if fmt & 0x10:
            p += 4 * nv          # normals, 3 x s8 + pad
        colors = None
        if fmt & 0x08:
            colors = [tuple(sec[p + 4 * i:p + 4 * i + 4]) for i in range(nv)]
            p += 4 * nv
        uvs = []
        for _ in range(nuv):
            uvs.append([struct.unpack_from("<2f", sec, p + 8 * i) for i in range(nv)])
            p += 8 * nv
        tris = []
        for i in range(nt):
            a, b, c, m = struct.unpack_from("<4H", sec, p + 8 * i)   # checked: indices < nv, mat < materials
            tris.append((a, b, c, base + m))
        plugins = [t3 for t3, o3, s3 in (chunks(sec, sk[1][1], sk[1][1] + sk[1][2]) if len(sk) > 1 else [])]
        sectors.append({"bbox": lo + hi, "verts": verts, "colors": colors, "uvs": uvs, "tris": tris,
                        "plugins": plugins})

    def node(t2, o2, s2):
        if t2 == 0x09:
            atomic(o2, s2)
        elif t2 == 0x0A:
            for c in chunks(sec, o2, o2 + s2)[1:3]:
                node(*c)
    node(*kids[2])
    return {"format": fmt, "triangles": ntri, "vertices": nvert, "plane_sectors": nplane, "atomic_sectors": nsect,
            "bbox": bbox, "materials": mats, "sectors": sectors}


def clump_mesh(sec):
    """A collision clump: every atomic's triangles in area space (frames applied), with material colours."""
    r = rw()
    out = []
    for c in r.read_clumps(sec):
        mats = r.world_matrices(c.frames)
        for fi, gi in c.atomics:
            g = c.geometries[gi]
            m = mats[fi]
            verts = [r.transform_point(p, m) for p in g.positions]
            fr = c.frames[fi]
            top = fr.parent >= 0 and c.frames[fr.parent].parent == 0   # child of the hierarchy root frame
            out.append({"frame": fi, "hanim": fr.hanim_id, "top": top, "verts": verts,
                        "tris": [(a, b, cc, mt) for a, b, cc, mt in g.tris],
                        "materials": [list(mm.color) for mm in g.materials]})
    return out


def bbox_of(points):
    if not points:
        return None
    return [min(p[i] for p in points) for i in range(3)] + [max(p[i] for p in points) for i in range(3)]


# ---------------------------------------------------------------------------
# ELF tables
# ---------------------------------------------------------------------------
class Areas:
    def __init__(self, iso):
        self.e = bdkit.Elf(os.path.join(iso, bdkit.ELF_NAME))
        try:
            self.text = bdkit.text_table(os.path.join(iso, "XAF", "CDATA.XAF"), NAME_TEXT)
        except Exception:
            self.text = {}

    def raw(self, v, n):
        o = self.e.v2o(v)
        return self.e.d[o:o + n]

    def in_elf(self, v):
        return bdkit.ELF_LOAD_VADDR <= v < bdkit.ELF_LOAD_VADDR + bdkit.ELF_LOAD_FILESZ

    def name(self, tid):
        return self.text.get(tid, "")

    def definition(self, a):
        d = self.raw(AREA_DEFS + AREA_DEF_SIZE * a, AREA_DEF_SIZE)
        u16 = lambda o: struct.unpack_from("<H", d, o)[0]
        f32 = lambda o, n=1: list(struct.unpack_from(f"<{n}f", d, o))
        spots_ptr = struct.unpack_from("<I", d, 0x14)[0]
        spots = []
        if spots_ptr and self.in_elf(spots_ptr):
            n, p = self.e.u32(spots_ptr), self.e.u32(spots_ptr + 4)
            if 0 < n < 64 and self.in_elf(p):
                spots = [[v * 0.1 for v in struct.unpack_from("<4h", self.e.d, self.e.v2o(p + 8 * i))]
                         for i in range(n)]
        default_spot = [v * 0.1 for v in struct.unpack_from("<4h", self.raw(BATTLE_SPOT_DEFAULT + 8 * a, 8))]
        return {
            "id": a, "name_text": u16(0), "name": self.name(u16(0)), "short_text": u16(2),
            "short_name": self.name(u16(2)),
            "sound_banks": [u16(4), u16(6)],   # SOUND.XAF banks via 0x004337D0, loaded as types 4 and 3
            "bgm": u16(8), "ambience": u16(0xA), "ambience_flag_b": u16(0xC), "def_0e": u16(0xE),
            "def_10": f32(0x10)[0], "def_18": struct.unpack_from("<I", d, 0x18)[0], "def_1c": list(d[0x1C:0x20]),
            "def_20": f32(0x20)[0],
            "ambient_light": f32(0x3C, 3),
            "light1_angles": f32(0x58, 3), "light1_color": f32(0x64, 3),
            "light2_angles": f32(0x80, 3), "light2_color": f32(0x8C, 3),
            "def_a0": f32(0xA0)[0],
            "floor_kinds": [x for x in struct.unpack_from("<18H", d, 0xC4)],
            "wall_kinds": [x for x in struct.unpack_from("<12H", d, 0xE8)],
            "flag_100": d[0x100], "flag_101": d[0x101],
            "battle_spots": spots, "battle_spot_default": default_spot,
            "far_clip": FAR_CLIP.get(a, 1500.0),
            "entries": [a + k for k in VARIANTS.get(a, [0])],
        }

    def objects(self, a):
        """g_AreaObjects: {s16 prop count, s16 extra count, fn init, desc ptr (0x28 per prop), fn extra list,
        s8 prop for type 1/3, s8 prop for types 2/3, s8 prop for type 1/2, s8 prop for type 1/1,
        u32 count, ptr to 0x24-byte placement records}."""
        d = self.raw(AREA_OBJECTS + 0x28 * a, 0x28)
        nprop, nextra, init, desc, extra, p3, p23, p2, p1, cnt, recs = struct.unpack_from("<hhIII4bII", d)
        out = []
        if recs and self.in_elf(recs):
            for k in range(min(cnt, 256)):
                r = self.raw(recs + 0x24 * k, 0x24)
                typ, sub, flag, x, y, z, ry = struct.unpack_from("<BBhhhhh", r)
                stages = [struct.unpack_from("<bb", r, 0xC + 2 * s) for s in range(12)]
                out.append({"type": typ, "kind": {1: "prop", 2: "special", 3: "weapon", 4: "item"}.get(typ, "?"),
                            "sub": sub, "hide_flag": flag if 5999 < flag < 0x1D4C else None,
                            "pos": [x * 0.1, y * 0.1, z * 0.1], "rot_y": ry * 0.1,
                            "stages": [s + 1 for s in range(11) if stages[s][0] >= 0],
                            "special_mode": stages[11][0] >= 0})
        return {"prop_count": nprop, "props_for": {"type1_sub3": p3, "type2_3": p23, "type1_sub2": p2,
                                                    "type1_sub1": p1}, "init": init, "descriptors": desc,
                "extra_fn": extra, "records": out}

    def door_flags(self, a):
        d = self.raw(DOOR_FLAGS + 0x14 * a, 0x14)
        allowed, base, cnt, tags = struct.unpack_from("<IhhI", d)
        tag_list = []
        if tags and self.in_elf(tags) and 0 < cnt < 64:
            tag_list = list(struct.unpack_from(f"<{cnt}h", self.e.d, self.e.v2o(tags)))
        allow = None
        if allowed and self.in_elf(allowed):
            n = struct.unpack_from("<b", self.e.d, self.e.v2o(allowed))[0]
            allow = list(self.e.d[self.e.v2o(allowed) + 1:self.e.v2o(allowed) + 1 + max(n, 0)])
        return {"first_flag": base, "tags": tag_list, "allowed_dest": allow}


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
def area_and_entry(a):
    ar = Areas(a.iso)
    d = ar.definition(a.area)
    entry = a.entry if a.entry is not None else d["entries"][0]
    blob = read_entry(a.iso, entry)
    if len(blob) < 8 or struct.unpack_from("<I", blob, 0)[0] not in (9, 10):
        sys.exit(f"FSTAGE.XAF entry {entry} is not an area pack (areas are 1-54; Area_Load sends 0 and 57+ to 4)")
    return ar, d, entry, sections(blob)


def cmd_areas(a):
    ar = Areas(a.iso)
    print("area  entries        bgm  sound   far   spots  name")
    for i in range(AREA_COUNT):
        d = ar.definition(i)
        if not d["name_text"] or d["name_text"] == 0xFFFF:
            print(f"{i:4d}  {'(no definition; FSTAGE entry is a variant of another area)'}")
            continue
        ents = ",".join(str(x) for x in d["entries"])
        print(f"{i:4d}  {ents:13s} {d['bgm']:4d}  {d['sound_banks'][0]:3d},{d['sound_banks'][1]:<3d} {d['far_clip']:5.0f}"
              f"  {len(d['battle_spots']):5d}  {d['name']} (text {d['name_text']})")


def cmd_pieces(a):
    ar, d, entry, secs = area_and_entry(a)
    print(f"area {a.area} {d['name']}: FSTAGE.XAF entry {entry} (variants {d['entries']}), {len(secs)} sections")
    for k, sec in enumerate(secs):
        label = SECTION_NAMES[k] if k < len(SECTION_NAMES) else "?"
        head = struct.unpack_from("<I", sec, 0)[0] if len(sec) >= 4 else None
        info = ""
        if not sec:
            info = "empty"
        elif k == 0:
            names = texture_names(sec)
            info = f"{len(names)} PS2 textures: {', '.join(names[:8])}{' ...' if len(names) > 8 else ''}"
        elif k == 1:
            w = read_world(sec)
            texs = sorted({m['texture'] for m in w['materials'] if m['texture']})
            info = (f"RpWorld {w['triangles']} tris, {w['vertices']} verts, {w['atomic_sectors']} sectors, "
                    f"{len(w['materials'])} materials ({len(texs)} textures), format {w['format']:#x}, bbox "
                    + " ".join(f"{v:.1f}" for v in w['bbox'][3:] + w['bbox'][:3]))
        elif k in COLLISION:
            m = clump_mesh(sec)
            nt = sum(len(x['tris']) for x in m)
            bb = bbox_of([p for x in m for p in x['verts']])
            info = (f"{COLLISION[k]} collision clump: {nt} tris, materials {[x['materials'] for x in m][0]}, bbox "
                    + " ".join(f"{v:.1f}" for v in bb))
        elif k == 5:
            m = clump_mesh(sec)
            info = f"doors clump: {len(m)} door panels"
        elif k in (6, 9):
            cs = chunks(sec)
            info = f"{len(cs)} HAnim animation(s) (0x1B)"
            if cs and cs[0][0] == 0x1B:
                nf, flags, dur = struct.unpack_from("<iIf", sec, cs[0][1] + 8)
                info += f", first: {nf} keys, {dur:.2f} s"
        elif k == 7:
            info = f"{head} prop clumps"
        elif k == 8 and sec[:2] == b"PB":
            info = f"PB: {struct.unpack_from('<h', sec, 2)[0]} prop placements"
        print(f"  {k} {label:16s} {len(sec):8d} bytes  {info}")
    o = ar.objects(a.area)
    print(f"  g_AreaObjects: {o['prop_count']} prop descriptors, {len(o['records'])} placed objects "
          f"({', '.join(sorted({r['kind'] for r in o['records']}))})")
    print(f"  battle spots: {len(d['battle_spots'])}; wall kinds {[x & 0x1F for x in d['wall_kinds'] if x]}; "
          f"lights: ambient {fmt3(d['ambient_light'])}, 1 {fmt3(d['light1_angles'][:2])}deg {fmt3(d['light1_color'])},"
          f" 2 {fmt3(d['light2_angles'][:2])}deg {fmt3(d['light2_color'])}; far clip {d['far_clip']:.0f}")


def fmt3(v):
    return "(" + ", ".join(f"{x:.2f}" for x in v) + ")"


def collision_data(a):
    ar, d, entry, secs = area_and_entry(a)
    out = {"area": a.area, "name": d["name"], "fstage_entry": entry, "units": "1 unit = about 10 cm, y up",
           "definition": {k: v for k, v in d.items() if k not in ("battle_spots",)}}
    for k, label in COLLISION.items():
        meshes = clump_mesh(secs[k])
        verts, tris = [], []
        mats = meshes[0]["materials"] if meshes else []
        for m in meshes:
            base = len(verts)
            verts += [list(p) for p in m["verts"]]
            tris += [[base + t[0], base + t[1], base + t[2], t[3]] for t in m["tris"]]
        entry_mats = []
        for i, c in enumerate(mats):
            em = {"color": c}
            if label == "walls" and i < 12:
                em["wall_kind"] = d["wall_kinds"][i] & 0x1F
            if label == "floor" and i < 18:
                em["floor_kind_raw"] = d["floor_kinds"][i]
            entry_mats.append(em)
        out[label] = {"materials": entry_mats, "vertices": verts, "triangles": tris, "bbox": bbox_of(verts)}
    doors = []
    names = {i: ar.definition(i)["name"] for i in range(AREA_COUNT)}
    for m in clump_mesh(secs[5]) if len(secs) > 5 and secs[5] else []:
        tag = m["hanim"]          # BONETAG: destination area, or -(area * 10 + entrance)
        dest = entrance = None
        if tag is not None and tag < 0:
            dest, entrance = (-tag) // 10, (-tag) % 10
        elif tag is not None:
            dest = tag
        doors.append({"bonetag": tag, "part": "zone" if m["top"] else "panel",
                      "dest_area": dest, "dest_name": names.get(dest, ""), "entrance": entrance,
                      "vertices": [list(p) for p in m["verts"]], "triangles": [list(t) for t in m["tris"]],
                      "bbox": bbox_of(m["verts"])})
    out["doors"] = doors
    out["door_flags"] = ar.door_flags(a.area)
    out["battle_spots"] = [{"pos": s[:3], "angle": s[3], "use": "story fight" if i == 0 else "nearest to player"}
                           for i, s in enumerate(d["battle_spots"])]
    out["objects"] = ar.objects(a.area)["records"]
    if len(secs) > 8 and secs[8][:2] == b"PB":
        n = struct.unpack_from("<h", secs[8], 2)[0]
        out["prop_placements"] = []
        for i in range(n):
            prop, x, y, z, qx, qy, qz, qw = struct.unpack_from("<i7f", secs[8], 4 + 32 * i)
            out["prop_placements"].append({"prop": prop, "pos": [x, y, z], "quat": [qx, qy, qz, qw]})
    w = read_world(secs[1])
    out["world_bbox"] = list(w["bbox"][3:]) + list(w["bbox"][:3])   # RwBBox is {sup, inf}; stored here min, max
    return out


def write_obj(path, groups):
    with open(path, "w") as f:
        f.write("# stagekit.py output: converted game data, do not commit\n")
        base = 1
        for name, verts, tris in groups:
            f.write(f"o {name}\n")
            for v in verts:
                f.write("v %.4f %.4f %.4f\n" % tuple(v))
            for t in tris:
                f.write("f %d %d %d\n" % (t[0] + base, t[1] + base, t[2] + base))
            base += len(verts)


def cmd_collision(a):
    c = collision_data(a)
    print(f"area {c['area']} {c['name']}, FSTAGE.XAF entry {c['fstage_entry']} ({c['units']})")
    print("world bbox (render geometry): " + " ".join(f"{v:.1f}" for v in c["world_bbox"]))
    for label in COLLISION.values():
        m = c[label]
        print(f"{label}: {len(m['triangles'])} triangles, {len(m['vertices'])} vertices, bbox "
              + " ".join(f"{v:.1f}" for v in m["bbox"]) + f"; materials {m['materials']}")
        if a.verbose:
            for t in m["triangles"]:
                print("   mat %d  " % t[3] + "  ".join(fmt3(m["vertices"][i]) for i in t[:3]))
    print(f"doors ({len(c['doors'])}):")
    for dr in c["doors"]:
        bb = dr["bbox"]
        print(f"   {dr['part']:5s} bonetag {dr['bonetag']}: to area {dr['dest_area']} {dr['dest_name']}, "
              f"entrance {dr['entrance']}; x {bb[0]:.1f}..{bb[3]:.1f} y {bb[1]:.1f}..{bb[4]:.1f} z {bb[2]:.1f}..{bb[5]:.1f}")
    print(f"door flags: {c['door_flags']}")
    print(f"battle spots ({len(c['battle_spots'])}, x y z angle):")
    for s in c["battle_spots"]:
        print(f"   {fmt3(s['pos'])} {s['angle']:.1f}deg  {s['use']}")
    print(f"objects placed per story stage ({len(c['objects'])}):")
    for r in c["objects"]:
        print(f"   {r['kind']:7s} sub {r['sub']:3d} at {fmt3(r['pos'])} rot {r['rot_y']:.1f}  stages {r['stages']}"
              + (" + special mode" if r["special_mode"] else "")
              + (f"  hidden once flag {r['hide_flag']} is set" if r["hide_flag"] else ""))
    pp = c.get("prop_placements", [])
    print(f"prop placements (PB, {len(pp)}):")
    for p in pp:
        print(f"   prop {p['prop']:3d} at {fmt3(p['pos'])} quat {fmt3(p['quat'])}")
    if a.json:
        with open(a.json, "w") as f:
            json.dump(c, f, indent=1)
        print(f"wrote {a.json}")
    if a.obj:
        groups = [(label, c[label]["vertices"], c[label]["triangles"]) for label in COLLISION.values()]
        groups += [(f"door_{i}_{dr['part']}_to_{dr['dest_area']}", dr["vertices"], dr["triangles"]) for i, dr in enumerate(c["doors"])]
        write_obj(a.obj, groups)
        print(f"wrote {a.obj}")


def cmd_world(a):
    ar, d, entry, secs = area_and_entry(a)
    w = read_world(secs[1])
    print(f"area {a.area} {d['name']}: {w['triangles']} tris, {w['vertices']} verts in {len(w['sectors'])} sectors")
    for i, s in enumerate(w["sectors"]):
        print(f"   sector {i}: {len(s['tris'])} tris, {len(s['verts'])} verts, plugins "
              f"{[hex(p) for p in s['plugins']]}, bbox " + " ".join(f"{v:.1f}" for v in s["bbox"]))
    if a.obj:
        write_obj(a.obj, [(f"sector_{i}", s["verts"], s["tris"]) for i, s in enumerate(w["sectors"])])
        print(f"wrote {a.obj}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    s = p.add_subparsers(dest="cmd", required=True)
    x = s.add_parser("areas", help="list every area")
    x.add_argument("iso")
    x.set_defaults(fn=cmd_areas)
    for name, fn, help_ in (("pieces", cmd_pieces, "list one area's pieces"),
                            ("collision", cmd_collision, "dump one area's collision"),
                            ("world", cmd_world, "one area's render geometry")):
        x = s.add_parser(name, help=help_)
        x.add_argument("iso")
        x.add_argument("area", type=lambda v: int(v, 0))
        x.add_argument("--entry", type=lambda v: int(v, 0), help="FSTAGE.XAF entry (default: the area's own)")
        if name != "pieces":
            x.add_argument("--obj", help="write an OBJ file (converted game data: keep it out of git)")
        if name == "collision":
            x.add_argument("--json", help="write everything as JSON (converted game data: keep it out of git)")
            x.add_argument("-v", "--verbose", action="store_true", help="print every triangle")
        x.set_defaults(fn=fn)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
