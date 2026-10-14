#!/usr/bin/env python3
"""Beat Down (SLUS-21150) code map helpers. Companion to bdkit.py and CODEMAP.md.

Python 3 standard library only. Needs bdkit.py in the same folder.

  python tools/codemap.py symbols   ISO/SLUS_211.50 symbols           # PCSX2 .sym, Ghidra script, CSV, C headers
  python tools/codemap.py commands  ISO/SLUS_211.50 ISO/XAF/CDATA.XAF 0x13  # a style's input -> action -> damage table
  python tools/codemap.py commands  ISO/SLUS_211.50 ISO/XAF/CDATA.XAF all > dumps/commands.txt
  python tools/codemap.py hits      ISO/SLUS_211.50 1805            # hit records (damage) of one action
  python tools/codemap.py actions   ISO/SLUS_211.50 1805 1806       # which animations an action plays (motion script)
  python tools/codemap.py actions   ISO/SLUS_211.50 0x13            # ... for every command of a style (0x01-0x2F)
  python tools/codemap.py anim-check ISO/SLUS_211.50                # motions each class's style plays but its groups don't load
  python tools/codemap.py anim-check ISO/SLUS_211.50 AARON 0x11     # ... if AARON (own groups) used style 0x11
  python tools/codemap.py pnach-map mods/SLUS-21150_C9F6EF9A.pnach   # addresses each cheat writes, and overlaps
  python tools/codemap.py persons   ISO/SLUS_211.50 > dumps/persons.txt
  python tools/codemap.py infer-types decomp/all.c symbols/inferred_types.tsv  # struct pointer params for Ghidra

Symbols live in symbols/symbols.tsv (tab separated: addr, kind, name, comment, optional C type) and
structs in symbols/structs.tsv. Add new names there and re-run `symbols`: it also regenerates the C mod
headers tools/cmod/structs.h and tools/cmod/symbols.h.
"""
import argparse
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bdkit  # noqa: E402

SYMBOLS_TSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "symbols", "symbols.tsv")
STRUCTS_TSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "symbols", "structs.tsv")
CMOD_INCLUDE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cmod")

STYLE_COMMANDS = 0x00515C10   # u32[48], per style: list of {u32 cond, u32 seq}, seq 0 ends the list
ACTION_HITS = 0x00580A40      # u32[2004], per action: 16-byte hit records, +8 u16 base damage, +14 u16 flags
ACTION_COUNT = 2004
ACTION_SCRIPTS = 0x005848E0   # 2001 x {u32 motion script, u32 second stream}; Fighter_SetAction 0x0031F120
# Motion script opcodes run by Action_Step 0x0031FAE0 (s16 words): name, number of words including the opcode.
# Opcodes it doesn't know take one word and do nothing. 0x34 is followed by a count and that many actions.
MOTION_OPS = {
    0x00: ("play", 5),      # anim id, start frame, end frame (-1 = to the end), blend frames; waits for it to finish
    0x01: ("end", 1),
    0x02: ("loop", 2),      # count (-1 = forever)
    0x03: ("next", 1),      # back to the matching loop
    0x04: ("reset", 1),     # clears fighter +0x3FD0
    0x05: ("speed", 2),     # playback speed x 1/1000
    0x06: ("goto", 2),      # continue with another action (Action_Next 0x0031F650)
    0x07: ("start", 2),     # start another action (Fighter_StartAction 0x00307E40)
    0x08: ("nop", 1),
    0x09: ("skip2", 3),
    0x13: ("op13", 5),      # calls 0x00324F80 with a float (5th word / 1000)
    0x15: ("op15", 1),
    0x16: ("op16", 2),
}
PERSON_DEFS = 0x00413130      # 602 x 72-byte person templates
PERSON_DEF_SIZE = 72
PERSON_DEF_COUNT = 602
ATTACK_RANK_MUL = 0x005D04D0  # float[7]

# Input codes in the style command lists, worked out from Aaron's (style 0x13) list.
INPUTS = {
    0x0E: "P", 0x0A: "→P", 0x0B: "←P", 0x0C: "↑P", 0x0D: "↓P",
    0x1C: "K", 0x18: "→K", 0x19: "←K", 0x1A: "↑K", 0x1B: "↓K",
    0x47: "→G", 0x48: "←G", 0x49: "↑G",
    0x05: "→→P", 0x13: "→→K", 0x16: "↓→K", 0x12: "→↓→K",
    0x2F: "GRAB P", 0x32: "GRAB K", 0x6B: "REAR GRAB P", 0x6C: "REAR GRAB K",
}


