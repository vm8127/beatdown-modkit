#!/usr/bin/env python3
"""PS2-native RenderWare textures (chunk 0x15 in a texture dictionary 0x16) to RGBA / PNG (docs/FORMATS.md,
"PS2-native textures").

Beat Down's world textures (FSTAGE.XAF section 0 of every area, the shared entries 55/56, CDATA.XAF 196-384, FSCENE)
are stored as GS upload packets: the pixels were uploaded with a GIF IMAGE transfer in another pixel format than
the one the texture is sampled with, so they are "swizzled". This module emulates the bit of GS local memory that
needs: write the upload rectangle in its transfer format, read the texture back in its own format (TEX0).

  python tools/ps2tex.py list ISO/XAF/FSTAGE.XAF 56           every texture: name, size, format
  python tools/ps2tex.py png ISO/XAF/FSTAGE.XAF 5 OUT [--section 0]   write each one as OUT/<name>.png

As a library: textures(blob) -> [Texture(name, mask, width, height, depth, rgba bytes)]; png(w, h, rgba).
Standard library only. Output is converted game data: keep it out of git.
"""
import argparse
import os
import struct
import sys
import zlib

TEXDICT, TEXNATIVE, STRUCT, STRING = 0x16, 0x15, 0x01, 0x02

# GS pixel storage formats (PSM) used here
PSMCT32, PSMCT16, PSMT8, PSMT4 = 0x00, 0x02, 0x13, 0x14

# GS local memory swizzle tables (GS User's Manual, "Local memory"; same as PCSX2's GSLocalMemory).
# Pages are 8 KB = 32 blocks of 256 bytes; a block is 4 columns of 64 bytes.
BLOCK32 = [[0, 1, 4, 5, 16, 17, 20, 21], [2, 3, 6, 7, 18, 19, 22, 23],
           [8, 9, 12, 13, 24, 25, 28, 29], [10, 11, 14, 15, 26, 27, 30, 31]]           # [y/8][x/8], page 64x32
BLOCK16 = [[0, 2, 8, 10], [1, 3, 9, 11], [4, 6, 12, 14], [5, 7, 13, 15],
           [16, 18, 24, 26], [17, 19, 25, 27], [20, 22, 28, 30], [21, 23, 29, 31]]    # [y/8][x/16], page 64x64
BLOCK8 = BLOCK32                                                                     # [y/16][x/16], page 128x64
BLOCK4 = BLOCK16                                                                     # [y/16][x/32], page 128x128


def _col32():
    """Word index inside an 8x8 PSMCT32 block."""
    base = [[0, 1, 4, 5, 8, 9, 12, 13], [2, 3, 6, 7, 10, 11, 14, 15]]
    return [[base[y & 1][x] + 16 * (y >> 1) for x in range(8)] for y in range(8)]


COL32 = _col32()
COL16 = [[0, 2, 8, 10, 16, 18, 24, 26, 1, 3, 9, 11, 17, 19, 25, 27],
         [4, 6, 12, 14, 20, 22, 28, 30, 5, 7, 13, 15, 21, 23, 29, 31]]
COL16 = [[v + 32 * (y >> 1) for v in COL16[y & 1]] for y in range(8)]               # halfword in a 16x8 block

# Byte inside a 16x16 PSMT8 block (rows 8-15 = rows 0-7 + 128)
_COL8_TABLE = [
    [0, 4, 16, 20, 32, 36, 48, 52, 2, 6, 18, 22, 34, 38, 50, 54],
    [8, 12, 24, 28, 40, 44, 56, 60, 10, 14, 26, 30, 42, 46, 58, 62],
    [33, 37, 1, 5, 49, 53, 17, 21, 35, 39, 3, 7, 51, 55, 19, 23],
    [41, 45, 9, 13, 57, 61, 25, 29, 43, 47, 11, 15, 59, 63, 27, 31],
    [96, 100, 112, 116, 64, 68, 80, 84, 98, 102, 114, 118, 66, 70, 82, 86],
    [104, 108, 120, 124, 72, 76, 88, 92, 106, 110, 122, 126, 74, 78, 90, 94],
    [65, 69, 81, 85, 97, 101, 113, 117, 67, 71, 83, 87, 99, 103, 115, 119],
    [73, 77, 89, 93, 105, 109, 121, 125, 75, 79, 91, 95, 107, 111, 123, 127],
]
COL8 = _COL8_TABLE + [[v + 128 for v in row] for row in _COL8_TABLE]

