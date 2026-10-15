#!/usr/bin/env python3
"""Drive a sandbox copy of PCSX2 for testing Beat Down mods, and read RAM out of save states.

The sandbox is a copy of the user's portable PCSX2 in __external_tools/pcsx2-sandbox (gitignored), with PINE
(memory access over a local socket) on, cheats on, pad 1 on the keyboard and pad 2 plugged in, so testing never
touches the user's own settings, memory cards or save states. Windows only for the window commands; the RAM and
trace-map commands work anywhere. Python 3 standard library only.

  python tools/pcsx2.py setup                       # create or refresh the sandbox (copies BIOS, memory card, states)
  python tools/pcsx2.py cheats "Section A" "B"      # copy mods/*.pnach into the sandbox and turn on these sections
  python tools/pcsx2.py cheats --c tools/debug/teleport.c   # ... plus C cheats built on the fly (sandbox only)
  python tools/pcsx2.py start [--state 1]           # boot the game (and load save state slot 1)
  python tools/pcsx2.py ram128 on|off               # PCSX2's 128 MB "Extended RAM (Dev Console)" for this game only;
                                                    # 32 MB save states don't load while it is on (docs/MEMORY-MAP.md)
  python tools/pcsx2.py stop
  python tools/pcsx2.py status                      # PINE: running / paused / shut down, and the game id
  python tools/pcsx2.py r32 0x006D3F8C [count]      # read words (also r8, r16); w32 / w16 / w8 ADDR VALUE write
  python tools/pcsx2.py dump 0x006CFB70 0x4730 out.bin
  python tools/pcsx2.py flag 0x5F6 0x1F41 [--set | --clear]   # story flags (g_EventFlags), read or change
  python tools/pcsx2.py keys "cross down*3 start:500 wait:1000 l2+r2"
  python tools/pcsx2.py shot out.png [scale]        # screenshot of the game window (scale 2 = half size)
  python tools/pcsx2.py save 1 | load 1             # save state slots (sandbox copies, never the user's)
  python tools/pcsx2.py show Fighter g_Fighters     # a struct's known fields (symbols/structs.tsv), live
  python tools/pcsx2.py show Person 0x0060D360 --state STATE.p2s   # ... or from a save state
  python tools/pcsx2.py ram STATE.p2s out.bin       # EE RAM (32 MB) out of any save state, no emulator needed
  python tools/pcsx2.py freeram [STATE.p2s ...]     # zero regions in save states; checks the mod areas
  python tools/pcsx2.py trace build                 # function coverage: write the trace cheat (then start)
  python tools/pcsx2.py trace clear | read          # forget / list the game functions that ran since `clear`

Keys: cross circle square triangle start select l1 l2 r1 r2 l3 r3 up down left right, and lup ldown lleft
lright (left stick). "a+b" presses together, "*n" repeats, ":ms" holds, "wait:ms" pauses. They are posted to
the sandbox window, so they work while it's in the background and never go to another program.

Function trace: every game function from decomp/index.tsv (0x00170000-0x0040D880 by default; --lo/--hi) gets
its first two instructions moved into a stub that stores its return address in a table, then continues.
`trace build` writes this as the cheat section "[Trace: function coverage]" into the sandbox's copy of the pnach
(the repo's file is not touched) and turns it on; restart the game for it to apply. `trace clear` zeroes the
table, `trace read` prints every function that ran since, with its last caller. Stubs and table use the
debug-only high RAM area 0x01F00000-0x01FBFFFF (docs/MEMORY-MAP.md).
"""
import argparse
import configparser
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import time
import zipfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

SOURCE = r"C:\Games\Emu\PCSX2"
SANDBOX = os.path.join(ROOT, "__external_tools", "pcsx2-sandbox")
EXE = "pcsx2-qtx64-avx2.exe"
ISO = os.path.join(ROOT, "disc", "Beat Down - Fists of Vengeance (USA).iso")
PNACH_NAME = "SLUS-21150_C9F6EF9A.pnach"
GAME_INI = "SLUS-21150_C9F6EF9A.ini"
STATE_PREFIX = "SLUS-21150 (C9F6EF9A)"
PINE_PORT = 28011
# Folders not copied into the sandbox: big, or the user's own data (states and cards are copied selectively).
SKIP = {"isos", "sstates", "memcards", "snaps", "videos", "cache", "covers", "textures", "logs", "bios"}
PAD1 = {"Up": "Up", "Right": "Right", "Down": "Down", "Left": "Left", "Triangle": "I", "Circle": "L",
        "Cross": "K", "Square": "J", "Select": "Backspace", "Start": "Return", "L1": "Q", "L2": "Z", "R1": "E",
        "R2": "C", "L3": "X", "R3": "V", "LUp": "W", "LRight": "D", "LDown": "S", "LLeft": "A", "RUp": "T",
        "RRight": "H", "RDown": "G", "RLeft": "F"}