def load_symbols():
    out = []
    with open(SYMBOLS_TSV, encoding="utf-8") as f:
        for line in f:
            if not line.strip() or line.startswith("#"):
                continue
            p = line.rstrip("\n").split("\t")
            out.append((int(p[0], 16), p[1], p[2], p[3] if len(p) > 3 else ""))
    return sorted(out)


def symbol_types():
    """{name: C type} from symbols.tsv's fifth column."""
    out = {}
    with open(SYMBOLS_TSV, encoding="utf-8") as f:
        for line in f:
            if not line.strip() or line.startswith("#"):
                continue
            p = line.rstrip("\n").split("\t")
            if len(p) > 4 and p[4].strip():
                out[p[2]] = p[4].strip()
    return out


PRIM_SIZES = {"s8": 1, "u8": 1, "char": 1, "s16": 2, "u16": 2, "s32": 4, "u32": 4, "f32": 4, "s64": 8, "u64": 8}
TYPE_RE = re.compile(r"^(\w+)\s*(\**)\s*(?:\[(\w+)\])?$")


def parse_type(t):
    """'Fighter *[4]' -> ('Fighter', 1, 4); count is None for a plain field."""
    m = TYPE_RE.match(t.strip())
    if not m:
        sys.exit(f"bad type {t!r} in symbols/")
    return m.group(1), len(m.group(2)), int(m.group(3), 0) if m.group(3) else None


