#!/usr/bin/env python3
"""RenderWare binary stream decoder for Beat Down's models (docs/FORMATS.md).

Beat Down's XAF entries are RenderWare 3.x binary streams (Criterion's engine): every chunk starts with
{u32 type, u32 size, u32 library id}, the same header bdkit.py's asset types are the first word of. Models are
clumps (type 0x10) of plain (not PS2-native) geometry: triangles, one UV set, positions and normals, with the Skin
and HAnim plugins for skinning. Textures are RwImage chunks (type 0x18, bdkit.texture_png converts them).

Library use (remake/tools/remake_assets.py):  read_clumps(blob) -> [Clump]   (each with frames, geometries, atomics)
Command line:
  python tools/rwkit.py tree FILE_OR_XAF [ENTRY]     print the chunk tree
  python tools/rwkit.py info XAF ENTRY               summary of every clump: frames, geometries, materials, skin

Standard library only.
"""
import argparse
import os
import struct
import sys

# Chunk ids (RenderWare's rwID_* values; the plugin ids are Criterion's toolkit ids)
STRUCT, STRING, EXTENSION, TEXTURE, MATERIAL, MATLIST = 0x01, 0x02, 0x03, 0x06, 0x07, 0x08
FRAMELIST, GEOMETRY, CLUMP, ATOMIC, TEXNATIVE, TEXDICT, IMAGE, GEOMLIST, ANIM = 0x0E, 0x0F, 0x10, 0x14, 0x15, 0x16, 0x18, 0x1A, 0x1B
SKIN_PLG, HANIM_PLG, USERDATA_PLG, BINMESH_PLG = 0x116, 0x11E, 0x11F, 0x50E
CONTAINERS = {EXTENSION, TEXTURE, MATERIAL, MATLIST, FRAMELIST, GEOMETRY, CLUMP, ATOMIC, TEXDICT, GEOMLIST}
NAMES = {STRUCT: "Struct", STRING: "String", EXTENSION: "Extension", TEXTURE: "Texture", MATERIAL: "Material",
         MATLIST: "MaterialList", FRAMELIST: "FrameList", GEOMETRY: "Geometry", CLUMP: "Clump", ATOMIC: "Atomic",
         TEXNATIVE: "TextureNative", TEXDICT: "TexDictionary", IMAGE: "Image", GEOMLIST: "GeometryList", ANIM: "HAnimAnimation",
         SKIN_PLG: "SkinPLG", HANIM_PLG: "HAnimPLG", USERDATA_PLG: "UserDataPLG", BINMESH_PLG: "BinMeshPLG"}

# Geometry flags (rpGEOMETRY*)
GEO_TRISTRIP, GEO_POSITIONS, GEO_TEXTURED, GEO_PRELIT, GEO_NORMALS, GEO_LIGHT, GEO_MODULATE = 1, 2, 4, 8, 0x10, 0x20, 0x40
GEO_NATIVE = 0x01000000


def libid_version(libid):
    """RenderWare library id -> version number like 0x37002 (RwEngineGetVersion style); the Image chunks use
    0x1803FFFF (3.6.0.3), the clumps 0x1C02000A (3.7.0.2)."""
    if libid & 0xFFFF0000 == 0:
        return libid << 8
    return ((libid >> 14 & 0x3FF00) + 0x30000) | (libid >> 16 & 0x3F)


class Chunk:
    __slots__ = ("type", "off", "size", "libid", "data", "children")

    def __init__(self, data, off):
        self.type, self.size, self.libid = struct.unpack_from("<III", data, off)
        self.off = off
        self.data = data[off + 12:off + 12 + self.size]
        self.children = parse(self.data) if self.type in CONTAINERS else []

    def find(self, t):
        return [c for c in self.children if c.type == t]

    def first(self, t):
        for c in self.children:
            if c.type == t:
                return c
        return None

    def ext(self, t):
        """A plugin chunk inside this chunk's Extension."""
        e = self.first(EXTENSION)
        return e.first(t) if e else None


