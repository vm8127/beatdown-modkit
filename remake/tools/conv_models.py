"""Converter: character models (street look and fight look) -> textured .glb.

The decoding is in tools/rwkit.py (RenderWare clumps, outfit slots, street packs); this module only writes glTF.
Static bind pose for now (M1); the skeleton and skin weights come with M2.
"""
import os
import struct

import bdkit
import rwkit
from gltf_writer import Gltf

SCALE = 0.1   # RenderWare units are about 10 cm (a man is about 18 units tall)

# What M1 extracts: (output name, kind, outfit preset)
MODELS = [
    ("street_089", "street", 89),     # large build, red jacket, blond (Eggusz's base street look)
    ("fighter_aaron_078", "outfit", 78),   # Aaron's fight look, built from his 22 outfit slots
]


class Disc:
    def __init__(self, iso):
        self.elf = bdkit.Elf(os.path.join(iso, "SLUS_211.50"))
        self.names = rwkit.texture_names(self.elf)
        self.paths = {a: os.path.join(iso, "XAF", f"{a}.XAF") for a in ("DATA", "CDATA")}
        self.index = {a: bdkit.xaf_entries(p) for a, p in self.paths.items()}

    def read(self, archive, entry):
        o, s = self.index[archive][entry][1:3]
        with open(self.paths[archive], "rb") as f:
            f.seek(o)
            return f.read(s)


def _png_and_alpha(blob):
    return bdkit.texture_png(blob), rwkit.image_has_alpha(blob)


def write_model(disc, parts, images, path):
    """parts: rwkit.Part list; images: texture id -> Image chunk (falls back to DATA.XAF entry = id)."""
    g = Gltf()
    mats = {}
    nodes = []
    for p in parts:
        geo = p.geo
        pos = [tuple(c * SCALE for c in rwkit.transform_point(v, p.matrix)) for v in geo.positions]
        nrm = [_norm(rwkit.transform_dir(n, p.matrix)) for n in geo.normals] if geo.normals else None
        uv = geo.uvs[0] if geo.uvs else None
        by_mat = {}
        for v0, v1, v2, m in geo.tris:
            if v0 != v1 and v1 != v2 and v0 != v2:
                by_mat.setdefault(m, []).extend((v0, v1, v2))
        prims = []
        for m in sorted(by_mat):
            tid = p.textures[m] if m < len(p.textures) else None
            if tid not in mats:
                if tid is None:
                    c = geo.materials[m].color
                    mats[tid] = g.material("untextured", color=tuple(x / 255 for x in c))
                else:
                    blob = images.get(tid) or disc.read("DATA", tid)
                    png, alpha = _png_and_alpha(blob)
                    # Alpha is real transparency only on hair; on clothes and skin it is a noise-like mask, most
                    # likely the specular/gloss amount (docs/FORMATS.md, open question), so those stay opaque.
                    hair = disc.names[tid].upper().startswith("HAI")
                    mats[tid] = g.material(disc.names[tid], g.texture(tid, png), alpha_mask=alpha and hair)
            # Compact the vertex arrays to what this primitive uses
            used = sorted(set(by_mat[m]))
            remap = {v: i for i, v in enumerate(used)}
            prims.append(([pos[v] for v in used], [nrm[v] for v in used] if nrm else None,
                          [uv[v] for v in used] if uv else None, [remap[v] for v in by_mat[m]], mats[tid]))
        if prims:
            nodes.append(g.node(p.name, g.mesh(p.name, prims), root=False))
    g.node(os.path.splitext(os.path.basename(path))[0], children=nodes)
    with open(path, "wb") as f:
        f.write(g.glb())


def _norm(v):
    l = (v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) ** 0.5 or 1.0
    return (v[0] / l, v[1] / l, v[2] / l)


def convert(iso, out, log=print):
    disc = Disc(iso)
    os.makedirs(os.path.join(out, "models"), exist_ok=True)
    presets = disc.read("CDATA", 0)
    written = []
    for name, kind, preset in MODELS:
        if kind == "street":
            parts, images = rwkit.street_model(disc.elf, disc.names, disc.read("CDATA", preset + 7), preset)
        else:
            parts = rwkit.outfit_model(disc.elf, disc.names, lambda i: disc.read("DATA", i), presets, preset)
            images = {}
        path = os.path.join(out, "models", name + ".glb")
        write_model(disc, parts, images, path)
        log(f"  models/{name}.glb: {len(parts)} parts, {sum(len(p.geo.tris) for p in parts)} triangles")
        written.append(f"models/{name}.glb")
    return written
