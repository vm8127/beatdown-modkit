#!/usr/bin/env python3
"""Build Beat Down (SLUS-21150) mods written in C into PCSX2 cheat sections.

The C file is compiled with the ps2dev PS2 compiler for a fixed address in a free code cave
(docs/MEMORY-MAP.md), linked against every name in symbols/symbols.tsv, and turned into
`patch=1,EE,...` lines: the code itself plus the hooks that make the game call it.

  python tools/cmod.py build ISO/SLUS_211.50 mods/c/aaron_chester_model.c          # prints a pnach section
  python tools/cmod.py build ISO/SLUS_211.50 mods/c/aaron_chester_model.c --asm    # also the disassembly
  python tools/cmod.py install ISO/SLUS_211.50 mods/c/aaron_chester_model.c        # adds/replaces the section
                                                                                  # in mods/ and the PCSX2 copy

Directives, in `// @name args` comment lines anywhere in the C file:
  @section NAME          pnach section name (required)
  @description TEXT      pnach description line
  @org ADDR              where the code goes (required; a free range from docs/MEMORY-MAP.md: small mods in
                         the C mod cave 0x00216738-0x00216FFF, big ones in the mod area 0x000A0000-0x000DFFFF)
  @max SIZE              fail if code + constants grow past SIZE bytes (default 0x100)
  @bss ADDR SIZE         where the mod's writable globals go (mod data area 0x000E0000-0x000EFFFF). They
                         start at zero when the game boots, are never written by the cheat, and are saved
                         in save states. Without @bss the mod may not have writable globals.
  @hook FUNC MYFUNC      make every call to game function FUNC (a name from symbols.tsv or an address) run
                         MYFUNC instead; MYFUNC can call the original as orig_FUNC (orig_0013B490 for an
                         address), which runs FUNC's first two instructions and continues at FUNC+8
  @jal SITE FUNC         SITE holds a `jal`; make it `jal FUNC` instead (FUNC gets the same arguments)
  @jump SITE FUNC        overwrite the instruction at SITE with `j FUNC` and the next one with `nop`
                         (replaces a whole game function when SITE is its first instruction; SITE may be a
                         symbols.tsv name for @jal, @jump, @ptr and @word too)
  @ptr SITE FUNC         write FUNC's address at SITE (function pointer tables)
  @word SITE VALUE       write a 32-bit VALUE at SITE (table entries)

Rules the build enforces:
  - No initialized writable globals (.data): the cheat rewrites the code every frame, so it can't own
    data that changes. Use const tables, or zero-initialized globals with @bss.
  - The game's code saves s0-s7 as 128-bit values, this compiler only 64 bits, so mods never use
    s0-s7 or fp (-ffixed-...). Leaf code, calls and hooks work normally.
  - Calls use the game's convention (EABI with 32-bit long and pointers): int and pointer arguments in
    a0-a7, float arguments in f12-f19, counted separately, so floats can be passed and returned.

The toolchain is __external_tools/ps2dev (README.md, "External tools"); set CMOD_TOOLCHAIN to the
folder holding mips64r5900el-ps2-elf-gcc to use another one.
"""
import argparse
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import bdkit  # noqa: E402

PREFIX = "mips64r5900el-ps2-elf-"
TOOLCHAIN = os.environ.get("CMOD_TOOLCHAIN", os.path.join(ROOT, "__external_tools", "ps2dev", "ee", "bin"))
SYMBOLS = os.path.join(ROOT, "symbols", "symbols.tsv")
INCLUDE = os.path.join(HERE, "cmod")
PNACH = os.path.join(ROOT, "mods", "SLUS-21150_C9F6EF9A.pnach")
PCSX2_PNACH = r"C:\Games\Emu\PCSX2\cheats\SLUS-21150_C9F6EF9A.pnach"
AUTHOR = "Claude for Daniel"

CFLAGS = ["-O2", "-G0", "-mabi=eabi", "-mlong32", "-mno-abicalls", "-fno-pic", "-mno-gpopt", "-ffreestanding", "-fno-builtin",
          "-fno-common", "-fno-toplevel-reorder", "-fno-asynchronous-unwind-tables", "-fno-unwind-tables",
          "-Wall", "-Werror=implicit-function-declaration"] + \
         [f"-ffixed-s{i}" for i in range(8)] + ["-ffixed-fp"]
NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def tool(name):
    exe = os.path.join(TOOLCHAIN, PREFIX + name + (".exe" if os.name == "nt" else ""))
    if not os.path.exists(exe):
        sys.exit(f"{exe} not found: install ps2dev into __external_tools (README.md, \"External tools\")")
    return exe