def parse(data, off=0, end=None):
    end = len(data) if end is None else end
    out = []
    while off + 12 <= end:
        t, s, v = struct.unpack_from("<III", data, off)
        if off + 12 + s > end or v == 0:
            break    # not a chunk (padding, or the end of the 2048-aligned entry)
        out.append(Chunk(data, off))
        off += 12 + s
    return out


def string(chunk):
    return chunk.data.split(b"\0")[0].decode("latin1")


# ---------------------------------------------------------------------------
# Clump contents
# ---------------------------------------------------------------------------
class Frame:
    """rot: 3x3 rows (right, up, at), pos: xyz, both relative to the parent; parent -1 = root.
    hanim_id: the HAnim node id (BONETAG) when the frame carries one; user: Softimage user data strings."""
    def __init__(self, rot, pos, parent):
        self.rot, self.pos, self.parent = rot, pos, parent
        self.hanim_id = None
        self.hanim = None    # the hierarchy {flags, key size, [(node id, index, flags)]} on the skeleton root
        self.user = []


class Material:
    def __init__(self, color, texture, mask, textured):
        self.color, self.texture, self.mask, self.textured = color, texture, mask, textured


class Geometry:
    def __init__(self):
        self.flags = 0
        self.uvs = []        # [ [(u, v)] per vertex ] per UV set
        self.colors = None   # prelit RGBA per vertex
        self.tris = []       # (v0, v1, v2, material)
        self.positions = []
        self.normals = []
        self.sphere = None
        self.materials = []
        self.skin = None     # Skin
        self.strips = None   # BinMesh: (is strip, [(material, [indices])])


class Skin:
    """bones: count; used: bone indices the vertices use; indices/weights: 4 per vertex; inverse: 4x4 inverse bind
    matrix per bone (RenderWare RwMatrix order, rows right, up, at, pos)."""
    def __init__(self, bones, used, maxw, indices, weights, inverse):
        self.bones, self.used, self.maxw, self.indices, self.weights, self.inverse = bones, used, maxw, indices, weights, inverse


class Clump:
    def __init__(self):
        self.frames = []
        self.geometries = []
        self.atomics = []    # (frame index, geometry index)


def read_frames(fl):
    st = fl.first(STRUCT).data
    n = struct.unpack_from("<I", st, 0)[0]
    frames = []
    for i in range(n):
        v = struct.unpack_from("<12fiI", st, 4 + 56 * i)
        frames.append(Frame([v[0:3], v[3:6], v[6:9]], v[9:12], v[12]))
    for fr, ext in zip(frames, fl.find(EXTENSION)):
        for c in ext.children:
            if c.type == HANIM_PLG:
                ver, node, count = struct.unpack_from("<Iii", c.data, 0)
                fr.hanim_id = node
                if count:
                    flags, keysize = struct.unpack_from("<II", c.data, 12)
                    nodes = [struct.unpack_from("<iii", c.data, 20 + 12 * k) for k in range(count)]
                    fr.hanim = {"flags": flags, "keysize": keysize, "nodes": nodes}
            elif c.type == USERDATA_PLG:
                fr.user = userdata(c.data)
    return frames


def userdata(d):
    """User data plugin: count, then {u32 name len, name, u32 type, u32 count, values} (type 3 = strings)."""
    out = []
    o = 4
    for _ in range(struct.unpack_from("<I", d, 0)[0]):
        ln = struct.unpack_from("<I", d, o)[0]
        name = d[o + 4:o + 4 + ln].split(b"\0")[0].decode("latin1")
        o += 4 + ln
        typ, cnt = struct.unpack_from("<II", d, o)
        o += 8
        vals = []
        for _ in range(cnt):
            if typ == 3:
                ln = struct.unpack_from("<I", d, o)[0]
                vals.append(d[o + 4:o + 4 + ln].split(b"\0")[0].decode("latin1"))
                o += 4 + ln
            else:
                vals.append(struct.unpack_from("<i" if typ == 1 else "<f", d, o)[0])
                o += 4
        out.append((name, vals))
    return out


