#!/usr/bin/env python3
"""Beat Down text: the CDATA.XAF text banks, the SCRIPT.XAF dialogue strings, and the game's control codes.

    python tools/textkit.py banks ISO/XAF/CDATA.XAF                 # the 8 banks: entries, id ranges, counts
    python tools/textkit.py get   ISO/XAF/CDATA.XAF 11069 18002 45698 [--lang en] [--raw]
    python tools/textkit.py find  ISO/XAF/CDATA.XAF "RECRUIT" [--lang en]
    python tools/textkit.py dialogue ISO/XAF/SCRIPT.XAF 0 [--lang en]   # one dialogue/mission script's strings

Prints game text to the terminal only; never commit its output (docs/FORMATS.md, "Text").

Format (read from the code: Text_Get 0x00387980, Text_LoadBank 0x00387780, the text encoder Text_Encode 0x001B2BE0):
  bank entry: {u32 size, u16 count, u16 language, count x {u16 id, u16 byte length, u32 offset}} then the strings,
  UTF-8, NUL-terminated, ASCII stored as full-width (U+FF01-FF5E, space U+3000).
Markup (to_markup): the game's codes become plain text plus {tokens}; see TOKENS below and docs/FORMATS.md.
Standard library only.
"""
import argparse
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bdkit  # noqa: E402

LANGS = ["jp", "en", "fr", "de", "es", "it"]          # order of a bank's six CDATA entries and of dialogue parts
LANG_ID = {"jp": 0, "en": 1, "de": 2, "es": 3, "fr": 4, "it": 5}   # the bank header's u16 language = g_SystemData.language

# (name, first CDATA.XAF entry (JP; + LANGS index), Text_Get slot, id ranges Text_Get routes to it)
# Slot 0 is always loaded; 1 moves and 2 items are fixed; 3/4 is one swappable bank at a time (Text_LoadBank).
BANKS = [
    ("ui", 385, 0, []),                                   # everything Text_Get doesn't route elsewhere
    ("items", 391, 2, [(12000, 17999)]),
    ("moves", 397, 1, [(40000, 49999)]),
    ("missions", 403, 3, [(35000, 39498)]),               # job titles and descriptions
    ("partner", 409, 3, [(61000, 63999)]),                # party member lines
    ("rumours", 415, 3, [(29000, 29999)]),                # town rumours and hints
    ("system", 421, 3, [(25000, 26999)]),                 # memory card messages
    ("credits", 427, 3, [(5000, 8999), (9100, 9399)]),
]
FALLBACK_ID = 10201      # Text_Get shows this UI text when an id is missing from its bank


def bank_for_id(tid):
    """The bank Text_Get reads a text id from (its range checks)."""
    for name, _, _, ranges in BANKS[1:]:
        if any(a <= tid <= b for a, b in ranges):
            return name
    return "ui"


def read_bank_raw(cdata, bank, lang="en"):
    """{text id: raw string} of one bank (UTF-8 decoded, NUL stripped, nothing else changed)."""
    first = {b[0]: b[1] for b in BANKS}[bank]
    o, s = bdkit.xaf_entries(cdata)[first + LANGS.index(lang)][1:3]
    with open(cdata, "rb") as f:
        f.seek(o)
        d = f.read(s)
    _, n, lid = struct.unpack_from("<IHH", d, 0)
    if lid != LANG_ID[lang]:
        raise ValueError(f"bank {bank} {lang}: header says language {lid}, expected {LANG_ID[lang]}")
    base = 8 + 8 * n
    out = {}
    for i in range(n):
        tid, ln, off = struct.unpack_from("<HHI", d, 8 + 8 * i)
        out[tid] = d[base + off:base + off + ln].split(b"\0", 1)[0].decode("utf-8", "replace")
    return out