_COL4_TABLE = [
    [0, 8, 32, 40, 64, 72, 96, 104, 2, 10, 34, 42, 66, 74, 98, 106,
     4, 12, 36, 44, 68, 76, 100, 108, 6, 14, 38, 46, 70, 78, 102, 110],
    [16, 24, 48, 56, 80, 88, 112, 120, 18, 26, 50, 58, 82, 90, 114, 122,
     20, 28, 52, 60, 84, 92, 116, 124, 22, 30, 54, 62, 86, 94, 118, 126],
    [65, 73, 97, 105, 1, 9, 33, 41, 67, 75, 99, 107, 3, 11, 35, 43,
     69, 77, 101, 109, 5, 13, 37, 45, 71, 79, 103, 111, 7, 15, 39, 47],
    [81, 89, 113, 121, 17, 25, 49, 57, 83, 91, 115, 123, 19, 27, 51, 59,
     85, 93, 117, 125, 21, 29, 53, 61, 87, 95, 119, 127, 23, 31, 55, 63],
    [192, 200, 224, 232, 128, 136, 160, 168, 194, 202, 226, 234, 130, 138, 162, 170,
     196, 204, 228, 236, 132, 140, 164, 172, 198, 206, 230, 238, 134, 142, 166, 174],
    [208, 216, 240, 248, 144, 152, 176, 184, 210, 218, 242, 250, 146, 154, 178, 186,
     212, 220, 244, 252, 148, 156, 180, 188, 214, 222, 246, 254, 150, 158, 182, 190],
    [129, 137, 161, 169, 193, 201, 225, 233, 131, 139, 163, 171, 195, 203, 227, 235,
     133, 141, 165, 173, 197, 205, 229, 237, 135, 143, 167, 175, 199, 207, 231, 239],
    [145, 153, 177, 185, 209, 217, 241, 249, 147, 155, 179, 187, 211, 219, 243, 251,
     149, 157, 181, 189, 213, 221, 245, 253, 151, 159, 183, 191, 215, 223, 247, 255],
]
COL4 = _COL4_TABLE + [[v + 256 for v in row] for row in _COL4_TABLE]


def _check_tables():
    for name, t, n in (("COL32", COL32, 64), ("COL16", COL16, 128), ("COL8", COL8, 256), ("COL4", COL4, 512)):
        flat = sorted(v for row in t for v in row)
        assert flat == list(range(n)), f"{name} is not a permutation"


_check_tables()


# ---------------------------------------------------------------------------
# GS local memory addressing. bp = base block (256-byte units), bw = buffer width in 64-pixel units.
# Each returns a unit address: words for CT32, halfwords for CT16, bytes for T8, nibbles for T4.
# ---------------------------------------------------------------------------
def addr32(bp, bw, x, y):
    page = (y >> 5) * bw + (x >> 6)
    return ((bp + page * 32 + BLOCK32[(y >> 3) & 3][(x >> 3) & 7]) << 6) + COL32[y & 7][x & 7]


def addr16(bp, bw, x, y):
    page = (y >> 6) * bw + (x >> 6)
    return ((bp + page * 32 + BLOCK16[(y >> 3) & 7][(x >> 4) & 3]) << 7) + COL16[y & 7][x & 15]


def addr8(bp, bw, x, y):
    page = (y >> 6) * max(bw >> 1, 1) + (x >> 7)
    return ((bp + page * 32 + BLOCK8[(y >> 4) & 3][(x >> 4) & 7]) << 8) + COL8[y & 15][x & 15]


