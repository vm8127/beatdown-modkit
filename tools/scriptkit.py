#!/usr/bin/env python3
"""Beat Down (SLUS-21150) script tools: disassemble SCRIPT.XAF and list the missions. docs/SCRIPTS.md explains it all.

  python tools/scriptkit.py dis ISO/SLUS_211.50 ISO/XAF/SCRIPT.XAF 1001          # mission/event script 1 (entry 1000 + id)
  python tools/scriptkit.py dis ISO/SLUS_211.50 ISO/XAF/SCRIPT.XAF 2 --lang en   # dialogue script 2 (EXF_MESSAGE 2), English
  python tools/scriptkit.py dis ISO/SLUS_211.50 ISO/XAF/SCRIPT.XAF missions --out dumps/scripts   # every mission script
  python tools/scriptkit.py missions ISO/SLUS_211.50 ISO/XAF/CDATA.XAF > dumps/missions.txt
  python tools/scriptkit.py stats ISO/SLUS_211.50 ISO/XAF/SCRIPT.XAF              # how often each command is used
  python tools/scriptkit.py jobs ISO/SLUS_211.50 ISO/XAF/CDATA.XAF                 # the 50 side jobs' prerequisites (Markdown)

SCRIPT.XAF entries 0-999 are dialogue scripts (six language parts each, played by EXF_MESSAGE n); entries 1000 + n
are mission/event scripts (mission id n, run by the event VM). Both use the 204 commands of g_ScriptOpcodes.
Python 3 standard library only.
"""
import argparse
import os
import struct
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bdkit  # noqa: E402

OPCODES = 0x00411AC0        # g_ScriptOpcodes: 204 x {u32 id, u32 words, u32 nargs, u8* types, char* name}
OP_HANDLERS = 0x005DACF0    # g_ScriptOpHandlers: 204 x {u32 flags, handler}
OP_COUNT = 204
MISSION_INFO = 0x005DB470   # 50 jobs x {u8 mission, u8 difficulty, u16 reward, u32 title text, u32 description text}
MISSION_INFO_COUNT = 50
JOB_LISTS = {"A": (0x005DB6D0, 0x22), "B": (0x005DB760, 0x10)}   # u32 mission ids offered by the two job lists
MISSION_REQ = 0x0059A750    # per mission id: {u16 stage mask, u8 min game clears (g_ClearCount), u8 min % of jobs cleared}
MISSION_FLAGS = 0x0059995C  # per mission id: u32 first story flag; the mission owns flags [first[id], first[id + 1])
AUTO_MISSIONS = (0x005DBD40, 26)   # u8 mission ids started when their condition function (0x0059A9A0) allows
TALK_MISSIONS = (0x005DBD60, 2)    # u32 mission ids that can start when talking to someone
MISSION_TEXT = {"jp": 403, "en": 404, "fr": 405, "de": 406, "es": 407, "it": 408}   # CDATA.XAF mission names
LANGS = ["jp", "en", "fr", "de", "es", "it"]

