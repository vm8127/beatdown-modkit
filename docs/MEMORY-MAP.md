# Memory used by our cheats

Which addresses every cheat in `mods/SLUS-21150_C9F6EF9A.pnach` writes, which free code space ("caves") is taken and what's left, and which cheats can't be on together. Read this before a new mod picks an address, and update it in the same commit.

Regenerate the per-cheat list with:

```
python tools/codemap.py pnach-map mods/SLUS-21150_C9F6EF9A.pnach
```

It prints every section's address ranges and every pair of sections that write the same bytes.

## Free RAM: the mod areas

The game never uses EE RAM below its own program (it loads at `0x00100000`) above `0x00096000`, and its heap (which starts at `0x00788180`, is grown to about `0x01EF7000` once at boot by `Boot_LoadModules` and then trimmed) stays under `0x01E00000`. `python tools/pcsx2.py freeram` checks this in save states: in all four of Daniel's (2023-01 to 2026-10, title screen to street fights) both areas below are zero, the heap top (`sbrk` break at `0x0040C274`) was between `0x01BB2000` and `0x01D78000`, and no instruction in the ELF builds an address in `0x000A0000`-`0x000FFFFF`.

| Area | Size | Use |
|---|---|---|
| `0x000A0000`-`0x000DFFFF` | 256 KB | **Mod area**: code of C mods too big for the cave below (`tools/cmod.py`, `@org`). Each mod claims a range in the table below |
| `0x000E0000`-`0x000EFFFF` | 64 KB | **Mod data area**: C mods' writable globals (`@bss`). Never written by a cheat, so it keeps its values; zero at boot; saved in save states |
| `0x000F0000`-`0x000FFFFF` | 64 KB | Debug scratch for live testing over PINE (logging caves, the teleport request word at `0x000F0000`). Never used by a shipped cheat |
| `0x01F00000`-`0x01FBFFFF` | 768 KB | Debug only: `tools/pcsx2.py trace` stubs and table. Above the heap's highest point seen, but the heap could in principle grow into it, so no shipped mod uses it |

Claimed ranges in the mod areas:

| Range | Used by |
|---|---|
| `0x000DF000`-`0x000DFFFF` | sandbox-only debug cheats in `tools/debug/` (`teleport.c` at `0x000DF000`); never installed in the real pnach |
| `0x000A0000`-`0x000A00FF` | "C mod test: the player takes no damage" (`mods/c/test_no_damage.c`, 96 bytes used of 0x100) |
| `0x000A1000`-`0x000A2FFF` | "New characters" (`mods/c/new_characters.c`, 7,044 bytes used of 0x2000) |
| `0x000E1000`-`0x000E1FFF` | its globals: built presets, the texture preload state, B.LIST sort buffers (1,840 bytes used of 0xC00 at `0x000E1000`); the moved B.LIST `0x000E1C00`-`0x000E1D91` and its copy `0x000E1E00`-`0x000E1F91` (fixed addresses, the patched code points there) |
| `0x000E2000`-`0x000E28FF` | its saved copies of the new characters' person records (0x43C each, room for 2; fixed address, used in VS CUSTOM) |
| `0x000E0000`-`0x000E000F` | its globals (8 bytes used of 0x10) |

## Extended RAM: 95 MB more in PCSX2 (optional)

PCSX2 can give the PS2 128 MB instead of 32 MB, like the dev-kit consoles had: **"Enable Extended RAM (Dev Console)"**, ini key `ExtraMemory = true` in section `[EmuCore/CPU]`. It works **per game**: put it in `gamesettings/SLUS-21150_C9F6EF9A.ini` and only Beat Down gets the extra RAM. Tested by Claude in the sandbox on 2026-10-14/15 (`python tools/pcsx2.py ram128 on|off` switches it there):

- The game boots, loads the memory card and runs normally. Its heap still starts at `0x00788180` (sbrk was `0x01569000` at the title), and its main stack moves to the new top of RAM (`0x07FF0000`-`0x07FFFFFF`). Everything else from `0x02000000` to `0x07EFFFFF`, **about 95 MB, stays zero**: free for mods.
- A cheat's code ran every frame and read and wrote `0x02000000` only with the option on (`tools/debug/ram128_probe.c`); with it off, PCSX2 drops writes there and reads 0 (no crash).
- **Save states don't cross over**: a 32 MB state won't load with 128 MB on ("Memory size mismatch, save state requires 32MB"), and the other way round. Memory card saves are fine both ways. Turning it on means making new save states.
- A real PS2 has no such RAM, so mods that need it are PCSX2-only (all of ours are anyway).

How mods should use it:

| Range | Use |
|---|---|
| `0x02000000`-`0x07EFFFFB` | **Extended mod data**: big tables, scripts, text, models, buffers. Only when `ExtRam_Present()` (`tools/cmod/game.h`) says the RAM is there; fall back or do nothing otherwise. Claim ranges in the table below |
| `0x07EFFFFC` | `ExtRam_Present()`'s test word |
| `0x07F00000`-`0x07FEFFFF` | keep clear: below the moved stack |