BUTTON_KEYS = {k.lower(): v for k, v in PAD1.items()}

# Memory areas (docs/MEMORY-MAP.md)
MOD_AREA = (0x000A0000, 0x000DFFFF)
MOD_DATA = (0x000E0000, 0x000EFFFF)
DEBUG_LOW = (0x000F0000, 0x000FFFFF)
DEBUG_HIGH = (0x01F00000, 0x01FBFFFF)
TRACE_BASE = DEBUG_HIGH[0]
TRACE_SECTION = "Trace: function coverage"


# ---------------------------------------------------------------- sandbox files

def ini_set(path, settings):
    """Set {(section, key): value} in an INI file, keeping everything else as it is."""
    lines = open(path, encoding="utf-8").read().split("\n") if os.path.exists(path) else []
    for (sec, key), val in settings.items():
        head = f"[{sec}]"
        if head not in [ln.strip() for ln in lines]:
            lines += ["", head]
        start = [ln.strip() for ln in lines].index(head) + 1
        end = start
        while end < len(lines) and not lines[end].strip().startswith("["):
            end += 1
        for i in range(start, end):
            if lines[i].split("=")[0].strip() == key:
                lines[i] = f"{key} = {val}"
                break
        else:
            at = end
            while at > start and not lines[at - 1].strip():
                at -= 1
            lines.insert(at, f"{key} = {val}")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))


def ini_section(path, sec, body_lines):
    """Replace a whole INI section (used for the repeated `Enable = ...` lines of [Cheats])."""
    lines = open(path, encoding="utf-8").read().split("\n") if os.path.exists(path) else []
    strip = [ln.strip() for ln in lines]
    head = f"[{sec}]"
    if head in strip:
        start = strip.index(head)
        end = start + 1
        while end < len(lines) and not lines[end].strip().startswith("["):
            end += 1
        lines[start:end] = [head] + body_lines + [""]
    else:
        lines += ["", head] + body_lines
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))


def cmd_setup(a):
    if not os.path.isdir(SOURCE):
        sys.exit(f"{SOURCE} not found")
    os.makedirs(SANDBOX, exist_ok=True)
    for name in os.listdir(SOURCE):
        src, dst = os.path.join(SOURCE, name), os.path.join(SANDBOX, name)
        if name.lower() in SKIP:
            continue
        if os.path.isdir(src):
            if not os.path.exists(dst) or a.refresh:
                shutil.copytree(src, dst, dirs_exist_ok=True)
        elif not os.path.exists(dst) or a.refresh:
            shutil.copy2(src, dst)
    user_ini = configparser.ConfigParser(strict=False, interpolation=None)
    user_ini.read(os.path.join(SOURCE, "inis", "PCSX2.ini"), encoding="utf-8")
    bios = user_ini.get("Filenames", "BIOS", fallback="")
    card = user_ini.get("MemoryCards", "Slot1_Filename", fallback="")
    os.makedirs(os.path.join(SANDBOX, "bios"), exist_ok=True)
    for ext in (".bin", ".mec", ".nvm"):
        src = os.path.join(SOURCE, "bios", os.path.splitext(bios)[0] + ext)
        if bios and os.path.exists(src):
            shutil.copy2(src, os.path.join(SANDBOX, "bios", os.path.basename(src)))
    os.makedirs(os.path.join(SANDBOX, "memcards"), exist_ok=True)
    if card and os.path.exists(os.path.join(SOURCE, "memcards", card)):
        dst = os.path.join(SANDBOX, "memcards", card)
        if not os.path.exists(dst) or a.refresh:
            shutil.copy2(os.path.join(SOURCE, "memcards", card), dst)
    os.makedirs(os.path.join(SANDBOX, "sstates"), exist_ok=True)
    for name in os.listdir(os.path.join(SOURCE, "sstates")):
        if name.startswith(STATE_PREFIX) and name.endswith(".p2s"):
            dst = os.path.join(SANDBOX, "sstates", name)
            if not os.path.exists(dst) or a.refresh:
                shutil.copy2(os.path.join(SOURCE, "sstates", name), dst)
    settings = {("UI", "ConfirmShutdown"): "false", ("UI", "StartFullscreen"): "false",
                ("EmuCore", "EnableCheats"): "true", ("EmuCore", "EnablePINE"): "true",
                ("EmuCore", "PINESlot"): str(PINE_PORT), ("EmuCore", "SaveStateOnShutdown"): "false",
                ("Pad1", "Type"): "DualShock2", ("Pad2", "Type"): "DualShock2"}
    settings.update({("Pad1", k): f"Keyboard/{v}" for k, v in PAD1.items()})
    ini_set(os.path.join(SANDBOX, "inis", "PCSX2.ini"), settings)
    # Analog sticks and rumble bound to the user's controller would still be read; drop pad 1's SDL bindings.
    path = os.path.join(SANDBOX, "inis", "PCSX2.ini")
    lines = open(path, encoding="utf-8").read().split("\n")
    out, sec = [], None
    for ln in lines:
        if ln.strip().startswith("["):
            sec = ln.strip()
        if sec == "[Pad1]" and "= SDL-" in ln:
            continue
        out.append(ln)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out))
    print(f"sandbox ready: {SANDBOX}\n  BIOS {bios}, memory card {card or '(none)'}, "
          f"{len([n for n in os.listdir(os.path.join(SANDBOX, 'sstates')) if n.endswith('.p2s')])} save states")


