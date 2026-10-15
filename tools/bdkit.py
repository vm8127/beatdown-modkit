#!/usr/bin/env python3
"""Beat Down: Fists of Vengeance (USA, SLUS-21150) modding kit.

Pure Python 3 standard library. Works on Windows, macOS and Linux.

Run from the top of the workspace, with the disc unpacked into ISO/ (see README.md).
Usage examples (run `python tools/bdkit.py -h` for the full list):
  python tools/bdkit.py iso-list    BeatDown.iso
  python tools/bdkit.py iso-extract BeatDown.iso ISO                  # unpack the whole disc into ISO/
  python tools/bdkit.py iso-extract BeatDown.iso ISO XAF/STAGE.XAF SLUS_211.50
  python tools/bdkit.py xaf-list    ISO/XAF/STAGE.XAF
  python tools/bdkit.py xaf-extract ISO/XAF/STAGE.XAF out_dir [index ...]
  python tools/bdkit.py archive-names ISO/XAF/ARCHIVE.XAF             # outfit part names (an .iso works too)
  python tools/bdkit.py chars     ISO/SLUS_211.50                     # character class table
  python tools/bdkit.py groups    ISO/SLUS_211.50                     # animation groups
  python tools/bdkit.py swap-moveset ISO/SLUS_211.50 AARON RAVEN      # prints a pnach section
  python tools/bdkit.py swap-moveset ISO/SLUS_211.50 AARON JASON_G --keep-body   # for different body sizes
  python tools/bdkit.py mix-moveset ISO/SLUS_211.50 AARON JASON_G --take grab   # keep A's moves, take B's grabs
  python tools/bdkit.py fighters  ISO/SLUS_211.50                     # fighter records: outfit preset (model) + class row
  python tools/bdkit.py swap-model ISO/SLUS_211.50 AARON CHESTER      # prints a pnach section (model only, keeps the name)
  python tools/bdkit.py roster    ISO/SLUS_211.50 mods/roster.json    # story heroes recast from a roster file
  python tools/bdkit.py moves     ISO/SLUS_211.50 ISO/XAF/CDATA.XAF 0x13   # move list (names + inputs) of a style
  python tools/bdkit.py style-map ISO/SLUS_211.50 ISO/XAF/CDATA.XAF > docs/movesets.md
  python tools/bdkit.py tex       ISO/XAF/DATA.XAF out_dir 8153 7489   # outfit textures (slot parts) as PNG
  python tools/bdkit.py read      ISO/SLUS_211.50 0x50D8B0 16         # hex dump at a game address
  python tools/bdkit.py addr      0x50D8B0                            # address <-> ELF/ISO offsets

Everything here was worked out from the US release; addresses are EE virtual
addresses as PCSX2 sees them.
"""
import argparse
import os
import struct
import sys

# ---------------------------------------------------------------------------
# Constants for SLUS-21150
# ---------------------------------------------------------------------------
ELF_NAME = "SLUS_211.50"
ELF_CRC = 0xC9F6EF9A          # PCSX2 pnach file name: SLUS-21150_C9F6EF9A.pnach
ELF_LOAD_VADDR = 0x00100000   # single LOAD segment
ELF_LOAD_OFFSET = 0x80        # file offset of that segment
ELF_LOAD_FILESZ = 0x4FEB00
ELF_ISO_LBA = 1156876         # where SLUS_211.50 sits on the disc (2048-byte sectors)

ARCHIVES = ["DATA", "STAGE", "GRAPH", "FBGM", "SOUND", "FSTAGE", "CDATA", "FSCENE", "SCRIPT", "ARCHIVE"]

TYPE_NAME_TABLE = 0x00589AF0  # char* [52], index = character type id
CLASS_TABLE = 0x0050D6A0      # 16-byte rows, row = type id - 1
CLASS_ROWS = 51
ANIM_GROUP_TABLE = 0x004FB4C0 # 8-byte rows {s16 stage_entry, s16 pad, u32 anim_id_list}
ANIM_GROUP_COUNT = 317
GROUP_LIST_END = 9999
BODY_NAMES = {0: "S", 1: "M", 2: "L"}
SHARED_GROUPS = [159, 15, 16, 39, 38, 19, 21, 22, 23, 27, 30, 31, 34]  # in every fighter's list
BODY_GROUPS = {0: [164, 165], 1: [160, 161], 2: [162, 163]}            # per body size
MOVE_LIST_TABLE = 0x005CAB40  # 8-byte rows {u16 cmd_first, u16 cmd_last, u16 name_first, u16 name_last}, row = style - 1
MOVE_LIST_ROWS = 47           # styles 0x01-0x2F; 0xFFFF = no move list (style 0x09)
MOVE_TEXT_ENTRY = {"jp": 397, "en": 398, "fr": 399, "de": 400, "es": 401, "it": 402}  # CDATA.XAF move text
BUTTONS = {"〆": "P", "◎": "K", "◇": "G", "4": "A"}   # punch, kick, guard, action (grab/search)
FIGHTER_TABLE = 0x00413134    # 72-byte records, one per fighter spawn ID: +0 s16 outfit preset, +2 u16 class row, +4 u8 ?, +0xC s16 HP
FIGHTER_COUNT = 602
HERO_SELECT = 0x004334B0      # s16[5] fighter IDs of the playable heroes: Raven 107, Jason G 53, Aaron 68, Lola 22, Gina 108
# Outfit presets are CDATA.XAF entry 0: 189 records of 0x498 bytes = 22 slots of {u32 slot, s16 parts[16] ending -1},
# then params at +0x318. Fighter init 0x0013B490 copies the preset's slots into the fighter (+0x68) to build its model.
PRESET_LOOKUP = 0x002A8720    # (preset, 1 = parts | 2 = params) -> pointer into CDATA.XAF entry 0
MODEL_HOOK_SITES = [0x0013B54C, 0x0013B55C]   # the two jal PRESET_LOOKUP in fighter init
MODEL_HOOK = 0x003E0130       # 20 unused zero words between the last code and the VU microcode
HERO_TEMPLATES = {"AARON": 68, "RAVEN": 107, "JASON_G": 53, "LOLA": 22, "GINA": 108}  # story heroes' fighter IDs
ROSTER_CAVE = 0x00216538      # 10,936-byte library function nothing calls or points to; the roster hooks live here
ROSTER_CAVE_SIZE = 10936
PERSON_GET = 0x0013C960       # Person_Get(person id) -> person record (preset at +0x44)
DISPLAY_NAME = 0x0013CA80     # Fighter_DisplayName(person id) -> name string
TEXT_GET = 0x00387980         # Text_Get(text id, 0) -> string
NAME_TEXT_BASE = 11001        # a fighter's name is text 11001 + its fighter ID (11069 Aaron, 11021 Chester)
HP_BAR_NAME_SITE = 0x0031B3E4 # jal DISPLAY_NAME in HpBar_Build 0x0031B210 (one line per team member)
STYLE_COMMANDS = 0x00515C10   # u32 per style: list of {u32 condition, u32 sequence}, sequence 0 ends it (docs/CODEMAP.md)
MIX_CAVE = 0x00217000         # mix-moveset's area: free part of ROSTER_CAVE (the roster uses +0..+0x200,
MIX_CAVE_END = 0x00218F00     # the negotiation mod 0x218F00-0x218F40). Layout:
MIX_LIST = MIX_CAVE           #   mixed command list, up to 191 commands
MIX_CONDS = 0x00217600        #   copies of condition records with their move list line renumbered (16 bytes each)
MIX_HOOKS = 0x00217A00        #   move list hooks (code)
MIX_MOVELIST = 0x00217C00     #   move list override: {u8 style, u8 lines, u16 0, u32 ptr} rows ending style 0,
MIX_LINES = 0x00217C10        #   then the lines, {u8 style, u8 line} each: which style's text each line shows
# The MOVE LIST screen reads a style's lines through four small functions (a = style, i = line):
MOVELIST_COUNT = 0x001C5BA0   # (?, a) -> number of lines
MOVELIST_NAME = 0x001C5BF0    # (?, a, i) -> name text
MOVELIST_INPUT = 0x001C5C30   # (?, a, i) -> input text
MOVELIST_COLOR = 0x001C5C70   # (a, i) -> 1 for the second text colour (depends on the text and a few hard-coded lines)
# Lines are hidden until learned: MoveList_IsLearned 0x00317E50 (fighter, style, line) finds the command whose
# condition's u16 +0 equals the line and checks it, so mixed lists renumber those condition records.
# Input families for mix-moveset: commands by their last input code, move list lines by their input text.
# Grabs: 0x2F GRAB P, 0x32 GRAB K, 0x29-0x34 the grab + direction/button variants (0x2B/0x2C GRAB →/←P,
# 0x2D GRAB ↑P, 0x2E GRAB ↓P, 0x33 GRAB G, 0x29 GRAB ∫∫P), 0x6B/0x6C rear grabs, 0x70-0x73 grabs near a wall.
INPUT_FAMILIES = {
    "grab": (set(range(0x29, 0x35)) | {0x6B, 0x6C, 0x70, 0x71, 0x72, 0x73}, lambda inp: "GRAB" in inp),
}