def read_material(mc):
    st = mc.first(STRUCT).data
    flags, color, _, textured = struct.unpack_from("<I4sII", st, 0)
    tex = mask = None
    tc = mc.first(TEXTURE)
    if tc:
        s = tc.find(STRING)
        tex = string(s[0]) if s else None
        mask = string(s[1]) if len(s) > 1 else None
    return Material(tuple(color), tex, mask or None, bool(textured))


def read_geometry(gc):
    g = Geometry()
    st = gc.first(STRUCT).data
    flags, ntri, nvert, nmorph = struct.unpack_from("<IIII", st, 0)
    g.flags = flags
    if flags & GEO_NATIVE:
        raise ValueError("PS2 native geometry is not supported (none seen in Beat Down so far)")
    o = 16
    if libid_version(gc.libid) < 0x34000:
        o += 12    # ambient, specular, diffuse
    nuv = (flags >> 16) & 0xFF or (2 if flags & 0x80 else 1 if flags & GEO_TEXTURED else 0)
    if flags & GEO_PRELIT:
        g.colors = [struct.unpack_from("<4B", st, o + 4 * i) for i in range(nvert)]
        o += 4 * nvert
    for _ in range(nuv):
        g.uvs.append([struct.unpack_from("<2f", st, o + 8 * i) for i in range(nvert)])
        o += 8 * nvert
    for i in range(ntri):
        v1, v0, mat, v2 = struct.unpack_from("<4H", st, o + 8 * i)
        g.tris.append((v0, v1, v2, mat))
    o += 8 * ntri
    if nmorph:
        g.sphere = struct.unpack_from("<4f", st, o)
        has_pos, has_nrm = struct.unpack_from("<II", st, o + 16)
        o += 24
        if has_pos:
            g.positions = [struct.unpack_from("<3f", st, o + 12 * i) for i in range(nvert)]
            o += 12 * nvert
        if has_nrm:
            g.normals = [struct.unpack_from("<3f", st, o + 12 * i) for i in range(nvert)]
            o += 12 * nvert
    ml = gc.first(MATLIST)
    idx = struct.unpack_from(f"<I{struct.unpack_from('<I', ml.first(STRUCT).data)[0]}i", ml.first(STRUCT).data)[1:]
    mats = [read_material(m) for m in ml.find(MATERIAL)]
    k = 0
    for i in idx:
        if i < 0:
            g.materials.append(mats[k])
            k += 1
        else:
            g.materials.append(g.materials[i])
    sk = gc.ext(SKIN_PLG)
    if sk:
        g.skin = read_skin(sk.data, nvert)
    bm = gc.ext(BINMESH_PLG)
    if bm:
        strip, nmesh, _ = struct.unpack_from("<III", bm.data, 0)
        o, meshes = 12, []
        for _ in range(nmesh):
            n, mat = struct.unpack_from("<II", bm.data, o)
            meshes.append((mat, list(struct.unpack_from(f"<{n}I", bm.data, o + 8))))
            o += 8 + 4 * n
        g.strips = (bool(strip), meshes)
    return g


def read_skin(d, nvert):
    bones, used, maxw = d[0], d[1], d[2]
    o = 4
    used_list = list(d[o:o + used])
    o += used
    idx = [tuple(d[o + 4 * i:o + 4 * i + 4]) for i in range(nvert)]
    o += 4 * nvert
    w = [struct.unpack_from("<4f", d, o + 16 * i) for i in range(nvert)]
    o += 16 * nvert
    inv = [struct.unpack_from("<16f", d, o + 64 * b) for b in range(bones)]
    return Skin(bones, used_list, maxw, idx, w, inv)