# Argument layouts, read from the event VM handlers (docs/SCRIPTS.md). Each entry: (byte offset, kind, name).
# Kinds: h u16, s s16, i s32, f float, r register (u16, shown as rN), R register (s32 index), p page (u16),
# F story flag (u16), P person (s32: 0 player, -1/-2 party members, else a person id), S string index.
# The instruction starts with the u16 opcode at +0; anything not listed is shown raw only if it isn't zero.
ARGS = {
    1: [(2, "h", "id")],
    3: [(4, "P", "who"), (8, "f", "x"), (12, "f", "y"), (16, "f", "z"), (22, "r", "who_reg")],
    4: [(4, "i", "battle")],
    5: [(4, "P", "who"), (10, "r", "who_reg")],
    6: [(4, "P", "who")],
    7: [(4, "P", "who")],
    8: [(4, "P", "caller"), (10, "h", "message"), (14, "r", "arg_reg")],
    9: [(6, "r", "dst"), (8, "r", "a"), (10, "r", "b"), (12, "i", "subtract")],
    10: [(6, "h", "kind")],
    11: [(4, "i", "mode"), (8, "i", "seconds")],
    15: [(6, "r", "dst"), (8, "i", "value"), (12, "i", "reverse_sub")],
    16: [(4, "P", "who"), (8, "f", "x"), (12, "f", "y"), (16, "f", "z"), (20, "i", "arg"), (26, "r", "who_reg")],
    17: [(4, "P", "who"), (8, "f", "x"), (12, "f", "y"), (16, "f", "z"), (20, "i", "arg"), (26, "r", "who_reg")],
    18: [(6, "r", "dst")],
    20: [(4, "f", "x"), (8, "f", "y"), (12, "f", "z")],
    21: [(4, "P", "who")],
    22: [(4, "i", "item"), (8, "i", "count"), (14, "r", "arg_reg")],
    23: [(4, "i", "item"), (8, "i", "count"), (14, "r", "arg_reg")],
    24: [(4, "i", "item"), (10, "r", "dst"), (12, "r", "arg_reg")],
    25: [(6, "r", "dst")],
    26: [(4, "i", "what")],
    27: [(4, "i", "failed")],
    28: [],
    29: [(4, "i", "failed")],
    30: [(4, "P", "who"), (10, "r", "dst")],
    32: [(4, "h", "message"), (8, "P", "speaker"), (14, "r", "speaker_reg")],
    33: [(4, "R", "who_reg")],
    34: [(4, "i", "npc")],
    35: [(4, "i", "amount"), (8, "i", "show"), (14, "r", "arg_reg")],
    36: [(4, "i", "sub_area"), (10, "r", "dst")],
    37: [(4, "i", "frames")],
    39: [(4, "i", "item"), (8, "i", "variant"), (14, "r", "dst")],
    40: [(4, "P", "who"), (8, "i", "a"), (12, "i", "b"), (18, "r", "who_reg")],
    41: [(4, "i", "on")],
    42: [(4, "P", "who"), (8, "r", "who_reg"), (10, "r", "dst")],
    43: [(4, "s", "who"), (10, "r", "dst")],
    45: [(2, "r", "dst"), (4, "i", "min"), (8, "i", "max")],
    47: [(4, "P", "who"), (10, "r", "who_reg")],
    48: [(6, "r", "dst"), (12, "i", "skill"), (16, "r", "who_dst")],
    49: [(6, "r", "dst")],
    50: [(4, "R", "who_reg"), (8, "R", "target_reg")],
    51: [(4, "i", "on")],
    52: [(6, "r", "dst"), (8, "P", "who")],
    53: [(4, "R", "a_reg"), (8, "R", "b_reg"), (12, "i", "frames"), (18, "r", "dst")],
    54: [(4, "P", "who"), (8, "f", "x"), (12, "f", "y"), (16, "f", "z"), (20, "f", "radius"), (24, "i", "area"),
         (30, "r", "dst")],
    56: [(4, "P", "who"), (8, "i", "skill_bit"), (12, "i", "on")],
    57: [(4, "P", "who"), (8, "i", "show"), (12, "i", "slot"), (16, "i", "arg")],
    58: [(10, "r", "dst")],
    59: [(4, "i", "category"), (8, "i", "variant"), (14, "r", "dst")],
    60: [(4, "i", "area"), (10, "r", "arg_reg"), (12, "i", "no_reg")],
    61: [(4, "i", "mode")],
    62: [(4, "i", "mask"), (10, "p", "page"), (14, "h", "arg")],
    63: [(2, "p", "page")],
    64: [(4, "P", "who"), (10, "r", "dst"), (12, "r", "who_reg")],
    65: [(4, "P", "who"), (8, "i", "motion"), (12, "i", "mode"), (18, "r", "who_reg")],
    66: [(4, "i", "a"), (8, "i", "b")],
    67: [(4, "s", "who"), (10, "r", "dst"), (12, "i", "amount"), (16, "r", "arg_reg")],
    68: [(4, "i", "a"), (8, "i", "b"), (12, "i", "clear")],
    69: [(4, "i", "slot"), (8, "i", "value")],
    70: [(4, "P", "who"), (8, "i", "a"), (12, "i", "b"), (16, "i", "slot")],
    71: [(6, "F", "flag"), (10, "p", "page")],
    72: [(6, "F", "flag"), (10, "p", "page")],
    74: [(2, "h", "slot"), (4, "i", "a"), (8, "i", "b"), (12, "i", "c"), (16, "i", "d"), (20, "i", "e"), (24, "i", "f")],
    75: [(2, "r", "who_dst"), (4, "r", "kind_dst")],
    76: [(2, "r", "reg"), (4, "h", "global"), (8, "i", "load")],
    78: [(4, "i", "a"), (10, "h", "b"), (12, "h", "c"), (18, "h", "d")],
    80: [(4, "P", "who"), (8, "R", "who_reg"), (12, "i", "arg")],
    81: [(6, "r", "dst")],
    82: [(6, "r", "dst"), (8, "i", "value"), (12, "i", "divide")],
    83: [(4, "i", "off")],
    84: [(4, "i", "mode")],
    85: [(4, "i", "mode")],
    86: [(4, "f", "x"), (8, "f", "y"), (12, "f", "z")],
    87: [(4, "f", "x"), (8, "f", "y"), (12, "f", "z"), (16, "i", "frames"), (20, "i", "no_ease")],
    88: [(4, "f", "x"), (8, "f", "y"), (12, "f", "z")],
    89: [(4, "f", "x"), (8, "f", "y"), (12, "f", "z"), (16, "i", "frames"), (20, "i", "no_ease")],
    90: [(4, "P", "who"), (8, "i", "angle"), (14, "r", "who_reg"), (16, "i", "arg")],
    91: [(4, "i", "value"), (8, "i", "mode")],
    92: [(4, "i", "value"), (8, "i", "on")],
    93: [(4, "i", "mode"), (10, "r", "dst"), (12, "r", "who")],
    94: [(4, "P", "who")],
    95: [(6, "r", "member1_dst"), (4, "r", "member2_dst")],
    96: [(6, "r", "dst"), (8, "i", "mode")],
    97: [(4, "i", "a"), (8, "i", "b"), (12, "i", "c")],
    98: [(4, "i", "mode"), (8, "i", "arg")],
    99: [(4, "i", "value")],
    100: [(6, "h", "on")],
    101: [(2, "p", "page")],
    102: [(2, "p", "next")],
    103: [(2, "p", "page")],
    **{k: [(2, "p", "page"), (4, "i", "value"), (10, "r", "reg")] for k in (104, 105, 111, 112)},
    **{k: [(2, "p", "page"), (4, "h", "value"), (10, "r", "reg")] for k in (106, 107, 108, 109, 113, 114, 115, 116)},
    **{k: [(2, "p", "page"), (4, "f", "value"), (10, "r", "reg")] for k in (110, 117)},
    **{k: [(2, "p", "page"), (6, "r", "reg")] for k in (118, 119, 120, 121)},
    140: [(2, "h", "channel"), (4, "i", "track")],
    141: [(2, "h", "channel")],
    142: [(2, "h", "channel"), (4, "i", "a"), (8, "i", "b"), (12, "i", "c")],
    143: [(2, "h", "channel"), (4, "i", "volume")],
    144: [(2, "h", "channel"), (4, "h", "on")],
    145: [(2, "h", "dst"), (4, "i", "a"), (8, "i", "b"), (12, "i", "c")],
    146: [(4, "i", "sound")],
    147: [(2, "r", "dst"), (4, "i", "mask_a"), (8, "i", "mask_b"), (12, "i", "mask_c"), (16, "i", "mask_d")],
    148: [(4, "f", "x"), (8, "f", "y"), (12, "f", "scale_x"), (16, "f", "scale_y"), (20, "i", "colour"),
          (24, "S", "string")],
    158: [(2, "F", "flag")],
    159: [(2, "F", "flag")],
    160: [(2, "F", "flag"), (6, "p", "page")],
    161: [(2, "F", "flag"), (6, "p", "page")],
    169: [(6, "h", "kind")],
    173: [(2, "h", "label")],
    174: [(2, "h", "label")],
    **{k: [(2, "r", "dst"), (4, "i", "value")] for k in (181, 182, 183, 184, 185, 186, 189, 190, 193, 194)},
    **{k: [(2, "r", "dst"), (4, "f", "value")] for k in (187, 191, 195)},
    188: [(2, "r", "reg"), (4, "i", "type")],
    **{k: [(2, "r", "dst"), (4, "r", "a"), (6, "r", "b")] for k in (192, 196, 197, 198, 199)},
    200: [(4, "r", "src"), (6, "r", "dst")],
    201: [(2, "r", "dst")],
    202: [(4, "i", "func")],
}


