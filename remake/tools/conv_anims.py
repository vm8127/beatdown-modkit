"""Converter: fighter animations -> anims/<name>.glb (the body skeleton + glTF animations, no mesh) and
anims/<name>.json (what the animated fighter needs to pick them).

The decoding is in tools/animkit.py (RenderWare compressed keyframes, docs/ANIMATION.md). Binding (docs/ANIMATION.md,
"Skeleton binding"): every node takes its rotation from the animation; the translation stays the skeleton's bone
offset, except nodes 1 and 8 (hips and spine), whose keys hold their position under the root. The keys are written
as they are (30 Hz grid, LINEAR = slerp/lerp like the game), not resampled.

Clips are named by anim id ("a34" = anim 34), so the fighter looks a move's clips up by the ids in its MoveData. Which
clips: every animation the style's actions play (conv_moves.build_style), the generic actions every fighter needs
(stance, walk, run) and the hit reactions, knockdowns, lying and getting up, read from the game's reaction tables
(docs/ANIMATION.md, "Hit reactions"):
  g_ReactionSets 0x005FE260 -> per reaction set, 0x16 reaction kinds -> 4 x {s16 action, s16 angle} (from behind,
  front, left, right); Combat_TakeHit 0x0030DFD0 picks set (Combat_SituationFactor's return), kind and direction.
Each action's anim is its motion script's first play op; "then" is the action its script continues with.

The JSON also carries g_AttackSpheres (bone, offset, radius per attack part) so the fighter can put a move's hit
spheres on the bones its MoveHit.parts name.

The skeleton's joint names are fixed (skeleton.BONE_NAMES), so in Godot the clips play on any model from
conv_models.py with the same body (the Skeleton3D bones match by name).
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools"))

import animkit  # noqa: E402
import bdkit  # noqa: E402
import codemap  # noqa: E402
import conv_moves  # noqa: E402
from conv_models import Disc, body_clump  # noqa: E402
from gltf_writer import Gltf  # noqa: E402
from skeleton import BONE_NAMES, MOVING_NODES, SCALE, Skeleton

REACTION_SETS = 0x005FE260      # u32[4] -> reaction set: u32[0x16] -> 4 x {s16 action, s16 angle}
REACTION_KINDS = 0x16
DIRECTIONS = ("behind", "front", "left", "right")   # entry order; the angle word says 180, 0, -90, 90
# Generic actions (docs/ANIMATION.md): stance (action 1), walk (action 2), run (action 3, Fighter_TaskWalk)
GENERIC = {"stance": 1, "walk": 2, "run": 3, "guard": 10}
# Lying actions (reached by "goto" from the knockdown reactions) -> their getup action (the script's own goto)
LOOPING_ACTIONS = (1, 2, 3, 19, 20)

# Output name -> (outfit preset whose body skeleton to use, style name in conv_moves.STYLES, the class row's
# animation groups in load order: the group each anim id is taken from, after the style's own preference list)
SETS = [
    ("aaron", 78, "aaron", [159, 15, 16, 39, 38, 19, 21, 22, 23, 27, 30, 31, 34, 160, 161, 184, 210]),
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


def first_play(e, act):
    """(anim id, blend, action it continues with or None, loops) of an action's motion script."""
    ops = codemap.motion_script(e, act)
    play = next((args for op, args in ops if op == "play"), None)
    then = next((args[0] for op, args in ops if op == "goto"), None)
    loops = any(op == "loop" and args and args[0] == -1 for op, args in ops)
    return (play[0] if play else None), (play[3] if play else 0), then, loops


def reaction_tables(e):
    """{set: {kind: {direction: action}}} for the sets Combat_TakeHit uses (0 normal, 1 heavy)."""
    out = {}
    for s in range(2):
        top = e.u32(REACTION_SETS + 4 * s)
        kinds = {}
        for k in range(REACTION_KINDS):
            p = e.u32(top + 4 * k)
            kinds[k] = {d: e.s16(p + 4 * i) for i, d in enumerate(DIRECTIONS)}
        out[s] = kinds
    return out