def sandbox_pnach():
    return os.path.join(SANDBOX, "cheats", PNACH_NAME)


def cmd_cheats(a):
    need_sandbox()
    os.makedirs(os.path.join(SANDBOX, "cheats"), exist_ok=True)
    text = open(os.path.join(ROOT, "mods", PNACH_NAME), encoding="utf-8").read()
    trace = os.path.join(SANDBOX, "trace.pnach")
    sections = list(a.sections)
    for c_file in a.c or []:     # C cheats built on the fly (tools/debug/*.c, or a mod being tested)
        import cmod
        section, sect_text, _, _ = cmod.build(os.path.join(ROOT, "ISO", "SLUS_211.50"), c_file)
        text = text.rstrip("\n") + "\n\n" + sect_text
        sections.append(section)
    if a.trace:
        if not os.path.exists(trace):
            sys.exit("no trace cheat yet: run `trace build` first")
        text = text.rstrip("\n") + "\n\n" + open(trace, encoding="utf-8").read()
        sections.append(TRACE_SECTION)
    names = [ln[1:-1] for ln in text.split("\n") if ln.startswith("[") and ln.endswith("]")]
    for s in sections:
        if s not in names:
            sys.exit(f"no section [{s}] in the pnach; sections are:\n  " + "\n  ".join(names))
    with open(sandbox_pnach(), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    gs = os.path.join(SANDBOX, "gamesettings", GAME_INI)
    os.makedirs(os.path.dirname(gs), exist_ok=True)
    ini_set(gs, {("EmuCore", "EnableCheats"): "true"})
    ini_section(gs, "Cheats", [f"Enable = {s}" for s in sections])
    print(f"{len(sections)} cheat section(s) on in the sandbox" + ("" if not sections else ":\n  " + "\n  ".join(sections)))


def cmd_ram128(a):
    need_sandbox()
    gs = os.path.join(SANDBOX, "gamesettings", GAME_INI)
    os.makedirs(os.path.dirname(gs), exist_ok=True)
    ini_set(gs, {("EmuCore/CPU", "ExtraMemory"): "true" if a.state == "on" else "false"})
    print(f"128 MB RAM {a.state} for {GAME_INI} in the sandbox; restart the game ({'only 128 MB save states load' if a.state == 'on' else '32 MB save states load again'})")


def need_sandbox():
    if not os.path.exists(os.path.join(SANDBOX, EXE)):
        sys.exit("no sandbox yet: run `python tools/pcsx2.py setup`")


# ---------------------------------------------------------------- processes and windows (Windows)

def sandbox_pids():
    import ctypes
    from ctypes import wintypes
    psapi, k32 = ctypes.windll.psapi, ctypes.windll.kernel32
    arr = (wintypes.DWORD * 4096)()
    got = wintypes.DWORD()
    psapi.EnumProcesses(arr, ctypes.sizeof(arr), ctypes.byref(got))
    want = os.path.normcase(os.path.abspath(os.path.join(SANDBOX, EXE)))
    out = []
    for pid in arr[:got.value // 4]:
        h = k32.OpenProcess(0x1000, False, pid)
        if not h:
            continue
        buf = ctypes.create_unicode_buffer(1024)
        n = wintypes.DWORD(1024)
        if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)) and os.path.normcase(buf.value) == want:
            out.append(pid)
        k32.CloseHandle(h)
    return out


