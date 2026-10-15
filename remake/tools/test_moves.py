#!/usr/bin/env python3
"""Check the generated moves (assets_ripped/moves/<style>.tres) against `codemap.py framedata`, in Godot.

    python remake/tools/test_moves.py ISO remake/godot/assets_ripped
    python remake/tools/test_moves.py ISO remake/godot/assets_ripped --style 0x13 --name aaron --godot <console exe>

Runs `tools/codemap.py framedata ISO/SLUS_211.50 <style>` (the frame data as the research tool prints it), turns
its text into expected values (command -> action, animation and blend, speeds, active windows with parts and damage,
cancel point, release, motion end; all in animation frames), then loads the MoveSet in headless Godot
(res://dev/move_check.gd) and compares field by field. Animation-frame values must match exactly. Game-frame values
are checked against the first game frame at or after the time framedata prints (ceil) within 2 frames: framedata
switches speed at the exact frame, the converter (like the game) on the first whole frame that reaches it, so moves
with several speed changes drift by a frame or two; those are listed as notes. Exit code 0 = everything matches.
"""
import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
GODOT = os.path.join(ROOT, "__external_tools", "godot", "Godot_v4.7.2-stable_win64_console.exe")

HEAD = re.compile(r"^(?P<inp>.+?)  action (?P<act>\d+): anim (?P<anim>-?\d+) \[(?P<s0>\d+)-(?P<s1>\w+), blend (?P<blend>\d+)"
                  r"(?:, anim length (?P<len>\d+))?\](?:  speed (?P<speed>.+))?$")
EVENT = re.compile(r"^\s+(?P<f>-?\d+)  \(game\s+(?P<g>-?[\d.]+)\)  (?P<txt>.*)$")
ACTIVE = re.compile(r"ACTIVE (-?\d+)-(-?\d+) \(game ([\d.]+)-([\d.]+)\) parts ([\d,]*), hit record (\d+) damage (\S+)")


def ceil_frame(x):
    """First whole game frame at or after a time framedata prints with one decimal."""
    v = float(x)
    return int(v) if abs(v - round(v)) < 0.051 and round(v) == int(v) else int(v) + 1


def split_codes(inp):
    """"→P P" -> ["→P", "P"]; keeps the codes with a space ("GRAB P", "REAR GRAB K") whole."""
    out = []
    for tok in inp.split(" "):
        if out and out[-1] in ("GRAB", "REAR", "REAR GRAB"):
            out[-1] += " " + tok
        else:
            out.append(tok)
    return out


def parse(text):
    acts, cmds, cur = {}, [], None
    for line in text.splitlines():
        m = HEAD.match(line)
        if m:
            act = int(m["act"])
            cmds.append(dict(seq=split_codes(m["inp"]), action=act))
            if act in acts:
                cur = None            # same action under another input: already parsed
                continue
            speeds = []
            for tok in (m["speed"] or "").split():
                s, f = tok.split("@")
                speeds.append([int(f), float(s)])
            length = int(m["len"]) if m["len"] else None
            s1 = -1 if m["s1"] == "end" else int(m["s1"])
            cur = acts[act] = dict(anim=int(m["anim"]), blend=int(m["blend"]), speeds=speeds, hits=[], cancel=-1,
                                   release=-1, end=(length if s1 == -1 else min(s1, length)) if length else None,
                                   cancel_g=-1, release_g=-1, end_g=-1)
            continue
        e = EVENT.match(line)
        if not e or cur is None:
            continue
        f, g, txt = int(e["f"]), e["g"], e["txt"]
        a = ACTIVE.search(txt)
        if a:
            cur["hits"].append(dict(start=int(a[1]), end=int(a[2]), start_g=ceil_frame(a[3]),
                                    parts=[int(x) for x in a[5].split(",") if x], damage=int(a[7])))
        elif txt.startswith("cancel point") and cur["cancel"] < 0:
            cur["cancel"], cur["cancel_g"] = f, ceil_frame(g)
        elif txt.startswith("control returns"):
            cur["release"], cur["release_g"] = f, ceil_frame(g)
        elif txt.startswith("motion ends"):
            cur["end_g"] = ceil_frame(g)
    return acts, cmds


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("iso")
    p.add_argument("assets", help="remake/godot/assets_ripped (holds moves/<name>.tres)")
    p.add_argument("--style", default="0x13")
    p.add_argument("--name", default="aaron")
    p.add_argument("--godot", default=GODOT)
    a = p.parse_args()
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    out = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "codemap.py"), "framedata",
                          os.path.join(a.iso, "SLUS_211.50"), a.style], capture_output=True, text=True,
                         encoding="utf-8", env=env, check=True).stdout
    acts, cmds = parse(out)
    want = dict(style=a.name, actions={str(k): v for k, v in acts.items()}, commands=cmds)
    path = os.path.join(a.assets, "moves", f"{a.name}.expected.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(want, f, ensure_ascii=False, indent=1)
    print(f"framedata {a.style}: {len(cmds)} commands, {len(acts)} actions -> {path}")
    r = subprocess.run([a.godot, "--headless", "--path", os.path.join(ROOT, "remake", "godot"),
                        "--script", "res://dev/move_check.gd", "--", f"--expect={os.path.abspath(path)}"],
                       capture_output=True, text=True, encoding="utf-8")
    lines = [l for l in r.stdout.splitlines() if l.strip() and not l.startswith("Godot Engine")]
    print("\n".join(lines))
    if r.returncode != 0 and r.stderr.strip():
        print(r.stderr[-2000:])
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
