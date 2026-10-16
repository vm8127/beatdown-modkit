#!/usr/bin/env python3
"""Converter: a fighting style's command list -> moves/<name>.tres (one MoveSet with its MoveData and MoveHit
sub-resources) for the Godot fighter (remake/godot/game/fighter/).

    python remake/tools/conv_moves.py ISO remake/godot/assets_ripped     # only this converter (keeps the rest)

Everything comes from the ELF (docs/ANIMATION.md, docs/MECHANICS.md, docs/CODEMAP.md):
  g_StyleCommands 0x515C10  command list: whole input sequences (P, P P, P P ↓P...) -> action (Cmd_MatchSequence)
  g_ActionScripts 0x5848E0  motion script (which animation, frame range, blend) + timeline (frame data)
  g_ActionHits    0x580A40  hit records: damage, Pride, hit level, reaction
  g_InputFallback 0x5CD9B0  code -> simpler code when nothing matches from neutral (→→P -> →P -> P; Cmd_MatchSingle)
  g_AttackSpheres 0x515D90  attack parts: skeleton node, offset, radius
and the animation lengths and hip translation (root motion) from STAGE.XAF (tools/animkit.py).

Timing: the timeline counts animation frames, played at the speed ops' rate. The converter steps the move one game
frame (1/60 s) at a time with exact fractions and writes every event as the first game frame whose (whole) animation
frame reaches it, the same rule as Action_Timeline's wait (motion frame >= n). action_sim.py runs the motion script
and the timeline together, so moves with several clips (REAR GRAB P: 3) play every clip; `frame_clip` / `frame_anim`
give the clip and animation frame on each game frame. The first clip's animation frame values are kept too (`anim_*`
fields) for checking against `codemap.py framedata`. Deterministic; writes only into the output folder.
"""
import os
import struct
import sys
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))

import action_sim  # noqa: E402
import animkit  # noqa: E402
import bdkit  # noqa: E402
import codemap  # noqa: E402

# Output name -> style id, animation groups to take animations from (the class row's list, first match wins)
STYLES = [
    ("aaron", 0x13, "Aaron (style 0x13)", [184, 210, 160, 161]),
]

INPUT_FALLBACK = 0x005CD9B0     # u32 per input code: the code Cmd_MatchSingle tries next, -1 = none
ACTION_EVENTS = 0x00582990      # g_ActionEvents: per action a record; +8 s16 = the partner's action (grabs and throws)
GRAB_CODE = "#1E"               # R1: Fighter_HandleCommand -> Fighter_PickWeaponMove -> generic action 10 (9 for styles 0x12, 2)
ATTACK_SPHERES = codemap.ATTACK_PARTS
SPHERE_SIZE = 20                # {s8 node, pad, f32 offset xyz, f32 radius}
UNIT = 0.1                      # game units are decimetres (docs/ANIMATION.md, "Animation file format")
HIT_LEVEL = {2: "high", 4: "mid", 8: "low"}
# Reaction bits (kind of the record after the hit, Combat_TakeHit 0x0030DFD0): which ones knock down (read from
# code: 0x20 = down; 0x10, 0x100, 0x200, 0x400, 0x800, 0x1000 pick the big reaction kinds and drop the weapon).
KNOCKDOWN_BITS = 0x20 | 0x10 | 0x100 | 0x200 | 0x400 | 0x800 | 0x1000


def code_name(c):
    return codemap.INPUTS.get(c, f"#{c:02X}")


def timeline(e, act):
    """The frame data of one action as plain values (animation frames)."""
    t, hit_index = 0, 0
    out = dict(speeds=[], attacks=[], cancel=[], combo=False, release=-1, guard=-1, invincible=[], ops=[])
    inv_start = None
    for op, name, args in codemap.action_stream(e, act):
        if name == "wait":
            t = args[0]
        elif name == "speed":
            out["speeds"].append((t, Fraction(args[0], 1000)))
        elif name == "attack":
            c, before, after = args[0], args[1], args[2]
            out["attacks"].append(dict(start=c - before, end=c + after, parts=list(args[3:-1]), record=hit_index))
        elif name == "hitindex":
            hit_index = args[0]
        elif name == "combo":
            out["combo"] = True
        elif name == "cancel":
            out["cancel"].append(t)
        elif name == "op3C":
            out["release"] = args[0] - 1 if args[0] else -1
            out["guard"] = args[1] - 1 if args[1] else -1
        elif name == "status":
            v = (args[1] & 0xFFFF) << 16 | (args[2] & 0xFFFF)
            if v & 1:                     # MATCHLESS: no damage taken
                if args[0] == 1:
                    inv_start = t
                elif inv_start is not None:
                    out["invincible"].append((inv_start, t))
                    inv_start = None
        elif name in ("branch", "ifstatus", "random", "loop"):
            out["ops"].append(name)
            if name == "loop":
                break
    if inv_start is not None:
        out["invincible"].append((inv_start, 9999))
    return out