def cmd_start(a):
    need_sandbox()
    if sandbox_pids():
        sys.exit("the sandbox PCSX2 is already running (`stop` first)")
    iso = a.iso or ISO
    if not os.path.exists(iso):
        sys.exit(f"{iso} not found (--iso)")
    args = [os.path.join(SANDBOX, EXE), "-fastboot"]
    if a.state is not None:
        args += ["-state", str(a.state)]
    subprocess.Popen(args + ["--", iso], cwd=SANDBOX, creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
    t0 = time.time()
    while time.time() - t0 < 60:
        try:
            if Pine().status() == 0:
                print(f"running after {time.time() - t0:.0f} s (PINE port {PINE_PORT})")
                return
        except OSError:
            pass
        time.sleep(1)
    sys.exit("PCSX2 started but PINE didn't answer within 60 s")


def cmd_stop(a):
    pids = sandbox_pids()
    for pid in pids:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    print(f"stopped {len(pids)} sandbox process(es)" if pids else "not running")


def game_windows():
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    pids = set(sandbox_pids())
    tops = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(h, _):
        pid = wintypes.DWORD()
        u.GetWindowThreadProcessId(h, ctypes.byref(pid))
        if pid.value in pids and u.IsWindowVisible(h):
            b = ctypes.create_unicode_buffer(256)
            u.GetWindowTextW(h, b, 256)
            if b.value:
                tops.append((h, b.value))
        return True
    u.EnumWindows(cb, 0)
    return tops


def display_window():
    """The window showing the game: titled with the game name rather than 'PCSX2 ...'."""
    tops = game_windows()
    if not tops:
        sys.exit("no sandbox PCSX2 window (start it first)")
    for h, title in tops:
        if "Beat Down" in title or "SLUS" in title or "|" in title:
            return h
    return tops[0][0]


VK = {"Return": 0x0D, "Backspace": 0x08, "Up": 0x26, "Down": 0x28, "Left": 0x25, "Right": 0x27, "Escape": 0x1B,
      "Space": 0x20, **{f"F{i}": 0x6F + i for i in range(1, 13)}}


def post_key(key, down):
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    v = VK.get(key) or ord(key.upper())
    sc = u.MapVirtualKeyW(v, 0)
    lp = 1 | (sc << 16) | ((1 if key in ("Up", "Down", "Left", "Right") else 0) << 24)
    if not down:
        lp |= 3 << 30
    targets = []
    for h, _ in game_windows():
        targets.append(h)

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def cb(c, _):
            targets.append(c)
            return True
        u.EnumChildWindows(h, cb, 0)
    for h in targets:
        u.PostMessageW(h, 0x100 if down else 0x101, v, lp)


def cmd_keys(a):
    if not game_windows():
        sys.exit("no sandbox PCSX2 window (start it first)")
    for tok in " ".join(a.seq).split():
        if tok.startswith("wait:"):
            time.sleep(int(tok[5:]) / 1000)
            continue
        hold, count = 80, 1
        if ":" in tok:
            tok, h = tok.split(":")
            hold = int(h)
        if "*" in tok:
            tok, c = tok.split("*")
            count = int(c)
        keys = []
        for name in tok.split("+"):
            if name.lower() in BUTTON_KEYS:
                keys.append(BUTTON_KEYS[name.lower()])
            elif name in VK or len(name) == 1:
                keys.append(name)
            else:
                sys.exit(f"unknown key {name!r}")
        for _ in range(count):
            for k in keys:
                post_key(k, True)
            time.sleep(hold / 1000)
            for k in reversed(keys):
                post_key(k, False)
            time.sleep(0.12)


def png(path, w, h, rows):
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    raw = b"".join(b"\0" + r for r in rows)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) +
                chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def cmd_shot(a):
    import ctypes
    from ctypes import wintypes
    u, g = ctypes.windll.user32, ctypes.windll.gdi32
    try:
        u.SetProcessDPIAware()
    except AttributeError:
        pass
    h = display_window()
    r = wintypes.RECT()
    u.GetClientRect(h, ctypes.byref(r))
    w, hh = r.right, r.bottom
    hdc = u.GetDC(h)
    mdc = g.CreateCompatibleDC(hdc)
    bmp = g.CreateCompatibleBitmap(hdc, w, hh)
    g.SelectObject(mdc, bmp)
    u.PrintWindow(h, mdc, 3)

    class BIH(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("w", ctypes.c_long), ("h", ctypes.c_long), ("planes", wintypes.WORD),
                    ("bits", wintypes.WORD), ("comp", wintypes.DWORD), ("img", wintypes.DWORD),
                    ("xp", ctypes.c_long), ("yp", ctypes.c_long), ("used", wintypes.DWORD), ("imp", wintypes.DWORD)]
    bi = BIH(40, w, -hh, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(w * hh * 4)
    g.GetDIBits(mdc, bmp, 0, hh, buf, ctypes.byref(bi), 0)
    g.DeleteObject(bmp)
    g.DeleteDC(mdc)
    u.ReleaseDC(h, hdc)
    sc, b, rows = a.scale, buf.raw, []
    for y in range(0, hh, sc):
        row = b[y * w * 4:(y + 1) * w * 4]
        px = bytearray()
        for x in range(0, w, sc):
            o = x * 4
            px += bytes((row[o + 2], row[o + 1], row[o]))
        rows.append(bytes(px))
    png(a.out, (w + sc - 1) // sc, len(rows), rows)
    print(f"{a.out} ({w}x{hh} window)")


# ---------------------------------------------------------------- PINE

class Pine:
    """PCSX2's PINE protocol: [u32 size][u8 op][args], several ops per message; replies [u32 size][u8 0=ok]..."""
    READ = {1: 0, 2: 1, 4: 2, 8: 3}
    WRITE = {1: 4, 2: 5, 4: 6, 8: 7}

    def call(self, ops, reply_size):
        msg = b"".join(ops)
        s = socket.create_connection(("127.0.0.1", PINE_PORT), timeout=10)
        try:
            s.sendall(struct.pack("<I", len(msg) + 4) + msg)
            data = b""
            while len(data) < 4:
                part = s.recv(4 - len(data))
                if not part:
                    raise OSError("PINE closed the connection")
                data += part
            n, = struct.unpack("<I", data)
            data = b""
            while len(data) < n - 4:
                part = s.recv(n - 4 - len(data))
                if not part:
                    raise OSError("PINE closed the connection")
                data += part
        finally:
            s.close()
        if data[0] != 0:
            raise SystemExit("PINE refused the request (is a game running?)")
        return data[1:]

    def read(self, addr, size):
        return int.from_bytes(self.call([struct.pack("<BI", self.READ[size], addr)], size), "little")

    def write(self, addr, value, size):
        self.call([struct.pack("<BI", self.WRITE[size], addr) + value.to_bytes(size, "little")], 0)

    def read_block(self, addr, size):
        """Bytes at addr..addr+size, read 8 at a time in batches (addr and size multiples of 8)."""
        out = b""
        for base in range(addr, addr + size, 0x8000):
            n = min(0x8000, addr + size - base) // 8
            out += self.call([struct.pack("<BI", 3, base + 8 * i) for i in range(n)], 8 * n)
        return out

    def write_block(self, addr, data):
        for base in range(0, len(data), 0x8000):
            chunk = data[base:base + 0x8000]
            self.call([struct.pack("<BI", 7, addr + base + i) + chunk[i:i + 8] for i in range(0, len(chunk), 8)], 0)

    def status(self):
        return struct.unpack("<I", self.call([b"\x0f"], 4))[0]

    def text(self, op):
        d = self.call([bytes([op])], 0)
        n, = struct.unpack_from("<I", d)
        return d[4:4 + n].rstrip(b"\0").decode("utf-8", "replace")


def num(s):
    return int(s, 0)


def cmd_read(a):
    size = {"r8": 1, "r16": 2, "r32": 4}[a.cmd]
    p = Pine()
    for i in range(a.count):
        addr = a.addr + i * size
        print(f"{addr:08X}  {p.read(addr, size):0{size * 2}X}")


def cmd_write(a):
    Pine().write(a.addr, a.value, {"w8": 1, "w16": 2, "w32": 4}[a.cmd])


def cmd_dump(a):
    start = a.addr & ~7
    data = Pine().read_block(start, (a.addr + a.size - start + 7) & ~7)
    with open(a.out, "wb") as f:
        f.write(data[a.addr - start:a.addr - start + a.size])
    print(f"{a.size} bytes from {a.addr:#010x} -> {a.out}")


EVENT_FLAGS = 0x0060A680   # g_EventFlags: flag n is bit (n & 7) of byte n >> 3


def cmd_flag(a):
    p = Pine()
    for n in a.flags:
        addr, bit = EVENT_FLAGS + (n >> 3), 1 << (n & 7)
        v = p.read(addr, 1)
        if a.set or a.clear:
            v = v | bit if a.set else v & ~bit
            p.write(addr, v, 1)
        print(f"flag {n:#06x} ({n}) = {1 if v & bit else 0}")


def cmd_status(a):
    p = Pine()
    st = {0: "running", 1: "paused", 2: "shut down"}.get(p.status(), "?")
    try:
        print(f"{st}: {p.text(0xB)} ({p.text(0xC)}, CRC {p.text(0xD)})")
    except SystemExit:
        print(st)


def cmd_state(a):
    Pine().call([bytes([9 if a.cmd == "save" else 0xA, a.slot])], 0)
    print(f"{'saved' if a.cmd == 'save' else 'loaded'} slot {a.slot}")


# ---------------------------------------------------------------- save states

def state_member(path, name):
    """One file out of a .p2s save state (stored, deflate or zstd; zstd uses PCSX2's own zstd.dll)."""
    zf = zipfile.ZipFile(path)
    info = zf.getinfo(name)
    if info.compress_type != 93:
        return zf.read(name)
    import ctypes
    dll = None
    for d in (SANDBOX, SOURCE):
        if os.path.exists(os.path.join(d, "zstd.dll")):
            dll = ctypes.CDLL(os.path.join(d, "zstd.dll"))
            break
    if dll is None:
        sys.exit("this save state is zstd-compressed and no zstd.dll was found (PCSX2's folder has one)")
    with open(path, "rb") as f:
        f.seek(info.header_offset)
        h = f.read(30)
        n, m = struct.unpack_from("<HH", h, 26)
        f.seek(info.header_offset + 30 + n + m)
        raw = f.read(info.compress_size)
    dll.ZSTD_decompress.restype = ctypes.c_size_t
    dll.ZSTD_decompress.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t]
    out = ctypes.create_string_buffer(info.file_size)
    got = dll.ZSTD_decompress(out, info.file_size, raw, len(raw))
    if got != info.file_size:
        sys.exit(f"zstd failed on {name} in {path}")
    return out.raw


def cmd_ram(a):
    data = state_member(a.state, "eeMemory.bin")
    with open(a.out, "wb") as f:
        f.write(data)
    print(f"EE RAM ({len(data)} bytes) -> {a.out}")


def cmd_freeram(a):
    states = a.states or sorted(
        os.path.join(d, n) for d in (os.path.join(SOURCE, "sstates"), os.path.join(SANDBOX, "sstates"))
        if os.path.isdir(d) for n in os.listdir(d) if n.startswith(STATE_PREFIX) and ".p2s" in n)
    areas = [("mod area", MOD_AREA), ("mod data", MOD_DATA), ("debug (low)", DEBUG_LOW), ("debug (high)", DEBUG_HIGH)]
    for path in states:
        ram = state_member(path, "eeMemory.bin")
        brk, = struct.unpack_from("<I", ram, 0x0040C274)
        print(f"{os.path.basename(path)}: heap top (sbrk) {brk:#010x}")
        runs, start = [], None
        for addr in range(0, len(ram), 0x1000):
            zero = not any(ram[addr:addr + 0x1000])
            if zero and start is None:
                start = addr
            if not zero and start is not None:
                if addr - start >= 0x10000:
                    runs.append((start, addr))
                start = None
        if start is not None:
            runs.append((start, len(ram)))
        for s, e in runs:
            print(f"  zero {s:08X}-{e - 1:08X} {(e - s) // 1024:5d} KB")
        for name, (lo, hi) in areas:
            used = [ad for ad in range(lo, hi + 1, 0x1000) if any(ram[ad:ad + 0x1000])]
            print(f"  {name} {lo:#010x}-{hi:#010x}: " +
                  ("all zero" if not used else f"{len(used)} pages not zero, first {used[0]:#010x}"))


def cmd_show(a):
    import codemap
    structs, sizes = codemap.load_structs()
    by = {n: (sz, fields) for n, sz, _, fields in structs}
    if a.struct not in by:
        sys.exit(f"unknown struct {a.struct}; known: {', '.join(by)}")
    syms = {name: addr for addr, _, name, _ in codemap.load_symbols()}
    addr = syms[a.addr] if a.addr in syms else int(a.addr, 0)
    size, fields = by[a.struct]
    end = size or max(off + 64 for off, *_ in fields)
    if a.state:
        ram = state_member(a.state, "eeMemory.bin")
        data = ram[addr:addr + end]
    else:
        start = addr & ~7
        data = Pine().read_block(start, (addr + end - start + 7) & ~7)[addr - start:]
    fmt = {"s8": "b", "u8": "B", "char": "B", "s16": "h", "u16": "H", "s32": "i", "u32": "I", "f32": "f",
           "s64": "q", "u64": "Q"}
    print(f"{a.struct} at {addr:#010x}")
    for off, t, name, com in sorted(fields):
        base, ptr, count = codemap.parse_type(t)
        if ptr:
            f, n = "I", 4
        elif base in fmt:
            f, n = fmt[base], struct.calcsize("<" + fmt[base])
        else:
            print(f"  +{off:#06x} {name:20s} ({base}, see `show {base} {addr + off:#x}`)")
            continue
        vals = [struct.unpack_from("<" + f, data, off + i * n)[0] for i in range(min(count or 1, 16))]
        shown = ", ".join(f"{v:#x}" if ptr or f in "IH" and v > 9 else (f"{v:g}" if f == "f" else str(v)) for v in vals)
        if count:
            shown = f"[{shown}{', ...' if count > 16 else ''}]"
        print(f"  +{off:#06x} {name:20s} {shown}")


# ---------------------------------------------------------------- function trace

def trace_map_path():
    return os.path.join(SANDBOX, "trace.json")


def cmd_trace(a):
    import bdkit
    import cmod
    if a.action == "build":
        index = os.path.join(ROOT, "decomp", "index.tsv")
        if not os.path.exists(index):
            sys.exit("decomp/index.tsv is needed for the function list (README.md, \"Ghidra\")")
        game = bdkit.Elf(os.path.join(ROOT, "ISO", "SLUS_211.50"))
        funcs, skipped = [], 0
        for line in open(index, encoding="utf-8"):
            p = line.rstrip("\n").split("\t")
            if p[0] == "address" or p[4] != "ok":
                continue
            addr, size = int(p[0], 16), int(p[2])
            if not a.lo <= addr < a.hi or size < 12:
                continue
            w0, w1 = game.u32(addr), game.u32(addr + 4)
            uses_at = any(((w >> 21) & 31) == 1 or ((w >> 16) & 31) == 1 or ((w >> 11) & 31) == 1 for w in (w0, w1))
            inner = any(cmod.branch_target(pc, game.u32(pc)) == addr + 4 for pc in range(addr, addr + size, 4))
            if cmod.is_control_transfer(w0) or cmod.is_control_transfer(w1) or uses_at or inner:
                skipped += 1
                continue
            funcs.append((addr, p[1], w0, w1))
        table = TRACE_BASE + ((len(funcs) * 24 + 0xFFF) & ~0xFFF)
        end = table + 4 * len(funcs)
        if end > DEBUG_HIGH[1] + 1:
            sys.exit(f"{len(funcs)} functions need up to {end:#010x}, past the debug area; narrow --lo/--hi")
        lines = [f"[{TRACE_SECTION}]", "author=tools/pcsx2.py trace build",
                 f"description=Debug only: records which game functions run ({len(funcs)} functions, "
                 f"{a.lo:#x}-{a.hi:#x}). Stubs {TRACE_BASE:#010x}, table {table:#010x}."]
        for i, (addr, name, w0, w1) in enumerate(funcs):
            stub, flag = TRACE_BASE + 24 * i, table + 4 * i
            hi, lo = (flag + 0x8000) >> 16, flag & 0xFFFF
            words = [0x3C010000 | hi, 0xAC3F0000 | lo, w0, w1, 0x08000000 | ((addr + 8) >> 2) & 0x03FFFFFF, 0]
            lines += [f"patch=1,EE,{0x20000000 | (stub + 4 * k):08X},extended,{w:08X}" for k, w in enumerate(words)]
            lines += [f"patch=1,EE,{0x20000000 | addr:08X},extended,{0x08000000 | (stub >> 2) & 0x03FFFFFF:08X}",
                      f"patch=1,EE,{0x20000000 | (addr + 4):08X},extended,00000000"]
        os.makedirs(SANDBOX, exist_ok=True)
        with open(os.path.join(SANDBOX, "trace.pnach"), "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines) + "\n")
        with open(trace_map_path(), "w", encoding="utf-8") as f:
            json.dump({"table": table, "funcs": [(ad, n) for ad, n, _, _ in funcs]}, f)
        print(f"{len(funcs)} functions traced ({skipped} skipped: they start with a branch, use $at, or loop "
              f"to their second instruction); table at {table:#010x}.\nTurn it on with `cheats --trace ...`, "
              "then restart the game (`stop`, `start`).")
        return
    if not os.path.exists(trace_map_path()):
        sys.exit("no trace map: run `trace build` first")
    m = json.load(open(trace_map_path(), encoding="utf-8"))
    p = Pine()
    n = len(m["funcs"])
    size = (4 * n + 7) & ~7
    if a.action == "clear":
        p.write_block(m["table"], b"\0" * size)
        print(f"cleared {n} entries")
        return
    data = p.read_block(m["table"], size)
    names = sorted(m["funcs"])
    import bisect
    starts = [ad for ad, _ in names]

    def where(ra):
        i = bisect.bisect_right(starts, ra - 8) - 1
        return f"{names[i][1]}+{ra - 8 - names[i][0]:#x}" if i >= 0 else f"{ra - 8:#010x}"
    hits = [(ad, nm, struct.unpack_from("<I", data, 4 * i)[0]) for i, (ad, nm) in enumerate(m["funcs"])]
    hits = [h for h in hits if h[2]]
    for ad, nm, ra in hits:
        print(f"{ad:08X}  {nm:40s} called from {ra - 8:08X} {where(ra)}")
    print(f"{len(hits)} of {n} traced functions ran", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    x = sub.add_parser("setup")
    x.add_argument("--refresh", action="store_true", help="copy everything again (after updating PCSX2)")
    x.set_defaults(fn=cmd_setup)
    x = sub.add_parser("cheats")
    x.add_argument("sections", nargs="*")
    x.add_argument("--trace", action="store_true", help="also turn on the trace cheat from `trace build`")
    x.add_argument("--c", action="append", metavar="FILE.c", help="build a C cheat with tools/cmod.py and turn it on "
                   "(sandbox only; e.g. tools/debug/teleport.c); repeatable")
    x.set_defaults(fn=cmd_cheats)
    x = sub.add_parser("start")
    x.add_argument("--state", type=int, help="save state slot to load")
    x.add_argument("--iso")
    x.set_defaults(fn=cmd_start)
    sub.add_parser("stop").set_defaults(fn=cmd_stop)
    x = sub.add_parser("ram128")
    x.add_argument("state", choices=("on", "off"))
    x.set_defaults(fn=cmd_ram128)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    x = sub.add_parser("flag")
    x.add_argument("flags", type=num, nargs="+")
    x.add_argument("--set", action="store_true")
    x.add_argument("--clear", action="store_true")
    x.set_defaults(fn=cmd_flag)
    for c in ("r8", "r16", "r32"):
        x = sub.add_parser(c)
        x.add_argument("addr", type=num)
        x.add_argument("count", type=num, nargs="?", default=1)
        x.set_defaults(fn=cmd_read)
    for c in ("w8", "w16", "w32"):
        x = sub.add_parser(c)
        x.add_argument("addr", type=num)
        x.add_argument("value", type=num)
        x.set_defaults(fn=cmd_write)
    x = sub.add_parser("dump")
    x.add_argument("addr", type=num)
    x.add_argument("size", type=num)
    x.add_argument("out")
    x.set_defaults(fn=cmd_dump)
    x = sub.add_parser("keys")
    x.add_argument("seq", nargs="+")
    x.set_defaults(fn=cmd_keys)
    x = sub.add_parser("shot")
    x.add_argument("out")
    x.add_argument("scale", type=int, nargs="?", default=2)
    x.set_defaults(fn=cmd_shot)
    for c in ("save", "load"):
        x = sub.add_parser(c)
        x.add_argument("slot", type=int)
        x.set_defaults(fn=cmd_state)
    x = sub.add_parser("show")
    x.add_argument("struct")
    x.add_argument("addr", help="address or symbol name")
    x.add_argument("--state", help="read from this save state instead of the running game")
    x.set_defaults(fn=cmd_show)
    x = sub.add_parser("ram")
    x.add_argument("state")
    x.add_argument("out")
    x.set_defaults(fn=cmd_ram)
    x = sub.add_parser("freeram")
    x.add_argument("states", nargs="*")
    x.set_defaults(fn=cmd_freeram)
    x = sub.add_parser("trace")
    x.add_argument("action", choices=("build", "clear", "read"))
    x.add_argument("--lo", type=num, default=0x00170000)
    x.add_argument("--hi", type=num, default=0x0040D880)
    x.set_defaults(fn=cmd_trace)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
