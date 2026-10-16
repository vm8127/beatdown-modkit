# Fight HUD, font and text colours

What Beat Down draws over a fight (HP bars, names, Pride gauge, combo counter) and how its text is drawn (font, colour palette, button icons). Researched 2026-10-16 for the remake's fight HUD (remake TODO "fight HUD"). **Read from the code and the disc** (decomp + ELF tables + GRAPH.XAF textures); **not compared with an emulator screenshot yet**, so positions are the code's constants, not checked on screen. Tools: the remake converter `remake/tools/conv_ui.py` writes everything below as PNG + JSON (`assets_ripped/ui/`).

Screen space: the HUD sprites (`Sprite2D_*`, `0x00334CD0` etc.) use a 640-wide screen with y in NTSC lines (about 448 high); the text boxes use a 640 x 480 layout squeezed to the field (`y' = (y - 16) x 0.4667`, `0x001B1310`). The remake draws both on a 640 x 448 canvas scaled to the window.

## GRAPH.XAF: the 2D textures

GRAPH.XAF (archive 2) is the game's 2D art: 602 entries, each one RenderWare Image chunk (0x18), a few with several. **Every entry has a name**: `g_GraphNames` `0x005AB0D0` (`g_ArchiveTexNames[2]`) is `{u32 0, char *name}` per entry, and entry n's name is row n (checked: 374 = `UNICODEFONT`, 32 = `BUTTON`, the font loaders ask for those ids). Some code finds textures by that name (`Tex_FindLoaded` `0x002C0E10` searches the loaded HUD groups `g_HudTexGroups` `0x006B6740`, 5 x 4).

**Palettes.** GRAPH's 8-bit images store their 256 colours in plain order (no CSM1 swap, unlike DATA.XAF's character textures: swapping scrambles them, checked on BUTTON, MURDER_01, MAP_PARTS02). Alpha is full range 0-255 (font: 0 or 255; BUTTON: soft edges). `bdkit.texture_png` (CSM1 swap, alpha x 2) is therefore wrong for GRAPH; `conv_ui.py` decodes them itself.

Entries used by the fight HUD and text (name = what the code asks for):