class OpTable:
    def __init__(self, elf):
        self.e = e = bdkit.Elf(elf)
        self.name, self.words, self.flags = {}, {}, {}
        for k in range(OP_COUNT):
            rec = OPCODES + 20 * k
            self.name[k] = e.cstr(e.u32(rec + 16))
            self.words[k] = e.u32(rec + 4)
            self.flags[k] = e.u32(OP_HANDLERS + 8 * k)


def script_parts(data, entry, lang):
    """The script image(s) of an entry: dialogue entries hold six language parts."""
    if entry >= 1000:
        return data
    n = struct.unpack_from("<I", data, 0)[0]
    offs = list(struct.unpack_from(f"<{n}I", data, 4)) + [len(data)]
    i = LANGS.index(lang)
    return data[offs[i]:offs[i + 1]]


def parse(img):
    sid, npages, ptab, nstr, stab, _, end, _ = struct.unpack_from("<HHIIIIII", img, 0)
    base = 0x20
    pages = [struct.unpack_from("<I", img, base + ptab + 4 * i)[0] for i in range(npages)]
    strings = []
    for i in range(nstr):
        o = struct.unpack_from("<I", img, base + stab + 4 * i)[0]
        s = img[base + stab + o:img.index(b"\0", base + stab + o)]
        strings.append(unicodedata.normalize("NFKC", s.decode("utf-8", "replace")))   # full-width ASCII
    return dict(id=sid, pages=pages, strings=strings, code=img[base:base + ptab])