# --- control codes ----------------------------------------------------------------------------------------------
# Text_Encode 0x001B2BE0 turns a UTF-8 string into the font's 16-bit codes plus a colour byte per character. Codes it
# handles (confidence: read from the code; the button defaults also from g_PadLayouts 0x005CF7C0):
#   "\" "n" (two characters) or LF  -> new line
#   "@"/"$" (half-width) + digit d  -> colour d for the following characters (0 = default); + anything else -> colour 0
#   U+3000 / " "                    -> space;  U+FF01-FF5E -> ASCII
# One-character placeholders filled from globals set by Text_Set* (0x001B7D80-0x001B7E10) before the text is shown:
TOKENS = {
    "∀": "{person}",     # ∀  person name: 0 = the player's hero (Fighter_DisplayName), else text 11001 + n (g_TextPerson)
    "⑫": "{person2}",    # ⑫  same, second slot (g_TextPerson2)
    "〒": "{area}",       # 〒  area name: g_AreaDefs[n].name_text (1-54), or the +2 text of g_AreaDefs[n - 100] (100-153)
    "㈲": "{item}",       # ㈲  item name: text 11999 + n (n < 108) else 17316 + n
    "⑦": "{item1}",      # ⑦  item name, slot 1 (a few n have their own text 0x39D1-0x39DB)
    "⑧": "{item2}",      # ⑧  item name, slot 2
    "㈱": "{money}",      # ㈱  "$" (text 10202) + number; German puts the number first
    "⑮": "{num1}",       # ⑮  number (Str_FromInt)
    "⑯": "{num2}",       # ⑯  number (controller port, memory card slot, ...)
    "⑬": "{text1}",      # ⑬  any text id
    "⑭": "{text2}",      # ⑭  any text id
    "⑩": "”",       # ⑩  closing quote ”
    "⑪": "“",       # ⑪  opening quote “
    # Buttons by action, from the player's controller layout (g_SystemData +5; JP remaps it). Default layout 0:
    "〆": "{btn:punch}",    # 〆  default □
    "◎": "{btn:kick}",     # ◎  default △
    "◇": "{btn:guard}",    # ◇  default ×
    "▽": "{btn:special}",  # ▽  default ○ (threaten, negotiate, DEVASTATOR)
    "≠": "{btn:punch_on}",   # ≠  the same four drawn filled (pressed)
    "⑳": "{btn:kick_on}",    # ⑳
    "◆": "{btn:guard_on}",   # ◆
    "▼": "{btn:special_on}", # ▼
    "♯": "{btn:ok}",       # ♯  × (JP: ○)
    "♭": "{btn:back}",     # ♭  △ (JP: ×)
    "♪": "{btn:third}",    # ♪  □ (JP: △)
    # Fixed button glyphs (the face buttons, outline and filled)
    "○": "{btn:circle}", "△": "{btn:triangle}", "□": "{btn:square}", "×": "{btn:cross}",
    "●": "{btn:circle_on}", "▲": "{btn:triangle_on}", "■": "{btn:square_on}", "Ⅹ": "{btn:cross_on}",
    # Icon glyphs: ①-⑥ shoulder / stick buttons (tutorials: ① + stick = RUN, ②/⑤ use equipped items, ④ grab/pick up,
    # ⑥ taunt; which physical button each is is not pinned down), ⑰ ⑱ two more icons, ∬ "rapid press" (GRAB ∬〆)
    "①": "{icon:1}", "②": "{icon:2}", "③": "{icon:3}", "④": "{icon:4}", "⑤": "{icon:5}",
    "⑥": "{icon:6}", "⑰": "{icon:17}", "⑱": "{icon:18}", "∬": "{icon:rapid}",
    "⑲": "®",       # ⑲  ®
    "α": "{icon:alpha}",  # α  a menu button in tutorials ("open a menu with α"; probably START), own glyph
    "β": "{icon:beta}",   # β  its partner glyph (probably SELECT; unused in English)
}
for _c in "㊤㊥㊦㊧㊨":   # ㊤㊥㊦㊧㊨: icon glyphs (unused in the English banks)
    TOKENS[_c] = "{icon:%04x}" % ord(_c)


def to_markup(raw):
    """Game string -> remake markup: plain UTF-8 with "\\n" new lines, {cN} colours and the {tokens} above."""
    out = []
    i, n = 0, len(raw)
    while i < n:
        c = raw[i]
        if c == "\\" and i + 1 < n and raw[i + 1] == "n":
            out.append("\n"); i += 2; continue
        if c in "@$":
            d = raw[i + 1] if i + 1 < n else ""
            out.append("{c%s}" % (d if d.isdigit() else "0")); i += 2; continue
        if c == "　":
            out.append(" ")
        elif "！" <= c <= "～":
            out.append(chr(ord(c) - 0xFEE0))
        elif c in TOKENS:
            out.append(TOKENS[c])
        elif c in "{}":
            out.append("{lb}" if c == "{" else "{rb}")
        else:
            out.append(c)
        i += 1
    return "".join(out)