| Entry | Name | Size | What |
|---|---|---|---|
| 374 | UNICODEFONT | 512x512x4 | the text font, page 0: Latin, Latin-1, Latin Extended-A, punctuation, kana |
| 375-378 | UNICODEFONT_KANJI01-04 | 1024x1024x4 (378: 512) | font pages 1-4, kanji; loaded only when the language is Japanese |
| 32 | BUTTON | 256x128x8 | page 5: button and stick icons for the text (33-37 `BUTTON_XBOX*` are the Xbox version's) |
| 305 | MURDER_01 | 64x64x8 | page 6: ⑰ ⑱ (a sheriff's star and a skull with a knife), only while `0x002D86E0` has it loaded |
| 355 | SYSFONT02 | 256x256x4 | the HP bar's name font (RenderWare RtCharset grid, 16 x 16 cells from code 0x20, ASCII then Latin-1 from row 8; gold metal look) |
| 173 | GD_HPG_01 | 128x32x4 | HP bar frame |
| 174 | GD_HPG_02 | 64x32x4 | HP bar fill (white, tinted per layer) |
| 131 | FONT_TEX_02 (`_ESP` `_FRA` `_GER` `_ITA` 132-135) | 256x256x8 | READY, YOU LOSE, big digits, the Pride gauge's lighter and fuse, flame frames 0-3 |
| 136 | FONT_TEX_03 (137-140) | 256x128x8 | flame frames 4-7, money digits and $, ESCAPED!, **HITS** and its digits, min / sec |
| 176-180 | GD_NGI_00-04 | 64x64x4 | the negotiation X marks |
| 525 | VS_PARTS_02 (526-529) | 32x128x4 | 1P / 2P / CPU1 / CPU2 / CPU markers over fighters |
| 84 | CURSOR | 256x32x4 | 8-frame spinning arrow (target marker) |
| 2-18 | BA_PARTS* | various | BATTLE RESULT panel (2 = the clipboard sheet, 18 = its clip, 6 = a highlight bar, 7-17 small digits) |

`Hud_LoadTextures` `0x00317F50` loads the HP bar set into `g_HudTex` `0x00737050` (10: GD_HPG_01, GD_HPG_02, MAP_BG (by language), MAP_MASK, MAP_PARTS01, MAP_PARTS02, SYSFONT02, GD_NGI_00, CURSOR, VS_PARTS_02 (by language)); `Hud_TexturesReady` `0x00318270` collects them. The Pride gauge takes FONT_TEX_02/03 by name (`PrideGauge_Init` `0x001C3210`, language suffix `_ESP` 4, `_FRA` 2... from `g_SystemData.language`).

## The text font

`Font_Load` `0x002C4090` requests GRAPH 374 (and 375-378 for Japanese, else pages 1-4 = page 0) and passes them to `Font_SetPages` `0x001B7D30` (`g_FontPages` `0x00662900`, 7 pointers: 0-4 font pages, 5 icons from `Font_SetIconPage` `0x001B7D60`, 6 ⑰⑱).

**Glyph tables** (ELF data; record `{u16 code, u16 u, u16 v, u16 w, u16 h}`, ends at code 0; dumped by `conv_ui.py`):

| Table | Address | Records | Page / texture |
|---|---|---|---|
| `g_FontGlyphs` | `0x005B8840` | 520 | 0, UNICODEFONT 512 x 512: every glyph 24 high, w 5-24 |
| `g_FontKanji1`-`4` | `0x005B9CA0`, `0x005BF050`, `0x005C4400`, `0x005C97B0` | 2140, 2140, 2140, 261 | 1-4 (code ranges 0x4E00-0x64FE, 0x6500-0x7E39, 0x7E3A-0x9B2E, 0x9B2F-0x9FA0) |
| `g_FontCrimeGlyphs` | `0x005CA1F0` | 2 | 6: ⑰ (0,0,32,32), ⑱ (0,32,32,32) |
| `g_FontIconGlyphs` | `0x005CA210` | 25 | 5, BUTTON 256 x 128 |

**Codes.** `Text_Encode` turns UTF-8 into 16-bit codes that are **Unicode code points** for everything but kanji: full-width ASCII U+FF01-FF5E becomes 0x21-0x7E, the ideographic space U+3000 stays 0x3000, Latin-1 and Latin Extended-A keep their code points, kana too; kanji get packed codes. So the remake can key glyphs by Unicode.

**Layout** (`Text_Layout` `0x001B1850`, per glyph `Text_GlyphQuad` `0x001B1310`): a glyph is looked up in the table of its range (icons: ←↑→↓ ㊤-㊨ ○△□× ●▲■Ⅹ ①-⑥ α β ∬ go to page 5; ⑰ ⑱ to page 6 when loaded), drawn w x h from (u, v), **advance = w x 0.95** (the quad is also drawn 0.95 wide), line height = the tallest glyph of the line (24). Icons are nudged vertically: ①-⑥ and the face buttons +2, ㊤-㊨ ←↑→↓ ∬ -1, ⑰ ⑱ -4, α β -6; everything +6 on NTSC (`g_SystemData +0x40` = 0). Box scale (`+0x20`, `+0x24`), rotation (`+0x28`, degrees), position (`+0x0C`, `+0x10`) and centring flags (`+0x08` bits 1/2 horizontal, 0x10/0x20 vertical) come from the text box record (`g_TextBoxes` `0x00662960`, 0x308 bytes each, index 1-127).

**Colour palette** (`g_TextPalette` `0x005CA320`, RGBA; `@N` / `$N` stores N as the colour byte of the following characters; 0 = the box's own colour at box `+0x34`):

| N | RGBA | |
|---|---|---|
| 0 | box colour | default (white in most boxes) |
| 1 | 255 255 255 255 | white |
| 2 | 255 0 0 255 | red |
| 3 | 0 255 0 255 | green |
| 4 | 0 0 255 255 | blue |
| 5 | 241 95 93 255 | light red |
| 6 | 255 255 95 255 | yellow (English: names, places) |
| 7 | 233 166 214 255 | pink |
| 8 | 113 238 200 255 | mint (English: items, keywords) |
| 9 | 0 0 0 0 | invisible |

Entries 10-15 are zero or garbage (alpha 0); no text uses them. The colour multiplies the glyph (white fill, black outline), so the outline stays black.

**Button icons** (BUTTON, `g_FontIconGlyphs`; the physical buttons, read from the picture):

| Glyph | Picture | Used for (FORMATS.md, "Text") |
|---|---|---|
| ○ △ □ × | face buttons, outline | fixed buttons; 〆 ◎ ◇ ▽ and ♯ ♭ ♪ map to these |
| ● ▲ ■ Ⅹ | the same, lit (pink) | the "pressed" forms |
| ① | **L1** | ① + stick = RUN |
| ② | **L2** | use equipped item |
| ④ | **R1** | grab / pick up |
| ⑤ | **R2** | use equipped item |
| ③ | **L3** (stick click) | |
| ⑥ | **R3** (stick click) | taunt |
| α β | **START** | open a menu |
| ∬ | the yellow circular arrow | rapid press / rotate |
| ← ↑ → ↓ | the d-pad with that direction lit | MOVE LIST directions |
| ㊧ ㊤ ㊨ ㊦ | the left stick pushed left / up / right / down | |
| ⑰ ⑱ | sheriff's star / skull with a knife (MURDER_01) | crime icons; not drawn when that texture isn't loaded |

Unused cells of BUTTON: SELECT, a lit R1, small arrows, three dots, plain sticks.

## HP bars

Per frame in a battle `Hud_BattleUpdate` `0x0031A2C0` runs, for each side (0 = the player's team on the left, 1 = the enemy team on the right): `HpBar_SyncMax` `0x0031AAF0`, `HpBar_TrackHP` `0x0031AD30`, `HpBar_Drain` `0x0031B010`, `HpBar_BuildQuads` `0x00318560`, `HpBar_PlaceNames` `0x0031B4A0`; then the Pride gauge. `HpBar_Draw` `0x0031A400` draws them. A side shows one bar per team member (up to 3; `Team_GetMember`); member 0 is the fighter on screen (side 1: the current target), the others read their person's HP.

**State** (`g_HpBars` `0x00732260`, 2 sides x 3 members x 0x28): `+0` max HP, `+4` **trail** (the shown value), `+8` HP, `+0xC` last damage, `+0x10` HP before it, `+0x14` trail left to drain, `+0x18` HP x 128 / max, `+0x1C` trail x 128 / max.

**Damage trail** (`HpBar_TrackHP`, `HpBar_Drain`): when HP changes, `+0x14` += the damage; then every frame, while `+0x14` > 0, `step = max(1, (trail - HP) / 60)` (integer), trail -= step, `+0x14` -= step; once it's 0 the trail snaps to HP. So the trail falls 1/60 of the gap per frame (fast at first, slowing down) until the damage is used up. Healing snaps (`+0x14` goes negative).

**Size** (`HpBar_LayerQuads` `0x0031BFE0`): the bar's length follows max HP: `k = 0.018` (`gp-0x6930`), the stretched middle is `1.4 x value x k` pixels (`0.0252` px per HP: 3000 HP = 75.6 px, 9999 = 252 px). Members 1-2 are drawn at 0.7 scale (length and height).

**Four layers**, each three quads (left cap, stretched middle, right cap), in draw order (`g_HpBarLayerOrder` `0x005D4378`: 1000, 1050, 1100, 1200):

| Layer | Texture, u ranges (cap / middle / cap) | Length from | Colour (RGBA) |
|---|---|---|---|
| 3 back | GD_HPG_02, 0-2 / 20-90 / 109-111 (of 111) | max HP | black 0 0 0 |
| 1 trail | GD_HPG_02 | trail | side 0: 255 32 32 (member 0; members 1-2: alpha 0, no trail); side 1: 160 190 255 |
| 2 HP | GD_HPG_02 | HP | side 0: cyan 0 255 255; side 1: magenta 255 0 190 (persons with `PersonDef +0xB` = 0) or orange 255 192 0 (the others); **at 20 % HP or less**: the pulse colour |
| 0 frame | GD_HPG_01, 0-10 / 20-90 / 117-128 (of 128) | max HP x k - 2 | white (texture as is) |

**Low-HP pulse** (`HpBar_BuildQuads`): base 255 180 50; a counter runs 0 -> 7 -> 0 one step a frame (8 on PAL), and the colour is `(255, 180 - 22.5 n, 50 - 6.25 n)` (PAL 25.7 / 7.14): orange to red and back about every 14 frames.

**Position** (side 0, member 0, top-left of the quads, 32 high): frame left cap at x 30, its middle from 40, its right cap at `40 + 1.4 x (max x k - 2)`, 11 wide; back / trail / HP caps 2 wide at x 37, middle from 39. y = 47 + 40 = 87 for member 0, 81 + 40 = 121 and 109 + 40 = 149 for members 1 and 2 (`0x00516960`), plus 12 for members 1-2 while the Pride gauge is up (`gp-0x4D18`, eased in over 0.2 s by `0x0031CF20`). Side 1 mirrors it: the caps are drawn flipped and anchored to `576 + ...` so the bars grow leftwards from x ~ 610. The frame's visible metal is rows 7-25 of its 32.

**Names** (`HpBar_Build` `0x0031B210`): each member's `Fighter_DisplayName` in SYSFONT02, cells 22 x 30, converted to ASCII (`Text_ToAscii`). Positions (`0x00516930`): side 0 (46, 75), (46, 105), (46, 133); side 1 (593.6, same y's) (`489.6 + 104`). Colours (`gp-0x6918`): side 0 white; side 1 white for member 0 when its person has `PersonDef +0xB` = 0, else 170 191 201. **No level, money or TIRED** is drawn in a fight.

## Pride gauge

Only when `Battle_PrideHudShown` (story mode, not a group fight). `Battle_Start` `0x002DCF60` calls `PrideGauge_Init` `0x001C3210` and `PrideGauge_Reset` `0x001C34C0(ratio, side)` for both fighters; each frame `Hud_BattleUpdate` passes `Fighter_GetPrideRatio` to `PrideGauge_SetRatio` `0x001C3440(ratio, side)` and runs `PrideGauge_Update` `0x001C33D0` (`PrideGauge_Side` `0x001C29F0` per side: a state machine 0-10; `g_PrideGauge` `0x00685110`, 2 x 0x4C).

It is a **lighter with a burning fuse**: six sprites per side (`PrideGauge_Build` `0x001C20D0`; layout `g_PrideGaugeLayout` `0x005CA830`, side 0 at (20, 105), side 1 at (591, 105) mirrored):

| Sprite | Offset (side 0) | Texture, u v w h |
|---|---|---|
| lighter | 0, 0 | FONT_TEX_02, 0 96 30 32 |
| cap | 10, -1 | FONT_TEX_03, 154 0 21 8 |
| fuse | 29, 15 | FONT_TEX_02, 29 112 73 16 |
| fuse end | 123, 16 | FONT_TEX_03, 154 8 21 8 |
| flames (frames 0-3) | 29, 5 | FONT_TEX_02, 77 x 16 at (102, 96) (179, 96) (102, 112) (179, 112) |
| flames (frames 4-7) | 29, 5 | FONT_TEX_03, 77 x 16 at (0, 0) (77, 0) (179, 96) (179, 112) |

Side 1 offsets: (-2, -1), (-94, 15), (-112, 16), (-100, 5), all flipped. **The flames are the gauge** (`PrideGauge_Flames` `0x001C2720`): scaled `ratio x 1.3` wide and `ratio x 1.8` high from the fuse's left end, cycling 8 frames, the next frame after `(1 - ratio) x 0.05 + 0.05` seconds (faster when Pride is high). At 0 Pride the flame is gone. The gauge slides in 200 px from the side over 0.2 s and out the same way.

**Empty Pride, side 1**: the enemy's side shows "NEGOTIATION OK!" + the special button (text 10446), blinking with the pressed form (10447) at 0.8 scale, sliding in from x 790 to 590, y 117 (`PrideGauge_Side` states 6.1-6.8; 10431 "NEGOTIATION" in a battle where `0x002DE500` says no).

## Combo counter

`Hud_ComboWatch` `0x0031BA50` watches the player's `Fighter.combo_hits` (`+0x450E`, the **attacker's** running hit count: `Fighter_AddComboHit` `0x002FC290` adds 1 per landed hit and keeps the "Biggest combo" record `0x0060D17C`; `Fighter_ResetCombo` `0x002FC260`). When it changes and is 2 or more, `Combo_Show` `0x002BD150(count, side)` starts a 40-frame task (`Combo_TaskLeft` `0x002BFD50` -> `Combo_DrawLeft` `0x002BED10`; side 1 = `0x002BFE60` / `0x002BF4B0`, only in VS-type battles). It draws the count (1-2 digits, max 99) in FONT_TEX_03's cyan digits (25 x 32 at (25 n, 64)) and **HITS** (175, 42, 81 x 22), sprite records `g_HudSprites` `0x00505920` (0x28 each: texture group/index, a default x y, texture size, u v w h).

Animation over its 40 frames f: the whole counter fades `alpha = (1 - 0.025 f) x 255`; for f < 15 the digits are drawn at 1.333 scale sliding in by `(10 - f) x 8` px and HITS slides by `8 f`; from f = 15 on, everything grows `1 + 0.025 f` and fades `255 - 6 f`. Position (side 0): digits around x 57-80, y 104 + 40 + 16; HITS to their right around x 90, y 109 + 40 + 11; 25 px lower per extra party member (`g_Party[1]`, `[2]`), 45 more in some team modes.

## TIRED

**Not on the HUD** (only `Debug_FighterInfo`). Read from `Fighter_StartAction` `0x00307E40` and `Fighter_TaskAction` `0x0030AEB0`: each action adds its cost to `tired` (`+0x442A`) and to a running total `+0x442E`; every 0.5 s (timer `+0x4430`) `tired` drops by 1 down to a floor `tired_max x (1 - f)`, where f (`+0x44E0`, the TIRED entry of the per-limb fatigue floats) starts at 1 (floor 0) and drops by 0.1, to 0.5 at least, each time the total passes another multiple of `tired_max`. So a long fight leaves a growing part of the meter permanently full. What a full meter does is still open. The remake shows it as a thin extra bar under the HP bar (remake-only, marked as such).

## Open questions

- Compare every position above with an emulator screenshot of a story fight (player alone, then with two party members) and a VS fight.
- The HP bar's quad origin (top-left assumed) and whether the names' y is the text's top or centre.
- `PersonDef +0xB`: which people get the magenta enemy bar (bosses / named characters?).
- What a full TIRED meter does; the initial value of `+0x44E0`.
- `0x002DE500` (NEGOTIATION vs NEGOTIATION OK!).
- The combo counter's exact positions (half the sprite's w / h are used as offsets; not checked on screen).
- The text box default colour (box `+0x34`) per box kind.