def records(e, act):
    """The action's hit records. The 16-byte table is read as an 8-byte header {u32 attack kind, u16 cost} followed
    by records {u16 damage, u8 pride, u8 strength, u16 reaction detail, u16 level flags, u32 reaction, u32 -} that
    overlap the next 16-byte slot: Combat_ResolveHit takes a hit's reaction from `hits[i + 1].kind`."""
    h = codemap.hits(e, act)
    out = []
    for i in range(len(h) - 1):
        out.append(dict(damage=h[i]["damage"], pride=h[i]["v10"] & 0xFF, strength=h[i]["v10"] >> 8,
                        detail=h[i]["v12"], level=h[i]["flags"], reaction=h[i + 1]["kind"]))
    return out, (h[0]["kind"], h[0]["v4"] & 0xFFFF) if h else (0, 0)


def spheres(e):
    out = []
    for i in range(12):
        o = e.v2o(ATTACK_SPHERES + SPHERE_SIZE * i)
        node = e.d[o] - 256 if e.d[o] > 127 else e.d[o]
        x, y, z, r = struct.unpack_from("<4f", e.d, o + 4)
        out.append(dict(node=node, offset=(x, y, z), radius=r * 2))   # x2 while attacking (Fighter_AttackCollide)
    return out


def anim_picker(lib, groups):
    """(anim id -> (group, Anim) or None) using the style's group preference list, cached."""
    cache = {}

    def pick(aid):
        if aid not in cache:
            locs = lib.where(aid)
            loc = next((l for g in groups for l in locs if l[0] == g), locs[0] if locs else None)
            cache[aid] = (loc[0], animkit.Anim(lib.entry(loc[1])[loc[2]])) if loc else None
        return cache[aid]
    return pick


def hip_z_track(pick, sim):
    """Node 1's forward (+Z) translation per game frame over every clip, metres, continuous across clip changes
    (each new clip continues from where the last one left the hips: the capsule's root motion)."""
    out, base, last_clip, prev = [], 0.0, -1, 0.0
    for k, a in zip(sim["clip_at"], sim["frame_at"]):
        got = pick(sim["clips"][k][0])
        z = hip_at(got[1], a / 60.0) if got else 0.0
        if k != last_clip:
            base = (out[-1] if out else 0.0) - z * UNIT
            last_clip = k
        out.append(round(base + z * UNIT, 4))
    return out


def hip_at(anim, t):
    keys = anim.tracks()[1]
    if t <= keys[0][0]:
        return keys[0][2][2]
    for a, b in zip(keys, keys[1:]):
        if a[0] <= t <= b[0]:
            u = (t - a[0]) / (b[0] - a[0]) if b[0] > a[0] else 0.0
            return a[2][2] + u * (b[2][2] - a[2][2])
    return keys[-1][2][2]


def build_move(e, lib, groups, act, name, sph, pick=None):
    pick = pick or anim_picker(lib, groups)
    tl = timeline(e, act)
    recs, (kind, cost) = records(e, act)
    m = dict(action=act, name=name or f"Action {act}", clips=[], kind=kind, cost=cost, notes=list(tl["ops"]))
    sim = action_sim.simulate(e, act, lambda aid: pick(aid)[1].frames if pick(aid) else None)
    if sim["clips"]:
        aid, s0, end, blend = sim["clips"][0]
        got = pick(aid)
        m.update(anim_id=aid, anim_group=got[0] if got else -1, anim_start=s0, anim_end=end, blend=blend)
        m["clips"] = [list(c) for c in sim["clips"]]
        m["frames"] = sim["frames"]
        m["frame_clip"] = sim["clip_at"]
        m["frame_anim"] = [round(x, 4) for x in sim["frame_at"]]
    else:
        m.update(anim_id=-1, anim_group=-1, anim_start=0, anim_end=60, blend=8, frames=60, frame_clip=[],
                 frame_anim=[])
        m["notes"].append("no motion script in the ELF")
    m["speeds"] = [(at, float(s)) for at, s in tl["speeds"]]
    m["combo_window"] = tl["combo"]
    m["anim_cancel"] = tl["cancel"][0] if tl["cancel"] else -1
    m["cancel"] = sim["cancel"][0] if sim["cancel"] else -1
    m["anim_release"] = tl["release"]
    m["release"] = sim["release"]
    m["anim_guard"] = tl["guard"]
    m["invincible"] = sim["invincible"]
    m["throws"] = [t["g"] for t in sim["throws"]]
    m["pair"] = pair_action(e, act)
    m["place"] = sim["place"]
    m["then"] = sim["then"] if sim["then"] is not None else -1
    m["root_z"] = hip_z_track(pick, sim) if sim["clips"] else []
    m["hits"] = []
    for w in sim["windows"]:
        r = recs[w["record"]] if w["record"] < len(recs) else dict(damage=0, pride=0, strength=0, detail=0, level=0,
                                                                     reaction=0)
        radius = max((sph[p]["radius"] for p in w["parts"] if 0 <= p < len(sph)), default=1.0) * UNIT
        m["hits"].append(dict(anim_start=w["anim_start"], anim_end=w["anim_end"], start=w["start"], end=w["end"],
                              parts=w["parts"], record=w["record"], radius=round(radius, 4), **r))
    # Throw damage (op 0x2B) uses the hit record current at that point, on the held target
    m["throw_hits"] = []
    for t in sim["throws"]:
        r = recs[t["record"]] if t["record"] < len(recs) else dict(damage=0, pride=0, strength=0, detail=0, level=0,
                                                                     reaction=0)
        m["throw_hits"].append(dict(anim_start=0, anim_end=0, start=t["g"], end=t["g"], parts=[], record=t["record"],
                                    radius=0.0, **r))
    return m