def game_text(cdata, lang="en", markup=True):
    """{text id: string} as Text_Get returns it: every bank merged by Text_Get's routing. Ids a bank holds but
    Text_Get never reads from it (UI-bank ids inside another bank's range) are left out."""
    out = {}
    for name, *_ in BANKS:
        for tid, s in read_bank_raw(cdata, name, lang).items():
            if bank_for_id(tid) == name:
                out[tid] = to_markup(s) if markup else s
    return dict(sorted(out.items()))


# --- SCRIPT.XAF strings ----------------------------------------------------------------------------------------
def script_strings(img):
    """The string table of one script image (docs/SCRIPTS.md, "Script file format"), raw."""
    _, _, _, nstr, stab = struct.unpack_from("<HHIII", img, 0)
    base = 0x20 + stab
    out = []
    for k in range(nstr):
        o = struct.unpack_from("<I", img, base + 4 * k)[0]
        out.append(decode(img[base + o:img.index(b"\0", base + o)]))
    return out


def decode(b):
    """UTF-8; a few unused scripts (SCRIPT.XAF 324, 485-499) still hold Shift-JIS from development."""
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("cp932", "replace")


def script_entry_strings(script_xaf, entry, lang="en", ents=None, f=None):
    """Strings of SCRIPT.XAF entry (0-999 dialogue: that language's part; 1000 + n: mission n, one language)."""
    ents = ents or bdkit.xaf_entries(script_xaf)
    o, s = ents[entry][1:3]
    if s < 0x20:
        return []
    own = f is None
    f = f or open(script_xaf, "rb")
    try:
        f.seek(o)
        data = f.read(s)
    finally:
        if own:
            f.close()
    if entry < 1000:
        k = struct.unpack_from("<I", data, 0)[0]
        if k != len(LANGS):
            return []
        offs = list(struct.unpack_from(f"<{k}I", data, 4)) + [len(data)]
        i = LANGS.index(lang)
        data = data[offs[i]:offs[i + 1]]
    if len(data) < 0x20:
        return []
    try:
        return script_strings(data)
    except (struct.error, ValueError):
        return []


def all_script_strings(script_xaf, lang="en", markup=True):
    """{SCRIPT.XAF entry: [strings]} for every entry that has any."""
    ents = bdkit.xaf_entries(script_xaf)
    out = {}
    with open(script_xaf, "rb") as f:
        for e in range(len(ents)):
            ss = script_entry_strings(script_xaf, e, lang, ents, f)
            if ss:
                out[e] = [to_markup(x) if markup else x for x in ss]
    return out


# --- CLI ----------------------------------------------------------------------------------------------------------
def cmd_banks(a):
    for name, first, slot, ranges in BANKS:
        t = read_bank_raw(a.cdata, name, "en")
        used = sum(1 for k in t if bank_for_id(k) == name)
        rng = ", ".join(f"{x}-{y}" for x, y in ranges) or "the rest"
        print(f"{name:9} entries {first}-{first + 5}  slot {slot}  ids {min(t)}-{max(t)} ({len(t)}, {used} reachable)"
              f"  Text_Get range: {rng}")


def cmd_get(a):
    t = game_text(a.cdata, a.lang, markup=not a.raw)
    for x in a.ids:
        tid = int(x, 0)
        print(f"{tid} [{bank_for_id(tid)}]: {t.get(tid, '(missing)')!r}")


def cmd_find(a):
    for tid, s in game_text(a.cdata, a.lang).items():
        if a.text.lower() in s.lower():
            print(f"{tid} [{bank_for_id(tid)}]: {s!r}")


def cmd_dialogue(a):
    for i, s in enumerate(script_entry_strings(a.script, a.entry, a.lang)):
        print(f"{i}: {(s if a.raw else to_markup(s))!r}")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    x = sub.add_parser("banks"); x.add_argument("cdata"); x.set_defaults(fn=cmd_banks)
    x = sub.add_parser("get"); x.add_argument("cdata"); x.add_argument("ids", nargs="+")
    x.add_argument("--lang", default="en", choices=LANGS); x.add_argument("--raw", action="store_true")
    x.set_defaults(fn=cmd_get)
    x = sub.add_parser("find"); x.add_argument("cdata"); x.add_argument("text")
    x.add_argument("--lang", default="en", choices=LANGS); x.set_defaults(fn=cmd_find)
    x = sub.add_parser("dialogue"); x.add_argument("script"); x.add_argument("entry", type=int)
    x.add_argument("--lang", default="en", choices=LANGS); x.add_argument("--raw", action="store_true")
    x.set_defaults(fn=cmd_dialogue)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
