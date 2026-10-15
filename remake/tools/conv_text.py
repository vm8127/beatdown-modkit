#!/usr/bin/env python3
"""Game text for the remake: every text bank and every script's strings, in all six languages, as JSON.

    python remake/tools/conv_text.py ISO remake/godot/assets_ripped     (or through remake_assets.py, "text")

Writes, under <out>/text/ (never commit; it is the game's text):
  <lang>.json           {"language", "text": {text id: string}}: what Text_Get returns, all banks merged
  dialogue_<lang>.json  {"scripts": {SCRIPT.XAF entry: [strings]}}: 0-999 dialogue, 1000 + n mission n
  index.json            banks and their id ranges, the markup tokens, area id -> name text, style -> move list ids,
                        the id bases (person names 11001 + n, item names 11999 + n)
Strings use the markup of tools/textkit.py (to_markup; docs/FORMATS.md, "Text"): "\n" new lines, {cN} colour,
{person} {area} {item} {money} ... placeholders, {btn:punch} ... buttons, {icon:N} icons.
Read by remake/godot/game/text/game_text.gd. Deterministic: ids in numeric order, UTF-8, LF.
"""
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))
import bdkit  # noqa: E402
import textkit  # noqa: E402

AREA_DEFS = 0x005170F0    # g_AreaDefs: 57 x 0x104, +0 u16 name text, +2 u16 short name text
AREA_COUNT = 57


def write_json(path, obj):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")


def index(elf):
    e = bdkit.Elf(elf)
    areas = {}
    for a in range(AREA_COUNT):
        name, short = struct.unpack_from("<HH", e.d, e.v2o(AREA_DEFS + 0x104 * a))
        areas[str(a)] = [name, short]
    moves = {str(s): list(v) for s, v in sorted(e.move_lists().items()) if v}
    return {
        "languages": textkit.LANGS,
        "banks": [{"name": n, "cdata_entry_jp": first, "slot": slot, "ranges": [list(r) for r in rng]}
                  for n, first, slot, rng in textkit.BANKS],
        "fallback_id": textkit.FALLBACK_ID,
        "bases": {"person_name": 11001, "item_name": 11999, "item_name_high": 17316, "item_high_from": 108,
                  "money_prefix": 10202},
        "tokens": sorted(set(v for v in textkit.TOKENS.values() if v.startswith("{"))) + ["{c0}..{c9}", "{lb}", "{rb}"],
        "areas": areas,                 # area id (Area_Current) -> [name text, short name text]
        "move_lists": moves,            # fighting style -> [first input text, last input text, first name text, last]
    }


def convert(iso, out, log=print):
    cdata = os.path.join(iso, "XAF", "CDATA.XAF")
    script = os.path.join(iso, "XAF", "SCRIPT.XAF")
    d = os.path.join(out, "text")
    os.makedirs(d, exist_ok=True)
    for lang in textkit.LANGS:
        t = textkit.game_text(cdata, lang)
        write_json(os.path.join(d, f"{lang}.json"), {"language": lang, "text": {str(k): v for k, v in t.items()}})
        s = textkit.all_script_strings(script, lang)
        write_json(os.path.join(d, f"dialogue_{lang}.json"),
                   {"language": lang, "scripts": {str(k): v for k, v in sorted(s.items())}})
        log(f"  text/{lang}.json: {len(t)} texts; dialogue_{lang}.json: {len(s)} scripts, "
            f"{sum(len(v) for v in s.values())} strings")
    write_json(os.path.join(d, "index.json"), index(os.path.join(iso, "SLUS_211.50")))
    log("  text/index.json")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    convert(sys.argv[1], sys.argv[2])
