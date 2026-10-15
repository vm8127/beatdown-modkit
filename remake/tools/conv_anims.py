"""Converter: fighter animations -> anims/*.glb (the body skeleton + its skin + glTF animations, no mesh).

The decoding is in tools/animkit.py (RenderWare compressed keyframes, docs/ANIMATION.md). Binding (docs/ANIMATION.md,
"Skeleton binding"): every node takes its rotation from the animation; the translation stays the skeleton's bone
offset, except nodes 1 and 8 (hips and spine), whose keys hold their position under the root. The keys are written
as they are (30 Hz grid, LINEAR = slerp/lerp like the game), not resampled.

The skeleton's joint names are fixed (skeleton.BONE_NAMES), so in Godot the clips of these files play on any model
from conv_models.py with the same body (the Skeleton3D bones match by name).
"""
import os

import animkit
from conv_models import Disc, body_clump
from gltf_writer import Gltf
from skeleton import MOVING_NODES, SCALE, Skeleton

# Output name -> outfit preset whose body skeleton to use, [(clip name, anim id, group, loops)]
SETS = [
    ("aaron", 78, [
        ("stance", 4, 160, True),
        ("walk", 5, 161, True),
        ("blade_cut", 34, 184, False),
    ]),
]


def _continuous(quats):
    """Flip each quaternion into the previous one's hemisphere (same rotation; keeps slerp on the short path)."""
    out = []
    for q in quats:
        if out and sum(a * b for a, b in zip(out[-1], q)) < 0:
            q = tuple(-c for c in q)
        out.append(tuple(round(c, 6) for c in q))
    return out


def add_clip(g, joints, anim, name, loops):
    chans = []
    for k, keys in enumerate(anim.tracks()):
        times = [round(t, 6) for t, _, _ in keys]
        chans.append((joints[k], "rotation", times, _continuous([q for _, q, _ in keys])))
        if k in MOVING_NODES:
            chans.append((joints[k], "translation", times,
                          [tuple(round(c * SCALE, 6) for c in tr) for _, _, tr in keys]))
    g.animation(name, chans, extras={"loop": loops, "frames_60hz": anim.frames})


def convert(iso, out, log=print):
    disc = Disc(iso)
    lib = animkit.Library(os.path.join(iso, "SLUS_211.50"), os.path.join(iso, "XAF", "STAGE.XAF"))
    presets = disc.read("CDATA", 0)
    os.makedirs(os.path.join(out, "anims"), exist_ok=True)
    written = []
    for name, preset, clips in SETS:
        g = Gltf()
        joints, _ = Skeleton(body_clump(disc, presets, preset)).add_to(g)
        for clip, aid, group, loops in clips:
            anim, _ = lib.anim(aid, group)
            add_clip(g, joints, anim, clip, loops)
            log(f"  anims/{name}.glb: {clip} = anim {aid} group {group}, {anim.frames} frames")
        with open(os.path.join(out, "anims", name + ".glb"), "wb") as f:
            f.write(g.glb())
        written.append(f"anims/{name}.glb")
    return written