# ---------------------------------------------------------------------------
# ELF helpers
# ---------------------------------------------------------------------------
class Elf:
    def __init__(self, path):
        with open(path, "rb") as f:
            self.d = f.read()
        if self.d[:4] != b"\x7fELF":
            sys.exit(f"{path} is not an ELF")

    @staticmethod
    def v2o(v):
        return v - ELF_LOAD_VADDR + ELF_LOAD_OFFSET

    @staticmethod
    def o2v(o):
        return o - ELF_LOAD_OFFSET + ELF_LOAD_VADDR

    def u32(self, v):
        return struct.unpack_from("<I", self.d, self.v2o(v))[0]

    def s16(self, v):
        return struct.unpack_from("<h", self.d, self.v2o(v))[0]

    def cstr(self, v):
        o = self.v2o(v)
        return self.d[o:self.d.index(b"\0", o)].decode("latin1")

    def crc(self):
        c = 0
        for (w,) in struct.iter_unpack("<I", self.d[: len(self.d) // 4 * 4]):
            c ^= w
        return c

    def type_names(self):
        return [self.cstr(self.u32(TYPE_NAME_TABLE + 4 * i)) for i in range(52)]

    def group_list(self, ptr):
        out = []
        while True:
            v = self.u32(ptr)
            if v == GROUP_LIST_END:
                return out
            out.append(v)
            ptr += 4

    def classes(self):
        names = self.type_names()
        rows = []
        for r in range(CLASS_ROWS):
            a = CLASS_TABLE + 16 * r
            body, style, skel, glist = (self.u32(a + 4 * k) for k in range(4))
            if glist == 0:
                break
            tid = r + 1
            rows.append(dict(row=r, addr=a, type_id=tid, name=names[tid] if tid < len(names) else "?",
                             body=body, style=style, skeleton=skel, groups_ptr=glist,
                             groups=self.group_list(glist)))
        return rows

    def anim_groups(self):
        out = []
        for g in range(ANIM_GROUP_COUNT):
            a = ANIM_GROUP_TABLE + 8 * g
            entry = self.s16(a)
            ptr = self.u32(a + 4)
            ids = []
            k = ptr
            while True:
                v = self.s16(k)
                k += 2
                if v == -1:
                    break
                ids.append(v)
            out.append(dict(group=g, stage_entry=entry, anim_ids=ids))
        return out

    def fighters(self):
        """Fighter spawn records: which outfit preset (model) and which class row each one uses."""
        out = []
        for i in range(FIGHTER_COUNT):
            a = FIGHTER_TABLE + 72 * i
            preset, row = struct.unpack_from("<hH", self.d, self.v2o(a))
            hp = self.s16(a + 0xC)
            out.append(dict(id=i, addr=a, preset=preset, row=row, hp=hp))
        return out

    def move_lists(self):
        """{style: (cmd_first, cmd_last, name_first, name_last)} text IDs from the move list table."""
        out = {}
        for r in range(MOVE_LIST_ROWS):
            v = struct.unpack_from("<4H", self.d, self.v2o(MOVE_LIST_TABLE + 8 * r))
            out[r + 1] = None if v[0] == 0xFFFF else v
        return out


# ---------------------------------------------------------------------------
# ISO9660
# ---------------------------------------------------------------------------
def iso_files(path):
    f = open(path, "rb")

    def rd(lba, n):
        f.seek(lba * 2048)
        return f.read(n)

    pvd = rd(16, 2048)
    if pvd[1:6] != b"CD001":
        sys.exit("not an ISO9660 image")
    root = pvd[156:190]
    out = []

    def walk(lba, size, prefix):
        data = rd(lba, size)
        i = 0
        while i < len(data):
            ln = data[i]
            if ln == 0:
                i = (i // 2048 + 1) * 2048
                continue
            rec = data[i:i + ln]
            i += ln
            elba, esz = struct.unpack_from("<I", rec, 2)[0], struct.unpack_from("<I", rec, 10)[0]
            flags, nl = rec[25], rec[32]
            name = rec[33:33 + nl]
            if name in (b"\0", b"\1"):
                continue
            name = name.decode("latin1").split(";")[0]
            p = f"{prefix}/{name}" if prefix else name
            if flags & 2:
                walk(elba, esz, p)
            else:
                out.append((p, elba, esz))

    walk(struct.unpack_from("<I", root, 2)[0], struct.unpack_from("<I", root, 10)[0], "")
    f.close()
    return out


def copy_range(src, off, size, dst):
    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
    with open(src, "rb") as f, open(dst, "wb") as o:
        f.seek(off)
        left = size
        while left:
            chunk = f.read(min(left, 1 << 20))
            if not chunk:
                break
            o.write(chunk)
            left -= len(chunk)


# ---------------------------------------------------------------------------
# XAF (XPEC archive)
# ---------------------------------------------------------------------------
ASSET_TYPES = {0x16: "model", 0x18: "texture", 0x10: "mesh", 0x1B: "anim"}


def xaf_entries(path):
    with open(path, "rb") as f:
        h = f.read(0x40)
        if h[:4] != b"XAF\0":
            sys.exit(f"{path} is not an XAF archive")
        n = struct.unpack_from("<I", h, 0x2C)[0]
        ents = [struct.unpack("<II", f.read(8)) for _ in range(n)]
        out = []
        for i, (o, s) in enumerate(ents):
            f.seek(o)
            head = f.read(16)
            out.append((i, o, s, head))
    return out


def describe(head):
    t = struct.unpack_from("<I", head, 0)[0] if len(head) >= 4 else None
    if head[:4] in (b"XAU\0", b"SSLD", b"@CON"):
        return head[:4].decode("latin1").strip("\0")
    if t in ASSET_TYPES:
        return ASSET_TYPES[t]
    if t is not None and len(head) >= 8 and struct.unpack_from("<I", head, 4)[0] & 0x80000000:
        return f"pack[{t}]"   # STAGE.XAF anim packs: count, then offsets | 0x80000000
    return f"0x{t:x}" if t is not None else "?"


def text_table(cdata, entry):
    """Read a CDATA.XAF text entry: {u32 size, u16 count, u16 lang, count x {u16 id, u16 len, u32 off}}, UTF-8."""
    import unicodedata
    o, s = xaf_entries(cdata)[entry][1:3]
    with open(cdata, "rb") as f:
        f.seek(o)
        d = f.read(s)
    n = struct.unpack_from("<H", d, 4)[0]
    base = 8 + 8 * n
    out = {}
    for i in range(n):
        tid, ln, off = struct.unpack_from("<HHI", d, 8 + 8 * i)
        t = d[base + off:base + off + ln].rstrip(b"\0").decode("utf-8", "replace")
        out[tid] = unicodedata.normalize("NFKC", t)   # the game stores full-width ASCII
    return out


def buttons(cmd):
    return "".join(BUTTONS.get(ch, ch) for ch in cmd)


def style_moves(e, cdata, lang="en"):
    """{style: [(name, input), ...]} for every style with a move list."""
    t = text_table(cdata, MOVE_TEXT_ENTRY[lang])
    out = {}
    for style, v in e.move_lists().items():
        if v:
            c0, c1, n0, _ = v
            out[style] = [(t.get(n0 + i, "?").strip(), buttons(t.get(c0 + i, "?"))) for i in range(c1 - c0 + 1)]
    return out


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
def cmd_iso_list(a):
    for p, lba, sz in iso_files(a.iso):
        print(f"{lba:8d} {sz:11d} {p}")


def cmd_iso_extract(a):
    want = {w.replace("\\", "/").upper().lstrip("/") for w in a.files}
    for p, lba, sz in iso_files(a.iso):
        if want and p.upper() not in want:
            continue
        dst = os.path.join(a.out, *p.split("/"))
        print(f"extract {p} ({sz} bytes)")
        copy_range(a.iso, lba * 2048, sz, dst)


def cmd_xaf_list(a):
    for i, o, s, head in xaf_entries(a.xaf):
        print(f"{i:5d} 0x{o:08x} {s:9d} {describe(head)}")


def cmd_xaf_extract(a):
    base = os.path.splitext(os.path.basename(a.xaf))[0]
    pick = {int(x) for x in a.index}
    os.makedirs(a.out, exist_ok=True)
    for i, o, s, head in xaf_entries(a.xaf):
        if pick and i not in pick:
            continue
        copy_range(a.xaf, o, s, os.path.join(a.out, f"{base}_{i:05d}.{describe(head).split('[')[0]}"))
    print("done")


def cmd_archive_names(a):
    # ARCHIVE.XAF (outfit/body parts) entries carry a part name like HAI_A01AAA near the start.
    import re
    # Takes either ISO/XAF/ARCHIVE.XAF or the whole disc image.
    with open(a.iso, "rb") as f:
        is_xaf = f.read(4) == b"XAF\0"
    if is_xaf:
        base = 0
    else:
        hit = [x for x in iso_files(a.iso) if x[0].upper() == "XAF/ARCHIVE.XAF"]
        base = hit[0][1] * 2048
    with open(a.iso, "rb") as f:
        f.seek(base + 0x2C)
        n = struct.unpack("<I", f.read(4))[0]
        f.seek(base + 0x40)
        ents = [struct.unpack("<II", f.read(8)) for _ in range(n)]
        for i, (o, s) in enumerate(ents):
            f.seek(base + o)
            m = re.search(rb"[A-Z0-9]{2,4}_[A-Z0-9_]{3,}", f.read(1024))
            print(f"{i:5d} {s:8d} {m.group().decode() if m else '?'}")


def cmd_chars(a):
    e = Elf(a.elf)
    print(f"{'row':>3} {'addr':>10} {'type':>4} {'name':<16} body style  groups")
    for c in e.classes():
        print(f"{c['row']:3d} 0x{c['addr']:08X} {c['type_id']:4d} {c['name']:<16} {BODY_NAMES.get(c['body'], c['body']):>4} "
              f"0x{c['style']:02X}   {c['groups']}")


def cmd_groups(a):
    e = Elf(a.elf)
    for g in e.anim_groups():
        print(f"group {g['group']:3d} STAGE[{g['stage_entry']:3d}] {len(g['anim_ids']):3d} anims {g['anim_ids']}")


def find_class(e, name):
    name = name.upper().replace(" ", "_")
    for c in e.classes():
        if c["name"].upper() == name:
            return c
    sys.exit(f"no character named {name}; run `chars` to see names")


def own_groups(c):
    """Groups that belong to the fighter's style: not shared, not body groups. First one is the move set."""
    body = {g for v in BODY_GROUPS.values() for g in v}
    return [g for g in c["groups"] if g not in SHARED_GROUPS and g not in body]


def moveset_patch(e, dst, src, keep_body=False):
    """(description, pnach lines) giving class dst the moves of class src."""
    if not keep_body:
        if dst["skeleton"] != src["skeleton"]:
            print(f"; WARNING: {dst['name']} and {src['name']} use different skeletons; animations may break. "
                  f"Use --keep-body instead.", file=sys.stderr)
        return (f"Style 0x{src['style']:02X} and anim groups of {src['name']} on {dst['name']}",
                [f"patch=1,EE,2{dst['addr'] + 4:07X},extended,{src['style']:08X}",
                 f"patch=1,EE,2{dst['addr'] + 12:07X},extended,{src['groups_ptr']:08X}"])
    # Keep dst's body groups: edit dst's own group list in place. Its move-set group is replaced by
    # src's, and src's other style groups are appended (into the zero padding after the 9999
    # terminator). Style move groups are body-size independent (BOXER S/M/L all load group 166), so
    # this avoids loading body animations for the wrong skeleton.
    d_own, s_own = own_groups(dst), own_groups(src)
    if not d_own or not s_own:
        sys.exit("one of the fighters has no style groups of its own")
    new = [s_own[0] if g == d_own[0] else g for g in dst["groups"]]
    new += [g for g in s_own[1:] if g not in new]
    ptr = dst["groups_ptr"]
    room = len(dst["groups"]) + 1
    while e.u32(ptr + 4 * room) == 0:
        room += 1
    if len(new) + 1 > room:
        sys.exit(f"new list needs {len(new) + 1} words but only {room} fit at 0x{ptr:08X}")
    lines = [f"patch=1,EE,2{dst['addr'] + 4:07X},extended,{src['style']:08X}",
             f"patch=1,EE,2{dst['addr'] + 12:07X},extended,{ptr:08X}"]
    for i, w in enumerate(new + [GROUP_LIST_END]):
        if e.u32(ptr + 4 * i) != w:
            lines.append(f"patch=1,EE,2{ptr + 4 * i:07X},extended,{w:08X}")
    return (f"Style 0x{src['style']:02X} of {src['name']} on {dst['name']}; keeps "
            f"{dst['name']}'s body groups. List at 0x{ptr:08X} becomes {new}", lines)


def command_list(e, style):
    """A style's command list as [(condition ptr, sequence ptr, [input codes], action)]."""
    out, p = [], e.u32(STYLE_COMMANDS + 4 * style)
    while e.u32(p + 4):
        cond, seq = e.u32(p), e.u32(p + 4)
        codes, action = [], 0
        while e.u32(seq) != 0xFFFFFFFF:
            codes.append(e.u32(seq))
            action = e.s16(seq + 4)
            seq += 8
        out.append((cond, e.u32(p + 4), codes, action))
        p += 8
    return out


def mips_hook_code(base, table):
    """The four move list hooks, assembled at `base`. Each one looks the style up in `table`; the count hook
    returns the override's line count, the others swap (style, line) for the line's source and run the original
    function. Returns (words, {function: hook address})."""
    def i_type(op, rs, rt, imm):
        return op << 26 | rs << 21 | rt << 16 | imm & 0xFFFF
    T0, T1, T2, T3, V0, RA = 8, 9, 10, 11, 2, 31
    hi, lo = (table + 0x8000) >> 16, table & 0xFFFF
    words, entry = [], {}
    for fn, style, line in [(MOVELIST_COUNT, 5, None), (MOVELIST_NAME, 5, 6), (MOVELIST_INPUT, 5, 6),
                            (MOVELIST_COLOR, 4, 5)]:
        entry[fn] = base + 4 * len(words)
        code = [i_type(0x0F, 0, T0, hi),                  # lui   t0, hi(table)
                i_type(0x09, T0, T0, lo),                 # addiu t0, t0, lo(table)
                i_type(0x24, T0, T1, 0)]                  # loop: lbu t1, 0(t0)
        found = ([0x03E00008,                             # jr    ra
                  i_type(0x24, T0, V0, 1)]                # lbu   v0, 1(t0)   line count
                 if line is None else
                 [i_type(0x23, T0, T3, 4),                # lw    t3, 4(t0)   lines
                  i_type(0x0C, line, T2, 0xFF),           # andi  t2, line, 0xff
                  T2 << 16 | T2 << 11 | 1 << 6,           # sll   t2, t2, 1
                  T3 << 21 | T2 << 16 | T3 << 11 | 0x21,  # addu  t3, t3, t2
                  i_type(0x24, T3, style, 0),             # lbu   style, 0(t3)
                  i_type(0x04, 0, 0, 3),                  # b     done
                  i_type(0x24, T3, line, 1)])             # lbu   line, 1(t3)
        n_found = len(found)
        code += [i_type(0x04, T1, 0, 4 + n_found + 2),    # beq   t1, zero, done
                 0,
                 i_type(0x0C, style, T2, 0xFF),           # andi  t2, style, 0xff
                 i_type(0x05, T1, T2, n_found + 1),       # bne   t1, t2, next
                 0] + found
        code += [i_type(0x04, 0, 0, -(len(code) - 2 + 1)),  # next: b loop
                 i_type(0x09, T0, T0, 8)]                 # addiu t0, t0, 8
        code += [None, None,                              # done: the function's first two instructions
                 0x08000000 | ((fn + 8) >> 2 & 0x3FFFFFF),  # j     function + 8
                 0]
        words += code
    return words, entry


def mix_patch(e, dst, src, take, moves=None):
    """(description, pnach lines) giving class dst the src commands of one input family.

    dst's own commands in the family are replaced by src's (same input, same place in the list), dst's that src
    lacks are dropped, and src's extra ones go at the end. The new list is written to MIX_LIST and dst's style
    pointer moved there; src's style groups are added to dst's group list so the new moves have their animations.
    With `moves` (style_moves() output) and a family that knows its move list lines, the MOVE LIST screen is fixed
    too: dst's family lines are swapped for src's, through the move list hooks."""
    codes, line_test = take
    d_cmds, s_cmds = command_list(e, dst["style"]), command_list(e, src["style"])
    fam = lambda c: c[2] and c[2][-1] in codes
    s_fam = [c for c in s_cmds if fam(c)]
    if not s_fam:
        sys.exit(f"{src['name']} has no commands with those inputs")
    used, new, dropped = set(), [], []
    for c in d_cmds:
        if not fam(c):
            new.append((dst["style"], c))
            continue
        m = next((i for i, x in enumerate(s_fam) if x[2] == c[2] and i not in used), None)
        if m is None:
            dropped.append(c)
        else:
            used.add(m)
            new.append((src["style"], s_fam[m]))
    new += [(src["style"], x) for i, x in enumerate(s_fam) if i not in used]
    if MIX_LIST + 8 * (len(new) + 1) > MIX_CONDS:
        sys.exit("mixed list doesn't fit in the cave")
    w = lambda addr, val: f"patch=1,EE,2{addr:07X},extended,{val:08X}"
    lines = [w(dst["addr"] + 4, dst["style"]),           # dst's own style and group list, as in the original game
             w(dst["addr"] + 12, dst["groups_ptr"]),
             w(STYLE_COMMANDS + 4 * dst["style"], MIX_LIST)]

    # Move list: dst's lines, with its family lines replaced by src's where the first of them was.
    menu, note = None, "MOVE LIST not changed"
    if moves and line_test and moves.get(dst["style"]) and moves.get(src["style"]):
        d_lines = [(dst["style"], i) for i, (_, inp) in enumerate(moves[dst["style"]]) if not line_test(inp)]
        s_lines = [(src["style"], i) for i, (_, inp) in enumerate(moves[src["style"]]) if line_test(inp)]
        first = next((i for i, (_, inp) in enumerate(moves[dst["style"]]) if line_test(inp)), len(d_lines))
        menu = d_lines[:first] + s_lines + d_lines[first:]
        if len(menu) > 255:
            sys.exit("move list too long")
        note = f"MOVE LIST shows {len(menu)} lines, {len(s_lines)} of them {src['name']}'s"

    # Commands, with condition records copied and renumbered to the new move list lines.
    conds = []
    for n, (style, (cond, seq, _, _)) in enumerate(new):
        if cond and menu:
            rec = e.d[e.v2o(cond):e.v2o(cond) + 16]
            old = struct.unpack_from("<H", rec)[0]
            line = menu.index((style, old)) if (style, old) in menu else 0xFFFF
            if line != old:
                rec = struct.pack("<H", line) + rec[2:]
                at = next((MIX_CONDS + 16 * k for k, r in enumerate(conds) if r == rec), None)
                if at is None:
                    at = MIX_CONDS + 16 * len(conds)
                    conds.append(rec)
                cond = at
        lines += [w(MIX_LIST + 8 * n, cond), w(MIX_LIST + 8 * n + 4, seq)]
    lines += [w(MIX_LIST + 8 * len(new), 0), w(MIX_LIST + 8 * len(new) + 4, 0)]
    if MIX_CONDS + 16 * len(conds) > MIX_HOOKS:
        sys.exit("too many condition records")
    for k, rec in enumerate(conds):
        for j in range(4):
            lines.append(w(MIX_CONDS + 16 * k + 4 * j, struct.unpack_from("<I", rec, 4 * j)[0]))

    if menu:
        code, entry = mips_hook_code(MIX_HOOKS, MIX_MOVELIST)
        fns = list(entry)
        k = 0
        for i, word in enumerate(code):
            if word is None:   # copy of the hooked function's first two instructions
                word = e.u32(fns[k // 2] + 4 * (k % 2))
                k += 1
            lines.append(w(MIX_HOOKS + 4 * i, word))
        table = [dst["style"] | len(menu) << 8, MIX_LINES, 0, 0]   # one row, then the style 0 end row
        for i, v in enumerate(table):
            lines.append(w(MIX_MOVELIST + 4 * i, v))
        data = b"".join(bytes(x) for x in menu) + b"\0" * (-2 * len(menu) % 4)
        for i in range(0, len(data), 4):
            lines.append(w(MIX_LINES + i, struct.unpack_from("<I", data, i)[0]))
        for fn, at in entry.items():   # hooked last, once the code is in place
            lines += [w(fn, 0x08000000 | (at >> 2 & 0x3FFFFFF)), w(fn + 4, 0)]

    groups = dst["groups"] + [g for g in own_groups(src) if g not in dst["groups"]]
    ptr, room = dst["groups_ptr"], len(dst["groups"]) + 1
    while e.u32(ptr + 4 * room) == 0:
        room += 1
    if len(groups) + 1 > room:
        sys.exit(f"group list needs {len(groups) + 1} words but only {room} fit at 0x{ptr:08X}")
    for i, v in enumerate(groups + [GROUP_LIST_END]):   # the whole list, in case another Aaron cheat changed it
        lines.append(w(ptr + 4 * i, v))
    taken = sum(1 for st, _ in new if st == src["style"])
    desc = (f"Style 0x{dst['style']:02X} list rebuilt at 0x{MIX_LIST:08X}: {len(new)} commands, {taken} from "
            f"{src['name']}" + (f", {len(dropped)} of {dst['name']}'s dropped" if dropped else "") +
            f". {note}. Group list at 0x{ptr:08X} becomes {groups}")
    return desc, lines


def cmd_mix_moveset(a):
    e = Elf(a.elf)
    dst, src = find_class(e, a.target), find_class(e, a.source)
    codes, line_test = set(), None
    for t in a.take.split(","):
        if t in INPUT_FAMILIES:
            codes |= INPUT_FAMILIES[t][0]
            line_test = INPUT_FAMILIES[t][1]
        else:
            codes.add(int(t, 16))
    if line_test and any(t not in INPUT_FAMILIES for t in a.take.split(",")):
        line_test = None   # can't tell which move list lines raw input codes belong to
    moves = None
    if os.path.exists(a.cdata):
        moves = style_moves(e, a.cdata)
    else:
        print(f"; {a.cdata} not found, so the MOVE LIST screen is left alone", file=sys.stderr)
    if not line_test:
        print("; raw input codes: the MOVE LIST screen is left alone", file=sys.stderr)
    desc, lines = mix_patch(e, dst, src, (codes, line_test), moves)
    title = lambda c: c["name"].replace("_", " ").title()
    print(f"[{title(dst)} uses {title(src)}'s {a.take} moves (one {title(dst)} cheat at a time)]")
    print(f"description={desc}")
    print("\n".join(lines))


def cmd_swap_moveset(a):
    e = Elf(a.elf)
    dst, src = find_class(e, a.target), find_class(e, a.source)
    desc, lines = moveset_patch(e, dst, src, a.keep_body)
    print(f"[{dst['name'].title()} uses {src['name'].title()}'s moveset]")
    print(f"description={desc}")
    print("\n".join(lines))


def cmd_fighters(a):
    e = Elf(a.elf)
    names = {c["row"]: c["name"] for c in e.classes()}
    heroes = struct.unpack_from("<5h", e.d, e.v2o(HERO_SELECT))
    print(f"{'id':>3} {'addr':>10} preset row  class             hp")
    for f in e.fighters():
        if f["row"] >= CLASS_ROWS:
            continue
        tag = "  (playable)" if f["id"] in heroes else ""
        print(f"{f['id']:3d} 0x{f['addr']:08X} {f['preset']:6d} {f['row']:3d}  {names.get(f['row'], '?'):<16} {f['hp']:5d}{tag}")


def cmd_swap_model(a):
    """Give class A the outfit parts (model) of class B by hooking the preset lookup in fighter init.

    A's fighter records keep their own preset number, because the game checks the preset number to
    recognise the heroes (HP bar name, and more). Only the two lookups in fighter init (parts at
    0x0013B54C, params at 0x0013B55C) are sent through a hook in unused padding at MODEL_HOOK, which
    swaps A's presets for B's before calling 0x002A8720.
    """
    e = Elf(a.elf)
    dst, src = find_class(e, a.target), find_class(e, a.source)
    if dst["body"] != src["body"]:
        print(f"; WARNING: {dst['name']} is {BODY_NAMES[dst['body']]} and {src['name']} is {BODY_NAMES[src['body']]}; "
              f"the model will play {dst['name']}'s body animations.", file=sys.stderr)
    fs = e.fighters()
    if a.preset is not None:
        preset = int(a.preset, 0)
    else:
        ps = [f["preset"] for f in fs if f["row"] == src["row"]]
        if not ps:
            sys.exit(f"no fighter record uses {src['name']}")
        preset = max(set(ps), key=ps.count)
    mine = sorted({f["preset"] for f in fs if f["row"] == dst["row"]})
    if not 1 <= len(mine) <= 5:
        sys.exit(f"{dst['name']} has {len(mine)} presets; the hook has room for 5")
    # for each target preset: addiu t0,zero,P / beq a0,t0,use / nop; then j lookup / nop;
    # use: addiu a0,zero,src / j lookup / nop
    use = 3 * len(mine) + 2
    words = []
    for p in mine:
        k = len(words)
        words += [0x24080000 | p, 0x10880000 | (use - (k + 2)), 0]
    words += [0x08000000 | (PRESET_LOOKUP >> 2), 0]
    words += [0x24040000 | preset, 0x08000000 | (PRESET_LOOKUP >> 2), 0]
    jal = 0x0C000000 | (MODEL_HOOK >> 2)
    print(f"[{dst['name'].title()} uses {src['name'].title()}'s model]")
    print(f"description=Fighter init builds {dst['name']} (presets {', '.join(map(str, mine))}) from {src['name']}'s "
          f"outfit preset {preset}; {dst['name']} keeps its own preset number, name and class row")
    for i, w in enumerate(words):
        print(f"patch=1,EE,2{MODEL_HOOK + 4 * i:07X},extended,{w:08X}")
    for site in MODEL_HOOK_SITES:
        print(f"patch=1,EE,2{site:07X},extended,{jal:08X}")


def find_fighter(e, spec, fs=None):
    """A fighter record from 'NAME' (that class's most common record) or 'fighter:ID'."""
    fs = fs or e.fighters()
    if spec.lower().startswith("fighter:"):
        return fs[int(spec.split(":", 1)[1], 0)]
    c = find_class(e, spec)
    recs = [f for f in fs if f["row"] == c["row"]]
    if not recs:
        sys.exit(f"no fighter record uses {c['name']}")
    best = max({f["preset"] for f in recs}, key=lambda p: sum(f["preset"] == p for f in recs))
    return next(f for f in recs if f["preset"] == best)


def preset_hook(table_addr):
    """Table-driven replacement for PRESET_LOOKUP: looks a0 up in {s16 from, s16 to} pairs ending -1."""
    hi, lo = (table_addr + 0x8000) >> 16, table_addr & 0xFFFF
    j = 0x08000000 | (PRESET_LOOKUP >> 2)
    return [0x3C080000 | hi,  # lui   t0, hi(table)
            0x25080000 | lo,  # addiu t0, t0, lo(table)
            0x85090000,       # loop: lh t1, 0(t0)
            0x05200009,       # bltz  t1, done
            0,
            0x15240004,       # bne   t1, a0, next
            0,
            0x85040002,       # lh    a0, 2(t0)      replacement preset
            0x10000004,       # b     done
            0,
            0x25080004,       # next: addiu t0, t0, 4
            0x1000FFF6,       # b     loop
            0,
            j,                # done: j PRESET_LOOKUP
            0]


def name_hook(table_addr):
    """Replacement for DISPLAY_NAME at the HP bar: if the person's preset is in {s16 preset, s16 text id}
    pairs ending -1, return that text, otherwise fall through to DISPLAY_NAME."""
    hi, lo = (table_addr + 0x8000) >> 16, table_addr & 0xFFFF
    return [0x27BDFFF0,                           # addiu sp, sp, -16
            0xFFBF0000,                           # sd    ra, 0(sp)
            0x0C000000 | (PERSON_GET >> 2),       # jal   Person_Get
            0xFFA40008,                           # sd    a0, 8(sp)
            0x844A0044,                           # lh    t2, 0x44(v0)   preset
            0xDFA40008,                           # ld    a0, 8(sp)
            0xDFBF0000,                           # ld    ra, 0(sp)
            0x27BD0010,                           # addiu sp, sp, 16
            0x3C080000 | hi,                      # lui   t0, hi(table)
            0x25080000 | lo,                      # addiu t0, t0, lo(table)
            0x85090000,                           # loop: lh t1, 0(t0)
            0x05200009,                           # bltz  t1, miss
            0,
            0x152A0004,                           # bne   t1, t2, next
            0,
            0x85040002,                           # lh    a0, 2(t0)      text id
            0x08000000 | (TEXT_GET >> 2),         # j     Text_Get
            0x0000282D,                           # daddu a1, zero, zero
            0x25080004,                           # next: addiu t0, t0, 4
            0x1000FFF6,                           # b     loop
            0,
            0x08000000 | (DISPLAY_NAME >> 2),     # miss: j DISPLAY_NAME
            0]


def cmd_roster(a):
    """Build one pnach section from a roster file that recasts the story heroes.

    Each story hero keeps its own fighter ID, preset number and class row, so story events, items and
    dialogue still see that hero. What changes is what the player sees and plays:
      model  - fighter init builds the hero from another fighter's outfit preset (table-driven hook)
      moves  - the hero's class row gets another fighter's style and animation groups
      name   - the HP bar shows another fighter's name (defaults to the model's; "keep" keeps the hero's)
      stats  - the hero template's HP and attack rank (new games only; person records are saved)
    """
    import json
    e = Elf(a.elf)
    cfg = json.load(open(a.roster, encoding="utf-8"))
    fs = e.fighters()
    remap, names, lines, notes = [], [], [], []
    for hero, want in cfg.get("heroes", {}).items():
        hero = hero.upper()
        if hero not in HERO_TEMPLATES:
            sys.exit(f"{hero} is not a story hero; pick one of {', '.join(HERO_TEMPLATES)}")
        dst = find_class(e, hero)
        tid = HERO_TEMPLATES[hero]
        if want.get("model"):
            src = find_fighter(e, want["model"], fs)
            src_cls = next(c for c in e.classes() if c["row"] == src["row"])
            if src_cls["body"] != dst["body"]:
                print(f"; WARNING: {hero} is {BODY_NAMES[dst['body']]} and {want['model']} is "
                      f"{BODY_NAMES[src_cls['body']]}; the model plays {hero}'s body animations", file=sys.stderr)
            for p in sorted({f["preset"] for f in fs if f["row"] == dst["row"]}):
                remap.append((p, src["preset"]))
            notes.append(f"{hero} looks like {want['model']} (preset {src['preset']})")
        name_spec = want.get("name", want.get("model"))
        if name_spec and str(name_spec).lower() != "keep":
            src = find_fighter(e, name_spec, fs)
            for p in sorted({f["preset"] for f in fs if f["row"] == dst["row"]}):
                names.append((p, NAME_TEXT_BASE + src["id"]))
            notes.append(f"{hero}'s HP bar says {name_spec}'s name (text {NAME_TEXT_BASE + src['id']})")
        if want.get("moves"):
            src = find_class(e, want["moves"])
            keep = want.get("keep_body", src["body"] != dst["body"])
            desc, ml = moveset_patch(e, dst, src, keep)
            lines += ml
            notes.append(f"{hero} fights as {src['name']}" + (" (keeps its body groups)" if keep else ""))
        if want.get("stats"):
            src = find_fighter(e, want["stats"], fs)
            t = e.fighters()[tid]["addr"]
            hp, rank = e.s16(src["addr"] + 0xC), e.d[e.v2o(src["addr"] + 0x11)]
            lines.append(f"patch=1,EE,1{t + 0xC:07X},extended,{hp & 0xFFFF:08X}")
            lines.append(f"patch=1,EE,0{t + 0x11:07X},extended,{rank:08X}")
            notes.append(f"{hero} starts with {want['stats']}'s HP {hp} and attack rank {rank} (new game)")
    if remap:
        code = preset_hook(ROSTER_CAVE + 0x40)
        table = [w for f, t in remap for w in (f, t)] + [-1, -1]
        for i, w in enumerate(code):
            lines.append(f"patch=1,EE,2{ROSTER_CAVE + 4 * i:07X},extended,{w:08X}")
        for i in range(0, len(table), 2):
            w = (table[i] & 0xFFFF) | ((table[i + 1] & 0xFFFF) << 16)
            lines.append(f"patch=1,EE,2{ROSTER_CAVE + 0x40 + 2 * i:07X},extended,{w:08X}")
        jal = 0x0C000000 | (ROSTER_CAVE >> 2)
        for site in MODEL_HOOK_SITES:
            lines.append(f"patch=1,EE,2{site:07X},extended,{jal:08X}")
    if names:
        code_at, table_at = ROSTER_CAVE + 0x100, ROSTER_CAVE + 0x180
        table = [w for p, t in names for w in (p, t)] + [-1, -1]
        for i, w in enumerate(name_hook(table_at)):
            lines.append(f"patch=1,EE,2{code_at + 4 * i:07X},extended,{w:08X}")
        for i in range(0, len(table), 2):
            w = (table[i] & 0xFFFF) | ((table[i + 1] & 0xFFFF) << 16)
            lines.append(f"patch=1,EE,2{table_at + 2 * i:07X},extended,{w:08X}")
        lines.append(f"patch=1,EE,2{HP_BAR_NAME_SITE:07X},extended,{0x0C000000 | (code_at >> 2):08X}")
    name = cfg.get("name", "Story roster")
    print(f"[{name}]")
    print("author=" + cfg.get("author", "bdkit roster"))
    print("description=" + "; ".join(notes) + ". Built by bdkit roster; turn off other cheats that write these heroes.")
    print("\n".join(lines))


def cmd_moves(a):
    e = Elf(a.elf)
    style = int(a.style, 0)
    moves = style_moves(e, a.cdata, a.lang).get(style)
    if not moves:
        sys.exit(f"style 0x{style:02X} has no move list")
    users = [c["name"] for c in e.classes() if c["style"] == style]
    print(f"style 0x{style:02X} ({', '.join(users) or 'no fighter in the class table'}): {len(moves)} moves")
    for i, (name, cmd) in enumerate(moves):
        print(f"{i:3d}  {name:<34} {cmd}")


def cmd_style_map(a):
    """Markdown reference: styles, fighters, swap compatibility, every move list."""
    e = Elf(a.elf)
    cls = e.classes()
    lists = e.move_lists()
    moves = style_moves(e, a.cdata, a.lang)
    body_ids = {g for v in BODY_GROUPS.values() for g in v}
    users = {}
    for c in cls:
        users.setdefault(c["style"], []).append(c)
    L = []
    w = L.append
    w("# Movesets and fighting styles")
    w("")
    w("Generated by `python tools/bdkit.py style-map ISO/SLUS_211.50 ISO/XAF/CDATA.XAF > docs/movesets.md`. Do not edit by hand; "
      "add notes to README.md instead.")
    w("")
    w("Button legend for the inputs: **P** punch, **K** kick, **G** guard, **A** action button (grab, search, "
      "pick up), arrows are directions relative to the fighter, `/` separates alternatives. "
      "The game's own glyphs are 〆 P, ◎ K, ◇ G, 4 A; a few rare ones (▽, ∫, ★) are left as they are.")
    w("")
    w("## Where this comes from")
    w("")
    w(f"- Fighter rows: class table `0x{CLASS_TABLE:08X}` (`{{body, style, skeleton, groups}}`).")
    w(f"- Move lists: table at `0x{MOVE_LIST_TABLE:08X}`, 8 bytes per style, row = style - 1: "
      "`{u16 first input text, u16 last input text, u16 first name text, u16 last name text}`. "
      "Read by `0x001C5C30` (input text) and `0x001C5C00` (name text), which call the text lookup `0x00387980`.")
    w(f"- Text: CDATA.XAF entry {MOVE_TEXT_ENTRY['en']} (English; JP {MOVE_TEXT_ENTRY['jp']}, FR 399, DE 400, ES 401, "
      "IT 402). Inputs are IDs 0x9C40-0xA0F3, names 0xAFC8-0xB47B, one pair per move.")
    w("- These are the in-game MOVE LIST screens, so the order is the menu order. Which animation each move plays "
      "is not mapped yet (that's the still-missing command table).")
    w("")
    w("## Fighting styles")
    w("")
    w("| Style | Moves | Used by (body) | Move groups | First moves |")
    w("|---|---|---|---|---|")
    for st in sorted(set(lists) | set(users)):
        us = users.get(st, [])
        mv = moves.get(st)
        who = ", ".join(f"{c['name']} ({BODY_NAMES[c['body']]})" for c in us) or "none"
        grp = sorted({g for c in us for g in own_groups(c) if c["name"] != "PERFECT"} or
                     {g for c in us for g in own_groups(c)})
        first = ", ".join(n for n, _ in mv[:4]) if mv else "no move list"
        w(f"| `0x{st:02X}` | {len(mv) if mv else 0} | {who} | {', '.join(map(str, grp)) or '-'} | {first} |")
    w("")
    w("## Fighters")
    w("")
    w("Every fighter also loads the shared groups " + ", ".join(map(str, SHARED_GROUPS)) +
      " and its body groups (S " + ", ".join(map(str, BODY_GROUPS[0])) + "; M " +
      ", ".join(map(str, BODY_GROUPS[1])) + "; L " + ", ".join(map(str, BODY_GROUPS[2])) + ").")
    w("")
    w("| Type | Fighter | Row address | Body | Style | Style groups | Moves |")
    w("|---|---|---|---|---|---|---|")
    for c in cls:
        mv = moves.get(c["style"])
        extra = [g for g in c["groups"] if g in body_ids and g not in BODY_GROUPS[c["body"]]]
        note = f" (also loads body groups {', '.join(map(str, extra))})" if extra else ""
        w(f"| {c['type_id']} | {c['name']} | `0x{c['addr']:08X}` | {BODY_NAMES[c['body']]} | `0x{c['style']:02X}` | "
          f"{', '.join(map(str, own_groups(c))) or '-'}{note} | {len(mv) if mv else 0} |")
    w("")
    w("## Which swaps work")
    w("")
    w("`swap-moveset A B` copies B's style and group list into A's row, so it is clean only when A and B have the "
      "same body size. Across body sizes use `--keep-body`, which keeps A's body groups and swaps only the style "
      "groups (tested for M getting L moves: Aaron with Jason G's moveset).")
    w("")
    for b in (0, 1, 2):
        names = [c["name"] for c in cls if c["body"] == b]
        w(f"- **Body {BODY_NAMES[b]}** ({len(names)}): plain swap among " + ", ".join(names) + ".")
    w("- **Different body sizes**: always add `--keep-body`.")
    w("- `--keep-body` edits A's own group list in place. Each hero has a list of its own; the generic S/M/L rows "
      "have not been checked for shared lists, so look before using one of them as A.")
    w("- **Style 0x09** (TESTER S/M/L) has no entry in the move list table (0xFFFF).")
    w("- **PERFECT** is an M body with style 0x04 (Juggler's moves) whose list loads every generic style group and "
      "all three body groups. As a source it gives only the Juggler moves plus a much bigger load, so use "
      "JUGGLER_M instead.")
    w("- Style 0x0B's list has Pedigree and Canadian Destroyer and 0x12's has Stunner and Belly to Belly, matching "
      "the developers' leftover notes (\"Glegoio\" / \"Jason\" use them), which confirms row = style - 1.")
    w("- **Styles 0x1C-0x23** are short versions (5-9 moves) of the eight generic styles 0x01-0x08, and "
      "**0x25-0x2F** are weapon move lists (bladed, blunt, swinging, large, handgun, katana, shotgun). No fighter "
      "row uses them; they are probably picked at run time (unarmed recruits, weapons in hand).")
    w("")
    w("## Move lists")
    for st in sorted(moves):
        us = users.get(st, [])
        who = ", ".join(c["name"] for c in us) or "no fighter row"
        w("")
        w(f"### Style 0x{st:02X} ({who})")
        w("")
        w("| # | Move | Input |")
        w("|---|---|---|")
        for i, (n, cmd) in enumerate(moves[st]):
            w(f"| {i} | {n.replace('|', '/') or '-'} | {cmd.replace('|', '/')} |")
    print("\n".join(L))


def texture_png(blob):
    """A DATA.XAF texture (asset type 0x18: 40-byte header with width at +0x18 and height at +0x1C, 8-bit pixels,
    then a 256-colour RGBA palette; 4-bit ones store one pixel per byte and have 16 colours) as PNG bytes. The
    256-colour palette is in the PS2's CSM1 order (entries 8-15 and 16-23 of every 32 swapped); alpha 0x80 means
    opaque."""
    import zlib
    w, h, bpp = struct.unpack_from("<III", blob, 0x18)
    n = w * h
    pix = blob[0x28:0x28 + n]
    ncol = 256 if bpp == 8 else 16
    pal = blob[0x28 + n:0x28 + n + 4 * ncol]
    cols = [pal[4 * i:4 * i + 4] for i in range(ncol)]
    if ncol == 256:
        cols = [cols[(i & ~0x18) | ((i & 0x08) << 1) | ((i & 0x10) >> 1)] for i in range(256)]
    pix = bytes(p % ncol for p in pix)
    rows = b"".join(b"\0" + b"".join(bytes(cols[p][:3]) + bytes([min(255, cols[p][3] * 2)]) for p in pix[y * w:(y + 1) * w])
                    for y in range(h))
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))


def cmd_tex(a):
    """Write DATA.XAF textures (the part ids in outfit slots) as PNG files."""
    os.makedirs(a.out, exist_ok=True)
    ents = xaf_entries(a.xaf)
    with open(a.xaf, "rb") as f:
        for i in (int(x, 0) for x in a.index):
            o, size = ents[i][1:3]
            f.seek(o)
            blob = f.read(size)
            if struct.unpack_from("<I", blob)[0] != 0x18:
                print(f"{i}: not a texture ({describe(blob[:16])})")
                continue
            path = os.path.join(a.out, f"{i}.png")
            with open(path, "wb") as g:
                g.write(texture_png(blob))
            w, h = struct.unpack_from("<II", blob, 0x18)
            print(f"{i}: {w}x{h} -> {path}")


def cmd_read(a):
    e = Elf(a.elf)
    v = int(a.addr, 0)
    n = int(a.length, 0)
    o = e.v2o(v)
    for i in range(0, n, 16):
        chunk = e.d[o + i:o + i + min(16, n - i)]
        print(f"{v + i:08X}  {chunk.hex(' ')}")


def cmd_addr(a):
    v = int(a.addr, 0)
    if ELF_LOAD_VADDR <= v < ELF_LOAD_VADDR + ELF_LOAD_FILESZ:
        o = Elf.v2o(v)
        print(f"EE address 0x{v:08X} = ELF offset 0x{o:X} = ISO offset 0x{ELF_ISO_LBA * 2048 + o:X}")
    else:
        print("address is outside the ELF's file data (bss or heap); patch it with a pnach only")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")   # move lists use arrows and the game's button glyphs
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    s = p.add_subparsers(dest="cmd", required=True)
    x = s.add_parser("iso-list"); x.add_argument("iso"); x.set_defaults(fn=cmd_iso_list)
    x = s.add_parser("iso-extract"); x.add_argument("iso"); x.add_argument("out"); x.add_argument("files", nargs="*"); x.set_defaults(fn=cmd_iso_extract)
    x = s.add_parser("xaf-list"); x.add_argument("xaf"); x.set_defaults(fn=cmd_xaf_list)
    x = s.add_parser("xaf-extract"); x.add_argument("xaf"); x.add_argument("out"); x.add_argument("index", nargs="*"); x.set_defaults(fn=cmd_xaf_extract)
    x = s.add_parser("archive-names"); x.add_argument("iso"); x.set_defaults(fn=cmd_archive_names)
    x = s.add_parser("chars"); x.add_argument("elf"); x.set_defaults(fn=cmd_chars)
    x = s.add_parser("groups"); x.add_argument("elf"); x.set_defaults(fn=cmd_groups)
    x = s.add_parser("swap-moveset"); x.add_argument("elf"); x.add_argument("target"); x.add_argument("source")
    x.add_argument("--keep-body", action="store_true", help="keep the target's body groups (needed when body sizes differ)")
    x.set_defaults(fn=cmd_swap_moveset)
    x = s.add_parser("mix-moveset"); x.add_argument("elf"); x.add_argument("target"); x.add_argument("source")
    x.add_argument("--take", required=True, help="input family (" + ", ".join(INPUT_FAMILIES) + ") or hex input codes, comma-separated")
    x.add_argument("--cdata", default=os.path.join("ISO", "XAF", "CDATA.XAF"), help="for the MOVE LIST text (default ISO/XAF/CDATA.XAF)")
    x.set_defaults(fn=cmd_mix_moveset)
    x = s.add_parser("fighters"); x.add_argument("elf"); x.set_defaults(fn=cmd_fighters)
    x = s.add_parser("swap-model"); x.add_argument("elf"); x.add_argument("target"); x.add_argument("source")
    x.add_argument("--preset", help="use this outfit preset instead of the source's most common one")
    x.set_defaults(fn=cmd_swap_model)
    x = s.add_parser("roster"); x.add_argument("elf"); x.add_argument("roster"); x.set_defaults(fn=cmd_roster)
    x = s.add_parser("moves"); x.add_argument("elf"); x.add_argument("cdata"); x.add_argument("style")
    x.add_argument("--lang", default="en", choices=sorted(MOVE_TEXT_ENTRY)); x.set_defaults(fn=cmd_moves)
    x = s.add_parser("style-map"); x.add_argument("elf"); x.add_argument("cdata")
    x.add_argument("--lang", default="en", choices=sorted(MOVE_TEXT_ENTRY)); x.set_defaults(fn=cmd_style_map)
    x = s.add_parser("tex"); x.add_argument("xaf"); x.add_argument("out"); x.add_argument("index", nargs="+"); x.set_defaults(fn=cmd_tex)
    x = s.add_parser("read"); x.add_argument("elf"); x.add_argument("addr"); x.add_argument("length", nargs="?", default="64"); x.set_defaults(fn=cmd_read)
    x = s.add_parser("addr"); x.add_argument("addr"); x.set_defaults(fn=cmd_addr)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