def pair_action(e, act):
    """The partner's action (g_ActionEvents[act] +8): the victim's side of a grab or throw; 0 = none."""
    p = e.u32(ACTION_EVENTS + 4 * act)
    return max(e.s16(p + 8), 0) if 0x00100000 <= p < 0x00600000 else 0


def style_names(e, iso):
    try:
        return bdkit.style_moves(e, os.path.join(iso, "XAF", "CDATA.XAF"))
    except Exception:  # noqa: BLE001 - names are only labels
        return {}


def build_style(e, lib, iso, style, groups):
    names = style_names(e, iso).get(style, [])
    by_input = {}
    for nm, inp in names:
        by_input.setdefault(inp, nm)
    sph = spheres(e)
    pick = anim_picker(lib, groups)
    commands, moves = [], {}
    for cond, codes, act in codemap.style_commands(e, style):
        if not codes or act <= 0:
            continue
        seq = [code_name(c) for c in codes]
        key = "".join(seq)
        nm = by_input.get(key) or next((n for n, s in names if key in s.split("/")), "")
        if act not in moves:
            moves[act] = build_move(e, lib, groups, act, nm, sph, pick)
        commands.append(dict(seq=seq, action=act, condition=bool(cond)))
    if not any(c["seq"] == [GRAB_CODE] for c in commands):
        # R1 from neutral: the generic grab attempt (Fighter_PickWeaponMove's default; Fighter_RemapAction(10) = 10)
        act = 9 if style in (0x12, 0x02) else 10
        if act not in moves:
            moves[act] = build_move(e, lib, groups, act, "Grab", sph, pick)
        commands.append(dict(seq=[GRAB_CODE], action=act, condition=False))
    fallback = {}
    for c in codemap.INPUTS:
        to = e.u32(INPUT_FALLBACK + 4 * c)
        if to != 0xFFFFFFFF and to in codemap.INPUTS:
            fallback[code_name(c)] = code_name(to)
    return commands, moves, fallback


# --- Godot text resources --------------------------------------------------------------------------------------