def addr4(bp, bw, x, y):
    page = (y >> 7) * max(bw >> 1, 1) + (x >> 7)
    return ((bp + page * 32 + BLOCK4[(y >> 4) & 7][(x >> 5) & 3]) << 9) + COL4[y & 15][x & 31]


def unswizzle(pixels, w, h, depth, rw, rh, tbw):
    """Texture of w x h at depth 4/8 whose bytes were uploaded as a rw x rh rectangle of PSMCT32 (8-bit) or PSMCT16
    (4-bit) with DBW = TBW / 2; returns one palette index per pixel, row major."""
    dbw = max(tbw >> 1, 1)
    mem = bytearray(max(len(pixels), 1) * 4 + (1 << 16))
    if depth == 8:
        for y in range(rh):
            for x in range(rw):
                i = (y * rw + x) * 4
                a = addr32(0, dbw, x, y) * 4
                mem[a:a + 4] = pixels[i:i + 4]
        return bytes(mem[addr8(0, tbw, x, y)] for y in range(h) for x in range(w))
    if depth == 4:
        for y in range(rh):
            for x in range(rw):
                i = (y * rw + x) * 2
                a = addr16(0, dbw, x, y) * 2
                mem[a:a + 2] = pixels[i:i + 2]
        out = bytearray(w * h)
        k = 0
        for y in range(h):
            for x in range(w):
                n = addr4(0, tbw, x, y)
                b = mem[n >> 1]
                out[k] = (b >> 4) if n & 1 else (b & 15)
                k += 1
        return bytes(out)
    raise ValueError(f"depth {depth}")


# ---------------------------------------------------------------------------
# RenderWare chunks
# ---------------------------------------------------------------------------
def _chunks(d, off=0, end=None):
    end = len(d) if end is None else end
    out = []
    while off + 12 <= end:
        t, s, v = struct.unpack_from("<III", d, off)
        if v == 0 or off + 12 + s > end:
            break
        out.append((t, off + 12, s))
        off += 12 + s
    return out


class Texture:
    def __init__(self, name, mask, width, height, depth, rgba, info):
        self.name, self.mask, self.width, self.height, self.depth, self.rgba, self.info = \
            name, mask, width, height, depth, rgba, info

    def has_alpha(self):
        return any(a < 255 for a in self.rgba[3::4])

    def png(self):
        return png(self.width, self.height, self.rgba)


def _alpha(a):
    return min(255, a * 2)       # GS alpha: 0x80 = opaque


def read_native(d, off, size):
    """One TextureNative (0x15) chunk's payload at d[off:off + size]."""
    k = _chunks(d, off, off + size)
    platform, flags = struct.unpack_from("<4sI", d, k[0][1])
    if platform != b"PS2\0":
        raise ValueError(f"texture native for platform {platform!r}, only PS2 is handled")
    name = d[k[1][1]:k[1][1] + k[1][2]].split(b"\0")[0].decode("latin1")
    mask = d[k[2][1]:k[2][1] + k[2][2]].split(b"\0")[0].decode("latin1")
    inner = _chunks(d, k[3][1], k[3][1] + k[3][2])
    ri = d[inner[0][1]:inner[0][1] + inner[0][2]]
    w, h, depth, rfmt = struct.unpack_from("<IIII", ri, 0)
    tex0, = struct.unpack_from("<Q", ri, 16)
    psize, palsize = struct.unpack_from("<II", ri, 48)
    data = d[inner[1][1]:inner[1][1] + inner[1][2]]
    headers = (rfmt >> 16) & 2
    if rfmt & 0x8000 or (rfmt & 0xFFFF) not in (0x2504, 0x4504, 0x0504):
        raise ValueError(f"{name}: raster format {rfmt:#x} (mipmaps or unknown) is not handled")
    if headers:
        rw, rh = struct.unpack_from("<II", data, 0x20)      # TRXREG of the pixel upload
        pix = data[0x50:psize]
    elif depth == 32:      # no GS headers (FSTAGE 122-180's 512x256 STG_nn_?CAR pictures): plain rows
        rw, rh = w, h
        pix = data[:psize]
    else:
        raise ValueError(f"{name}: palettized raster without GS headers (format {rfmt:#x}) is not handled")
    tbw = (tex0 >> 14) & 0x3F
    psm = (tex0 >> 20) & 0x3F
    info = {"flags": flags, "raster_format": rfmt, "psm": psm, "tbw": tbw, "upload": (rw, rh)}
    if depth == 32:
        rgba = bytearray(w * h * 4)
        if (rw, rh) != (w, h):
            raise ValueError(f"{name}: 32-bit upload {rw}x{rh} for {w}x{h}")
        for i in range(w * h):        # uploaded in its own format: linear rows
            rgba[4 * i:4 * i + 3] = pix[4 * i:4 * i + 3]
            rgba[4 * i + 3] = _alpha(pix[4 * i + 3])
        return Texture(name, mask, w, h, depth, bytes(rgba), info)
    idx = unswizzle(pix, w, h, depth, rw, rh, tbw)
    pal = data[psize + 0x50:psize + palsize]
    prw, prh = struct.unpack_from("<II", data, psize + 0x20)
    info["palette_upload"] = (prw, prh)
    ncol = 256 if depth == 8 else 16
    cols = [pal[4 * i:4 * i + 4] for i in range(ncol)]
    if ncol == 256:      # CSM1: entries 8-15 and 16-23 of every 32 are swapped (as bdkit.texture_png)
        cols = [cols[(i & ~0x18) | ((i & 0x08) << 1) | ((i & 0x10) >> 1)] for i in range(256)]
    lut = [bytes(c[:3]) + bytes([_alpha(c[3])]) for c in cols]
    return Texture(name, mask, w, h, depth, b"".join(lut[i] for i in idx), info)