def person(v):
    return {0: "player", -1: "party1", -2: "party2"}.get(v, f"person {v}")


def fmt_arg(kind, ins, off, strings):
    if off + (4 if kind in "ifPR" else 2) > len(ins):
        return "?"
    if kind in "hpFr":
        v = struct.unpack_from("<H", ins, off)[0]
        return {"h": str(v), "p": f"@{v}" if v != 0xFFFF else "-", "F": f"flag {v:#x}", "r": f"r{v}"}[kind]
    if kind == "s":
        return str(struct.unpack_from("<h", ins, off)[0])
    if kind == "f":
        return f"{struct.unpack_from('<f', ins, off)[0]:g}"
    v = struct.unpack_from("<i", ins, off)[0]
    if kind == "P":
        return person(v)
    if kind == "R":
        return f"r{v}"
    if kind == "S":
        return f"str {v}" + (f" {strings[v]!r}" if 0 <= v < len(strings) else "")
    return str(v)


def disassemble(ops, img, show_text=True):
    s = parse(img)
    code, out = s["code"], []
    page_at = {o: i for i, o in enumerate(s["pages"])}
    out.append(f"; script id {s['id']}, {len(s['pages'])} pages, {len(s['strings'])} strings, {len(code)} bytes of code")
    pc = 0
    while pc + 2 <= len(code):
        if pc in page_at:
            out.append(f"@{page_at[pc]}:")
        op = struct.unpack_from("<H", code, pc)[0]
        if op >= OP_COUNT or ops.words[op] == 0:
            out.append(f"  {pc:05X}  ?? {code[pc:pc + 4].hex()}")
            pc += 4
            continue
        size = 4 * ops.words[op]
        ins = code[pc:pc + size]
        spec = ARGS.get(op)
        if spec is not None:
            used = {o for o, k, _ in spec for o in range(o, o + (4 if k in "ifPRS" else 2))}
            args = [f"{n}={fmt_arg(k, ins, o, s['strings'])}" for o, k, n in spec]
            for o in range(2, size, 2):     # anything the layout doesn't name but isn't zero
                if o not in used and o + 2 <= len(ins) and struct.unpack_from("<H", ins, o)[0]:
                    args.append(f"+{o}={struct.unpack_from('<H', ins, o)[0]:#x}")
        else:
            args = []
            if size >= 4 and struct.unpack_from("<H", ins, 2)[0]:
                args.append(f"+2={struct.unpack_from('<H', ins, 2)[0]:#x}")
            for o in range(4, size, 4):
                v = struct.unpack_from("<i", ins, o)[0]
                if v:
                    args.append(f"+{o}={v:#x}" if abs(v) > 0xFFFF else f"+{o}={v}")
        tag = {1: " ;jump", 2: " ;waits"}.get(ops.flags[op], "")
        out.append(f"  {pc:05X}  {ops.name[op]:<24s} {', '.join(args)}{tag}")
        pc += size
    if s["strings"]:
        out.append("; strings")
        for i, t in enumerate(s["strings"]):
            out.append(f";   {i}: {t!r}" if show_text else f";   {i}: ({len(t)} bytes)")
    return out


