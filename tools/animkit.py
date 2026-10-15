#!/usr/bin/env python3
"""Beat Down (SLUS-21150) animation decoder: STAGE.XAF animation packs -> per-bone keyframe tracks.

Format (docs/ANIMATION.md, "Animation file format"; read from the game's code 2026-10-15):
  * STAGE.XAF entry = pack: u32 count, then count x u32 {bits 28-31 compression, bits 0-27 offset in the entry}
    (plus one end word). Compression 0 = raw (size = next offset - offset), 8 = LZSS (Okumura: 4 KB window
    starting at 0xFEE, flag bit 1 = literal; first u32 of the item = unpacked size). STAGE.XAF entry 0 is one
    bare animation. The animations of a pack are numbered by the animation group's id list, in order.
  * Each item is a RenderWare 3.x RtAnimAnimation chunk (type 0x1B, 12-byte chunk header {type, size, libid}):
    s32 version 0x100, s32 interpolator type (always 2 = RpHAnim compressed keyframes), s32 keyframe count,
    s32 flags, f32 duration (seconds), keyframes x 22 bytes {f32 time, u16 qx qy qz qw, u16 tx ty tz,
    s32 previous keyframe of the same bone as a byte offset in 24-byte units}, then 24 bytes of custom data
    {f32 offset xyz, f32 scale xyz} for the translations.
  * u16 values are RenderWare's 16-bit floats: sign bit 15, exponent bits 11-14 (IEEE exponent - 112),
    mantissa bits 0-10. Rotation = that quaternion; translation = float16 * scale + offset.
  * Keyframe order is RenderWare's: keyframes 0..N-1 are every bone's key at time 0, N..2N-1 every bone's
    second key, then the rest sorted by when they are needed; each key names the previous key of its bone,
    so following those links splits the keys into N bone tracks (N = the skeleton's HAnim node count).

Commands:
  python tools/animkit.py list  ISO/SLUS_211.50 --group 184          # animations of one group (Aaron's style)
  python tools/animkit.py list  ISO/SLUS_211.50 --entry 96           # one STAGE.XAF entry
  python tools/animkit.py dump  ISO/SLUS_211.50 34                   # one animation (global anim id), text
  python tools/animkit.py dump  ISO/SLUS_211.50 34 --json > a.json   # ... keys per bone as JSON
  python tools/animkit.py dump  ISO/SLUS_211.50 34 --sample 60       # ... sampled at 60 fps (slerp, as the game)
  python tools/animkit.py check ISO/SLUS_211.50                      # decode every pack, sanity statistics

Standard library only. Reads ISO/XAF/STAGE.XAF next to the ELF's folder unless --stage is given.
"""
import argparse
import json
import math
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bdkit  # noqa: E402

ANIM_CHUNK = 0x1B
INTERP_COMPRESSED = 2      # RpHAnim compressed keyframes (registered at 0x002540xx, callbacks 0x00253550..)
KEY_SIZE_STREAM = 22
KEY_SIZE_MEM = 24
FPS = 60                   # Fighter_PlayMotion frames are 1/60 s


# ---------------------------------------------------------------------------
# containers
# ---------------------------------------------------------------------------
def lzss(src, size):
    """The game's LZSS (0x0029E3C0): 4096-byte window, write position starts at 0xFEE, match = 2 bytes
    {offset low 8 | (high nibble of byte 2) << 8, length = low nibble + 3}."""
    win = bytearray(0x1000)
    w = 0xFEE
    out = bytearray()
    i = 0
    flags = 0
    while len(out) < size and i < len(src):
        flags >>= 1
        if not flags & 0x100:
            flags = src[i] | 0xFF00
            i += 1
        if flags & 1:
            b = src[i]
            i += 1
            out.append(b)
            win[w] = b
            w = (w + 1) & 0xFFF
        else:
            lo, hi = src[i], src[i + 1]
            i += 2
            off = lo | (hi & 0xF0) << 4
            for k in range((hi & 0xF) + 3):
                b = win[(off + k) & 0xFFF]
                out.append(b)
                win[w] = b
                w = (w + 1) & 0xFFF
                if len(out) >= size:
                    break
    return bytes(out)


def xaf_entry(path, idx):
    with open(path, "rb") as f:
        h = f.read(0x40)
        n = struct.unpack_from("<I", h, 0x2C)[0]
        if not 0 <= idx < n:
            sys.exit(f"entry {idx} out of range (0-{n - 1})")
        f.seek(0x40 + 8 * idx)
        o, s = struct.unpack("<II", f.read(8))
        f.seek(o)
        return f.read(s)


def pack_items(blob):
    """Split one STAGE.XAF entry into its animation chunks (decompressed)."""
    if struct.unpack_from("<I", blob, 0)[0] == ANIM_CHUNK:
        return [blob]
    count = struct.unpack_from("<I", blob, 0)[0]
    words = struct.unpack_from("<%dI" % (count + 1), blob, 4)
    out = []
    for k in range(count):
        kind, off = words[k] >> 28, words[k] & 0x0FFFFFFF
        if kind == 0:
            end = words[k + 1] & 0x0FFFFFFF if k + 1 < count else len(blob)
            out.append(blob[off:end])
        elif kind == 8:
            size = struct.unpack_from("<I", blob, off)[0]
            out.append(lzss(blob[off + 4:], size))
        else:
            raise ValueError(f"pack item {k}: unknown compression {kind}")
    return out