def textures(blob):
    """Every PS2-native texture in the texture dictionaries of a RenderWare stream."""
    out = []
    for t, o, s in _chunks(blob):
        if t != TEXDICT:
            continue
        for t2, o2, s2 in _chunks(blob, o, o + s):
            if t2 == TEXNATIVE:
                out.append(read_native(blob, o2, s2))
    return out


def png(w, h, rgba):
    rows = b"".join(b"\0" + rgba[y * w * 4:(y + 1) * w * 4] for y in range(h))
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------
def _load(path, entry, section):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import bdkit
    o, s = bdkit.xaf_entries(path)[entry][1:3]
    with open(path, "rb") as f:
        f.seek(o)
        blob = f.read(s)
    if section is not None:     # an FSTAGE area pack: u32 count, then {offset, size} per section
        so, ss = struct.unpack_from("<II", blob, 4 + 8 * section)
        blob = blob[so:so + ss]
    return blob


def _section_default(a):
    if a.section is None and os.path.basename(a.xaf).upper() == "FSTAGE.XAF" and 1 <= a.entry <= 54:
        return 0
    return a.section


def cmd_list(a):
    for t in textures(_load(a.xaf, a.entry, _section_default(a))):
        i = t.info
        print(f"{t.name:16s} {t.width:4d}x{t.height:<4d} {t.depth:2d}-bit psm {i['psm']:#04x} upload "
              f"{i['upload'][0]}x{i['upload'][1]} tbw {i['tbw']}{' alpha' if t.has_alpha() else ''}"
              f"{' mask ' + t.mask if t.mask else ''}")


def cmd_png(a):
    os.makedirs(a.out, exist_ok=True)
    for t in textures(_load(a.xaf, a.entry, _section_default(a))):
        with open(os.path.join(a.out, t.name + ".png"), "wb") as f:
            f.write(t.png())
        print(f"{t.name}: {t.width}x{t.height} {t.depth}-bit")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    s = p.add_subparsers(dest="cmd", required=True)
    for name, fn in (("list", cmd_list), ("png", cmd_png)):
        x = s.add_parser(name)
        x.add_argument("xaf")
        x.add_argument("entry", type=lambda v: int(v, 0))
        if name == "png":
            x.add_argument("out")
        x.add_argument("--section", type=int, help="FSTAGE area pack section (default 0 for areas 1-54)")
        x.set_defaults(fn=fn)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