Keep code (and the hooks) in the normal mod area, so a mod still loads cleanly when someone hasn't turned the option on; put only data in extended RAM. Cheat lines (`patch=1`) can write there too, but they would rewrite megabytes every frame; a C mod should build its data there at run time instead.

| Extended range | Used by |
|---|---|
| (none yet) | |

## Code caves

The game has no free memory set aside inside its own image, so small hooks go in places nothing runs or reads. Bigger code goes in the mod area above.

| Cave | Size | Why it's free | Used by | Free |
|---|---|---|---|---|
| `0x003E0130`-`0x003E017F` | 20 words | zero padding between the last code and the VU microcode | `0x003E0130`-`0x003E0167` model hook (`swap-model`, and the cheat "Aaron uses Ignacy's moveset and Chester's model"); `0x003E0168`-`0x003E017F` negotiation on knockout (KO hook) | none |
| `0x00216538`-`0x00218FEF` | 10,936 bytes | a DMA/GS library function nothing calls or points to (checked over the whole ELF) | see the next table | `0x00216838`-`0x00216FFF` (1,992 bytes, for C mods) and `0x00218F44`-`0x00218FEF` (172 bytes) |

Inside `0x00216538` (constants `ROSTER_CAVE` and `MIX_*` in `tools/bdkit.py`):

| Range | Used by | Layout |
|---|---|---|
| `0x00216538`-`0x00216737` | **roster** (`bdkit.py roster`), reserved | `+0x00` model hook code, `+0x40` preset remap table, `+0x100` name hook code, `+0x180` name table. The current roster writes up to `0x002166C7`. |
| `0x00216738`-`0x00216FFF` | **C mods** (`tools/cmod.py`): each C file claims a range with `@org` and `@max` | `0x00216738`-`0x00216837` "Aaron uses Ignacy's moveset and Chester's model (C version)" (`mods/c/aaron_chester_model.c`, 48 bytes used of 0x100). Free: `0x00216838`-`0x00216FFF` |
| `0x00217000`-`0x002175FF` | **mix-moveset**: the mixed command list (up to 191 commands) | `MIX_LIST` |
| `0x00217600`-`0x002179FF` | mix-moveset: renumbered condition records, 16 bytes each | `MIX_CONDS` |
| `0x00217A00`-`0x00217BFF` | mix-moveset: MOVE LIST hook code | `MIX_HOOKS` |
| `0x00217C00`-`0x00218EFF` | mix-moveset: move list override table and its lines | `MIX_MOVELIST`, `MIX_LINES` |
| `0x00218F00`-`0x00218F43` | **negotiation on knockout** (CANCEL hook, v2) | |
| `0x00218F44`-`0x00218FEF` | **free** | |

Because mix-moveset always writes the same addresses and its move list table has one style row, **only one mixed-moveset cheat can be on at a time**, whichever style it changes. A second simultaneous mix would need its own area (the free `0x00216738` block) and a move list table with two rows, taken out of the C mod area.

## Every cheat's writes