def run(args):
    p = subprocess.run(args, capture_output=True, text=True)
    if p.returncode:
        sys.exit((p.stderr or p.stdout).strip() or f"{os.path.basename(args[0])} failed ({p.returncode:#x})")
    return p.stdout


def num(s):
    return int(s, 0)


def site(s):
    """A patch site: a number, or a name from symbols.tsv (resolved by the build)."""
    try:
        return int(s, 0)
    except ValueError:
        if not NAME_RE.match(s):
            raise
        return s


def parse_directives(src):
    d = dict(section=None, description="", org=None, max=0x100, bss=None, patches=[], hooks=[])
    for ln, line in enumerate(src.splitlines(), 1):
        m = re.match(r"\s*//\s*@(\w+)\s*(.*?)\s*$", line)
        if not m:
            continue
        key, rest = m.group(1), m.group(2)
        args = rest.split()
        try:
            if key in ("section", "description"):
                d[key] = rest
            elif key in ("org", "max"):
                d[key] = num(args[0])
            elif key == "bss":
                d["bss"] = (num(args[0]), num(args[1]))
            elif key == "hook":
                d["hooks"].append((args[0], args[1]))
            elif key in ("jal", "jump", "ptr"):
                d["patches"].append((key, site(args[0]), args[1]))
            elif key == "word":
                d["patches"].append((key, site(args[0]), num(args[1])))
            else:
                sys.exit(f"line {ln}: unknown directive @{key}")
        except (IndexError, ValueError):
            sys.exit(f"line {ln}: bad @{key} line: {line.strip()}")
    if not d["section"] or d["org"] is None:
        sys.exit("the C file needs // @section and // @org lines")
    return d