def read_clump(cc):
    c = Clump()
    c.frames = read_frames(cc.first(FRAMELIST))
    gl = cc.first(GEOMLIST)
    c.geometries = [read_geometry(g) for g in gl.find(GEOMETRY)] if gl else []
    for a in cc.find(ATOMIC):
        fr, geo = struct.unpack_from("<II", a.first(STRUCT).data, 0)
        c.atomics.append((fr, geo))
    return c


def read_clumps(blob):
    """Every clump in an XAF entry (a street pack has its images first, then the body clump and the hair clump)."""
    return [read_clump(c) for c in parse(blob) if c.type == CLUMP]


def images(blob):
    """The Image chunks of an entry, as whole chunk blobs bdkit.texture_png accepts."""
    return [blob[c.off:c.off + 12 + c.size] for c in parse(blob) if c.type == IMAGE]


# ---------------------------------------------------------------------------
# Frame maths (row vectors, RenderWare style: world = local x parent)
# ---------------------------------------------------------------------------
def frame_matrix(fr):
    """4x4 row-major matrix, row vectors (p' = p x M)."""
    r = fr.rot
    return [list(r[0]) + [0.0], list(r[1]) + [0.0], list(r[2]) + [0.0], list(fr.pos) + [1.0]]


def mat_mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def world_matrices(frames):
    out = []
    for fr in frames:
        m = frame_matrix(fr)
        out.append(mat_mul(m, out[fr.parent]) if fr.parent >= 0 else m)
    return out


def transform_point(p, m):
    return tuple(p[0] * m[0][j] + p[1] * m[1][j] + p[2] * m[2][j] + m[3][j] for j in range(3))


def transform_dir(p, m):
    return tuple(p[0] * m[0][j] + p[1] * m[1][j] + p[2] * m[2][j] for j in range(3))


def image_has_alpha(blob):
    """True when an Image chunk's used palette entries are not all opaque (alpha 0x80 = opaque on the PS2)."""
    w, h, bpp = struct.unpack_from("<III", blob, 0x18)
    n = w * h
    ncol = 256 if bpp == 8 else 16
    pal = blob[0x28 + n:0x28 + n + 4 * ncol]
    used = set(p % ncol for p in blob[0x28:0x28 + n])
    return any(pal[4 * i + 3] < 0x80 for i in used)


# ---------------------------------------------------------------------------
# Beat Down model assembly: which geometry goes where, with which texture
# ---------------------------------------------------------------------------
ITEM_TABLE = 0x004F2400       # g_ItemTable: 52-byte ItemDef {u32 category, u32 attach node, u32 flags, void *handler,
ITEM_SIZE = 52                #   u16 DATA.XAF mesh, u16 second mesh, s16 placeholder textures[] ending -1}
TEX_NAMES = 0x0059AE30        # {u32 ?, char *name} per DATA.XAF entry; CDATA.XAF uses the same table
STREET_TEXTURES = 0x00430C90  # g_StreetTextures s16[189][10]
STREET_RETEXTURE = 0x00431B60 # u8[189]: 1 = swap the street pack's 4 placeholder textures for the person's 4
PRESET_SIZE = 0x498           # CDATA.XAF entry 0: 22 outfit slots {u32 item, s16 parts[16]} then params
DATA_ENTRIES = 8276


class Part:
    """One placed geometry: vertices already in the model's bind-pose space (RenderWare units, about 10 cm), with a
    DATA.XAF texture id (or None) per material."""
    def __init__(self, name, geo, matrix, textures):
        self.name, self.geo, self.matrix, self.textures = name, geo, matrix, textures


def _elf_str(e, va):
    o = e.v2o(va)
    return e.d[o:e.d.index(b"\0", o)].decode("latin1")


def texture_names(e):
    """DATA.XAF entry id -> texture name (the cache key), for every entry."""
    return [_elf_str(e, struct.unpack_from("<II", e.d, e.v2o(TEX_NAMES + 8 * i))[1]) for i in range(DATA_ENTRIES)]


