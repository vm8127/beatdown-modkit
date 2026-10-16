#!/usr/bin/env python3
"""The game's 2D look for the remake: the text font, its button icons, the colour palette and the fight HUD art.

    python remake/tools/conv_ui.py ISO remake/godot/assets_ripped     (or through remake_assets.py, "ui")

Writes, under <out>/ui/ (never commit; it is the game's art):
  font_page0.png   UNICODEFONT (GRAPH.XAF 374): Latin, Latin-1, Latin Extended-A, punctuation, kana
  font_icons.png   BUTTON (GRAPH 32): face buttons, shoulder buttons, sticks, d-pad
  font_crime.png   MURDER_01 (GRAPH 305): the two crime icons
  name_font.png    SYSFONT02 (GRAPH 355): the HP bar's name font, 16 x 16 cells from code 0x20
  hp_frame.png     GD_HPG_01 (173), hp_fill.png GD_HPG_02 (174): HP bar frame and fill
  hud_tex02.png    FONT_TEX_02 (131), hud_tex03.png FONT_TEX_03 (136): Pride gauge, combo counter (English ones)
  font.json        glyphs {code point: [page, u, v, w, h, y nudge]}, pages, advance factor, the @N colour palette
  hud.json         HP bar, Pride gauge and combo counter constants, read from the ELF (docs/HUD.md)
Read by remake/godot/game/ui/ (GameFont, FightHud). Everything here is documented in docs/HUD.md. GRAPH.XAF's
8-bit images use a plain palette order (no CSM1 swap) and full-range alpha, unlike DATA.XAF's.
Deterministic. Standard library only.
"""
import json
import os
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))
import bdkit  # noqa: E402
import rwkit  # noqa: E402

# GRAPH.XAF entries (names from g_GraphNames 0x005AB0D0)
TEXTURES = {
    "font_page0": 374,   # UNICODEFONT
    "font_icons": 32,    # BUTTON
    "font_crime": 305,   # MURDER_01
    "name_font": 355,    # SYSFONT02
    "hp_frame": 173,     # GD_HPG_01
    "hp_fill": 174,      # GD_HPG_02
    "hud_tex02": 131,    # FONT_TEX_02 (English; 132-135 ESP FRA GER ITA)
    "hud_tex03": 136,    # FONT_TEX_03 (137-140)
}

# Glyph tables {u16 code, u, v, w, h}, 0-terminated (docs/HUD.md, "The text font")
GLYPH_TABLES = [(0, 0x005B8840, "font_page0"), (5, 0x005CA210, "font_icons"), (6, 0x005CA1F0, "font_crime")]
TEXT_PALETTE = 0x005CA320     # g_TextPalette RGBA x 16
GLYPH_ADVANCE = 0.95          # Text_Layout: advance = w x 0.95
# Text_Layout's vertical nudges per icon (pixels, + = down)
NUDGE = {}
for _c in "①②③④⑤⑥○△□×●▲■Ⅹ":
    NUDGE[ord(_c)] = 2
for _c in "㊤㊥㊦㊧㊨←↑→↓∬":
    NUDGE[ord(_c)] = -1
for _c in "⑰⑱":
    NUDGE[ord(_c)] = -4
for _c in "αβ":
    NUDGE[ord(_c)] = -6

# HUD constants (addresses in docs/HUD.md)
GP = 0x00604BF0
HPBAR_K = GP - 0x6930            # f32 0.018
HPBAR_NAME_COLOURS = GP - 0x6918  # 6 x RGBA
HPBAR_ROW_Y = 0x00516960          # f32[3]
HPBAR_TEX_WH = 0x00516970         # f32[4]: frame w h, fill w h (UV space)
HPBAR_NAME_POS = 0x00516930       # f32[6][2]
HPBAR_PULSE = 0x005168C0          # RGBA
HPBAR_ORDER = 0x005D4378          # u16[4]
HPBAR_COLOURS = {                 # 4 vertex RGBA each; HpBar_LayerQuads picks them
    "hp_side0": 0x005167E0, "hp_side0_party": 0x005167F0, "hp_side1": 0x00516800, "hp_side1_party": 0x00516810,
    "frame_side0": 0x00516820, "frame_side0_party": 0x00516830, "frame_side1": 0x00516840,
    "frame_side1_party": 0x00516850, "back": 0x00516860, "trail_side0": 0x00516870,
    "trail_side0_party": 0x00516880, "trail_side1": 0x00516890, "trail_side1_party": 0x005168A0,
    "hp_side1_other": 0x005168B0,
}
PRIDE_LAYOUT = 0x005CA830        # s16[2][10]
PRIDE_FLAMES = 0x005CA860        # f32[8][2]
PRIDE_SLIDE = 0x005CA8A0         # f32[2]
HUD_SPRITES = 0x00505920         # 0x28 each: s16 group, index, ?, f32 x, y, texture w, h, u, v, w, h


def write_png(path, w, h, rgba):
    rows = b"".join(b"\0" + rgba[y * w * 4:(y + 1) * w * 4] for y in range(h))
    ch = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)) +
                ch(b"IDAT", zlib.compress(rows, 9)) + ch(b"IEND", b""))


def graph_image(blob):
    """A GRAPH.XAF Image chunk as (w, h, RGBA bytes): one palette index per byte, 16 or 256 colours in plain
    order (no CSM1 swap), alpha 0-255 as stored."""
    im = rwkit.images(blob)[0]
    w, h, depth = struct.unpack_from("<III", im, 0x18)
    n = w * h
    pix = im[0x28:0x28 + n]
    ncol = 256 if depth == 8 else 16
    pal = im[0x28 + n:0x28 + n + 4 * ncol]
    return w, h, b"".join(pal[4 * (p % ncol):4 * (p % ncol) + 4] for p in pix)


