#!/usr/bin/env python3
"""Beat Down: Fists of Vengeance (USA, SLUS-21150) modding kit.

Pure Python 3 standard library. Works on Windows, macOS and Linux.

Usage examples (run `python bdkit.py -h` for the full list):
  python bdkit.py iso-list  BeatDown.iso
  python bdkit.py iso-extract BeatDown.iso out_dir            # every file on the disc
  python bdkit.py iso-extract BeatDown.iso out_dir XAF/STAGE.XAF SLUS_211.50
  python bdkit.py xaf-list  STAGE.XAF
  python bdkit.py xaf-extract STAGE.XAF out_dir [index ...]
  python bdkit.py archive-names BeatDown.iso                 # outfit part names in ARCHIVE.XAF
  python bdkit.py chars     SLUS_211.50                      # character class table
  python bdkit.py groups    SLUS_211.50                      # animation groups
  python bdkit.py swap-moveset SLUS_211.50 AARON RAVEN       # prints a pnach section
  python bdkit.py swap-moveset SLUS_211.50 AARON JASON_G --keep-body   # for different body sizes
  python bdkit.py fighters  SLUS_211.50                      # fighter records: outfit preset (model) + class row
  python bdkit.py swap-model SLUS_211.50 AARON CHESTER       # prints a pnach section (model only, keeps the name)
  python bdkit.py moves     SLUS_211.50 CDATA.XAF 0x13           # move list (names + inputs) of a style
  python bdkit.py style-map SLUS_211.50 CDATA.XAF > movesets.md  # styles, fighters, swaps, move lists
  python bdkit.py read      SLUS_211.50 0x50D8B0 16          # hex dump at a game address
  python bdkit.py addr      0x50D8B0                         # address <-> ELF/ISO offsets

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


def cmd_swap_moveset(a):
    e = Elf(a.elf)
    dst, src = find_class(e, a.target), find_class(e, a.source)
    if a.keep_body:
        return swap_keep_body(e, dst, src)
    if dst["skeleton"] != src["skeleton"]:
        print(f"; WARNING: {dst['name']} and {src['name']} use different skeletons; animations may break. "
              f"Use --keep-body instead.", file=sys.stderr)
    print(f"[{dst['name'].title()} uses {src['name'].title()}'s moveset]")
    print(f"description=Style 0x{src['style']:02X} and anim groups of {src['name']} on {dst['name']}")
    print(f"patch=1,EE,2{dst['addr'] + 4:07X},extended,{src['style']:08X}")
    print(f"patch=1,EE,2{dst['addr'] + 12:07X},extended,{src['groups_ptr']:08X}")


def swap_keep_body(e, dst, src):
    """Give dst src's style while dst keeps its own body groups.

    Edits dst's own group list in place: its move-set group is replaced by src's, and src's other
    style groups are appended (into the zero padding after the 9999 terminator). Style move groups
    are body-size independent (BOXER S/M/L all load group 166), so this avoids loading body
    animations for the wrong skeleton.
    """
    d_own, s_own = own_groups(dst), own_groups(src)
    if not d_own or not s_own:
        sys.exit("one of the fighters has no style groups of its own")
    new = [s_own[0] if g == d_own[0] else g for g in dst["groups"]]
    new += [g for g in s_own[1:] if g not in new]
    ptr = dst["groups_ptr"]
    old = dst["groups"]
    room = len(old) + 1
    while e.u32(ptr + 4 * room) == 0:
        room += 1
    if len(new) + 1 > room:
        sys.exit(f"new list needs {len(new) + 1} words but only {room} fit at 0x{ptr:08X}")
    print(f"[{dst['name'].title()} uses {src['name'].title()}'s moveset]")
    print(f"description=Style 0x{src['style']:02X} of {src['name']} on {dst['name']}; keeps "
          f"{dst['name']}'s body groups. List at 0x{ptr:08X} becomes {new}")
    print(f"patch=1,EE,2{dst['addr'] + 4:07X},extended,{src['style']:08X}")
    print(f"patch=1,EE,2{dst['addr'] + 12:07X},extended,{ptr:08X}")
    words = new + [GROUP_LIST_END]
    for i, w in enumerate(words):
        cur = e.u32(ptr + 4 * i)
        if cur != w:
            print(f"patch=1,EE,2{ptr + 4 * i:07X},extended,{w:08X}")


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
    w("Generated by `python bdkit.py style-map SLUS_211.50 CDATA.XAF > movesets.md`. Do not edit by hand; "
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
    x = s.add_parser("fighters"); x.add_argument("elf"); x.set_defaults(fn=cmd_fighters)
    x = s.add_parser("swap-model"); x.add_argument("elf"); x.add_argument("target"); x.add_argument("source")
    x.add_argument("--preset", help="use this outfit preset instead of the source's most common one")
    x.set_defaults(fn=cmd_swap_model)
    x = s.add_parser("moves"); x.add_argument("elf"); x.add_argument("cdata"); x.add_argument("style")
    x.add_argument("--lang", default="en", choices=sorted(MOVE_TEXT_ENTRY)); x.set_defaults(fn=cmd_moves)
    x = s.add_parser("style-map"); x.add_argument("elf"); x.add_argument("cdata")
    x.add_argument("--lang", default="en", choices=sorted(MOVE_TEXT_ENTRY)); x.set_defaults(fn=cmd_style_map)
    x = s.add_parser("read"); x.add_argument("elf"); x.add_argument("addr"); x.add_argument("length", nargs="?", default="64"); x.set_defaults(fn=cmd_read)
    x = s.add_parser("addr"); x.add_argument("addr"); x.set_defaults(fn=cmd_addr)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