def load_structs():
    """[(name, size or None, comment, [(offset, type, field, comment)])] in file order."""
    structs, by = [], {}
    with open(STRUCTS_TSV, encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            if not line.strip() or line.startswith("#"):
                continue
            p = line.rstrip("\n").split("\t") + ["", "", ""]
            name, off = p[0], p[1]
            if off == "size":
                if name in by:
                    sys.exit(f"structs.tsv line {ln}: {name} defined twice")
                by[name] = (name, None if p[2] == "?" else int(p[2], 0), p[4], [])
                structs.append(by[name])
            elif name not in by:
                sys.exit(f"structs.tsv line {ln}: {name} has no size line before its fields")
            else:
                by[name][3].append((int(off, 0), p[2], p[3], p[4]))
    sizes = {}
    for name, size, _, fields in structs:
        end = 0
        for off, t, field, _ in sorted(fields):
            base, ptr, count = parse_type(t)
            if ptr:
                n = 4
            elif base in PRIM_SIZES:
                n = PRIM_SIZES[base]
            elif sizes.get(base):
                n = sizes[base]
            else:
                sys.exit(f"structs.tsv: {name}.{field}: type {base} is unknown or has no known size")
            n *= count or 1
            if off < end:
                sys.exit(f"structs.tsv: {name}.{field} at {off:#x} overlaps the field before it")
            end = off + n
        if size is not None and end > size:
            sys.exit(f"structs.tsv: {name} fields run to {end:#x}, past its size {size:#x}")
        sizes[name] = size if size is not None else None
    return structs, sizes


def c_decl(t, name):
    base, ptr, count = parse_type(t)
    return f"{base} {'*' * ptr}{name}{f'[{count:#x}]' if count else ''}"


def write_c_headers(out_dir):
    structs, _ = load_structs()
    gen = "/* Generated by `python tools/codemap.py symbols` from symbols/{}; edit that file, not this one. */\n"
    h = [gen.format("structs.tsv"), "#ifndef BEATDOWN_STRUCTS_H", "#define BEATDOWN_STRUCTS_H", ""]
    h += [f"typedef struct {n} {n};" for n, *_ in structs] + [""]
    for name, size, com, fields in structs:
        if com:
            h.append(f"/* {com} */")
        h.append(f"struct {name} {{")
        pos, asserts = 0, []
        for off, t, field, fcom in sorted(fields):
            if off > pos:
                h.append(f"    u8 _{pos:04X}[{off - pos:#x}];")
            h.append(f"    {c_decl(t, field)};{f'  /* +{off:#x} {fcom} */' if fcom else f'  /* +{off:#x} */'}")
            asserts.append(f"_Static_assert(__builtin_offsetof({name}, {field}) == {off:#x}, \"{name}.{field}\");")
            base, ptr, count = parse_type(t)
            n = 4 if ptr else PRIM_SIZES.get(base) or next(sz for sn, sz, _, _ in structs if sn == base)
            pos = off + n * (count or 1)
        if size is not None and size > pos:
            h.append(f"    u8 _{pos:04X}[{size - pos:#x}];")
        h.append("};")
        h += asserts
        if size is not None:
            h.append(f"_Static_assert(sizeof({name}) == {size:#x}, \"sizeof {name}\");")
        h.append("")
    h.append("#endif")
    with open(os.path.join(out_dir, "structs.h"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(h) + "\n")

    s = [gen.format("symbols.tsv (the type column)"), "#ifndef BEATDOWN_SYMBOLS_H", "#define BEATDOWN_SYMBOLS_H", ""]
    types = symbol_types()
    for addr, kind, name, com in load_symbols():
        t = types.get(name)
        if not t:
            continue
        if kind == "func":
            i = t.index("(")
            ret = t[:i].strip()
            s.append(f"{ret}{'' if ret.endswith('*') else ' '}{name}{t[i:]};  /* {addr:#010x} */")
        else:
            m = re.match(r"^(.*?)\s*(\[\w+\])?$", t)
            ret = m.group(1)
            s.append(f"extern {ret}{'' if ret.endswith('*') else ' '}{name}{m.group(2) or ''};  /* {addr:#010x} */")
    s += ["", "#endif"]
    with open(os.path.join(out_dir, "symbols.h"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(s) + "\n")


GHIDRA_TYPES = r'''
from ghidra.program.model.data import (ArrayDataType, ByteDataType, CategoryPath, CharDataType,
    DataTypeConflictHandler, FloatDataType, FunctionDefinitionDataType, IntegerDataType, LongLongDataType,
    ParameterDefinitionImpl, PointerDataType, ShortDataType, SignedByteDataType, StructureDataType,
    UnsignedIntegerDataType, UnsignedLongLongDataType, UnsignedShortDataType, VoidDataType)
from ghidra.app.cmd.function import ApplyFunctionSignatureCmd
import re

dtm = currentProgram.getDataTypeManager()
CAT = CategoryPath("/BeatDown")

# The ELF's zero-initialized globals (0x005FEB00-0x00788180) get no memory block from the loader, so
# Ghidra can't type or follow them; map them as an uninitialized read/write block.
mem = currentProgram.getMemory()
pos, gaps = 0x005FEB00, []
for blk in sorted(mem.getBlocks(), key=lambda b: b.getStart().getOffset()):
    lo, hi = blk.getStart().getOffset(), blk.getEnd().getOffset() + 1
    if hi <= pos or lo >= 0x00788180:
        continue
    if lo > pos:
        gaps.append((pos, lo))
    pos = max(pos, hi)
if pos < 0x00788180:
    gaps.append((pos, 0x00788180))
for i, (lo, hi) in enumerate(gaps):
    b = mem.createUninitializedBlock(".bss%s" % (i or ""), toAddr(lo), hi - lo, False)
    b.setRead(True)
    b.setWrite(True)
    print("mapped .bss %08X-%08X" % (lo, hi - 1))
PRIM = {"s8": SignedByteDataType.dataType, "u8": ByteDataType.dataType, "char": CharDataType.dataType,
        "s16": ShortDataType.dataType, "u16": UnsignedShortDataType.dataType, "s32": IntegerDataType.dataType,
        "u32": UnsignedIntegerDataType.dataType, "f32": FloatDataType.dataType, "s64": LongLongDataType.dataType,
        "u64": UnsignedLongLongDataType.dataType, "void": VoidDataType.dataType, "int": IntegerDataType.dataType}

def resolve(t):
    t = t.replace("const ", "").strip()
    m = re.match(r"^(\w+)\s*(\**)\s*(?:\[(\w+)\])?$", t)
    base, ptr, count = m.group(1), len(m.group(2)), m.group(3)
    dt = PRIM.get(base) or dtm.getDataType(CAT, base)
    for _ in range(ptr):
        dt = PointerDataType(dt, 4, dtm)
    if count:
        dt = ArrayDataType(dt, int(count, 0), dt.getLength())
    return dt

for name, size, com, fields in STRUCTS:
    end = size or max(o + 1 for o, _, _, _ in fields)
    s = StructureDataType(CAT, name, end, dtm)
    s.setDescription(com)
    dtm.addDataType(s, DataTypeConflictHandler.REPLACE_HANDLER)
for name, size, com, fields in STRUCTS:
    s = dtm.getDataType(CAT, name)
    for off, t, field, fcom in fields:
        dt = resolve(t)
        if size is None and off + dt.getLength() > s.getLength():
            s.growStructure(off + dt.getLength() - s.getLength())
        s.replaceAtOffset(off, dt, dt.getLength(), field, fcom or None)

def apply_func(addr, name, proto):
    i = proto.index("(")
    fd = FunctionDefinitionDataType(name)
    fd.setReturnType(resolve(proto[:i]))
    params = []
    for a in proto[i + 1:proto.rindex(")")].split(","):
        a = a.strip()
        if a in ("", "void"):
            continue
        if a == "...":
            fd.setVarArgs(True)
            continue
        m = re.match(r"^(.*?)(\w+)$", a)
        params.append(ParameterDefinitionImpl(m.group(2), resolve(m.group(1)), None))
    fd.setArguments(params)
    ApplyFunctionSignatureCmd(toAddr(addr), fd, SourceType.USER_DEFINED).applyTo(currentProgram)

typed = 0
for addr, kind, name, proto in TYPES:
    try:
        if kind == "func":
            apply_func(addr, name, proto)
        else:
            dt = resolve(proto)
            a = toAddr(addr)
            clearListing(a, a.add(dt.getLength() - 1))
            createData(a, dt)
        typed += 1
    except Exception as e:
        print("type for %s not applied: %s" % (name, e))
print("Applied %d structs and %d symbol types" % (len(STRUCTS), typed))
'''


def cmd_symbols(a):
    syms = load_symbols()
    structs, _ = load_structs()
    types = symbol_types()
    os.makedirs(a.out, exist_ok=True)
    # PCSX2 debugger / no$ style: one "address name" per line.
    with open(os.path.join(a.out, "SLUS_211.50.sym"), "w", encoding="utf-8", newline="\n") as f:
        for addr, kind, name, _ in syms:
            f.write(f"{addr:08X} {name}\n")
    with open(os.path.join(a.out, "beatdown_symbols.csv"), "w", encoding="utf-8", newline="\n") as f:
        f.write("address,kind,name,comment\n")
        for addr, kind, name, com in syms:
            f.write(f"0x{addr:08X},{kind},{name},\"{com.replace(chr(34), chr(39))}\"\n")
    # Ghidra: Script Manager -> run this file with the program loaded at 0x00100000.
    with open(os.path.join(a.out, "ImportBeatdownSymbols.py"), "w", encoding="utf-8", newline="\n") as f:
        f.write("# Labels and comments for Beat Down (SLUS-21150). Run from Ghidra's Script Manager.\n")
        f.write("# @category BeatDown\n")
        f.write("from ghidra.program.model.symbol import SourceType\n")
        f.write("SYMS = [\n")
        for addr, kind, name, com in syms:
            f.write(f"    (0x{addr:08X}, {kind!r}, {name!r}, {com!r}),\n")
        f.write("]\n")
        f.write("STRUCTS = [\n")
        for name, size, com, fields in structs:
            f.write(f"    ({name!r}, {size!r}, {com!r}, {sorted(fields)!r}),\n")
        f.write("]\n")
        f.write("TYPES = [\n")
        for addr, kind, name, com in syms:
            if name in types:
                f.write(f"    (0x{addr:08X}, {kind!r}, {name!r}, {types[name]!r}),\n")
        f.write("]\n")
        f.write("for addr, kind, name, com in SYMS:\n")
        f.write("    a = toAddr(addr)\n")
        f.write("    if kind == 'func' and getFunctionAt(a) is None:\n")
        f.write("        disassemble(a)\n")
        f.write("        createFunction(a, name)\n")
        f.write("    createLabel(a, name, True, SourceType.USER_DEFINED)\n")
        f.write("    if com:\n")
        f.write("        setPlateComment(a, com)\n")
        f.write("print('Imported %d Beat Down symbols' % len(SYMS))\n")
        f.write(GHIDRA_TYPES)
    write_c_headers(CMOD_INCLUDE)
    print(f"wrote {len(syms)} symbols ({len(types)} typed) and {len(structs)} structs to {a.out} and "
          f"{os.path.relpath(CMOD_INCLUDE)}")


INFER_RULES = [  # (struct, offsets only it has): a parameter used only within its size, at least once in range
    ("Fighter", 0x3F00, 0x4730),
]


def cmd_infer_types(a):
    """Parameter types for functions the decomp shows using struct-only offsets on a parameter."""
    src = open(a.all_c, encoding="utf-8").read()
    rows = []
    for f in re.split(r"\n(?=// \S+ @ 0x[0-9A-F]{8}, \d+ bytes\n)", src):
        m = re.match(r"// (\S+) @ 0x([0-9A-F]{8})", f)
        if not m:
            continue
        sig = re.search(r"^[^\n/][^\n]*\b" + re.escape(m.group(1)) + r"\(([^)]*)\)\s*\n", f, re.M)
        if not sig:
            continue
        params = [p.strip() for p in sig.group(1).split(",") if p.strip() and p.strip() != "void"]
        for i, p in enumerate(params):
            pm = re.match(r"(.*?)(param_\d+)$", p)
            if not pm or any(n in pm.group(1) for n, _, _ in INFER_RULES):
                continue
            name, typ = pm.group(2), pm.group(1).strip()
            offs = [int(x, 16) for x in re.findall(r"(?:\(\w+\))?" + re.escape(name) + r" \+ 0x([0-9a-f]+)\)", f)]
            scale = {"int *": 4, "uint *": 4, "undefined4 *": 4, "float *": 4, "short *": 2, "ushort *": 2,
                     "undefined2 *": 2}.get(typ)
            if scale:
                offs += [scale * int(x, 16) for x in re.findall(re.escape(name) + r"\[0x([0-9a-f]+)\]", f)]
            for struct_name, lo, size in INFER_RULES:
                hits = [o for o in offs if lo <= o < size]
                if hits and all(o < size for o in offs):
                    rows.append((m.group(2), m.group(1), i, struct_name + " *", len(hits)))
    # Keep earlier rows: once applied, a parameter is typed in the decomp and no longer shows up here.
    known = {}
    if os.path.exists(a.out):
        for line in open(a.out, encoding="utf-8"):
            if line.strip() and not line.startswith("#"):
                c = line.rstrip("\n").split("\t")
                known[(c[0], c[2])] = c
    new = 0
    for r in rows:
        if (r[0], str(r[2])) not in known:
            new += 1
        known[(r[0], str(r[2]))] = [r[0], r[1], str(r[2]), r[3], str(r[4])]
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# Generated by `python tools/codemap.py infer-types decomp/all.c symbols/inferred_types.tsv`;\n"
                 "# applied by tools/ghidra/ApplyInferredTypes.py. addr, function, parameter index, type, evidence.\n")
        for k in sorted(known):
            fh.write("\t".join(known[k]) + "\n")
    print(f"{new} new parameter types, {len(known)} in all -> {a.out}")


def style_commands(e, style):
    """[(cond, [input codes], action)] for one style."""
    t = e.u32(STYLE_COMMANDS + 4 * style)
    out = []
    if not t:
        return out
    i = 0
    while True:
        cond, seq = e.u32(t + 8 * i), e.u32(t + 8 * i + 4)
        if seq == 0:
            return out
        codes, act, j = [], 0, 0
        while e.u32(seq + 8 * j) != 0xFFFFFFFF:
            codes.append(e.u32(seq + 8 * j))
            act = e.s16(seq + 8 * j + 4)
            j += 1
        out.append((cond, codes, act))
        i += 1


def hits(e, act):
    if not 0 < act < ACTION_COUNT:
        return []
    p = e.u32(ACTION_HITS + 4 * act)
    out = []
    for k in range(4):
        kind, v4, dmg, v10, v12, flags = struct.unpack_from("<IIHHHH", e.d, e.v2o(p + 16 * k))
        out.append(dict(kind=kind, v4=v4, damage=dmg, v10=v10, v12=v12, flags=flags, addr=p + 16 * k + 8))
    return out


def cmd_commands(a):
    e = bdkit.Elf(a.elf)
    names = {}
    if a.cdata:
        try:
            names = bdkit.style_moves(e, a.cdata)
        except Exception as x:  # noqa: BLE001
            print(f"(move names unavailable: {x})", file=sys.stderr)
    styles = range(1, 0x25) if a.style == "all" else [int(a.style, 0)]
    for st in styles:
        lst = style_commands(e, st)
        print(f"## Style 0x{st:02X}  (list at 0x{e.u32(STYLE_COMMANDS + 4 * st):08X}, {len(lst)} commands)")
        by_input = {}
        for nm, inp in names.get(st, []):
            by_input.setdefault(inp, nm)
        for i, (cond, codes, act) in enumerate(lst):
            inp = " ".join(INPUTS.get(c, f"#{c:02X}") for c in codes)
            # a sequence like "→P P P" matches the move list's "→PPP"
            key = "".join(INPUTS.get(c, "?") for c in codes)
            guess = by_input.get(key) or next((n for n, s in names.get(st, []) if key in s.split("/")), "")
            dmg = [h["damage"] for h in hits(e, act) if h["damage"]]
            first = hits(e, act)[0]["addr"] if hits(e, act) else 0
            print(f"  {i:3}  {'cond' if cond else '    '}  {inp:<18} action {act:5}  damage {str(dmg):<16}"
                  f" {('@0x%08X' % first) if first else '':<12} {guess}")
        print()


def cmd_hits(a):
    e = bdkit.Elf(a.elf)
    act = int(a.action, 0)
    print(f"action {act}: hit records at 0x{e.u32(ACTION_HITS + 4 * act):08X}")
    for k, h in enumerate(hits(e, act)):
        print(f"  hit {k}: kind {h['kind']}  v4 {h['v4']}  damage {h['damage']} (u16 at 0x{h['addr']:08X})"
              f"  v10 {h['v10']}  v12 {h['v12']}  flags 0x{h['flags']:X}")


def motion_script(e, act):
    """Decode an action's motion script into (op name, args) tuples. Empty if the script isn't in the ELF."""
    if not 0 <= act < ACTION_COUNT:
        return []
    p = e.u32(ACTION_SCRIPTS + 8 * act)
    if not 0x00100000 <= p < 0x005FE000:
        return []   # loaded at run time (.mtd files) or unused
    out = []
    for _ in range(256):
        op = e.s16(p)
        if op == 0x34:
            n = e.s16(p + 2)
            out.append(("random", [e.s16(p + 4 + 2 * i) for i in range(n)]))
            p += 2 * (n + 2)
            continue
        name, size = MOTION_OPS.get(op, (f"op{op:02X}", 1))
        out.append((name, [e.s16(p + 2 * (i + 1)) for i in range(size - 1)]))
        p += 2 * size
        if op == 0x01:
            break
    return out


def cmd_actions(a):
    e = bdkit.Elf(a.elf)
    groups = {}
    for g in e.anim_groups():
        for m in g["anim_ids"]:
            groups.setdefault(m, []).append(g["group"])
    todo = []
    for x in a.ids:
        v = int(x, 0)
        if x.lower().startswith("0x") and v < 0x30:   # a style: every command's action
            todo += [act for _, _, act in style_commands(e, v)]
        else:
            todo.append(v)
    for act in dict.fromkeys(todo):
        ops = motion_script(e, act)
        if not ops:
            print(f"action {act}: no motion script in the ELF")
            continue
        parts = []
        for name, args in ops:
            if name == "play":
                m, s0, s1, blend = args
                parts.append(f"play {m} [{s0}-{'end' if s1 == -1 else s1}, blend {blend}]"
                             f" (groups {','.join(map(str, groups.get(m, []))) or 'none'})")
            elif name != "end":
                parts.append(name + ("" if not args else " " + ",".join(map(str, args))))
        print(f"action {act}: " + "; ".join(parts))


def style_motions(e, style):
    """Animation ids played by the first motion script of every command in a style's list."""
    out = set()
    for _, _, act in style_commands(e, style):
        for name, args in motion_script(e, act):
            if name == "play":
                out.add(args[0])
    return out


def cmd_anim_check(a):
    e = bdkit.Elf(a.elf)
    loaded = {g["group"]: set(g["anim_ids"]) for g in e.anim_groups()}
    classes = [c for c in e.classes() if c["style"] and (not a.cls or c["name"] == a.cls.upper())]
    if a.cls and not classes:
        sys.exit(f"no class named {a.cls}")
    gaps = 0
    for c in classes:
        style = int(a.style, 0) if a.style else c["style"]
        have = set().union(*(loaded.get(g, set()) for g in c["groups"]))
        missing = sorted(style_motions(e, style) - have)
        if missing or a.cls:
            gaps += bool(missing)
            print(f"{c['name']:<16} style 0x{style:02X}: {len(missing)} motions not in its groups"
                  + (f": {missing}" if missing else ""))
    if not a.cls:
        print(f"{gaps} classes with gaps (only the first motion of each command is checked)")


def pnach_sections(path):
    """[(section name, [(addr, size)])] from a pnach file; sizes from the patch type digit (0 byte, 1 half, 2 word)."""
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("[") and line.endswith("]"):
                out.append((line[1:-1], []))
            m = re.match(r"patch=\d+,EE,([0-9A-Fa-f]{8}),\w+,", line)
            if m and out:
                v = int(m.group(1), 16)
                out[-1][1].append((v & 0x0FFFFFFF, {0: 1, 1: 2, 2: 4}.get(v >> 28, 4)))
    return out


def ranges(writes):
    rs = []
    for addr, size in sorted(writes):
        if rs and addr <= rs[-1][1]:
            rs[-1][1] = max(rs[-1][1], addr + size)
        else:
            rs.append([addr, addr + size])
    return rs


def cmd_pnach_map(a):
    secs = pnach_sections(a.pnach)
    for name, writes in secs:
        rs = ranges(writes)
        print(f"[{name}]  {len(writes)} writes")
        print("    " + ", ".join(f"0x{s:08X}" if e - s <= 4 else f"0x{s:08X}-0x{e - 1:08X}" for s, e in rs))
    print("\nOverlaps (these cheats can't be on together):")
    found = False
    for i, (n1, w1) in enumerate(secs):
        for n2, w2 in secs[i + 1:]:
            hit = [(s, e) for s, e in ranges(w1) for s2, e2 in ranges(w2) if s < e2 and s2 < e]
            if hit:
                found = True
                print(f"  {n1}\n    x {n2}  (from 0x{hit[0][0]:08X})")
    if not found:
        print("  none")


def cmd_persons(a):
    e = bdkit.Elf(a.elf)
    tn = e.type_names()
    ranks = [struct.unpack_from("<f", e.d, e.v2o(ATTACK_RANK_MUL + 4 * i))[0] for i in range(7)]
    print("Person templates (g_PersonDefs, 0x00413130, 72 bytes each). HP/level/money are the starting values.")
    print(" id  address     preset row  type            lvl    HP  guard  atk-rank  money")
    for i in range(PERSON_DEF_COUNT):
        b = PERSON_DEFS + PERSON_DEF_SIZE * i
        o = e.v2o(b)
        preset, row = struct.unpack_from("<hH", e.d, o + 4)
        lvl = e.d[o + 14]
        hp, guard = struct.unpack_from("<hh", e.d, o + 16)
        rank = e.d[o + 21]
        money = struct.unpack_from("<i", e.d, o + 24)[0]
        t = tn[row + 1] if row + 1 < len(tn) else "?"
        r = f"{rank} (x{ranks[rank]:.1f})" if rank < 7 else str(rank)
        print(f"{i:3}  0x{b:08X}  {preset:5} {row:3}  {t:<14} {lvl:4} {hp:5} {guard:6}  {r:<9} {money:6}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    s = ap.add_subparsers(dest="cmd", required=True)
    x = s.add_parser("symbols"); x.add_argument("elf"); x.add_argument("out"); x.set_defaults(fn=cmd_symbols)
    x = s.add_parser("infer-types"); x.add_argument("all_c"); x.add_argument("out"); x.set_defaults(fn=cmd_infer_types)
    x = s.add_parser("commands"); x.add_argument("elf"); x.add_argument("cdata", nargs="?"); x.add_argument("style", nargs="?", default="all")
    x.set_defaults(fn=cmd_commands)
    x = s.add_parser("hits"); x.add_argument("elf"); x.add_argument("action"); x.set_defaults(fn=cmd_hits)
    x = s.add_parser("persons"); x.add_argument("elf"); x.set_defaults(fn=cmd_persons)
    x = s.add_parser("actions"); x.add_argument("elf"); x.add_argument("ids", nargs="+"); x.set_defaults(fn=cmd_actions)
    x = s.add_parser("anim-check"); x.add_argument("elf"); x.add_argument("cls", nargs="?"); x.add_argument("style", nargs="?")
    x.set_defaults(fn=cmd_anim_check)
    x = s.add_parser("pnach-map"); x.add_argument("pnach"); x.set_defaults(fn=cmd_pnach_map)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
