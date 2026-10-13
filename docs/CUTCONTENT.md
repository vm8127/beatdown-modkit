# Cut content and unreachable code

What the US release (SLUS-21150) still carries that normal play can't reach, how each piece was found, and how to bring it back. The cheats named here are sections in `mods/SLUS-21150_C9F6EF9A.pnach`. **None of them has been tested in-game yet.**

Confidence words: **confirmed** = read in the code or data; **probably** = inferred from the code, not run.

## Contents

1. [Summary](#summary)
2. [DEBUG item on the title menu](#debug-item-on-the-title-menu)
3. [The DEBUG menu: scene player and language select](#the-debug-menu-scene-player-and-language-select)
4. [Labels for debug tools that were removed](#labels-for-debug-tools-that-were-removed)
5. [Developer debug switches](#developer-debug-switches)
6. [Options: DIFFICULTY and the other hidden items](#options-difficulty-and-the-other-hidden-items)
7. [Unused fighting styles and classes](#unused-fighting-styles-and-classes)
8. [Debug shop picker](#debug-shop-picker)
9. [Leftover text](#leftover-text)
10. [Leftover assets](#leftover-assets)
11. [Unreferenced code](#unreferenced-code)
12. [Corrections to other docs](#corrections-to-other-docs)
13. [How this was searched](#how-this-was-searched)

## Summary

| Find | Status | Cheat |
|---|---|---|
| DEBUG item on the title menu, and the DEBUG menu behind it (scene player, language select) | Code and data complete, only the menu entry is missing (**confirmed**) | `Cut content: DEBUG on the title screen` |
| Language select limited to Japanese and English; French, German, Spanish and Italian text is on the disc | **confirmed** | `Cut content: all six languages in the debug LANGUAGE menu` |
| Developer debug switch table with nothing writing it; switch 5 = fighter info overlay, fast movement, collision skip | **probably** (read in code) | `Cut content: developer debug mode (switch 5)` |
| DIFFICULTY option: shown on the title-screen OPTIONS by the data, hidden in the pause menu | **probably**; conflicts with what was seen in-game, needs a check | `Cut content: DIFFICULTY in the pause menu options` |
| TESTER style 0x09 (67 commands) and TESTER S/M/L classes, used by no fighter | **confirmed** | `Aaron uses the cut TESTER moveset` |
| Eight short generic styles 0x1C-0x23 with command lists, used by no class | **confirmed** | `Cut content: boxers use the short boxer style 0x1C` |
| Classes no fighter record uses: PERFECT, JUGGLER_L, STRIDER_L, POLICE_S, POLICE_M | **confirmed** | swap-moveset recipe |
| Labels for 7 removed debug tools (SCRIPT VIEWER, ARCHIVE MAKER, SCENE EDITOR, ...) | Text only; code is gone | none |
| Debug shop picker "[SELECT SHOP]" | Code present, only reached with no shop number set | none yet |
| Dummy items, "???" item descriptions, Xbox texts, test graphics (END_BGTEST_A/B, CHS_NTEST01, WIN_TEST) | Data only | none |

## DEBUG item on the title menu

**Confirmed.** The title screen (`Title_Main` `0x0033D7A0`, drawn by `Title_DrawMenu` `0x0033E980`) builds its menu from three tables:

| Table | Address | Format |
|---|---|---|
| Menu items | `0x00589680` | 5 x `{s16 element, s16 enabled, s16 action, s16 0}`, then `-1` |
| Elements | `0x00589760` | 8 x 20 bytes `{float x, float y, float scale, u16 label, u16 0, u32 colour ptr}` |
| Label text IDs | `0x00589740` | `u16` per label; 0 means "use the ASCII string" |
| ASCII labels | `0x00589710` | `PRESS START BUTTON, NEW GAME, LOAD GAME, VS MODE NORMAL, VS MODE CUSTOM, OPTIONS, DEBUG, DEBUG` |
| Action handlers | `0x005D7890` | 6 handlers: 0 NEW GAME, 1 LOAD GAME, 2 and 3 VS MODE (`VsMode_Main` `0x00340C60`), 4 OPTIONS, **5 DEBUG** (`0x0033DE38`) |

The menu list has five items (actions 0-4). Element 7 is still laid out (label 7 = "DEBUG", at y 403, under OPTIONS), its text ID is 0 so it falls back to the ASCII "DEBUG", and handler 5 still starts the debug menu. Only the menu item was removed. The item count 5 is also hard-coded in at least six places (`0x33D96C`, `0x33DAE0`, `0x33DBB0`, `0x33E448`, `0x33E574`, `0x33EACC`), so adding a sixth item means patching all of them.

**Restore (cheat):** the simplest safe change is to reuse the VS MODE CUSTOM slot: set its action to 5 and its element's label to 7.

```
patch=1,EE,2058969C,extended,00000005   menu item 3: action 3 -> 5 (DEBUG)
patch=1,EE,205897D0,extended,00000007   element 5 label: 5 -> 7 ("DEBUG")
```

VS MODE NORMAL is untouched. Turn the cheat off to get VS MODE CUSTOM back.

## The DEBUG menu: scene player and language select

**Confirmed.** `DebugMenu_Main` `0x00340220` (drawn by `0x00340020`) has three items in `g_DebugMenuItems` `0x005899E0`, 24 bytes each `{u32 handler, float x, float y, float scale, u16 text id, ...}`:

| Item | Text ID | Handler | What it does |
|---|---|---|---|
| SCENE PLAYER | `0x2946` | `ScenePlayer_Main` `0x001C89A0` | Plays any FSCENE.XAF cutscene: SELECT SCENE (number), SELECT PLAYER (hero), SELECT LANGUAGE, PLAY, EXIT, with a LOOP counter. The OPTIONS menu's MOVIE VIEWER also uses this player, but there you only get unlocked scenes. |
| LANGUAGE | `0x294C` | `DebugLanguage_Main` `0x003B7400` | Writes the language byte `0x0060C710` (g_SystemData +0x10) and reloads the text |
| EXIT | `0x294B` | `Title_Main` `0x0033D7A0` | Back to the title |

Up/down moves the cursor, ○ runs the item.

### Language select

The language list `0x005AC3A0` has six entries (text IDs `0x294D`-`0x2952`: JAPANESE, ENGLISH, FRANCE, GERMANY, SPAIN, ITALY), matching the six text banks in CDATA.XAF (JP, EN, FR, DE, ES, IT), but the cursor is clamped to the first two (`slti v0,v0,2` at `0x003B75F0`, wrap to 1 at `0x003B75D0`). The value written is the list index: 0 Japanese, 1 English, 2 French, 3 German, 4 Spanish, 5 Italian. GRAPH.XAF also has `_ESP`/`_FRA`/`_GER`/`_ITA` versions of the logos and menu pictures.

**Restore (cheat):** `Cut content: all six languages in the debug LANGUAGE menu` lifts the clamp:

```
patch=1,EE,203B75F0,extended,28420006   slti v0,v0,6
patch=1,EE,203B75D0,extended,24020005   wrap to 5
```

A pnach can also set the language directly with `patch=1,EE,0060C710,extended,000000XX` (8-bit), but the text is loaded at boot, so the menu route is more likely to work. Japanese needs the kanji font, which is on the disc (`UNICODEFONT_KANJI01-04`).

## Labels for debug tools that were removed

**Confirmed, text only.** The UI text bank (CDATA.XAF entry 386 for English) has labels for developer tools next to the three that survived:

| Text ID | Label |
|---|---|
| `0x2941`, `0x2942` | "↑↓ An item is chosen", "○ An item is executed" (menu help) |
| `0x2943` | SCRIPT VIEWER |
| `0x2944` | ARCHIVE MAKER |
| `0x2945` | SCENE EDITOR |
| `0x2947` | EVENT TEST |
| `0x2948` | MEMORY LEAK CHECKER |
| `0x2949` | NPCSET |
| `0x294A` | ARCHIVE LOWPOLYMODEL |

No code uses these IDs, so the tools themselves were cut. The ELF still has the scene editor's file paths (`./SceneEditor/data/scene/`, `camera/`, `model/`, `motion/`, `music/`, `light/`, `caption/`, `sound\` near `0x005B3830`) and its whole `@`-command vocabulary (`@VIEWANGLE`, `@CAPTION`, `@MORPH`, ...), because the retail scene player reads the same script format. A `FREE MEMORY CHECK [%s]` printer (`0x005CEBB0`) is probably what the memory leak checker used.

## Developer debug switches

**Probably.** `g_DebugSwitches` `0x00599000` is 48 u32 switches read only by `Debug_GetSwitch` `0x0039BA00` (`n -> switch[n] != 0`). No code writes them, so they are compile-time settings. In the retail ELF, switches 1-3 are 100 and 6, 11, 23, 26, 30, 39, 40 and 41 are 1. The code checks switches 5, 8, 10, 11, 16, 17, 18 and 39.

**Switch 5 is a developer debug mode.** With it on (from the code, not run yet):

| Effect | Where | Buttons |
|---|---|---|
| Fighter info overlay in fights: `Debug_FighterInfo` `0x00302260` (HP, DAMAGE, TIRED, REV, LENGTH, motion state), 10 pages | `0x0030B1C4` | hold L2 and click L3 to change page |
| Faster movement: speed x2.45 and a value of 2.72 at fighter +0x3FE8 | `0x0030CCEC` | hold R1 |
| Three collision-type checks return "no hit" early (probably walking through walls or objects) | `0x00160790`, `0x003D19E0`, `0x003D1B70` | hold L1 + R1 + Square (or L3) |

The buttons come from `Pad_RemapButtons` `0x001D02B0`, which turns the raw pad into the game's own bits (held at `0x00685454`, newly pressed at `0x00685458`): Left 1, Right 2, Up 4, Down 8, Start 0x10, Select 0x20, Triangle 0x40, Cross 0x80, Square 0x100, Circle 0x200, L1 0x400, L2 0x800, R1 0x1000, R2 0x2000, L3 0x4000, R3 0x8000.

**Restore (cheat):** `Cut content: developer debug mode (switch 5)` = `patch=1,EE,20599014,extended,00000001`.

Other switches, not traced further: 17 passes pad 2's state (`0x006854D0`) to the fighter input routine `0x0030A5A0` at `0x0030B068` (maybe driving a fighter from the second controller); 10 adds a call to `0x001C8270` before `0x002B2610` (`0x002C9820`) and gates a block at `0x0032258C`; 8, 16, 18 and 39 are each checked once (`0x0031676C`, `0x002E3E88`, `0x0019F37C`, `0x001BD34C`). These are good next targets: set switch n with a 32-bit write to `0x00599000 + 4n` and watch what changes.

## Options: DIFFICULTY and the other hidden items

Options are pages of 16 x 32-byte records from `g_OptionPages` `0x00509D90` (pages `0x200` apart). `Options_SetMode` `0x002E9590` is called with 0 from the title screen (`0x0033DEF8`) and 1 from the in-game menu (`0x001A37B4`, called from `0x001A2620`; probably the pause menu), and every list routine checks byte `+26 + mode`. So **byte +26 = shown on the title-screen OPTIONS, +27 = shown on the pause-menu options** (**confirmed** in the code).

Page 0 (OPTIONS):

| Item | Record | Title (+26) | Pause (+27) |
|---|---|---|---|
| DIFFICULTY | `0x509D90` | 1 | **0** |
| SUBTITLES, MAP, GAGE | `0x509DB0`-`0x509DF0` | 1 | 1 |
| BLOOD (MALE), BLOOD (FEMALE), BRUISING (MALE), BRUISING (FEMALE) | `0x509E10`-`0x509E70` | 1 | **0** |
| AUDIO CONFIG, CONTROL CONFIG, SCREEN ADJUST, BRIGHTNESS | `0x509E90`-`0x509EF0` | 1 | 1 |
| MOVIE VIEWER | `0x509F10` | 1 (only once `0x0013D9E0(1)` is set, `0x002E9EB0`) | **0** |
| DEFAULT SETTING, EXIT | `0x509F30`, `0x509F50` | 1 | 1 |

Every item has +26 = 1, so **by the code DIFFICULTY should be in the title-screen OPTIONS**. That conflicts with MECHANICS.md ("hidden option") and with what was seen in-game, which may have been the pause menu. **Please check OPTIONS from the title screen.** If DIFFICULTY is there, it isn't cut, just missing from the pause menu. If it isn't, something else hides it and this needs another look.

**Restore (cheat):** `Cut content: DIFFICULTY in the pause menu options` sets DIFFICULTY's +27 to 1 (`patch=1,EE,20509DA8,extended,01010100`). The same works for the blood and bruising items (+27 at `0x509E2B`, `0x509E4B`, `0x509E6B`, `0x509E8B`). Setting difficulty directly: `patch=1,EE,0060C704,extended,000000XX` (1 EASY, 2 NORMAL, 3 HARD).

Bytes +24 and +25 are never read by the option code.

## Unused fighting styles and classes

All **confirmed** against the class table `0x0050D6A0`, the fighter records (`dumps/fighters.txt`) and `Fighter_GetStyle` `0x002F8E00`, which always uses the class row's style (no code picks a different style at run time).

### TESTER, style 0x09

Classes TESTER_M (type 40), TESTER_S (45) and TESTER_L (46) use style `0x09` with animation group 174 (STAGE.XAF pack 109, 83 animations, all shared with other groups). No fighter record uses them, and style 0x09 is the only one without a MOVE LIST entry (`0xFFFF` in `0x005CAB40`). Its command list (`0x005D10B0`, 67 commands, see `dumps/commands.txt`) is a developers' test kit: one or two moves from many styles, from a 90-damage jab up to two 1000-damage actions (760), grabs and rear grabs.

**Restore (cheat):** `Aaron uses the cut TESTER moveset` (made with `python tools/bdkit.py swap-moveset ISO/SLUS_211.50 AARON TESTER_M`; both medium bodies). It writes Aaron's row like the other Aaron cheats, so only one at a time.

### Short generic styles 0x1C-0x23

Eight styles with real command lists and MOVE LIST pages that no class row points to. Each is a 2-8 move cut-down version of a generic enemy style (only the opening moves plus two shared actions, 17 and 120), possibly for weak or tutorial enemies:

| Style | Shortens | Moves | Animation group of the full style |
|---|---|---|---|
| `0x1C` | BOXER `0x01` | Jab, Boxer Step, Punch Combo, Left Hook Combo, Uppercut Combo | 166 |
| `0x1D` | GRAPPLER `0x02` | Lariat, Front Kick, Belly to Belly Suplex, Scissors Kick | 167 |
| `0x1E` | KNUCKLEMASTER `0x03` | Shoda, Senkyaku, Rensho, Renken, Renkentetsui | 168 |
| `0x1F` | JUGGLER `0x04` | Spin Cycle, Back Flip, Side Roll, Jump Roll, Trick Combo | 169 |
| `0x20` | KICKBOXER `0x05` | Straight, High Kick, Rolling Kick Combo, Magnum Blow, Flying Kick | 170 |
| `0x21` | STRIDER `0x06` | Slide Attack, Slide Kick, Needle Attack, Screw Dive, Javelin Kick | 171 |
| `0x22` | WEAPONMASTER `0x07` | Chop, Low Kick | 172 |
| `0x23` | NEGOTIATER `0x08` | Slap, Thrust Kick | 173 |

**Restore:** point a class row's style (+4) at the short style and keep the row's groups (which already include the full style's group). Example cheat `Cut content: boxers use the short boxer style 0x1C` does it for BOXER_S/M/L (`0x50D6A4`, `0x50D6B4`, `0x50D6C4`).

Styles `0x25`-`0x2F` are different: they only exist as MOVE LIST text (Weapon Combo 1-7). `g_StyleCommands` stops at `0x24`, so they have no command lists; weapon moves come from `Style_GetWeaponCommandList` `0x00317BE0`. Whether the MOVE LIST screen ever shows those pages wasn't checked.

### Classes no fighter uses

PERFECT (type 31: JUGGLER style 0x04 on a medium body, but it loads every generic move group 166-173 and 178 plus all three body sets), JUGGLER_L, STRIDER_L, POLICE_S and POLICE_M. No fighter record points at them, and the VS MODE roster (`g_VsRoster` `0x00589A40`, 84 fighter IDs) only lists fighter records. JUGGLER_L, STRIDER_L and the police rows are ordinary rows that just weren't used. PERFECT looks like a test class. To try one, give a hero its moves with `swap-moveset` (PERFECT is medium, so `swap-moveset ... AARON PERFECT` is a plain swap).

## Debug shop picker

**Confirmed in code.** `Debug_ShopSelect` `0x003340D0` ("[SELECT SHOP]", "NUMBER:%02d", "LEVEL : %d") is called from the shop scene `0x003348A0` only when the shop number at `gp-26460` (`0x005FE494`) is negative, which normal entry never does. It was probably reached from the removed EVENT TEST tool. Not restored yet: entering a shop with that value forced to -1 should show it.

## Leftover text

From CDATA.XAF entries 386 (UI) and 392 (items), English bank:

- Item names `WEAPON:(DUMMY 06)`, `(DUMMY 07)`, `(DUMMY 08)`, `(DUMMY 24)`, `(DUMMY 37)`, `(DUMMY 41)`-`(DUMMY 44)`, `(DUMMY 46)` (`0x3075`-`0x309D`): empty weapon slots between real weapons, and `OTHER:(NOITEM)` (`0x30C6`).
- Item help with no description: `R DRUG - ???`, `DISCOUNT MED - ???`, `HEATDOWN - ???`, `BOILERMAKER - ???`, `BACKFIRE - ???`, `DRAFT BEER - ???`, `ODD DRINK - ???`. HEATDOWN, BOILERMAKER, BACKFIRE, DRAFT BEER and ODD DRINK have no item name entry of their own in the list at `0x3000`-`0x3013`, so they may be cut drinks. Also `LIFE +16`, `MAXLIFE +16`, `PRIDE +16` (`0x30DB`-`0x30DD`), which read like debug items.
- Unusual item names worth tracing: `BLUE GUN`, `SPY GUN`, `M.GUN PARTS`, `CROWN TABLET`, `UDON FLOUR`, `BUTTER`, `JUNK No.1`-`No.15`.
- Speaker names `????` (`0x2B97`, `0x2B98`) and `Dummy` (`0x2B9F`, `0x2BA0`), and a place called `Dummy Downtown ST.` (`0x56BA`, `0x56BB`).
- Xbox texts left in the PS2 build: "Now checking... remove any Xbox memory units" (`0x4A91`, `0x6205`, `0x6594`), "Press A to continue" (`0x4AA1`).

All six languages have the same set of IDs (no Japanese-only lines).

## Leftover assets

GRAPH.XAF entry names come from `g_GraphNames` `0x005AB0D0` (602 entries). Entries are loaded by number, so which ones are never loaded isn't known yet; these names stand out:

| Entry | Name | Note |
|---|---|---|
| 118, 119 | `END_BGTEST_A`, `END_BGTEST_B` | test versions of the 15 ending backgrounds `END_BG01`-`END_BG15` |
| 78 | `CHS_NTEST01` | test picture among the character select parts |
| (outfit list) | `WIN_TEST` | name in the outfit part list near `0x005F3118` (ARCHIVE.XAF side) |
| 33-37, 86, 319 | `BUTTON_XBOX*`, `DOLBY_ROGO_X`, `OPT_PARTS_01_X` | Xbox button and logo graphics |

Others: SCRIPT.XAF has 172 identical 964-byte entries (504 onward) that look like empty mission script slots, and a run of 15 identical scripts (485-499). FSCENE.XAF cutscenes 153 and 154 have models named "Dummy1"-"Dummy3". STAGE.XAF entry 0 (a lone animation) isn't in the animation group table; entry 317 is loaded directly by number.

## Unreferenced code

A pass over the whole ELF (every `jal`, `j`, `lui`+`addiu`/`ori` pair and every data word pointing into code, against every function start) found about 820 functions with no reference at all. Nearly all are in the middleware between `0x001E0000` and `0x0029B000` (the 3D engine and library code, normal for a static link), plus Sony library code. The game's own code (`0x0029B000`-`0x0040D880`) has only a handful of small unused helpers (`0x0029B738`, `0x00348E88`, `0x003490E0`, `0x00360A38`-`0x00361060`). So the cut content lives in data and in reachable code behind disabled entries (the DEBUG item, the debug switches), not in dead functions.

## Corrections to other docs

- `0x00340C60` is the VS MODE screen (`VsMode_Main`: CHARACTER SELECT `0x003404B0`, STAGE SELECT `0x003409C0`), not the save/load screen. CODEMAP.md and symbols.tsv are updated.
- CDATA.XAF entries 415-420 aren't blank: they hold the town rumours and hints. CODEMAP.md is updated.
- DIFFICULTY: see [Options](#options-difficulty-and-the-other-hidden-items). MECHANICS.md now points here.

## How this was searched

- Disassembly: `mips-linux-gnu-objdump -z -D -b binary -m mips:5900 -EL --adjust-vma=0xFFF80 ISO/SLUS_211.50`, plus small Python scripts for cross-references (all `jal`/`j` targets, `lui`+`addiu` address pairs and data words pointing into code) and function starts (after each `jr ra`).
- Every ASCII string in the ELF's data, searched for debug, test, select, dummy and menu words, then traced to the code that uses it.
- All eight English text banks, checked for dev words and compared with the Japanese and French banks.
- Class rows against fighter records and the VS roster; style command lists against class rows; animation groups against STAGE.XAF.
- New names are in `symbols/symbols.tsv` (regenerated with `python tools/codemap.py symbols ISO/SLUS_211.50 symbols`).