def q(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def gd(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return repr(round(v, 4))
    if isinstance(v, int):
        return str(v)
    if isinstance(v, str):
        return q(v)
    raise TypeError(v)


def limb_of(parts):
    """Capsule visuals only: which limb the attack parts belong to (0/1, 4/5 arms; 2/3, 6/7 legs)."""
    if any(p in (2, 3, 6, 7) for p in parts):
        return "leg", (min(parts) % 2) if parts else 0
    return "arm", (min(parts) % 2) if parts else 0


def write_tres(path, title, style, commands, moves, fallback):
    hit_lines, move_lines = [], []
    for act in sorted(moves):
        m = moves[act]
        hit_ids, throw_ids = [], []
        for k, h in enumerate(m["hits"] + m["throw_hits"]):
            hid = f"hit_{act}_{k}"
            (hit_ids if k < len(m["hits"]) else throw_ids).append(hid)
            down = bool(h["reaction"] & KNOCKDOWN_BITS)
            hit_lines += [f'[sub_resource type="Resource" id="{hid}"]', 'script = ExtResource("3_hit")',
                          f"start = {h['start']}", f"end = {h['end']}",
                          f"anim_start = {h['anim_start']}", f"anim_end = {h['anim_end']}",
                          f"parts = PackedInt32Array({', '.join(map(str, h['parts']))})",
                          f"record = {h['record']}", f"damage = {h['damage']}", f"pride = {h['pride']}",
                          f"strength = {h['strength']}", f"level = {h['level']}",
                          f"level_name = {q(HIT_LEVEL.get(h['level'] & 0xE, 'none'))}",
                          f"reaction = {h['reaction']}", f"reaction_detail = {h['detail']}",
                          f"knockdown = {gd(down)}", f"radius = {gd(h['radius'])}", ""]
        first = m["hits"][0] if m["hits"] else None
        limb, side = limb_of(first["parts"] if first else [])
        lines = [f'[sub_resource type="Resource" id="move_{act}"]', 'script = ExtResource("2_move")',
                 f"move_name = {q(m['name'])}", f"limb = {q(limb)}", f"side = {side}",
                 f"frames = {m['frames']}",
                 f"active_start = {first['start'] if first else 999}", f"active_end = {first['end'] if first else -1}",
                 f"cancel_start = {m['cancel']}", f"cancel_end = {m['cancel']}",
                 f"damage = {first['damage'] if first else 0}",
                 f"hits = [{', '.join(f'SubResource({q(h)})' for h in hit_ids)}]",
                 f"action_id = {act}", f"release_frame = {m['release']}", f"combo_window = {gd(m['combo_window'])}",
                 f"invincible = PackedVector2Array({', '.join(f'{a}, {b}' for a, b in m['invincible'])})",
                 f"root_z = PackedFloat32Array({', '.join(gd(float(z)) for z in m['root_z'])})",
                 f"anim_id = {m['anim_id']}", f"anim_group = {m['anim_group']}",
                 f"anim_start = {m['anim_start']}", f"anim_end = {m['anim_end']}", f"blend = {m['blend']}",
                 f"anim_cancel = {m['anim_cancel']}", f"anim_release = {m['anim_release']}",
                 f"speeds = PackedVector2Array({', '.join(f'{a}, {gd(s)}' for a, s in m['speeds'])})",
                 f"clips = [{', '.join('PackedInt32Array(' + ', '.join(map(str, c)) + ')' for c in m['clips'])}]",
                 f"frame_clip = PackedInt32Array({', '.join(map(str, m['frame_clip']))})",
                 f"frame_anim = PackedFloat32Array({', '.join(gd(float(x)) for x in m['frame_anim'])})",
                 f"throws = PackedInt32Array({', '.join(map(str, m['throws']))})", f"then_action = {m['then']}",
                 f"throw_hits = [{', '.join(f'SubResource({q(h)})' for h in throw_ids)}]",
                 f"pair_action = {m['pair']}",
                 f"place = PackedFloat32Array({', '.join(gd(float(x)) for x in (m['place'] or []))})",
                 f"attack_kind = {m['kind']}", f"cost = {m['cost']}",
                 f"notes = PackedStringArray({', '.join(q(n) for n in m['notes'])})", ""]
        move_lines += lines
    cmd = ", ".join("{" + f'"seq": PackedStringArray({", ".join(q(s) for s in c["seq"])}), '
                    f'"move": SubResource("move_{c["action"]}"), "condition": {gd(c["condition"])}' + "}"
                    for c in commands)
    fb = ", ".join(f"{q(k)}: {q(v)}" for k, v in sorted(fallback.items()))
    n_sub = sum(1 for x in hit_lines + move_lines if x.startswith("[sub_resource"))
    head = [f'[gd_resource type="Resource" script_class="MoveSet" load_steps={n_sub + 4} format=3]', "",
            '[ext_resource type="Script" path="res://game/fighter/move_set.gd" id="1_set"]',
            '[ext_resource type="Script" path="res://game/fighter/move_data.gd" id="2_move"]',
            '[ext_resource type="Script" path="res://game/fighter/move_hit.gd" id="3_hit"]', ""]
    tail = ["[resource]", 'script = ExtResource("1_set")', f"style_name = {q(title)}", f"style_id = {style}",
            f"commands = [{cmd}]", f"fallback = {{{fb}}}", ""]
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(head + hit_lines + move_lines + tail))


def convert(iso, out, log=print):
    elf = os.path.join(iso, "SLUS_211.50")
    e = bdkit.Elf(elf)
    lib = animkit.Library(elf, os.path.join(iso, "XAF", "STAGE.XAF"))
    d = os.path.join(out, "moves")
    os.makedirs(d, exist_ok=True)
    for name, style, title, groups in STYLES:
        commands, moves, fallback = build_style(e, lib, iso, style, groups)
        path = os.path.join(d, f"{name}.tres")
        write_tres(path, title, style, commands, moves, fallback)
        hits = sum(len(m["hits"]) for m in moves.values())
        log(f"  moves/{name}.tres: {len(commands)} commands, {len(moves)} actions, {hits} hit windows")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    convert(sys.argv[1], sys.argv[2])
