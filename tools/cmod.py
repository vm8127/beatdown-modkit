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
  @org ADDR              where the code goes (required; a free range from docs/MEMORY-MAP.md)
  @max SIZE              fail if code + constants grow past SIZE bytes (default 0x100)
  @jal SITE FUNC         SITE holds a `jal`; make it `jal FUNC` instead (FUNC gets the same arguments)
  @jump SITE FUNC        overwrite the instruction at SITE with `j FUNC` and the next one with `nop`
                         (replaces a whole game function when SITE is its first instruction)
  @ptr SITE FUNC         write FUNC's address at SITE (function pointer tables)
  @word SITE VALUE       write a 32-bit VALUE at SITE (table entries)

Rules the build enforces:
  - No writable globals (.data/.bss): cheats are rewritten every frame, so they would reset.
    Keep state in game memory. Constants (.rodata, strings) are fine.
  - The game's code saves s0-s7 as 128-bit values, this compiler only 64 bits, so mods never use
    s0-s7 or fp (-ffixed-...). Leaf code and calls work normally.

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

CFLAGS = ["-O2", "-G0", "-mno-abicalls", "-fno-pic", "-mno-gpopt", "-ffreestanding", "-fno-builtin",
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


def parse_directives(src):
    d = dict(section=None, description="", org=None, max=0x100, patches=[])
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
            elif key in ("jal", "jump", "ptr"):
                d["patches"].append((key, num(args[0]), args[1]))
            elif key == "word":
                d["patches"].append((key, num(args[0]), num(args[1])))
            else:
                sys.exit(f"line {ln}: unknown directive @{key}")
        except (IndexError, ValueError):
            sys.exit(f"line {ln}: bad @{key} line: {line.strip()}")
    if not d["section"] or d["org"] is None:
        sys.exit("the C file needs // @section and // @org lines")
    return d


def symbol_lines():
    """Linker script lines defining every symbols.tsv name at its game address."""
    seen = set()
    out = []
    with open(SYMBOLS, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 3 or not NAME_RE.match(cols[2]) or cols[2] in seen:
                continue
            seen.add(cols[2])
            out.append(f"{cols[2]} = 0x{int(cols[0], 16):08X};")
    return "\n".join(out)


def link_script(path, org):
    with open(path, "w") as f:
        f.write(symbol_lines() + f"""
SECTIONS
{{
  . = 0x{org:08X};
  .text : {{ *(.text .text.*) }}
  .rodata : {{ *(.rodata .rodata.* .rodata1) }}
  .data : {{ *(.data .data.* .sdata .sdata.*) }}
  .bss : {{ *(.bss .bss.* .sbss .sbss.* COMMON) }}
  /DISCARD/ : {{ *(.MIPS.abiflags .MIPS.options .reginfo .comment .pdr .gnu.attributes .mdebug.* .note.*) }}
}}
""")


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
    with tempfile.TemporaryDirectory() as tmp:
        obj, out, binf = (os.path.join(tmp, n) for n in ("mod.o", "mod.elf", "mod.bin"))
        lds = os.path.join(tmp, "mod.ld")
        link_script(lds, d["org"])
        run([tool("gcc")] + CFLAGS + ["-I", INCLUDE, "-c", c_path, "-o", obj])
        run([tool("ld"), "-e", "0", "-T", lds, "-o", out, obj])
        secs = elf_sections(out)
        for s in (".data", ".bss"):
            if secs.get(s, (0, 0))[1]:
                sys.exit(f"the mod has writable globals ({s}, {secs[s][1]} bytes); cheats are rewritten every "
                         "frame, so keep state in game memory or make tables const")
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
    for k, site, _ in d["patches"]:
        if d["org"] <= site < end:
            sys.exit(f"@{k} {site:#010x} is inside the mod's own code")
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
    lines = [f"[{d['section']}]", f"author={AUTHOR}"]
    if d["description"]:
        lines.append(f"description={d['description']}")
    lines += [f"patch=1,EE,{0x20000000 | (a & 0x0FFFFFFF):08X},extended,{v:08X}" for a, v in writes]
    info = [f"code {d['org']:#010x}-{end - 1:#010x} ({len(code)} bytes, @max {d['max']:#x})"] + notes
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