def glyphs(e, addr):
    out = []
    while True:
        r = struct.unpack_from("<5H", e.d, e.v2o(addr + 10 * len(out)))
        if r[0] == 0:
            return out
        out.append(r)


def f32s(e, addr, n):
    return list(struct.unpack_from("<%df" % n, e.d, e.v2o(addr)))


def rgba(e, addr):
    return list(e.d[e.v2o(addr):e.v2o(addr) + 4])


def font_json(e, sizes):
    g = {}
    for page, addr, tex in GLYPH_TABLES:
        for code, u, v, w, h in glyphs(e, addr):
            g.setdefault(str(code), [page, u, v, w, h, NUDGE.get(code, 0)])
    pal = [list(e.d[e.v2o(TEXT_PALETTE) + 4 * i:e.v2o(TEXT_PALETTE) + 4 * i + 4]) for i in range(10)]
    pages = {str(p): {"texture": t + ".png", "size": sizes[t]} for p, _, t in GLYPH_TABLES}
    return {"source": "g_FontGlyphs 0x005B8840, g_FontIconGlyphs 0x005CA210, g_FontCrimeGlyphs 0x005CA1F0, "
                      "g_TextPalette 0x005CA320 (docs/HUD.md)",
            "line_height": 24, "advance": GLYPH_ADVANCE, "pages": pages, "palette": pal, "glyphs": g,
            "name_font": {"texture": "name_font.png", "cell": 16, "first": 0x20, "columns": 16,
                          "draw_size": [22, 30], "rows": [[0, 6, 0x20], [8, 16, 0xA0]]}}


def hud_json(e):
    lay = [list(struct.unpack_from("<10h", e.d, e.v2o(PRIDE_LAYOUT + 0x14 * s))) for s in range(2)]
    sprites = []
    for i in range(24):
        o = e.v2o(HUD_SPRITES + 0x28 * i)
        grp, idx = struct.unpack_from("<2h", e.d, o)
        x, y, tw, th, u, v, w, h = struct.unpack_from("<8f", e.d, o + 8)
        sprites.append({"group": grp, "index": idx, "pos": [x, y], "tex": [tw, th], "uv": [u, v, w, h]})
    names = [rgba(e, HPBAR_NAME_COLOURS + 4 * i) for i in range(6)]
    return {
        "source": "docs/HUD.md (read from the code, positions not yet checked against the game on screen)",
        "screen": [640, 448],
        "hp_bar": {
            "k": f32s(e, HPBAR_K, 1)[0], "row_y": f32s(e, HPBAR_ROW_Y, 3), "row_y_add": 40.0,
            "party_scale": 0.7, "tex_wh": f32s(e, HPBAR_TEX_WH, 4),
            "frame_u": [[0, 10], [20, 70], [117, 11]], "fill_u": [[0, 2], [20, 70], [109, 2]],
            "frame_x": [30, 40], "fill_x": [37, 39], "side1_mirror": 640,
            "name_pos": [f32s(e, HPBAR_NAME_POS + 8 * i, 2) for i in range(6)], "name_side1_add": 104.0,
            "name_colours": names, "pulse": rgba(e, HPBAR_PULSE), "pulse_step": [22.5, 6.25], "pulse_frames": 7,
            "low_hp": 0.2, "order": list(struct.unpack_from("<4H", e.d, e.v2o(HPBAR_ORDER))),
            "colours": {k: rgba(e, a) for k, a in HPBAR_COLOURS.items()},
            "drain_div": 60, "pride_offset": 12.0,
        },
        "pride": {
            "layout": lay, "slide": f32s(e, PRIDE_SLIDE, 2), "slide_time": 0.2,
            "pieces": [  # PrideGauge_Build: [texture, u, v, w, h, layout offset index (into layout[2..9] pairs)]
                ["hud_tex02", 0, 96, 30, 32, -1], ["hud_tex03", 154, 0, 21, 8, 0], ["hud_tex02", 29, 112, 73, 16, 1],
                ["hud_tex03", 154, 8, 21, 8, 2]],
            "flame_size": [77, 16], "flame_offset": 3,
            "flame_frames": [[("hud_tex02" if i < 4 else "hud_tex03")] + f32s(e, PRIDE_FLAMES + 8 * i, 2)
                             for i in range(8)],
            "flame_scale": [1.3, 1.8], "flame_time": [0.05, 0.05],
            "negotiation": {"text": 10446, "text_on": 10447, "text_no": 10431, "pos": [590, 117],
                            "from_x": 790, "scale": 0.8},
        },
        "combo": {"frames": 40, "hits": sprites[0], "digits": sprites[12:22], "min_count": 2, "max": 99},
    }


def convert(iso, out):
    e = bdkit.Elf(os.path.join(iso, "SLUS_211.50"))
    graph = os.path.join(iso, "XAF", "GRAPH.XAF")
    ents = bdkit.xaf_entries(graph)
    d = os.path.join(out, "ui")
    os.makedirs(d, exist_ok=True)
    sizes = {}
    with open(graph, "rb") as f:
        for name, entry in TEXTURES.items():
            f.seek(ents[entry][1])
            w, h, px = graph_image(f.read(ents[entry][2]))
            write_png(os.path.join(d, name + ".png"), w, h, px)
            sizes[name] = [w, h]
    fj = font_json(e, sizes)
    for name, obj in (("font.json", fj), ("hud.json", hud_json(e))):
        with open(os.path.join(d, name), "w", encoding="utf-8", newline="\n") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
            f.write("\n")
    print(f"  ui: {len(TEXTURES)} textures, {len(fj['glyphs'])} glyphs, palette, HUD layout -> {d}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    convert(sys.argv[1], sys.argv[2])