def game_symbols():
    """{name: address} of every symbols.tsv name (the first one wins)."""
    out = {}
    with open(SYMBOLS, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            cols = line.rstrip("\n").split("\t")
            if len(cols) >= 3 and NAME_RE.match(cols[2]) and cols[2] not in out:
                out[cols[2]] = int(cols[0], 16)
    return out


def link_script(path, org, bss):
    syms = "\n".join(f"{n} = 0x{a:08X};" for n, a in game_symbols().items())
    bss_at = f"0x{bss[0]:08X} (NOLOAD)" if bss else ""
    with open(path, "w") as f:
        f.write(syms + f"""
SECTIONS
{{
  . = 0x{org:08X};
  .text : {{ *(.text .text.*) }}
  .rodata : {{ *(.rodata .rodata.* .rodata1) }}
  .data : {{ *(.data .data.* .sdata .sdata.*) }}
  .bss {bss_at} : {{ *(.bss .bss.* .sbss .sbss.* COMMON) }}
  /DISCARD/ : {{ *(.MIPS.abiflags .MIPS.options .reginfo .comment .pdr .gnu.attributes .mdebug.* .note.*) }}
}}
""")


BRANCH_OPS = (0x01, 0x04, 0x05, 0x06, 0x07, 0x14, 0x15, 0x16, 0x17)


def is_cop_branch(w):
    return w >> 26 in (0x10, 0x11, 0x12) and (w >> 21) & 0x1F == 0x08


def is_control_transfer(w):
    """True for jumps, branches and anything else that can't run at another address."""
    op = w >> 26
    if op == 0:
        return (w & 0x3F) in (0x08, 0x09, 0x0C, 0x0D)  # jr, jalr, syscall, break
    return op in (0x02, 0x03) + BRANCH_OPS or is_cop_branch(w) or (op == 0x10 and (w & 0x3F) == 0x18)  # eret


def branch_target(pc, w):
    op = w >> 26
    if op in (0x02, 0x03):
        return (pc + 4) & 0xF0000000 | (w & 0x03FFFFFF) << 2
    if op in BRANCH_OPS or is_cop_branch(w):
        off = w & 0xFFFF
        return pc + 4 + ((off - 0x10000 if off & 0x8000 else off) << 2)
    return None


def hook_trampolines(game, hooks, syms):
    """Assembly for the orig_FUNC trampolines, and the entry patches, for every @hook."""
    asm = [".set noreorder", ".section .text.zhooks,\"ax\""]
    patches = []
    lo, hi = bdkit.Elf.o2v(bdkit.ELF_LOAD_OFFSET), bdkit.Elf.o2v(len(game.d))
    for func, mine in hooks:
        site = syms[func] if func in syms else num(func)
        name = "orig_" + (func if func in syms else f"{site:08X}")
        w0, w1 = game.u32(site), game.u32(site + 4)
        if any(is_control_transfer(w) for w in (w0, w1)):
            sys.exit(f"@hook {func}: the first two instructions ({w0:08X} {w1:08X}) include a jump or "
                     "branch, so they can't be moved; hook a call site with @jal instead")
        for pc in range(max(lo, site - 0x20000), min(hi, site + 0x20000), 4):
            if branch_target(pc, game.u32(pc)) == site + 4:
                sys.exit(f"@hook {func}: {pc:#010x} branches to {site + 4:#010x}, the second instruction, "
                         "which the hook overwrites; hook a call site with @jal instead")
        back = 0x08000000 | ((site + 8) >> 2) & 0x03FFFFFF
        asm += [f".globl {name}", f".type {name},@function", f"{name}:",
                f".word 0x{w0:08X}", f".word 0x{w1:08X}", f".word 0x{back:08X}", "nop",
                f".size {name}, .-{name}"]
        patches.append((site, mine, name, w0, w1))
    return "\n".join(asm) + "\n", patches


def elf_sections(path):
    """{name: (addr, size)} of an ELF32 little-endian file."""
    d = open(path, "rb").read()
    shoff, = struct.unpack_from("<I", d, 0x20)
    shentsize, shnum, shstrndx = struct.unpack_from("<HHH", d, 0x2E)
    hdrs = [struct.unpack_from("<10I", d, shoff + i * shentsize) for i in range(shnum)]
    stroff = hdrs[shstrndx][4]
    out = {}
    for h in hdrs:
        name = d[stroff + h[0]:d.index(b"\0", stroff + h[0])].decode()
        out[name] = (h[3], h[5])
    return out


def build(elf_path, c_path, asm=False):
    src = open(c_path, encoding="utf-8").read()
    d = parse_directives(src)
    game = bdkit.Elf(elf_path)
    hook_asm, hook_patches = hook_trampolines(game, d["hooks"], game_symbols())
    with tempfile.TemporaryDirectory() as tmp:
        obj, hobj, out, binf = (os.path.join(tmp, n) for n in ("mod.o", "hooks.o", "mod.elf", "mod.bin"))
        lds, hsrc = os.path.join(tmp, "mod.ld"), os.path.join(tmp, "hooks.s")
        link_script(lds, d["org"], d["bss"])
        with open(hsrc, "w") as f:
            f.write(hook_asm)
        run([tool("gcc")] + CFLAGS + ["-I", INCLUDE, "-c", c_path, "-o", obj])
        run([tool("gcc")] + CFLAGS + ["-c", hsrc, "-o", hobj])
        run([tool("ld"), "-m", "elf32lr5900", "-e", "0", "-T", lds, "-o", out, obj, hobj])
        secs = elf_sections(out)
        if secs.get(".data", (0, 0))[1]:
            sys.exit(f"the mod has initialized writable globals (.data, {secs['.data'][1]} bytes); make them "
                     "const, or zero-initialized with @bss")
        bss_size = secs.get(".bss", (0, 0))[1]
        if bss_size and not d["bss"]:
            sys.exit(f"the mod has writable globals ({bss_size} bytes of .bss) but no @bss line saying where "
                     "they go (docs/MEMORY-MAP.md, mod data area)")
        if d["bss"] and bss_size > d["bss"][1]:
            sys.exit(f"writable globals are {bss_size} bytes, over the @bss size {d['bss'][1]:#x}")
        run([tool("objcopy"), "-O", "binary", "-j", ".text", "-j", ".rodata", out, binf])
        code = open(binf, "rb").read()
        code += b"\0" * (-len(code) % 4)
        if len(code) > d["max"]:
            sys.exit(f"code is {len(code)} bytes, over @max {d['max']:#x}")
        addrs = {}
        for line in run([tool("nm"), out]).splitlines():
            parts = line.split()
            if len(parts) == 3:
                addrs[parts[2]] = int(parts[0], 16)
        listing = run([tool("objdump"), "-d", out]) if asm else ""

    def addr_of(name):
        if name not in addrs:
            sys.exit(f"{name} is not defined by the mod or symbols.tsv")
        return addrs[name]

    end = d["org"] + len(code)
    gsyms = game_symbols()
    for i, (k, st, a) in enumerate(d["patches"]):
        if isinstance(st, str):
            if st not in gsyms:
                sys.exit(f"@{k} {st}: not a name in symbols.tsv")
            d["patches"][i] = (k, gsyms[st], a)
    for k, site, _ in d["patches"]:
        if d["org"] <= site < end:
            sys.exit(f"@{k} {site:#010x} is inside the mod's own code")
    if d["bss"] and d["bss"][0] < end and d["org"] < d["bss"][0] + d["bss"][1]:
        sys.exit("@bss overlaps the mod's code")
    writes = [(d["org"] + i, struct.unpack_from("<I", code, i)[0]) for i in range(0, len(code), 4)]
    notes = []
    for kind, site, arg in d["patches"]:
        if kind == "word":
            writes.append((site, arg))
            continue
        target = addr_of(arg)
        old = game.u32(site)
        if kind == "jal":
            if old >> 26 != 3:
                sys.exit(f"@jal {site:#010x}: the game has {old:08X} there, not a jal")
            writes.append((site, 0x0C000000 | (target >> 2) & 0x03FFFFFF))
            notes.append(f"{site:#010x} jal {(old & 0x03FFFFFF) << 2:#010x} -> jal {arg} {target:#010x}")
        elif kind == "jump":
            writes += [(site, 0x08000000 | (target >> 2) & 0x03FFFFFF), (site + 4, 0)]
            notes.append(f"{site:#010x} -> j {arg} {target:#010x} (overwrites {old:08X} {game.u32(site + 4):08X})")
        elif kind == "ptr":
            writes.append((site, target))
            notes.append(f"{site:#010x} {old:08X} -> {arg} {target:#010x}")
    for site, mine, orig, w0, w1 in hook_patches:
        target = addr_of(mine)
        writes += [(site, 0x08000000 | (target >> 2) & 0x03FFFFFF), (site + 4, 0)]
        notes.append(f"{site:#010x} hooked: j {mine} {target:#010x}; {orig} {addr_of(orig):#010x} runs "
                     f"{w0:08X} {w1:08X}, then back to {site + 8:#010x}")
    lines = [f"[{d['section']}]", f"author={AUTHOR}"]
    if d["description"]:
        lines.append(f"description={d['description']}")
    lines += [f"patch=1,EE,{0x20000000 | (a & 0x0FFFFFFF):08X},extended,{v:08X}" for a, v in writes]
    info = [f"code {d['org']:#010x}-{end - 1:#010x} ({len(code)} bytes, @max {d['max']:#x})"]
    if d["bss"]:
        info.append(f"globals at {d['bss'][0]:#010x}: {bss_size} bytes of @bss size {d['bss'][1]:#x} "
                    "(not written by the cheat)")
    info += notes
    funcs = sorted((a, n) for n, a in addrs.items() if d["org"] <= a < end)
    info += [f"  {a:#010x} {n}" for a, n in funcs]
    return d["section"], "\n".join(lines) + "\n", info, listing


def install(section, text, paths):
    """Replace the section with this name (or append it) in each pnach file, backing up first."""
    for path in paths:
        if not os.path.exists(path):
            print(f"skipped {path}: not found", file=sys.stderr)
            continue
        old = open(path, encoding="utf-8").read()
        shutil.copy2(path, path + ".bak")
        blocks = re.split(r"(?m)^(?=\[)", old)
        head = f"[{section}]"
        new_blocks, done = [], False
        for b in blocks:
            if b.startswith(head + "\n") or b.startswith(head + "\r\n"):
                new_blocks.append(text + "\n")
                done = True
            else:
                new_blocks.append(b)
        if not done:
            if not new_blocks[-1].endswith("\n\n"):
                new_blocks[-1] = new_blocks[-1].rstrip("\n") + "\n\n"
            new_blocks.append(text)
        new = "".join(new_blocks)
        new = new.rstrip("\n") + "\n"
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(new)
        print(f"{'replaced' if done else 'added'} [{section}] in {path} (backup {path}.bak)", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("build", "install"):
        p = sub.add_parser(name)
        p.add_argument("elf", help="ISO/SLUS_211.50, to check the hook sites")
        p.add_argument("c_file")
        p.add_argument("--asm", action="store_true", help="print the disassembly of the mod")
    a = ap.parse_args()
    section, text, info, listing = build(a.elf, a.c_file, a.asm)
    for i in info:
        print(i, file=sys.stderr)
    if listing:
        print(listing, file=sys.stderr)
    if a.cmd == "build":
        sys.stdout.write(text)
    else:
        install(section, text, [PNACH, PCSX2_PNACH])


if __name__ == "__main__":
    main()