def xaf_read(path, entry):
    o, n = bdkit.xaf_entries(path)[entry][1:3]
    with open(path, "rb") as f:
        f.seek(o)
        return f.read(n)


def cmd_dis(a):
    ops = OpTable(a.elf)
    count = len(bdkit.xaf_entries(a.script))
    if a.entry == "missions":
        entries = range(1000, count)
    elif a.entry == "all":
        entries = range(0, count)
    else:
        entries = [int(a.entry, 0)]
    if a.out:
        os.makedirs(a.out, exist_ok=True)
    for ent in entries:
        img = script_parts(xaf_read(a.script, ent), ent, a.lang)
        kind = f"mission {ent - 1000}" if ent >= 1000 else f"dialogue {ent} ({a.lang})"
        lines = [f"; SCRIPT.XAF entry {ent}: {kind}"] + disassemble(ops, img)
        text = "\n".join(lines) + "\n"
        if a.out:
            name = f"mission_{ent - 1000:03d}.txt" if ent >= 1000 else f"dialogue_{ent:03d}.txt"
            with open(os.path.join(a.out, name), "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
        else:
            sys.stdout.write(text + "\n")
    if a.out:
        print(f"wrote {len(entries)} scripts to {a.out}")


def cmd_stats(a):
    ops = OpTable(a.elf)
    from collections import Counter
    use = {"mission": Counter(), "dialogue": Counter()}
    for ent in range(len(bdkit.xaf_entries(a.script))):
        img = script_parts(xaf_read(a.script, ent), ent, "en")
        code = parse(img)["code"]
        kind = "mission" if ent >= 1000 else "dialogue"
        pc = 0
        while pc + 2 <= len(code):
            op = struct.unpack_from("<H", code, pc)[0]
            if op >= OP_COUNT or not ops.words[op]:
                pc += 4
                continue
            use[kind][op] += 1
            pc += 4 * ops.words[op]
    print(f"{'op':>3}  {'name':24s} {'missions':>8} {'dialogue':>8}  flags")
    for k in range(1, OP_COUNT):
        print(f"{k:3d}  {ops.name[k]:24s} {use['mission'][k]:8d} {use['dialogue'][k]:8d}  {ops.flags[k]}")


def cmd_missions(a):
    e = bdkit.Elf(a.elf)
    text = bdkit.text_table(a.cdata, MISSION_TEXT[a.lang])
    jobs = {}
    for i in range(MISSION_INFO_COUNT):
        r = MISSION_INFO + 12 * i
        mid, diff, reward = e.d[e.v2o(r)], e.d[e.v2o(r) + 1], struct.unpack_from("<H", e.d, e.v2o(r) + 2)[0]
        jobs[mid] = (i, diff, reward, e.u32(r + 4), e.u32(r + 8))
    lists = {}
    for name, (addr, n) in JOB_LISTS.items():
        for k in range(n):
            lists.setdefault(e.u32(addr + 4 * k), []).append(name)
    auto = {e.d[e.v2o(AUTO_MISSIONS[0]) + k] for k in range(AUTO_MISSIONS[1])}
    talk = {e.u32(TALK_MISSIONS[0] + 4 * k) for k in range(TALK_MISSIONS[1])}
    print(f"Generated by `python tools/scriptkit.py missions ISO/SLUS_211.50 ISO/XAF/CDATA.XAF`. docs/SCRIPTS.md "
          "explains the columns.\n")
    print(f"{'id':>4} {'script':>6}  {'job':>3} {'stars':>5} {'reward':>6}  {'chapters':16s} {'clr':>3} {'%':>3}  "
          f"{'flags':13s} {'start':10s} title")
    for mid in range(0, 0x93):
        req = MISSION_REQ + 4 * mid
        mask, lo1, lo2 = struct.unpack_from("<H", e.d, e.v2o(req))[0], e.d[e.v2o(req) + 2], e.d[e.v2o(req) + 3]
        f0, f1 = e.u32(MISSION_FLAGS + 4 * mid), e.u32(MISSION_FLAGS + 4 * mid + 4)
        chapters = ",".join(str(b) for b in range(16) if mask >> b & 1) or "-"
        flags = f"{f0:#06x}-{f1 - 1:#06x}" if 0 < f0 < f1 < 0x2000 else "-"
        start = []
        if mid in lists:
            start.append("job " + "/".join(lists[mid]))
        if mid in auto:
            start.append("auto")
        if mid in talk:
            start.append("talk")
        j = jobs.get(mid)
        title = text.get(j[3], "") if j else ""
        print(f"{mid:#04x} {1000 + mid:6d}  {j[0] if j else '':>3} {j[1] if j else '':>5} {j[2] if j else '':>6}  "
              f"{chapters:16s} {lo1:3d} {lo2:3d}  {flags:13s} {','.join(start):10s} {title}")


JOB_EXTRA = {   # Mission_Unavailable 0x003B02C0 special cases (docs/UNLOCKS.md)
    0x4E: "3+ healthy allies, and one of persons 116, 178-182, 186-189, 192, 194-198 is a healthy ally not in your party",
    0x4F: "player is male (Aaron, Raven, Jason G)",
    0x50: "player is male (Aaron, Raven, Jason G)",
    0x54: "player is female (Lola, Gina); person 183 is an ally but not in your party",
}


def cmd_jobs(a):
    e = bdkit.Elf(a.elf)
    text = bdkit.text_table(a.cdata, MISSION_TEXT[a.lang])
    lists = {}
    for name, (addr, n) in JOB_LISTS.items():
        for k in range(n):
            lists[e.u32(addr + 4 * k)] = name
    print("| Job | List | Mission | Title | Stars | Reward | Stages | Jobs cleared | Game clears | Extra |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for i in range(MISSION_INFO_COUNT):
        r = MISSION_INFO + 12 * i
        mid, stars = e.d[e.v2o(r)], e.d[e.v2o(r) + 1]
        reward = struct.unpack_from("<H", e.d, e.v2o(r) + 2)[0]
        q = MISSION_REQ + 4 * mid
        mask, clears, pct = struct.unpack_from("<H", e.d, e.v2o(q))[0], e.d[e.v2o(q) + 2], e.d[e.v2o(q) + 3]
        stages = ", ".join(str(b) for b in range(16) if mask >> b & 1)
        print(f"| {i} | {lists.get(mid, '?')} | 0x{mid:02X} | {text.get(e.u32(r + 4), '')} | {stars} | ${reward} | "
              f"{stages} | {pct}% ({pct // 2} jobs) | {clears or ''} | {JOB_EXTRA.get(mid, '')} |")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    x = sub.add_parser("dis")
    x.add_argument("elf")
    x.add_argument("script", help="ISO/XAF/SCRIPT.XAF")
    x.add_argument("entry", help="entry number, 'missions' (1000+) or 'all'")
    x.add_argument("--lang", default="en", choices=LANGS, help="language part of a dialogue script")
    x.add_argument("--out", help="write one file per script into this folder")
    x.set_defaults(fn=cmd_dis)
    x = sub.add_parser("stats")
    x.add_argument("elf")
    x.add_argument("script")
    x.set_defaults(fn=cmd_stats)
    x = sub.add_parser("jobs")
    x.add_argument("elf")
    x.add_argument("cdata")
    x.add_argument("--lang", default="en", choices=LANGS)
    x.set_defaults(fn=cmd_jobs)
    x = sub.add_parser("missions")
    x.add_argument("elf")
    x.add_argument("cdata", help="ISO/XAF/CDATA.XAF, for the job titles")
    x.add_argument("--lang", default="en", choices=LANGS)
    x.set_defaults(fn=cmd_missions)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
