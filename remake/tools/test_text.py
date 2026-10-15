#!/usr/bin/env python3
"""Check the converted game text (conv_text.py) as the remake reads it (GameText) against the older decoders.

    python remake/tools/test_text.py ISO remake/godot/assets_ripped

Expected values come from bdkit.py's own text reader (the one docs/movesets.md was generated with: every style's
MOVE LIST, names and inputs), README.md / docs facts (11069 Aaron, area 5 = ABANDONED SUBWAY STATION, the four
negotiation choices) and scriptkit.py (dialogue 1's string count). Godot runs dev/text_check.gd on them.
Needs the text converted first (remake_assets.py, or conv_text.py alone). Exit code 0 = all match.
"""
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import bdkit  # noqa: E402
import scriptkit  # noqa: E402

GODOT = os.path.join(ROOT, "__external_tools", "godot", "Godot_v4.7.2-stable_win64_console.exe")
# bdkit's text (NFKC) button characters -> the glyphs GameText draws for the default controller layout
GLYPH = {"〆": "□", "◎": "△", "◇": "×", "▽": "○", "∫∫": "[rapid]"}


def glyphs(s):
    for k, v in GLYPH.items():
        s = s.replace(k, v)
    return re.sub(r"(?<![0-9])4(?![0-9])", "[4]", s)   # NFKC turned the ④ icon (action button) into "4"


def main():
    sys.stdout.reconfigure(encoding="utf-8")  # the texts hold button glyphs (□ △ ×) a Windows console code page can't print
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    iso = sys.argv[1]
    cdata = os.path.join(iso, "XAF", "CDATA.XAF")
    e = bdkit.Elf(os.path.join(iso, "SLUS_211.50"))
    t = bdkit.text_table(cdata, bdkit.MOVE_TEXT_ENTRY["en"])     # the reader docs/movesets.md was made with
    moves = {}
    for style, v in e.move_lists().items():
        if v:
            c0, c1, n0, _ = v
            moves[str(style)] = [[t.get(n0 + i, "?").strip(), glyphs(t.get(c0 + i, "?"))] for i in range(c1 - c0 + 1)]
    img = scriptkit.script_parts(scriptkit.xaf_read(os.path.join(iso, "XAF", "SCRIPT.XAF"), 1), 1, "en")
    want = {
        "texts": {"11069": "Aaron", "18002": "ABANDONED SUBWAY STATION", "45698": "Blade Cut",
                  "10004": "RECRUIT", "10005": "ROB", "10006": "INTERROGATE", "10007": "BEATDOWN",
                  "50587": "Wanna join me?\nOr would you rather die?",
                  "30232": "□:PUNCH △:KICK ×:GUARD"},
        "person_68": "Aaron",
        "area_5": "ABANDONED SUBWAY STATION",
        "move_lists": moves,
        "dialogue_1_count": len(scriptkit.parse(img)["strings"]),
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(want, f, ensure_ascii=False)
        path = f.name
    try:
        r = subprocess.run([GODOT, "--headless", "--path", os.path.join(ROOT, "remake", "godot"),
                            "--script", "res://dev/text_check.gd", "--", "--expect=" + path],
                           capture_output=True, text=True, encoding="utf-8")
    finally:
        os.unlink(path)
    lines = [x for x in r.stdout.splitlines() if not x.startswith("Godot Engine")]
    print("\n".join(lines))
    if r.returncode and r.stderr:
        print(r.stderr[-2000:])
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
