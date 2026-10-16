"""Measure Aaron's moves in the real game (sandbox PCSX2) for the game-vs-remake combat comparison.

Needs the sandbox running a VS fight where the CPU stands still: VS MODE NORMAL, PLAYER vs CPU, Aaron vs anyone,
debug switch 17 on (`pcsx2.py w32 0x00599044 1`: the CPU fighter reads pad 2, which nobody presses) and both
weapons taken away (`w16` fighter +0x432C = -1). docs/ANIMATION.md, "Measured in the game", says how it was set up.

For each sequence: walks Aaron (slot 0) to the given distance from the CPU fighter (slot 1), refills both HPs,
presses the inputs, records every field change with game_rec.py's sampler, and prints one line per move: the
actions Aaron played with their game frame of start, every hit (game frame, damage, the victim's reaction action,
its posture), whether the victim ended lying, and the distance moved. `--json` writes all of it for
remake/tools/compare_combat.py.

  python remake/tools/game_probe.py "P P P" "→P P P" --dist 1.2 --json remake/tools/game_combat.json
  python remake/tools/game_probe.py "P P" --gap 8         # press each next input 8 frames after the move starts

Inputs are move codes as the remake writes them: P (□), K (△), G (×), → / ← (toward / away from the CPU: the
fight camera looks from the side with Aaron on the left, so d-pad right / left), a space between presses.
"""
import argparse
import json
import os
import struct
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(__file__))
import game_rec  # noqa: E402
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools"))
import pcsx2  # noqa: E402

F, N = 0x006CFB70, 0x4730
BUTTONS = {"P": "J", "K": "I", "G": "K"}   # pad 1 keys (pcsx2.PAD1): square, triangle, cross
DIRS = {"→": "Right", "←": "Left", "↑": "Up", "↓": "Down"}


def rf(p, a):
    return struct.unpack("<f", struct.pack("<I", p.read(a, 4)))[0]


def dist(p):
    return ((rf(p, F + 0x2AC) - rf(p, F + N + 0x2AC)) ** 2 + (rf(p, F + 0x2B4) - rf(p, F + N + 0x2B4)) ** 2) ** 0.5 / 10


def idle(p):
    return p.read(F + 0x4346, 2) in (1, 979) and p.read(F + N + 0x4346, 2) in (1, 994, 979, 571, 8)


def wf(p, a, v):
    p.write(a, struct.unpack("<I", struct.pack("<f", v))[0], 4)


def face(p):
    """Turns both fighters to face each other (the idle CPU doesn't turn by itself; facing = game angle atan2(dx, dz))."""
    import math
    dx = rf(p, F + N + 0x2AC) - rf(p, F + 0x2AC)
    dz = rf(p, F + N + 0x2B4) - rf(p, F + 0x2B4)
    a = math.degrees(math.atan2(dx, dz))
    wf(p, F + 0x2D0, a)
    wf(p, F + N + 0x2D0, a + 180 if a < 0 else a - 180)
    time.sleep(0.1)


def find_dirs(p):
    """The d-pad keys that walk toward / away from the CPU with the current camera: taps each, keeps the best."""
    got = {}
    for key in ("Right", "Left", "Up", "Down"):
        d = dist(p)
        pcsx2.post_key(key, True)
        time.sleep(0.12)
        pcsx2.post_key(key, False)
        time.sleep(0.45)
        got[key] = dist(p) - d
    DIRS["→"] = min(got, key=got.get)
    DIRS["←"] = max(got, key=got.get)


def approach(p, want, tol=0.06):
    """Walk Aaron toward / away from the CPU until the distance is within tol metres of `want`."""
    find_dirs(p)
    best = dist(p)
    for i in range(60):
        d = dist(p)
        if abs(d - want) <= tol:
            return d
        if i and abs(d - want) >= abs(best - want) - 0.01:
            find_dirs(p)   # no progress: the camera turned
        best = d
        if os.environ.get("PROBE_DEBUG"):
            print(f"  approach {i}: d {d:.2f} toward {DIRS['→']}", file=sys.stderr)
        key = DIRS["→"] if d > want else DIRS["←"]
        hold = min(0.2, max(0.03, abs(d - want) / 5.0))   # a long hold turns the walk into a run and overshoots
        pcsx2.post_key(key, True)
        time.sleep(hold)
        pcsx2.post_key(key, False)
        time.sleep(0.5)
    return dist(p)


IDLE_ACTIONS = (1, 979, 994, 2, 3, 287, 288, 289, 290, 693, 694, 695, 696, 697, 698, 699, 797)