def item_def(e, item):
    o = e.v2o(ITEM_TABLE + ITEM_SIZE * item)
    cat, node, flags, handler, mesh, mesh2 = struct.unpack_from("<IIIIHH", e.d, o)
    ph = list(struct.unpack_from("<16h", e.d, o + 0x14))
    return {"category": cat, "node": node, "flags": flags, "mesh": mesh, "mesh2": mesh2,
            "placeholders": ph[:ph.index(-1)] if -1 in ph else ph}


def outfit_slots(preset_blob, preset):
    """[(item, [texture ids])] of an outfit preset, ending at the first item < 1."""
    out = []
    for k in range(22):
        item, *parts = struct.unpack_from("<I16h", preset_blob, preset * PRESET_SIZE + 36 * k)
        if item < 1 or item >= 0x80000000:
            break
        out.append((item, parts[:parts.index(-1)] if -1 in parts else parts))
    return out


def _textured(g):
    return any(m.texture for m in g.materials)


def skeleton_nodes(clump):
    """HAnim node index -> frame index, from the hierarchy on the skeleton root frame."""
    root = next((f for f in clump.frames if f.hanim), None)
    if not root:
        return {}
    by_id = {f.hanim_id: i for i, f in enumerate(clump.frames) if f.hanim_id is not None}
    return {idx: by_id[nid] for nid, idx, _ in root.hanim["nodes"]}


def outfit_model(e, names, read_data, preset_blob, preset):
    """The fight model of an outfit preset built from its slots, like the game does for persons 51/52
    (Fighter_LoadModel 0x002F53A0 / Fighter_AttachPart 0x002F4BF0). read_data(id) returns a DATA.XAF entry.
    The body (category 0) is a skinned clump with the skeleton; every other item's clump is either skinned in the
    same bind-pose space (tops, pants) or rigid, hung on body skeleton node ItemDef.node (head 10, hands 19/14,
    feet 7/4). Material textures named like an item placeholder are replaced by the slot's texture at that index."""
    parts, body, nodes, body_world = [], None, {}, None
    for item, texs in outfit_slots(preset_blob, preset):
        d = item_def(e, item)
        clump = read_clumps(read_data(d["mesh"]))[0]
        world = world_matrices(clump.frames)
        if d["category"] == 0:
            body, nodes, body_world = clump, skeleton_nodes(clump), world
        swap = {names[p]: t for p, t in zip(d["placeholders"], texs)}
        for fr, gi in clump.atomics:
            g = clump.geometries[gi]
            if not _textured(g):
                continue    # one-triangle untextured markers (ground contact / hand points?); see docs/FORMATS.md
            if g.skin or d["category"] == 0:
                m = world[fr] if not g.skin else IDENTITY
            else:
                attach = body_world[nodes[d["node"]]] if body else IDENTITY
                m = mat_mul(world[fr], attach)
            tex = []
            for mt in g.materials:
                n = mt.texture
                tex.append(swap.get(n, names.index(n) if n in names else None) if n else None)
            parts.append(Part(f"item{item}_mesh{d['mesh']}_{gi}", g, m, tex))
    return parts