| Cheat (pnach section) | Writes | Kind |
|---|---|---|
| Aaron uses Raven's moveset | `0x0050D8B4`, `0x0050D8BC` | Aaron's class row: style, group list pointer |
| Aaron uses Jason G's moveset | `0x0050D8B4`, `0x0050D8BC`; `0x0050D13C`-`0x0050D14B` | class row; Aaron's group list at `0x0050D100` (swaps group 184 for 183, adds 209 in the padding) |
| Aaron uses Ignacy's moveset and Chester's model | `0x0050D8B4`, `0x0050D8BC`; `0x0013B54C`, `0x0013B55C`; `0x003E0130`-`0x003E0167` | class row; both `jal Preset_Get` in fighter init; model hook code |
| Story roster: Aaron is Chester with Ignacy's moves | `0x0050D8B4`, `0x0050D8BC`; `0x0013B54C`, `0x0013B55C`; `0x0031B3E4`; `0x00216538`-`0x002166C7` | class row; fighter init hooks; HP bar name call in `HpBar_Build`; roster cave |
| Aaron uses the cut TESTER moveset | `0x0050D8B4`, `0x0050D8BC` | class row |
| Aaron keeps his moves but grapples like Jason G | `0x0050D8B4`, `0x0050D8BC`; `0x0050D100`-`0x0050D14F`; `0x00515C5C`; `0x001C5BA0`, `0x001C5BF0`, `0x001C5C30`, `0x001C5C70` (8 bytes each); `0x00217000`-`0x00218EFF` (parts) | class row; Aaron's whole group list; `g_StyleCommands[0x13]`; the four MOVE LIST functions' first two instructions; mix area |
| Aaron uses Ignacy's moveset and Chester's model (C version) | `0x0050D8B4`, `0x0050D8BC`; `0x0013B54C`, `0x0013B55C`; `0x00216738`-`0x00216767` | class row; both `jal Preset_Get` in fighter init, now `jal Mod_PresetGet`; the C code |
| New characters: Eggusz (person 51) in the subway, chapter 2 | `0x000A1000`-`0x000A2B83`; `0x0013AAB0`, `0x00344550`, `0x0013B490`, `0x00178700`, `0x002A8720`, `0x002E67C0`, `0x002F52C0`, `0x00387980`, `0x0018D250`, `0x0018EBC0`, `0x0018EC00`, `0x0018EDE0`, `0x00371160` (8 bytes each); 56 single words in `0x00188074`-`0x0018ED9C`; `0x00341DB0`-`0x00341DB7`, `0x00341DF0`; `0x003445DC`-`0x003445E3`, `0x00344790`-`0x00344797`, `0x0034479C`, `0x003447B0`, `0x003447B8` | the C code; `@hook`s on Person_Init, NpcSpawn_Step, Area_BuildPeople, Text_Get, Fighter_UsesPresetModel, SaveData_Unpack, VsMode_MakeFighters; `@jump`s replacing Preset_Get, BList_Build, BList_Clear, BList_GetList, BList_IndexOf, VsCustom_SetupLists; the `lui`/`addiu` pairs in the other BList functions that address `g_BList` (moved to `0x000E1C00`); VS CUSTOM's hero marks 0x33/0x34 made 0x10033/0x10034 (VsMode_Main's mark loop, VsMode_MakeFighters' tests). (Until 2026-10-15 it also wrote `g_VsRoster` entries 84-85; dropped, only the old CHARACTER SELECT reads that table.) At run time it also writes `g_PersonDefs[51]` and `g_StreetTextures[87]` |
| C mod test: the player takes no damage (hook, mod area, globals) | `0x000A0000`-`0x000A005F`; `0x002FB880`-`0x002FB887` | the C code; `Fighter_ApplyDamage`'s first two instructions (`@hook`). Its globals at `0x000E0000` are not written by the cheat |
| Negotiation menu on knockout (test v2) | `0x002DE478`-`0x002DE48B`; `0x002DEF70`-`0x002DEF77`; `0x003E0168`-`0x003E017F`; `0x00218F00`-`0x00218F43`; `0x005990FC` | after-KO talk hook; CANCEL hook; two caves; negotiation menu descriptor (Triangle → CANCEL) |
| Cut content: DEBUG on the title screen | `0x0058969C`, `0x005897D0` | title menu item action and label |
| Cut content: all six languages in the debug LANGUAGE menu | `0x003B75D0`, `0x003B75F0` | two clamp instructions |
| Cut content: developer debug mode (switch 5) | `0x00599014` | `g_DebugSwitches[5]` |
| Cut content: DIFFICULTY in the pause menu options | `0x00509DA8` | option record byte `+27` (written as a word) |
| Cut content: boxers use the short boxer style 0x1C | `0x0050D6A4`, `0x0050D6B4`, `0x0050D6C4` | BOXER S/M/L class rows' style |

All 426 writes are 32-bit (`patch=1,EE,2...`) and `patch=1`, so PCSX2 rewrites them every frame while the cheat is on, and the values stay in memory after the cheat is turned off until the game restarts.

## Which cheats can be on together

From `pnach-map`'s overlap list:

- **The seven Aaron cheats** (Raven, Jason G, Ignacy + Chester and its C version, roster, TESTER, Jason G grabs) all write Aaron's class row, so only one may be on. The roster and both Ignacy + Chester cheats also share the fighter init hooks.
- "New characters" replaces `Preset_Get` itself; cheats that redirect its calls in fighter init (the Aaron model cheats, the roster) still work on top, since they call it.
- Everything else writes separate addresses, so the negotiation cheat, the five cut content cheats and any one Aaron cheat can be on together.
- The roster cheat writes every hero it recasts; once it recasts other heroes, it also conflicts with any cheat for those heroes.

## Other patches

PCSX2's bundled **Widescreen 16:9** patch (Game Properties, Patches) writes `0x00375388`, `0x00375394` and `0x0037539C` plus `gsaspectratio=16:9`. None of our cheats are near those addresses (checked 2026-10-13), so it can be used with all of them. Not yet tried together in-game.

## Picking an address for a new mod

1. Prefer changing data (a table entry) over code. The data tables we change are listed above; `docs/CODEMAP.md` lists the rest.
2. For new code, use the free ranges above, then record the new range in both tables here and in the README's "Known code addresses".
3. A hook replaces a `jal` (or the first instructions of a function) with a jump into the cave. Put the original instruction back in the cave code, and check with `codemap.py pnach-map` that no other cheat writes the same words.
4. A C mod (`tools/cmod.py`) picks its `@org` range from the C mod cave (small mods) or the mod area `0x000A0000`-`0x000DFFFF` (anything bigger), its `@bss` range from the mod data area, and records both in the tables above. A `@hook` writes the hooked function's first two instructions; `pnach-map` shows it like any other write.
5. If a new tool command writes fixed addresses (like `mix-moveset`), name the constants in `tools/bdkit.py` and say here that only one cheat made by it can be on.
