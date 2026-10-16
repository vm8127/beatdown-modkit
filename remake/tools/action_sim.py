"""Plays one action's two streams together, game frame by game frame, the way Action_Step 0x0031FAE0 (motion script)
and Action_Timeline 0x00320310 (second stream) run them (docs/ANIMATION.md, "Actions and their motion scripts",
"Frame data"). Used by conv_moves.py (moves) and conv_anims.py (hit reactions, knockdowns, getups, guard).

What it models (read from code, 2026-10-16):
- The motion script plays its clips in order (op 0 play: anim, start, end, blend); each waits until the motion ends.
- The timeline's clock is the current motion frame (+0x2D4, the animation frame), so its waits ("wait n": motion
  frame >= n) count from the clip that is playing. A multi-clip action's timeline is split by a `wait 999` (never
  reached by a clip) that the motion script's op 4 ("reset", clears the wait +0x3FD0) releases when the next clip
  starts: so the ops after it run against the next clip's frames (REAR GRAB P, action 304: clips 286, 287, 288).
- Playback speed (+0x3FE8) is set to 1.0 by Fighter_SetAction and changed by speed ops in either stream; a new clip
  keeps it. The animation frame advances by the speed every game frame (exact fractions), and an op waiting on frame n
  fires on the first game frame whose whole animation frame reaches n.
- Not modelled: branches (0x32/0x33), random follow-ups, timeline loops (they stop the timeline); the motion script's
  own loop (lying actions 19/20) ends the simulation with `loops` = True.
"""
import math
from fractions import Fraction

import codemap

MAX_FRAMES = 2000


def simulate(e, act, length_of):
    """Run action `act`. `length_of(anim id)` gives a clip's length in animation frames (None if unknown).

    Returns a dict:
      clips     [[anim, start, end, blend]] in play order, end = the effective end frame (capped at the length)
      clip_at   per game frame: index into clips;  frame_at: animation frame shown (float)
      frames    game frame on which the last clip has ended (the action is over)
      windows   attack windows: {clip, anim_start, anim_end, start, end, parts, record} (start/end in game frames)
      cancel    game frames of cancel points (op 0x16); combo: op 0x15 seen
      release   game frame control returns (op 0x3C release r: motion frame r - 1 of its clip), -1 = none
      guard     game frame the GUARD control bit is set (op 0x3C guard frame), -1 = none
      invincible [(first, last)] game frames with status MATCHLESS
      throws    game frames of op 0x2B (throw damage on the held target)
      then      the action the motion script continues with (goto / start), None
      loops     the motion script loops forever (lying)
    """
    script = codemap.motion_script(e, act)
    stream = codemap.action_stream(e, act)
    out = dict(clips=[], clip_at=[], frame_at=[], frames=0, windows=[], cancel=[], combo=False, release=-1,
               guard=-1, invincible=[], throws=[], then=None, loops=False, notes=[])
    if not script:
        out["notes"].append("no motion script in the ELF")
        return out
    mpc = 0                   # motion script position
    tpc = 0                   # timeline position
    t_wait = None             # timeline waiting for motion frame >= t_wait
    t_stopped = False
    speed = Fraction(1)
    a = Fraction(0)
    clip = -1
    end = Fraction(0)
    hit_index = 0
    inv_start = None
    pend_release = None       # (clip, frame) checks made by op 0x3C
    pend_guard = None
    windows = []              # (clip, s, e, parts, record), resolved to game frames at the end

    def run_motion():
        """Runs motion ops until a play starts (True) or the action is over (False)."""
        nonlocal mpc, clip, a, end, speed, t_wait
        while mpc < len(script):
            name, args = script[mpc]
            mpc += 1
            if name == "play":
                aid, s0, s1, blend = args
                n = length_of(aid)
                e_ = n if s1 == -1 else (min(s1, n) if n is not None else s1)
                if e_ is None:
                    e_ = 60
                    out["notes"].append(f"anim {aid} length unknown")
                out["clips"].append([aid, s0, e_, blend])
                clip = len(out["clips"]) - 1
                a = Fraction(s0)
                end = Fraction(e_)
                return True
            if name == "reset":
                t_wait = None
            elif name == "speed":
                speed = Fraction(args[0], 1000)
            elif name in ("goto", "start"):
                out["then"] = args[0]
                return False
            elif name == "random":
                out["then"] = args[0] if args else None
                out["notes"].append("random follow-up")
                return False
            elif name == "loop":
                out["loops"] = True
                return False
            elif name == "end":
                return False
        return False

    def run_timeline(g):
        nonlocal tpc, t_wait, t_stopped, speed, hit_index, inv_start, pend_release, pend_guard
        while not t_stopped and tpc < len(stream):
            if t_wait is not None:
                if math.floor(a) >= t_wait:
                    t_wait = None
                else:
                    return
            op, name, args = stream[tpc]
            tpc += 1
            if name == "wait":
                t_wait = args[0]
            elif name == "speed":
                speed = Fraction(args[0], 1000)
            elif name == "attack":
                c, before, after = args[0], args[1], args[2]
                windows.append((clip, c - before, c + after, list(args[3:-1]), hit_index))
            elif name == "hitindex":
                hit_index = args[0]
            elif name == "combo":
                out["combo"] = True
            elif name == "cancel":
                out["cancel"].append(g)
            elif name == "op3C":
                if args[0]:
                    pend_release = (clip, args[0] - 1)
                if args[1]:
                    pend_guard = (clip, args[1] - 1)
            elif name == "throwhit":
                out["throws"].append(g)
            elif name == "status":
                v = (args[1] & 0xFFFF) << 16 | (args[2] & 0xFFFF)
                if v & 1:                     # MATCHLESS: takes no damage
                    if args[0] == 1:
                        inv_start = g
                    elif inv_start is not None:
                        out["invincible"].append((inv_start, g))
                        inv_start = None
            elif name in ("branch", "ifstatus", "random"):
                out["notes"].append(name)
            elif name == "loop":
                out["notes"].append("loop")
                t_stopped = True
            elif name == "end":
                t_stopped = True

    if not run_motion():
        return out
    g = 0
    while g < MAX_FRAMES:
        run_timeline(g)
        if a >= end:
            if not run_motion():
                out["clip_at"].append(clip)
                out["frame_at"].append(float(end))
                break
            run_timeline(g)               # the new clip's frame-0 ops (the reset released the wait)
        out["clip_at"].append(clip)
        out["frame_at"].append(float(a))
        for chk, key in ((pend_release, "release"), (pend_guard, "guard")):
            if chk and out[key] < 0 and chk[0] == clip and math.floor(a) >= chk[1]:
                out[key] = g
        a += speed
        g += 1
    out["frames"] = g
    if inv_start is not None:
        out["invincible"].append((inv_start, 9999))
    for k, s, e_, parts, rec in windows:
        gs = [i for i, (c, f) in enumerate(zip(out["clip_at"], out["frame_at"])) if c == k]
        first = next((i for i in gs if math.floor(out["frame_at"][i]) >= s), out["frames"])
        last = max((i for i in gs if math.floor(out["frame_at"][i]) <= e_), default=first)
        out["windows"].append(dict(clip=k, anim_start=s, anim_end=e_, start=first, end=last, parts=parts, record=rec))
    return out