def street_model(e, names, pack_blob, preset):
    """The walking-around model of an outfit preset: CDATA.XAF entry preset + 7 = 8 Image chunks (in
    g_StreetTextures order) + the body clump (skinned) + the hair clump. When g_StreetRetexture[preset] is 1
    (NpcSpawn_Step 0x00178700, callbacks 0x001754B0 / 0x001755E0), a body material whose texture is list[i] (i < 4)
    gets list[i + 4], and every hair material gets list[7]. Returns (parts, images by texture id). The hair clump
    is hung on the body's head node (10), like an outfit item; that is a guess from the outfit code."""
    ids = struct.unpack_from("<10h", e.d, e.v2o(STREET_TEXTURES + 20 * preset))
    ids = [i for i in ids if i > 0]
    imgs = images(pack_blob)
    by_id = dict(zip(ids, imgs))
    retex = e.d[e.v2o(STREET_RETEXTURE + preset)] == 1
    clumps = read_clumps(pack_blob)
    parts = []
    body_world = world_matrices(clumps[0].frames)
    nodes = skeleton_nodes(clumps[0])
    for ci, clump in enumerate(clumps):
        world = world_matrices(clump.frames)
        for fr, gi in clump.atomics:
            g = clump.geometries[gi]
            if not _textured(g):
                continue
            m = world[fr] if ci == 0 or g.skin else mat_mul(world[fr], body_world[nodes[10]])
            tex = []
            for mt in g.materials:
                t = names.index(mt.texture) if mt.texture in names else None
                if retex and len(ids) >= 8:
                    if ci == 0 and t in ids[:4]:
                        t = ids[ids.index(t) + 4]
                    elif ci > 0:
                        t = ids[7]
                tex.append(t)
            parts.append(Part(f"clump{ci}_{gi}", g, m, tex))
    return parts, by_id


IDENTITY = [[1.0, 0, 0, 0], [0, 1.0, 0, 0], [0, 0, 1.0, 0], [0, 0, 0, 1.0]]


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------
def load(path, entry):
    if entry is None:
        with open(path, "rb") as f:
            return f.read()
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import bdkit
    o, s = bdkit.xaf_entries(path)[int(entry, 0)][1:3]
    with open(path, "rb") as f:
        f.seek(o)
        return f.read(s)


def cmd_tree(a):
    def show(chs, dep):
        for c in chs:
            extra = ""
            if c.type == STRING:
                extra = repr(string(c))
            elif not c.children:
                extra = c.data[:24].hex(" ")
            print(f"{'  ' * dep}{c.off:#07x} {c.type:#x} {NAMES.get(c.type, '?')} size={c.size:#x} {extra}")
            show(c.children, dep + 1)
    show(parse(load(a.file, a.entry)), 0)


def cmd_info(a):
    blob = load(a.file, a.entry)
    for i, im in enumerate(images(blob)):
        w, h, bpp = struct.unpack_from("<III", im, 0x18)
        print(f"image {i}: {w}x{h} {bpp}-bit")
    for ci, c in enumerate(read_clumps(blob)):
        print(f"clump {ci}: {len(c.frames)} frames, {len(c.geometries)} geometries, atomics {c.atomics}")
        for fi, fr in enumerate(c.frames):
            tag = f" hanim {fr.hanim_id}" if fr.hanim_id is not None else ""
            if fr.hanim:
                tag += f" hierarchy of {len(fr.hanim['nodes'])}"
            ud = "; ".join(f"{n}={v}" for n, v in fr.user)
            print(f"  frame {fi}: parent {fr.parent} pos ({fr.pos[0]:.3f}, {fr.pos[1]:.3f}, {fr.pos[2]:.3f}){tag} {ud}")
        for gi, g in enumerate(c.geometries):
            mats = ", ".join(m.texture or f"rgba{m.color}" for m in g.materials)
            sk = f" skin {g.skin.bones} bones ({len(g.skin.used)} used, {g.skin.maxw} weights)" if g.skin else ""
            sph = "" if not g.sphere else " sphere ({:.3f}, {:.3f}, {:.3f}) r {:.3f}".format(*g.sphere)
            print(f"  geometry {gi}: flags {g.flags:#x}, {len(g.positions)} verts, {len(g.tris)} tris{sph}{sk}; {mats}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    s = p.add_subparsers(dest="cmd", required=True)
    x = s.add_parser("tree"); x.add_argument("file"); x.add_argument("entry", nargs="?"); x.set_defaults(fn=cmd_tree)
    x = s.add_parser("info"); x.add_argument("file"); x.add_argument("entry", nargs="?"); x.set_defaults(fn=cmd_info)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