def press(code):
    d, b = code[:-1], code[-1]
    keys = [DIRS[c] for c in d[:1]] + [BUTTONS[b]]
    for k in keys:
        pcsx2.post_key(k, True)
    time.sleep(0.04)
    for k in reversed(keys):
        pcsx2.post_key(k, False)


def run(p, fast, seq, want, gap, secs):
    for _ in range(100):
        if idle(p):
            break
        time.sleep(0.1)
    d0 = approach(p, want)
    face(p)
    p.write(F + 0x441C, 4400, 2)
    p.write(F + N + 0x441C, 4400, 2)
    time.sleep(0.6)
    rows, presses = [], []
    codes = seq.split()
    t0 = time.perf_counter()
    due = 0.1                  # first press after 0.1 s, then `gap` frames after each new attack starts
    moves_seen = 0
    last, last_act = None, None
    while time.perf_counter() - t0 < secs:
        t = time.perf_counter() - t0
        if codes and due is not None and t >= due:
            presses.append(round(t * 60))
            threading.Thread(target=press, args=(codes.pop(0),), daemon=True).start()
            due = None
        v = game_rec.sample(fast, [0, 1])
        act = v[0]
        if act != last_act and act not in IDLE_ACTIONS:
            moves_seen += 1
            if codes and due is None and moves_seen == len(presses):
                due = t + gap / 60
        last_act = act
        if v != last:
            rows.append([t] + v)
            last = v
    return d0, presses, rows


def analyse(seq, d0, presses, rows):
    names = [n for n, *_ in game_rec.FIELDS]
    k = len(names)
    get = lambda r, s, n: r[1 + s * k + names.index(n)]
    moves, hits, reacts = [], [], []
    prev_mf = 0
    hp = get(rows[0], 1, "hp")
    act1 = get(rows[0], 1, "action")
    x0 = (get(rows[0], 0, "x"), get(rows[0], 0, "z"))
    for r in rows:
        f = round(r[0] * 60)
        a = get(r, 0, "action")
        if not moves or moves[-1]["action"] != a:
            moves.append({"action": a, "frame": f, "mframe0": get(r, 0, "mframe"), "prev_mframe": prev_mf})
        prev_mf = get(r, 0, "mframe")
        h = get(r, 1, "hp")
        a1 = get(r, 1, "action")
        if a1 != act1:
            reacts.append({"frame": f, "action": a1, "posture": get(r, 1, "posture"), "status": get(r, 1, "status")})
            act1 = a1
        if h < hp:
            hits.append({"frame": f, "damage": hp - h, "by": a, "mframe": get(r, 0, "mframe"),
                         "dist": round(((get(r, 0, "x") - get(r, 1, "x")) ** 2 + (get(r, 0, "z") - get(r, 1, "z")) ** 2) ** 0.5 / 10, 2)})
            hp = h
    x1 = (get(rows[-1], 0, "x"), get(rows[-1], 0, "z"))
    attacks = [m for m in moves if m["action"] not in (1, 979, 2, 693)]
    lying = any(rr["action"] in (19, 20) for rr in reacts)
    return {"seq": seq, "dist": round(d0, 2), "presses": presses, "moves": attacks, "hits": hits, "reactions": reacts,
            "lying": lying, "travel": round(((x1[0] - x0[0]) ** 2 + (x1[1] - x0[1]) ** 2) ** 0.5 / 10, 2)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("seqs", nargs="+")
    ap.add_argument("--dist", type=float, default=1.2)
    ap.add_argument("--gap", type=float, default=4, help="game frames after a move starts to press the next input (default 4)")
    ap.add_argument("--secs", type=float, default=3.5)
    ap.add_argument("--json")
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = fast = game_rec.FastPine()   # PINE serves one connection at a time
    out = []
    for seq in a.seqs:
        res = analyse(seq, *run(p, fast, seq, a.dist, a.gap, a.secs))
        out.append(res)
        mv = " ".join(f"{m['action']}@{m['frame']}(prev m{m['prev_mframe']})" for m in res["moves"])
        ht = " ".join(f"f{h['frame']}:-{h['damage']}({h['by']} m{h['mframe']} d{h['dist']})" for h in res["hits"])
        rc = " ".join(f"{r['action']}@{r['frame']}/p{r['posture']}" for r in res["reactions"])
        print(f"{seq:<12} d{res['dist']} presses {res['presses']} | moves {mv} | hits {ht} | victim {rc}"
              f"{' LYING' if res['lying'] else ''} | travel {res['travel']} m")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