def attack_parts(e):
    out = []
    for i, sp in enumerate(conv_moves.spheres(e)):
        node = sp["node"]
        out.append(dict(part=i, node=node, bone=BONE_NAMES[node] if 0 <= node < len(BONE_NAMES) else "",
                        offset=[round(c * SCALE, 5) for c in sp["offset"]], radius=round(sp["radius"] * SCALE, 5)))
    return out


def plan(e, lib, iso, style_name, class_groups):
    """Every clip to export: {anim id: role list}, plus the reaction / action tables for the JSON."""
    name, style, title, prefs = next(s for s in conv_moves.STYLES if s[0] == style_name)
    _, moves, _ = conv_moves.build_style(e, lib, iso, style, prefs)
    want = {}
    for act, m in sorted(moves.items()):
        for c in m["clips"]:
            want.setdefault(c[0], []).append(f"action {act}")
    actions = {}

    def add_action(act, role):
        if act in actions or act <= 0:
            return
        aid, blend, then, loops = first_play(e, act)
        actions[act] = dict(anim=aid if aid is not None else -1, blend=blend, then=then if then is not None else -1,
                            loop=loops)
        if aid is not None:
            want.setdefault(aid, []).append(role)
        if then is not None and then not in (1, -1):
            add_action(then, f"after {act}")

    for role, act in GENERIC.items():
        add_action(act, role)
    reactions = reaction_tables(e)
    for s, kinds in reactions.items():
        for k, dirs in kinds.items():
            for d, act in dirs.items():
                add_action(act, f"reaction set {s} kind {k:#x} {d}")
    return prefs, want, actions, reactions


def pick_group(lib, aid, prefs, class_groups):
    """The group an anim id is taken from: the style's preference list (like conv_moves), else the class row's
    first group that has it, else the first group at all."""
    locs = lib.where(aid)
    for g in list(prefs) + list(class_groups):
        for loc in locs:
            if loc[0] == g:
                return loc
    return locs[0] if locs else None


def convert(iso, out, log=print):
    disc = Disc(iso)
    elf = os.path.join(iso, "SLUS_211.50")
    e = bdkit.Elf(elf)
    lib = animkit.Library(elf, os.path.join(iso, "XAF", "STAGE.XAF"))
    presets = disc.read("CDATA", 0)
    os.makedirs(os.path.join(out, "anims"), exist_ok=True)
    written = []
    for name, preset, style_name, class_groups in SETS:
        prefs, want, actions, reactions = plan(e, lib, iso, style_name, class_groups)
        loop_anims = {a["anim"] for act, a in actions.items() if a["loop"] and act in LOOPING_ACTIONS}
        g = Gltf()
        joints, _ = Skeleton(body_clump(disc, presets, preset)).add_to(g)
        clips, missing = {}, []
        for aid in sorted(want):
            loc = pick_group(lib, aid, prefs, class_groups)
            if loc is None:
                missing.append(aid)
                continue
            anim = animkit.Anim(lib.entry(loc[1])[loc[2]])
            loops = aid in loop_anims
            add_clip(g, joints, anim, f"a{aid}", loops)
            clips[f"a{aid}"] = dict(anim=aid, group=loc[0], frames=anim.frames, loop=loops, used_by=want[aid][:6])
        with open(os.path.join(out, "anims", name + ".glb"), "wb") as f:
            f.write(g.glb())
        meta = dict(clips=clips, generic=GENERIC, actions={str(k): v for k, v in sorted(actions.items())},
                    reactions={str(s): {str(k): v for k, v in kinds.items()} for s, kinds in reactions.items()},
                    attack_parts=attack_parts(e), missing=missing)
        with open(os.path.join(out, "anims", name + ".json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(meta, f, indent=1, sort_keys=True)
        log(f"  anims/{name}.glb: {len(clips)} clips (style {style_name}, generic, reactions)"
            + (f"; not in any group: {missing}" if missing else ""))
        written += [f"anims/{name}.glb", f"anims/{name}.json"]
    return written


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: conv_anims.py ISO OUT")
    convert(sys.argv[1], sys.argv[2])