# ---------------------------------------------------------------------------
# the animation chunk
# ---------------------------------------------------------------------------
def half(v):
    """RenderWare 16-bit float (decompress code at 0x00253660)."""
    bits = (v & 0x8000) << 16
    if v & 0x7FFF:
        bits |= ((v & 0x7800) << 12) + 0x38000000 | (v & 0x7FF) << 12
    return struct.unpack("<f", struct.pack("<I", bits & 0xFFFFFFFF))[0]


class Anim:
    def __init__(self, chunk):
        ctype, csize, libid = struct.unpack_from("<III", chunk, 0)
        if ctype != ANIM_CHUNK:
            raise ValueError(f"not an animation chunk (type 0x{ctype:x})")
        p = 12
        self.version, self.interp, self.nkeys, self.flags, self.duration = struct.unpack_from("<iiiif", chunk, p)
        if self.version != 0x100 or self.interp != INTERP_COMPRESSED:
            raise ValueError(f"unsupported animation: version 0x{self.version:x} interpolator {self.interp}")
        p += 20
        self.keys = []      # (time, (qx, qy, qz, qw), (tx, ty, tz) raw u16, prev index)
        for i in range(self.nkeys):
            t, qx, qy, qz, qw, tx, ty, tz, prev = struct.unpack_from("<f7Hi", chunk, p)
            self.keys.append((t, (half(qx), half(qy), half(qz), half(qw)), (tx, ty, tz), prev // KEY_SIZE_MEM))
            p += KEY_SIZE_STREAM
        self.offset = struct.unpack_from("<3f", chunk, p)
        self.scale = struct.unpack_from("<3f", chunk, p + 12)
        self.size = csize + 12
        self._tracks = None

    @property
    def frames(self):
        return round(self.duration * FPS)

    def trans(self, raw):
        return tuple(half(raw[k]) * self.scale[k] + self.offset[k] for k in range(3))

    @property
    def bones(self):
        n = 0
        while n < self.nkeys and self.keys[n][0] == 0.0:
            n += 1
        return n

    def tracks(self):
        """[bone] -> [(time, quat, translation)] following the previous-key links."""
        if self._tracks is None:
            n = self.bones
            owner = list(range(n)) + [None] * (self.nkeys - n)
            for i in range(n, self.nkeys):
                p = self.keys[i][3]
                if not 0 <= p < i or owner[p] is None:
                    raise ValueError(f"key {i}: bad previous-key link {p}")
                owner[i] = owner[p]
            tr = [[] for _ in range(n)]
            for i, (t, q, raw, _) in enumerate(self.keys):
                tr[owner[i]].append((t, q, self.trans(raw)))
            for b in tr:
                b.sort(key=lambda k: k[0])
            self._tracks = tr
        return self._tracks

    def sample(self, t):
        """Pose at time t (seconds): per bone (quat, translation), slerp + lerp like the game's interpolator."""
        out = []
        for keys in self.tracks():
            if t <= keys[0][0]:
                out.append(keys[0][1:])
                continue
            for a, b in zip(keys, keys[1:]):
                if a[0] <= t <= b[0]:
                    u = (t - a[0]) / (b[0] - a[0]) if b[0] > a[0] else 0.0
                    out.append((slerp(a[1], b[1], u), tuple(x + u * (y - x) for x, y in zip(a[2], b[2]))))
                    break
            else:
                out.append(keys[-1][1:])
        return out


def slerp(a, b, u):
    d = sum(x * y for x, y in zip(a, b))
    if d < 0:
        b, d = tuple(-x for x in b), -d
    if d > 0.9995:
        r = tuple(x + u * (y - x) for x, y in zip(a, b))
    else:
        th = math.acos(min(1.0, d))
        s = math.sin(th)
        wa, wb = math.sin((1 - u) * th) / s, math.sin(u * th) / s
        r = tuple(wa * x + wb * y for x, y in zip(a, b))
    n = math.sqrt(sum(x * x for x in r)) or 1.0
    return tuple(x / n for x in r)


# ---------------------------------------------------------------------------
# lookup by group / global anim id
# ---------------------------------------------------------------------------
class Library:
    def __init__(self, elf_path, stage_path=None):
        self.elf = bdkit.Elf(elf_path)
        self.stage = stage_path or os.path.join(os.path.dirname(os.path.abspath(elf_path)), "XAF", "STAGE.XAF")
        self.groups = self.elf.anim_groups()
        self._cache = {}

    def entry(self, idx):
        if idx not in self._cache:
            self._cache[idx] = pack_items(xaf_entry(self.stage, idx))
        return self._cache[idx]

    def where(self, anim_id):
        """Every (group, stage entry, index in pack) that holds a global anim id."""
        return [(g["group"], g["stage_entry"], g["anim_ids"].index(anim_id))
                for g in self.groups if anim_id in g["anim_ids"]]

    def anim(self, anim_id, group=None):
        locs = self.where(anim_id)
        if group is not None:
            locs = [l for l in locs if l[0] == group]
        if not locs:
            sys.exit(f"anim {anim_id} is in no animation group" + (f" {group}" if group is not None else ""))
        g, e, k = locs[0]
        return Anim(self.entry(e)[k]), (g, e, k)


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------
def fmt(v, n=4):
    return "(" + ", ".join(f"{x:.{n}f}" for x in v) + ")"


def cmd_list(a):
    lib = Library(a.elf, a.stage)
    if a.group is not None:
        g = lib.groups[a.group]
        entry, ids = g["stage_entry"], g["anim_ids"]
    else:
        entry, ids = a.entry, None
    items = lib.entry(entry)
    print(f"STAGE.XAF entry {entry}: {len(items)} animations" + (f" (group {a.group})" if ids else ""))
    print(" idx  anim  frames  seconds  bones  keys")
    for k, it in enumerate(items):
        an = Anim(it)
        aid = ids[k] if ids and k < len(ids) else "-"
        print(f"{k:4} {aid!s:>5} {an.frames:7} {an.duration:8.3f} {an.bones:6} {an.nkeys:5}")


def cmd_dump(a):
    lib = Library(a.elf, a.stage)
    an, (g, e, k) = lib.anim(a.anim, a.group)
    tr = an.tracks()
    info = dict(anim=a.anim, group=g, stage_entry=e, index=k, duration=an.duration, frames=an.frames,
                bones=an.bones, keys=an.nkeys, flags=an.flags, translation_offset=an.offset,
                translation_scale=an.scale)
    if a.sample:
        n = int(round(an.duration * a.sample))
        poses = [an.sample(f / a.sample) for f in range(n + 1)]
        if a.json:
            info["fps"] = a.sample
            info["poses"] = [[dict(q=q, t=t) for q, t in p] for p in poses]
            json.dump(info, sys.stdout, indent=1)
            return
        print(json.dumps({x: info[x] for x in info}))
        bones = [a.bone] if a.bone is not None else range(an.bones)
        for f, p in enumerate(poses):
            for b in bones:
                q, t = p[b]
                print(f"f{f:4} bone {b:2} q{fmt(q)} t{fmt(t, 3)}")
        return
    if a.json:
        info["tracks"] = [[dict(time=t, q=q, t=tt) for t, q, tt in keys] for keys in tr]
        json.dump(info, sys.stdout, indent=1)
        return
    print(json.dumps(info))
    for b, keys in enumerate(tr):
        if a.bone is not None and b != a.bone:
            continue
        print(f"bone {b}: {len(keys)} keys")
        for t, q, tt in keys:
            print(f"  {t * FPS:7.2f}f q{fmt(q)} t{fmt(tt, 3)}")


def cmd_check(a):
    lib = Library(a.elf, a.stage)
    n_anim = bad = 0
    worst_norm = worst_jump = 0.0
    bone_counts = {}
    entries = sorted({g["stage_entry"] for g in lib.groups if g["anim_ids"]})
    for e in entries:
        for k, it in enumerate(lib.entry(e)):
            try:
                an = Anim(it)
                tr = an.tracks()
            except ValueError as ex:
                bad += 1
                print(f"entry {e} item {k}: {ex}")
                continue
            n_anim += 1
            bone_counts[an.bones] = bone_counts.get(an.bones, 0) + 1
            for keys in tr:
                if keys[-1][0] > an.duration + 1e-4:
                    print(f"entry {e} item {k}: key after the end")
                for t, q, _ in keys:
                    worst_norm = max(worst_norm, abs(math.sqrt(sum(x * x for x in q)) - 1))
                for x, y in zip(keys, keys[1:]):
                    d = abs(sum(p * r for p, r in zip(x[1], y[1])))
                    worst_jump = max(worst_jump, math.degrees(2 * math.acos(min(1.0, d))))
    print(f"{n_anim} animations from {len(entries)} STAGE.XAF entries decoded, {bad} failed")
    print(f"bone counts: {dict(sorted(bone_counts.items()))}")
    print(f"largest |quaternion| - 1: {worst_norm:.4f}; largest rotation between two keys: {worst_jump:.1f} deg")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list", help="animations of a group or STAGE.XAF entry")
    p.add_argument("elf")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--group", type=int)
    g.add_argument("--entry", type=int)
    p.add_argument("--stage")
    p.set_defaults(fn=cmd_list)
    p = sub.add_parser("dump", help="one animation's tracks (global anim id)")
    p.add_argument("elf")
    p.add_argument("anim", type=int)
    p.add_argument("--group", type=int, help="take it from this group (default: the first that lists it)")
    p.add_argument("--bone", type=int)
    p.add_argument("--sample", type=float, help="sample at this rate (fps) instead of printing the keys")
    p.add_argument("--json", action="store_true")
    p.add_argument("--stage")
    p.set_defaults(fn=cmd_dump)
    p = sub.add_parser("check", help="decode every animation and print sanity statistics")
    p.add_argument("elf")
    p.add_argument("--stage")
    p.set_defaults(fn=cmd_check)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
