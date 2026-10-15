# Beat Down: Fists of Vengeance modding kit

Everything learned so far about the US release (SLUS-21150), plus tools to extract files and make patches. Start here before any new mod.

## Before you start: unpack your own disc into `ISO/`

The kit works on files from the game disc, which are **not** in this repository (they are copyrighted, and `ISO/` is in `.gitignore` so they can't be committed by accident). You need your own copy of exactly this release:

| | |
|---|---|
| Game | Beat Down: Fists of Vengeance |
| Region | USA, NTSC-U |
| Serial | SLUS-21150 (boot file `SLUS_211.50`), version 1.02 |
| Disc image | 3,317,039,104 bytes, volume `BEATDOWN` |
| ELF check | PCSX2 CRC `C9F6EF9A`; `SLUS_211.50` is 5,238,064 bytes, MD5 `b2e575877da83f07d039f888db446697` |

Other regions (PAL, Japan) have different code addresses, so the patches and addresses here don't apply to them.

Unpack the whole disc, keeping its folder layout, into `ISO/` at the top of this workspace:

```
python tools/bdkit.py iso-extract "Beat Down - Fists of Vengeance (USA).iso" ISO
```

Afterwards you should have:

| File | Bytes | MD5 |
|---|---|---|
| `ISO/SLUS_211.50` | 5,238,064 | `b2e575877da83f07d039f888db446697` |
| `ISO/XAF/CDATA.XAF` | 57,597,952 | `e54e4b47496fad24d933e027b9a0a554` |
| `ISO/XAF/DATA.XAF` | 195,262,464 | `7f783e16416d582be0880467e80522a7` |
| `ISO/XAF/FSCENE.XAF` | 15,722,496 | `42ecfc5de6ac1e298638600b833cd40f` |
| `ISO/XAF/FSTAGE.XAF` | 101,451,776 | `9332532ecc2ef385b402c0ec1f01ce65` |
| `ISO/XAF/GRAPH.XAF` | 64,227,328 | `75ae7e230fcde017a7b49a0707a6a481` |
| `ISO/XAF/SCRIPT.XAF` | 8,400,896 | `e9415720cfb21ed8ccc753ec7e880006` |
| `ISO/XAF/STAGE.XAF` | 46,284,800 | `7e68e323c79246b0ac4c2c0b1c3b75ac` |
| `ISO/XAF/ARCHIVE.XAF`, `FBGM.XAF`, `SOUND.XAF` | 1,011,259,392 / 837,335,040 / 30,087,168 | |
| `ISO/MOVIES/`, `ISO/MODULES/`, `ISO/ICON/`, `ISO/IOPRP300.IMG`, `ISO/SYSTEM.CNF` | | |

The full file list with sizes is in `dumps/iso_files.txt`. Only `SLUS_211.50` and the XAF archives are needed for the tools. If the MD5 of `ISO/SLUS_211.50` matches, you have the right release.

All commands below are run from the top of the workspace.

## What's in this workspace

| Path | What it is |
|---|---|
| `CLAUDE.md` | How Claude works in this folder (rules, workflow) |
| `ISO/` | Your unpacked disc. Never committed, never modified. |
| `tools/bdkit.py` | Command-line tool (Python 3, no extra packages). Run `python tools/bdkit.py -h`. |
| `tools/codemap.py` | Code map helpers: symbol exports, command tables with damage, person templates, motion scripts (`actions`), missing-animation check (`anim-check`), which addresses each cheat writes (`pnach-map`). Run `python tools/codemap.py -h`. |
| `docs/movesets.md` | **Moveset map**: every fighting style ID, who uses it, each fighter's body and move groups, which swaps work, and every style's move list with names and inputs |
| `docs/CODEMAP.md` | **Code map**: named functions, tables and structs in the main program (combat and damage, the command table, character loading, people and money, items, saves) |
| `docs/MECHANICS.md` | **Game mechanics**: what the stats do and the formulas behind them (damage, Pride Gauge, EXP and levels, Stamina/Attack/Technique points, weapons, difficulty, Criminal Level and titles, records), plus a mod cheat sheet |
| `docs/CUTCONTENT.md` | **Cut content**: the hidden DEBUG title item and debug menu (scene player, language select), developer debug switches, hidden options, unused styles and classes (TESTER, short styles), leftover text and assets, with cheats to restore them |
| `docs/ROSTER.md` | **Story roster**: recast the five story heroes (model, moves, HP bar name, starting stats) from one file, `mods/roster.json`, with `bdkit.py roster` |
| `docs/PLAN-auto-negotiation.md` | **Negotiation on knockout** (built, tested): the plan, the battle and talk-scene code it hooks, and the test runs |
| `docs/SCRIPTS.md` | **Scripts, missions, side jobs, events and dialogue**: how missions start (job menu, area load, talking, story flags), their requirements and results, the 50 side jobs, the script file format, the event VM and all 204 commands, with a worked example and modding notes |
| `docs/UNLOCKS.md` | **Unlocks**: the prerequisites of all 50 side jobs (story stage, % of jobs cleared, game clears, special conditions) and of meeting and recruiting each hero in story mode (story stage, Criminal Level, location, disguise, flags), plus location ids, appearance categories and chapter objectives |
| `tools/scriptkit.py` | Disassembles SCRIPT.XAF (mission and dialogue scripts), lists every mission (`dumps/missions.txt`, `dumps/scripts/`, `dumps/script_ops.txt`) and the job prerequisites (`jobs`) |
| `docs/ANIMATION.md` | **Animation system**: animation groups and the global animation slots, action motion scripts (which animation each move plays, frame ranges), body remap tables, and what that means for moveset mods |
| `docs/MEMORY-MAP.md` | **Memory used by our cheats**: every address each cheat writes, the code caves (used and free), and which cheats can't be on together |
| `symbols/symbols.tsv` | Every name we've given an address, with its C type when known (single source); `symbols/` also holds the generated PCSX2 `.sym`, Ghidra script and CSV |
| `symbols/structs.tsv` | The game's structs (fighter, person, template, class row, preset, hit record, battle...) field by field; `codemap.py symbols` turns it into `tools/cmod/structs.h` and Ghidra types |
| `tools/ghidra/ExportDecompiled.py` | Ghidra script that writes the decompiled C of every function to `decomp/` (see "Ghidra") |
| `tools/ghidra/ApplyPS2Signatures.py`, `ps2sigdb.py` | Name the Sony PS2 SDK library functions (sceCdRead, scePadRead, memcpy, sprintf...) by signature before the export (see "Ghidra") |
| `dumps/ps2_sdk_functions.tsv` | The 707 Sony library functions the signatures find: address, name, library, size, strong or weak match (`ps2sigdb.py`) |
| `ghidra/`, `decomp/` | Your local Ghidra project and its pseudocode export. Never committed: both are derived from the game's code. |
| `dumps/commands.txt` | Every style's command table: input, action ID, base damage and its address, move name (`codemap.py commands`) |
| `dumps/persons.txt` | All 602 person templates with level, HP, guard, attack rank and money (`codemap.py persons`) |
| `dumps/characters.txt` | Every fighter: class row, address, body size, style, animation groups |
| `dumps/fighters.txt` | Every fighter spawn record: outfit preset (model) and class row (`bdkit.py fighters`) |
| `dumps/anim_groups.txt` | All 317 animation groups: which STAGE.XAF pack and which animation IDs |
| `dumps/iso_files.txt` | Every file on the disc with sector (LBA) and size |
| `dumps/xaf_*.txt` | Index of every XAF archive: entry number, offset, size, asset type |
| `dumps/xaf_ARCHIVE.txt` | Outfit and body part names (HAI_ hair, EYE_, MOU_ mouth, WEA_ weapons...) |
| `mods/SLUS-21150_C9F6EF9A.pnach` | Finished patches (PCSX2 cheats), one `[section]` per mod |
| `mods/roster.json` | The story roster `bdkit.py roster` builds its cheat section from (see docs/ROSTER.md) |
| `tools/cmod.py`, `tools/cmod/game.h` | Builds mods written in C into cheat sections (see "Mods in C"); `structs.h` and `symbols.h` next to `game.h` are generated |
| `tools/pcsx2.py` | Sandbox PCSX2 for testing: start/stop, memory over PINE, keys, screenshots, save states, struct viewer, free-RAM check, function trace (see "Testing in a sandbox PCSX2") |
| `mods/c/` | Mods written in C, one file each |
| `__external_tools/`, `disc/` | Ghidra, JDK, PyGhidra and the PS2 compiler; your disc image. Never committed (see "External tools") |

## Quick facts

| | |
|---|---|
| Game | Beat Down: Fists of Vengeance (USA), Capcom 2005, developed by XPEC |
| Serial | SLUS-21150, boot file `SLUS_211.50`, NTSC, version 1.02 |
| ISO | 3,317,039,104 bytes, volume `BEATDOWN` |
| PCSX2 CRC | `C9F6EF9A`, so patches go in `SLUS-21150_C9F6EF9A.pnach` |
| PCSX2 cheats folder | `C:\Games\Emu\PCSX2\cheats` |
| CPU | Emotion Engine (MIPS R5900), little-endian |
| Symbols | None. Every name in this guide was worked out by hand. |

## Disc layout

| File | Size | Contents |
|---|---|---|
| `SLUS_211.50` | 5.2 MB | Main program (ELF) |
| `XAF/ARCHIVE.XAF` | 1.0 GB | 5737 outfit and body parts for the character creator |
| `XAF/FBGM.XAF` | 837 MB | 3131 music/voice streams (`XAU` format) |
| `XAF/DATA.XAF` | 195 MB | 8276 entries: mostly textures, plus prop meshes and animations |
| `XAF/FSTAGE.XAF` | 101 MB | 181 fight arena entries |
| `XAF/GRAPH.XAF` | 64 MB | 602 UI and menu graphics |
| `XAF/CDATA.XAF` | 58 MB | 433 character entries: texture packs, models, per-model texture lists, localized text |
| `XAF/STAGE.XAF` | 46 MB | 318 animation packs (the moves themselves) |
| `XAF/SOUND.XAF` | 30 MB | 146 sound effect banks (`SSLD`) |
| `XAF/FSCENE.XAF` | 16 MB | 332 cutscene scripts (`@CONSOLE "PS2"` text) and models |
| `XAF/SCRIPT.XAF` | 8 MB | 1148 mission/event bytecode scripts |
| `MOVIES/*.PSS` | 8 files | FMVs (standard PS2 MPEG-2 PSS) |
| `MODULES/MODULE.BIN`, `IOPRP300.IMG` | | IOP (sound/disc) modules |

## XAF archive format (XPEC)

```
0x00  "XAF\0"
0x04  u32 0x100                     version
0x08  char[32] "XPEC Entertainment Inc. 2003"
0x28  u32 count + 1
0x2C  u32 count
0x30  u32 total size
0x40  count x { u32 offset, u32 size }   offset from archive start, 2048-aligned
```

Entries have no names. The game asks for them by number. The loader is `0x0029BC40(archive_id, entry, mode)`. Archive IDs: 0 DATA, 1 STAGE, 2 GRAPH, 3 FBGM, 4 SOUND, 5 FSTAGE, 6 CDATA, 7 FSCENE, 8 SCRIPT, 9 ARCHIVE.

### Asset types (first u32 of an entry)

| Value | Type | Notes |
|---|---|---|
| `0x16` | model | chunk tree, sub-chunk tags look like `0x1C02000F` / `0x1C02002D` |
| `0x18` | texture pack | e.g. 128x128 8-bit with palette; header has width/height |
| `0x10` | mesh | contains Softimage user data like `BONETAG=29` |
| `0x1B` | animation | |
| STAGE.XAF pack | animation pack | `u32 count`, then `count` offsets with bit 31 set |

## Characters and movesets

### Character types

Name table at `0x00589AF0` (52 pointers). Type IDs:

| ID | Name | ID | Name |
|---|---|---|---|
| 0 | UNKNOWN | 34 | **AARON** |
| 1-3 | BOXER S/M/L | 35 | **RAVEN** |
| 4-6 | GRAPPLER S/M/L | 36 | **LOLA** |
| 7-9 | KNUCKLEMASTER S/M/L | 37 | **GINA** |
| 10-12 | JUGGLER S/M/L | 38 | **JASON_G** |
| 13-15 | KICKBOXER S/M/L | 39 | IGNACY |
| 16-18 | STRIDER S/M/L | 40, 45, 46 | TESTER M/S/L |
| 19-21 | WEAPONMASTER S/M/L | 41 | QUINCY |
| 22-24 | NEGOTIATER S/M/L | 42 | EUGENE |
| 25-27 | GANG S/M/L | 43 | ZANETTI |
| 28-30 | POLICE S/M/L | 44 | CARLO |
| 31 | PERFECT (has every style) | 47 | MELVIN |
| 32 | FATIMA | 48 | WARREZ |
| 33 | GREGOLIO | 49-51 | WENDEL, TRACY, CHESTER |

### Character class table: the moveset switch

`0x0050D6A0`, 16 bytes per row, row = type ID - 1:

```
+0  u32 body        0 = small, 1 = medium, 2 = large (which skeleton/body animations)
+4  u32 style       fighting style ID; selects the move set
+8  u32 skeleton    action remap table, one per body size (S 0x50C230, M 0x50B990, L 0x50BDE0); see docs/CODEMAP.md
+C  u32 groups      pointer to a list of animation group IDs ending in 9999
```

The five heroes:

| Hero | Row address | Body | Style | Own animation groups |
|---|---|---|---|---|
| Aaron | `0x0050D8B0` | M | `0x13` | 184, 210 |
| Raven | `0x0050D8C0` | M | `0x11` | 182, 211 |
| Lola | `0x0050D8D0` | M | `0x15` | 186, 206 |
| Gina | `0x0050D8E0` | S | `0x14` | 185, 212 |
| Jason G | `0x0050D8F0` | L | `0x12` | 183, 209 |

Every list also contains the shared groups `159, 15, 16, 39, 38, 19, 21, 22, 23, 27, 30, 31, 34` and two body groups (S `164,165`, M `160,161`, L `162,163`). The generic enemy styles are `0x01`-`0x08`, gang `0x24`, police `0x0D`, and their move groups are 166-173, 201 and 178. See `movesets.md` for every style, its fighters and its full move list.

**To give fighter A the moves of fighter B**, copy B's `style` (+4) and `groups` (+C) into A's row. Keep A's body and skeleton. That only works cleanly when both have the same body size. `python tools/bdkit.py swap-moveset ISO/SLUS_211.50 A B` prints the patch lines for you and warns when the bodies differ.

**When the body sizes differ** (say Aaron M gets Jason G's L moves), use `python tools/bdkit.py swap-moveset ISO/SLUS_211.50 A B --keep-body`. Style move groups don't depend on body size (BOXER S/M/L all load group 166, and PERFECT loads every style group on an M body), so instead of borrowing B's list, A's own list is edited in place: A's move group is swapped for B's, B's extra groups are added into the zero padding after the 9999 terminator, and A keeps its own body groups. Each hero's list is used by that hero's row only (Aaron's list at `0x0050D100` has one reference, at `0x0050D8BC`).

**To mix two movesets** (A keeps most of its moves but takes one kind of move from B), use `python tools/bdkit.py mix-moveset ISO/SLUS_211.50 A B --take grab`. A style's command list is a list of `{condition, input sequence}` pairs and the action IDs in them are global, so a new list can hold commands from both styles. The tool keeps A's commands in their places, swaps the ones whose last input is in the family for B's command with the same input, drops the ones B lacks, and puts B's extra ones at the end. It writes the new list to the free cave at `0x00217000` (the part of the roster's unused function that nothing else uses, up to `0x00218F00`), points A's style at it in `g_StyleCommands` `0x00515C10`, and adds B's style groups to A's group list so the new moves have their animations (like `--keep-body`, it works across body sizes). Families: `grab` (GRAB P/K, grab + direction or G, rear grabs, wall grabs); hex input codes work too, for example `--take 0x2F,0x32`. **The MOVE LIST screen follows the mix**: A's lines in the family are swapped for B's (at the place of A's first one), through small hooks at `0x00217A00` on the four move list functions, and every copied unlock condition is renumbered to its new line so locked moves stay hidden until learned. This needs the move text, so the tool reads `ISO/XAF/CDATA.XAF` (`--cdata` for another path). It is only needed for mixes: `swap-moveset` and the roster switch the whole style, and the game then shows that style's own list. Raw hex codes can't be matched to move list lines, so with them the screen is left alone. Limits: combo strings should move as a whole family, because a string like P P P is matched against the input history; and two styles' animation groups are loaded at once, which uses more memory (PERFECT already loads all eight generic style groups).

### Fighter records: the model switch

Fighter table at `0x00413134`, 72 bytes per record, 602 records, indexed by fighter ID (not type ID). Fighter init `0x0013B490(slot, fighter_id, 0)` reads it:

```
+0   s16 outfit preset   index into CDATA.XAF entry 0; selects the model and outfit parts
+2   u16 class row       row in the class table (0x0050D6A0); selects body, style and animation groups
+4   u8  ?               copied to fighter +0x46
+0xC s16 HP
```

The playable heroes' fighter IDs are at `0x004334B0`: Raven 107, Jason G 53, **Aaron 68**, Lola 22, Gina 108. Aaron also has records 153 and 590 (used outside the player slot). Chester is 20 and 152, preset 23. Ignacy is 11, 74 and 162 (presets 84 and 160).

Outfit presets are CDATA.XAF entry 0: 189 records of `0x498` bytes, read through `0x002A8720(preset, 1 = parts | 2 = params)`. Each record is 22 slots of `{u32 slot id, s16 parts[16] ending in -1}`, which init copies into the fighter at `+0x68`, then params at `+0x318`. Boss presets (Chester's 23) set param `+0x18` = 1, which sets fighter flag 8.

**To give fighter A the look of fighter B**, don't change A's preset number: the game checks preset numbers to recognise the heroes (the HP bar name `0x0013CA80`, name ID `0x002F9930`, and at least 7 other functions with the same preset switch), so a hero given a boss preset loses its name. Instead, `bdkit.py swap-model SLUS_211.50 A B` prints a hook: 14 words in unused padding at `0x003E0130` that swap A's presets for B's, and both `jal 0x002A8720` in fighter init (`0x0013B54C` parts, `0x0013B55C` params) are pointed at it. A keeps its preset number, name and class row. Keep body sizes equal (A's class row still picks the body animations); the tool warns when they differ.

For story heroes, prefer the **roster** (`docs/ROSTER.md`): `bdkit.py roster ISO/SLUS_211.50 mods/roster.json` does model, moves, HP bar name and starting stats for any of the five heroes in one section, with a table-driven hook in the unused library function at `0x00216538`.

### Move lists (names and inputs)

Table at `0x005CAB40`, 8 bytes per style, row = style - 1: `{u16 first input text, u16 last input text, u16 first name text, u16 last name text}` (`0xFFFF` = none; only style 0x09 TESTER). 47 rows cover styles `0x01`-`0x2F`: `0x1C`-`0x23` are short versions of the generic styles and `0x25`-`0x2F` are weapon lists, none of them used by a class row. The text lives in CDATA.XAF entries 397-402 (JP, EN, FR, DE, ES, IT), format `{u32 size, u16 count, u16 language, count x {u16 id, u16 len, u32 offset}}` then UTF-8 strings in full-width characters. Buttons in the inputs: 〆 punch, ◎ kick, ◇ guard, 4 action. `bdkit.py moves SLUS_211.50 CDATA.XAF 0x13` prints one style; `bdkit.py style-map SLUS_211.50 CDATA.XAF > movesets.md` regenerates the map. This is the in-game MOVE LIST screen. Which animation each move plays is in its action's motion script: see docs/ANIMATION.md and `python tools/codemap.py actions ISO/SLUS_211.50 0x13`.

### Animation groups

Table at `0x004FB4C0`, 8 bytes per group: `{s16 STAGE.XAF entry, s16 0, u32 pointer to s16 animation IDs ending in -1}`. Group N loads STAGE.XAF entry `stage_entry`, and the animations in that pack are numbered by the ID list in order. The loader is `0x002DC360`, and the per-fighter loop is `0x002DC550`. See `dumps/anim_groups.txt`. Animation IDs are global (one slot per ID at `0x006C55F0`, reference counted, so groups that share an ID load it once), and an action's motion script names the IDs it plays. Full description in docs/ANIMATION.md; `python tools/codemap.py anim-check ISO/SLUS_211.50 A 0xSTYLE` lists the animations a planned swap would be missing.

## Known code addresses

The full map of functions, tables and structs is in `docs/CODEMAP.md`; this is the short list.

| Address | What |
|---|---|
| `0x00100008` | ELF entry point |
| `0x0029BA10` | Opens all ten XAF archives and reads their indexes into `0x006A3ED0[10]` |
| `0x0029BC40` | Queue an XAF entry load `(archive, entry, mode)` |
| `0x0029CD10` | Load an animation (chunk type 0x1B) from an XAF entry |
| `0x0029ED70` | Load an animation pack plus its ID list |
| `0x002DC360` | Load one animation group |
| `0x002DC550` | Load every group in a 9999-terminated list |
| `0x002DC680` | Uses the class table to load a fighter's groups |
| `0x00387760` | Loads localized text from CDATA (entries 385-432, six languages) |
| `0x00387980` | Look up a text string by ID |
| `0x001C5C00` | Move name text for (style, move index), via the move list table |
| `0x001C5C30` | Move input text for (style, move index), via the move list table |
| `0x001107C8` | `scePrintf`, Sony kernel debug print (libc `printf` is `0x0012CDF8`) |
| `0x0013B490` | Fighter init `(slot, fighter_id, 0)`: reads the fighter table at `0x00413134`, copies the outfit preset |
| `0x002A8720` | Outfit preset record `(preset, 1 = parts, 2 = params)` from CDATA.XAF entry 0 |
| `0x0013CA80` | Fighter display name; hero presets (`0x18, 0x3F, 0x4E, 0x71, 0x73, 0x99-0x9D`) get the hero name |
| `0x002F9930` | Preset number to name/fighter ID (Aaron's presets 78 and 153 give 68 = text 11069 "Aaron") |
| `0x003E0130` | 20 unused zero words before the VU microcode. `swap-model` uses `0x003E0130`-`0x003E0164`; the negotiation-on-knockout mod uses `0x003E0168`-`0x003E017C`. Full. |
| `0x00216538` | 10,936-byte DMA/GS library function that nothing calls or points to: roster hooks `0x00216538`-`0x00216737`, mix-moveset `0x00217000`-`0x00218EFF`, negotiation-on-knockout `0x00218F00`-`0x00218F43`. C mods (`tools/cmod.py`) `0x00216738`-`0x00216FFF`. Free: `0x00218F44`-`0x00218FEF`. See docs/MEMORY-MAP.md. |
| `0x02000000` | With PCSX2's Extended RAM on (128 MB, per game): about 95 MB free up to `0x07EFFFFF`, for mod data. Tested in the sandbox 2026-10-15. See docs/MEMORY-MAP.md. |
| `0x000A0000` | Free RAM below the program: the **mod area** `0x000A0000`-`0x000DFFFF` (C mod code), the **mod data area** `0x000E0000`-`0x000EFFFF` (C mod globals) and debug scratch `0x000F0000`-`0x000FFFFF`. Zero in every save state checked and never addressed by the game. See docs/MEMORY-MAP.md. |

## Addresses, offsets and patching

- The ELF has one LOAD segment: EE address `0x00100000` = file offset `0x80`. So **ELF offset = address - 0x100000 + 0x80**.
- `SLUS_211.50` starts at ISO sector 1156876, so **ISO offset = 1156876 x 2048 + ELF offset**.
- `python tools/bdkit.py addr 0x50D8B4` does both conversions.
- PCSX2 pnach line for a 32-bit write: `patch=1,EE,2XXXXXXX,extended,VALUE`, where `XXXXXXX` is the address without its top digit. A `[Section name]` header makes it a cheat you can toggle under Game Properties, Cheats.

## External tools (`__external_tools/`)

Third-party programs the workflow needs live in `__external_tools/` at the top of this folder. Git ignores it, so a fresh clone has to fill it once (Windows). `bdkit.py` and `codemap.py` need none of this, only Python 3.

| Folder | What | Needed for | Get it |
|---|---|---|---|
| `ghidra_12.1.4_PUBLIC/` | Ghidra 12.1.4 | rebuilding `decomp/` | [Ghidra releases](https://github.com/NationalSecurityAgency/ghidra/releases), unzip here |
| `ghidra_12.1.4_PUBLIC/Ghidra/Extensions/ghidra-emotionengine-reloaded/` | PS2 CPU support for Ghidra (adds the `r5900:LE:32:default` language, so MMI and VU0 instructions decode) | rebuilding `decomp/` | [ghidra-emotionengine-reloaded](https://github.com/chaoticgd/ghidra-emotionengine-reloaded/releases), the build for this exact Ghidra version; unzip into `Ghidra\Extensions` |
| `jdk-21.0.12.1+1/` | Java 21 (Ghidra 12 needs it) | Ghidra | [Temurin JDK 21](https://adoptium.net), unzip here. Then in `ghidra_12.1.4_PUBLIC\support\launch.properties` set `JAVA_HOME_OVERRIDE=` to this folder's **full** path with doubled backslashes, e.g. `C:\\Users\\V\\source\\_personal\\claude\\ReBeatdown\\__external_tools\\jdk-21.0.12.1+1` |
| `pyghidra-venv/` | Python venv with PyGhidra, so Ghidra runs our Python scripts | rebuilding `decomp/` | `py -3.13 -m venv __external_tools\pyghidra-venv`, then `__external_tools\pyghidra-venv\Scripts\python -m pip install --no-index -f __external_tools\ghidra_12.1.4_PUBLIC\Ghidra\Features\PyGhidra\pypkg\dist pyghidra` (the wheels ship with Ghidra) |
| `ps2dev/` | PS2 toolchain: `ee\bin\mips64r5900el-ps2-elf-gcc` (GCC 15.2) and binutils for the game's CPU | compiling mods written in C | [ps2dev releases](https://github.com/ps2dev/ps2dev/releases) v2.0.0, `ps2dev-windows-latest.tar.gz` (272 MB); unpack so `ps2dev\ee\bin` exists (tar's errors about `ps2sdk\ports\bin` links don't matter). The build is **32-bit** and ships without its MinGW DLLs: take the 32-bit ones from the [MSYS2 mingw32 repo](https://mirror.msys2.org/mingw/mingw32/) packages `mingw-w64-i686-{gmp,isl,mpc,mpfr,libiconv,libwinpthread,zstd,libgcc}` (`tar -xf` unpacks the `.pkg.tar.zst`) and copy `libgmp-10.dll`, `libisl-23.dll`, `libmpc-3.dll`, `libmpfr-6.dll`, `libiconv-2.dll`, `libwinpthread-1.dll`, `libzstd.dll` and `libgcc_s_dw2-1.dll` into `ee\bin`, `ee\libexec\gcc\mips64r5900el-ps2-elf\15.2.0` and `ee\mips64r5900el-ps2-elf\bin`. 64-bit DLLs (Git's, for example) fail with error `0xC000007B` |
| `pcsx2-sandbox/` | a copy of the portable PCSX2 for testing, made by `python tools/pcsx2.py setup` | `tools/pcsx2.py` | made by the tool from `C:\Games\Emu\PCSX2` |
| `_dl/` | the downloaded archives, kept for reinstalling | nothing | |

If this folder moves, recreate `pyghidra-venv` (a venv stores its own path) and fix `JAVA_HOME_OVERRIDE`. Everything else moves freely.

`disc/` (also ignored) holds the user's original disc image, `Beat Down - Fists of Vengeance (USA).iso`, used only to re-extract `ISO/` or to boot a scratch PCSX2 for testing.

## Ghidra (readable pseudocode)

Ghidra turns the game's MIPS code into C-like pseudocode. Ghidra itself lives in `__external_tools/` (next section); the project (`ghidra/`) and the export (`decomp/`) live here. Git ignores all three.

Import, name, analyze and export in one headless run, from this folder:

```
__external_tools\pyghidra-venv\Scripts\python __external_tools\ghidra_12.1.4_PUBLIC\Ghidra\Features\PyGhidra\support\pyghidra_launcher.py __external_tools\ghidra_12.1.4_PUBLIC -H ghidra BeatDown -import ISO\SLUS_211.50 -overwrite -processor r5900:LE:32:default -scriptPath "symbols;tools\ghidra" -preScript ImportBeatdownSymbols.py -postScript ApplyPS2Signatures.py -postScript ApplyInferredTypes.py -postScript ExportDecompiled.py decomp
```

`ImportBeatdownSymbols.py` (generated from `symbols/symbols.tsv` and `symbols/structs.tsv`) names our known functions and tables before analysis, maps the game's zero-initialized globals (`0x005FEB00`-`0x00788180`, which the ELF loader leaves out), creates our structs and applies every type from `symbols.tsv`, so the pseudocode reads `fighter->hp` and `g_Persons[0].money`. `ApplyInferredTypes.py` then types the parameters listed in `symbols/inferred_types.tsv` (made by `python tools/codemap.py infer-types decomp/all.c symbols/inferred_types.tsv` from the previous export: a parameter used only at offsets only a `Fighter` has becomes `Fighter *`; the list keeps growing, so run it after each export and Ghidra again). With the first 98 typed symbols, 18 structs and 176 inferred parameters, about 9,000 of the 30,500 raw `*(type *)(p + 0x...)` accesses became named fields. `ApplyPS2Signatures.py` then names the Sony library functions (next section). `decomp/` then holds `all.c` (every function in address order), `funcs/<address>_<name>.c` (one file per function) and `index.tsv` (address, name, size, file, ok or failed). After adding symbols, regenerate the script with `codemap.py symbols` and rerun the command above. To browse interactively, open the `ghidra/BeatDown` project with `__external_tools\ghidra_12.1.4_PUBLIC\support\pyghidraRun.bat` (or `ghidraRun.bat`).

### Sony library signatures

About 740 of the game's functions (`0x00100000-0x00133500`, plus the sound libraries near `0x348D88` and `0x3606B8`) are Sony's PS2 SDK 3.0 libraries, not game code. `ApplyPS2Signatures.py` finds them by signature and names them, so the pseudocode reads `sceCdRead`, `scePadRead`, `sceOpen`, `sceGsSyncV`, `memcpy`, `sprintf` instead of `FUN_0011xxxx`.
- Signatures: the sce-symbol-scanner database (5,300 names from libkernl, libc, libgraph, libdma, libpad, libcdvd, libmc, libmpeg, libm, libgcc and more, built from PS2 games that shipped with debug symbols), as embedded in [PS2Recomp](https://github.com/ran-j/PS2Recomp) (GPL-3.0). The first run downloads it once (12 MB, [this file](https://raw.githubusercontent.com/ran-j/PS2Recomp/2c5fbb9389e11dd95693385969490c9e8e6f57b4/ps2xAnalyzer/include/ps2recomp/sce_symbol_database_data.h)) into `ghidra/sigdb/` and checks its SHA-256. With no internet on that PC, download that file by hand into `ghidra\sigdb\`.
- How it matches: each library function's code is hashed with its relocated fields (call targets, addresses) masked out. A match with at least 256 fixed bits is "strong"; smaller ones ("weak") count only when unambiguous and from a library that also has strong matches. When several functions share the same code (`EnableIntc` and `DisableIntc`), what they call decides. Version tags in the ELF (`PsIIlibkernl3000`) say SDK 3.0, so 3.0 variants win ties.
- What it changes: unnamed functions get the Sony name and the comment "PS2 SDK libpad (signature match)". Our own names from `symbols/symbols.tsv` always win. Library code that Ghidra had merged into its neighbour (about 70 functions) is split out into its own function. C library functions also get their prototypes from Ghidra's `generic_clib` archive.
- Result: 707 functions named, listed in `dumps/ps2_sdk_functions.tsv`: libkernl 247 (threads, semaphores, SIF/RPC, file I/O `sceOpen`/`sceRead`/`sceLseek`, timers), libc 111, libmpeg 105, libm 40, 6 more that libc and libm share, libgcc 32, libpad 32, libcdvd 32, libmc 25, libdma 19, libgraph 18, libsein 16, libipu 7, libpkt 5, libspu2m 4, libsdr 4, gcc_wrapper 3, crt0 1. Another 37 places had several equally good candidates (`open`/`stat`/`unlink` are the same stub) and are left alone. Each Ghidra run writes what it applied, and those ambiguous places, to `ghidra/ps2_signatures.tsv`.
- Without Ghidra: `python tools/ghidra/ps2sigdb.py ISO/SLUS_211.50 --known decomp/index.tsv --out dumps/ps2_sdk_functions.tsv` runs the same scan (`--ambiguous` lists the unresolved places).
- `0x001107C8`, which we had called `printf`, is Sony's kernel debug print `scePrintf`; the C library's `printf` is `0x0012CDF8`.

## Mods so far

| Mod | File | Status |
|---|---|---|
| Aaron uses Raven's moveset | `mods/SLUS-21150_C9F6EF9A.pnach` | Works in-game (tested by Daniel, 2026-10-12) |
| Aaron keeps his moves but grapples like Jason G (first mixed moveset, `mix-moveset AARON JASON_G --take grab`) | `mods/SLUS-21150_C9F6EF9A.pnach` | Works in-game (tested by Daniel, 2026-10-13): the moves, and the MOVE LIST showing Jason G's grab lines in Aaron's list. Confirms the move list hooks work. Stunner and Power Bomb keep Jason G's stat-level requirements. Aaron cheat: one at a time |
| Aaron uses Jason G's moveset (keeps Aaron's medium body groups) | `mods/SLUS-21150_C9F6EF9A.pnach` | Works in-game (tested by Daniel, 2026-10-12). Confirms `--keep-body` works for M-body heroes using L-body styles. |
| Aaron uses Ignacy's moveset and Chester's model (all medium bodies; first model swap) | `mods/SLUS-21150_C9F6EF9A.pnach` | First version (Aaron's records set to Chester's preset) showed Chester but lost the HP bar name (Daniel, 2026-10-12). Replaced by the init hook, which keeps Aaron's preset number: works in-game with name and model (tested by Daniel, 2026-10-12) |
| Story roster: Aaron is Chester with Ignacy's moves (built by `bdkit.py roster` from `mods/roster.json`; HP bar says Chester) | `mods/SLUS-21150_C9F6EF9A.pnach` | Untested. Replaces the older Aaron cheats: turn those off |
| Negotiation menu on knockout (test v2) | `mods/SLUS-21150_C9F6EF9A.pnach` | v1 tested in PCSX2 2026-10-13 (Miles, 1-on-1 street fight): the menu opens on knockout and RECRUIT, ROB, INTERROGATE and BEATDOWN all work with no freezes. v2 tested 2026-10-13: CANCEL and Triangle after a knockout give the normal after-KO talk and BATTLE RESULT; ROB and BEATDOWN still work; a manual threaten's CANCEL still resumes the fight (Triangle now does that too). Daniel tested v2 2026-10-13: works as intended. Group fights and bosses not tried yet (the code should leave them alone). See docs/PLAN-auto-negotiation.md |
| Cut content: DEBUG on the title screen (replaces VS MODE CUSTOM) | `mods/SLUS-21150_C9F6EF9A.pnach` | Works in-game (tested by Claude in PCSX2, 2026-10-13): DEBUG menu, scene player and language select all work. See docs/CUTCONTENT.md, Test results |
| Cut content: all six languages in the debug LANGUAGE menu | `mods/SLUS-21150_C9F6EF9A.pnach` | Works in-game (tested by Claude in PCSX2, 2026-10-13): German gives German text and menu graphics. Needs the DEBUG title cheat; left/right picks, Cross confirms |
| Cut content: developer debug mode (switch 5) | `mods/SLUS-21150_C9F6EF9A.pnach` | Works in-game (tested by Claude in PCSX2, 2026-10-13): the 10-page fighter overlay works (hold L2 + press R2 to show it, hold L2 + click L3 to page). The R1 speed-up can't be used because R1 is grab |
| Cut content: DIFFICULTY in the pause menu options | `mods/SLUS-21150_C9F6EF9A.pnach` | Works in-game (tested by Claude in PCSX2, 2026-10-13). DIFFICULTY is already in the title-screen OPTIONS without any cheat; this adds it to the pause menu's CONFIG. page |
| Aaron uses the cut TESTER moveset | `mods/SLUS-21150_C9F6EF9A.pnach` | Works in-game (tested by Claude in PCSX2, 2026-10-13): TESTER's action IDs confirmed with the debug overlay. In VS mode Aaron starts with a knife, which uses knife moves until it's gone. Aaron cheat: one at a time |
| Cut content: boxers use the short boxer style 0x1C | `mods/SLUS-21150_C9F6EF9A.pnach` | Style 0x1C works (tested by Claude in PCSX2 on a stand-in fighter, 2026-10-13); not yet seen on street boxers in story mode |
| Aaron uses Ignacy's moveset and Chester's model (C version): the first mod written in C (`mods/c/aaron_chester_model.c`, built by `tools/cmod.py`); same effect as the hand-written cheat above | `mods/SLUS-21150_C9F6EF9A.pnach` | Works in-game, same as the hand-written version, so C mods work (tested by Daniel, 2026-10-14). Aaron cheat: one at a time |
| C mod test: the player takes no damage (`mods/c/test_no_damage.c`): tests `@hook` (a hook on `Fighter_ApplyDamage` that calls the original), the mod area `0x000A0000` and `@bss` globals (hits and damage blocked at `0x000E0000`) | `mods/SLUS-21150_C9F6EF9A.pnach` | Works in-game: the player's HP never drops, so `@hook`, the mod area and `@bss` globals all work (tested by Daniel, 2026-10-14). Can be on with any other cheat |

When adding a new mod, add a new `[section]` to that same pnach file, because PCSX2 reads one file per game. All the Aaron cheats write Aaron's row, so turn on only one of them, and restart the game after switching (a cheat that is turned off leaves its last values in memory). Only one mixed-moveset cheat can be on at a time, because `mix-moveset` always uses the same code space. Everything else can be combined; `python tools/codemap.py pnach-map mods/SLUS-21150_C9F6EF9A.pnach` prints every cheat's addresses and any overlaps, and docs/MEMORY-MAP.md has the full table.

### Mods in C

Mods can be written in C instead of hand-assembled MIPS. `tools/cmod.py` compiles a C file with the PS2 compiler (`__external_tools/ps2dev`, see "External tools"), places it at a fixed address in free memory, links it against every name in `symbols/symbols.tsv`, and prints a pnach section with the code and the hooks:

```
python tools/cmod.py build ISO/SLUS_211.50 mods/c/aaron_chester_model.c --asm
python tools/cmod.py install ISO/SLUS_211.50 mods/c/aaron_chester_model.c
```

`install` adds or replaces the section in `mods/` and in the PCSX2 cheats folder (both get a `.bak`). The C file says where it goes and what it hooks in `// @` comment lines; `mods/c/aaron_chester_model.c` is the example and the top of `tools/cmod.py` lists them all:

| Directive | Does |
|---|---|
| `@section`, `@description` | the cheat's name and description |
| `@org ADDR`, `@max SIZE` | where the code goes and how big it may get: the C mod cave `0x00216738`-`0x00216FFF` for small mods, the **mod area** `0x000A0000`-`0x000DFFFF` (256 KB) for big ones |
| `@bss ADDR SIZE` | where writable globals go, in the **mod data area** `0x000E0000`-`0x000EFFFF` (64 KB): zero at boot, kept between frames, saved in save states |
| `@hook FUNC MYFUNC` | every call to game function `FUNC` runs `MYFUNC`, which can call the original as `orig_FUNC(...)` |
| `@jal SITE FUNC` | one call site calls `FUNC` instead |
| `@jump SITE FUNC` | replace a whole function |
| `@ptr SITE FUNC`, `@word SITE VALUE` | function pointers and table entries |

A hook that changes how damage works, keeping the game's own code for the rest:

```c
// @section Half damage for the player
// @org 0x000A0000
// @max 0x100
// @hook Fighter_ApplyDamage My_ApplyDamage
#include "game.h"

void orig_Fighter_ApplyDamage(Fighter *f, int damage);

void My_ApplyDamage(Fighter *f, int damage)
{
    if (f == &g_Fighters[FIGHTER_PLAYER])
        damage /= 2;
    orig_Fighter_ApplyDamage(f, damage);
}
```

**Types.** `game.h` includes two generated headers: `structs.h` (from `symbols/structs.tsv`: `Fighter`, `Person`, `PersonDef`, `ClassRow`, `Preset`, `HitRecord`, `Battle` and more, with every known field at its offset, checked at compile time) and `symbols.h` (a declaration for every symbol with a type in `symbols.tsv`'s fifth column, so `Person_Get(0)->money` or `g_Fighters[0].hp` just work). The same files give Ghidra its types, so the pseudocode in `decomp/` says `fighter->hp` instead of `*(short *)(param_1 + 0x441c)`. Add a field to `structs.tsv` or a type to `symbols.tsv`, run `python tools/codemap.py symbols ISO/SLUS_211.50 symbols`, and both pick it up (rerun Ghidra for `decomp/`).

Limits: no initialized writable globals (make tables `const`, or use zero-initialized globals with `@bss`), and mods don't use registers s0-s7 (the game saves them as 128-bit values, this compiler as 64-bit; the build reserves them, so this is automatic). Calls use the game's convention (EABI): ints and pointers in a0-a7 and floats in f12-f19, so float arguments and results work. A `@hook` needs a function whose first two instructions aren't jumps or branches; the build checks and says so.

### Testing a cheat in PCSX2

1. Copy `mods/SLUS-21150_C9F6EF9A.pnach` to `C:\Games\Emu\PCSX2\cheats` (after a `git pull` in this folder).
2. In PCSX2, right-click the game, Properties, Cheats, and tick the section. A renamed section (say "test v1" to "test v2") has to be ticked again.
3. Restart the game. Turn off the other cheats that write the same addresses.
4. For moveset work, the developer overlay (cheat "Cut content: developer debug mode (switch 5)": hold L2 + press R2, hold L2 + click L3 to page) shows the current action (`TASK`) and animation (`MOT`).
5. A save state next to the thing you're testing saves a lot of walking: street enemies with a Pride bar for the negotiation mod, a VS fight for movesets.

In the table above, "tested by Daniel" means played in his own game; "tested by Claude" means checked in a separate copy of PCSX2 on his PC.

### Testing in a sandbox PCSX2

`tools/pcsx2.py` (first used live 2026-10-14: start, PINE reads and writes, keys, screenshots, save state load, the teleport cheat all work) runs a copy of the portable PCSX2 in `__external_tools/pcsx2-sandbox` with PINE (memory access), cheats, a keyboard pad 1 and a plugged-in pad 2, so tests never touch the real settings, memory cards or save states (it copies the BIOS, the memory card and the game's save states once). Keys are posted to the sandbox window, so they work in the background and never reach another program.

```
python tools/pcsx2.py setup
python tools/pcsx2.py cheats "Half damage for the player" "Cut content: developer debug mode (switch 5)"
python tools/pcsx2.py start --state 1
python tools/pcsx2.py show Fighter g_Fighters      # every known field of the player's fighter, live
python tools/pcsx2.py keys "l2+r2 square*3 wait:500"
python tools/pcsx2.py shot shot.png
python tools/pcsx2.py stop
```

- `show STRUCT ADDR` prints a struct from `symbols/structs.tsv` from live memory, or from a save state with `--state FILE.p2s` (no emulator needed). `r32`/`w32` (and 8/16), `dump`, `save`/`load` cover the rest.
- `freeram` lists the zero regions in save states and checks the mod areas (docs/MEMORY-MAP.md); run it on a new save state from a part of the game not seen before.
- `flag N... [--set|--clear]` reads or changes story flags. `cheats --c FILE.c` builds a C cheat with `tools/cmod.py` and turns it on in the sandbox only; `tools/debug/teleport.c` is one: write area id + 1 to `0x000F0000` (`pcsx2.py w32 0x000F0000 18` = PLATFORM) and the player is sent there once any fight is over (ids in docs/UNLOCKS.md). Tested 2026-10-14.
- `ram128 on|off`: PCSX2's 128 MB Extended RAM for this game only (docs/MEMORY-MAP.md, "Extended RAM"); 32 MB save states don't load while it's on. `tools/debug/ram128_probe.c` checks from the game's side that the RAM is there.
- Save states from old PCSX2 versions (Daniel's 2023 slot 2) don't load in PCSX2 2.x; their RAM can still be read offline with `show --state` / `ram`.
- **Function trace**, to find the code behind something on screen: `trace build` puts a stub on every game function (from `decomp/index.tsv`) as the sandbox-only cheat "Trace: function coverage"; `cheats --trace ...`, restart, then `trace clear`, do the thing, `trace read`: every function that ran, with its last caller. Clear and read once while idle first to see what runs every frame.

**Widescreen patch:** PCSX2's bundled "Widescreen 16:9" patch (ElHecht, pnach NTSC-U by Arapapa; Game Properties, Patches) is safe to use with every cheat here. It writes only three words, `0x375388`, `0x375394` and `0x37539C` (horizontal FOV code placed in unused zero words), plus `gsaspectratio=16:9`. None of our cheats write anywhere near those (our nearest writes are `0x31B3E4` and `0x3B75D0`; the code caves are at `0x3E0130`-`0x3E017F` and `0x216538`-`0x218FEF`; full list in docs/MEMORY-MAP.md). Checked 2026-10-13 against PCSX2/pcsx2_patches `SLUS-21150_C9F6EF9A.pnach`; not yet tested together in-game.

## Open questions and next targets

- **What a style ID controls.** Found: the style picks a command list (`0x00515C10`) that turns inputs into action IDs, each action has hit records with its base damage, and a motion script that names the animations it plays and their frame ranges. See docs/CODEMAP.md, "The command table", and docs/ANIMATION.md. The style is read live from the class row, so changing it mid-fight changes the next move. Frame data (when a hit is active) is still open: probably the action's second stream or event records.
- **Fighter stats**: found (HP, level, attack rank, money in the person templates at `0x00413130` and person records at `0x0060D360`). See docs/CODEMAP.md.
- **Cut content**: see docs/CUTCONTENT.md. All six cheats are tested. Next: try switch 18 (debug head start, on a new game) and switch 17 (controller 2 drives enemies) in story mode, trace switches 16 and 39, see the short boxer style on real street boxers, and find which GRAPH/SCRIPT/FSCENE entries are never loaded.
- **Game mechanics**: damage formula, Pride Gauge, EXP, ability points and Criminal Level are mapped. See docs/MECHANICS.md; its "Open leads" lists what is left (status effects, disguises, item effects, negotiation outcomes).
- **CDATA.XAF entry 0**: 189 appearance presets of 1176 bytes: 22 outfit slots `{u32 item, s16 parts[16]}` then body parameters. See docs/CODEMAP.md, "Character loading".
- **CDATA.XAF entries 1-4**: blocks starting with `f21b`, probably compressed.
- **SCRIPT.XAF**: decoded (docs/SCRIPTS.md). Entries 1000 + n are mission n's script (story chapters, the 50 side jobs, random events), 0-999 are dialogue scripts in six languages; both are disassembled by `tools/scriptkit.py`. Next: the dialogue player's commands, the job menu, and a first script mod (a new or changed job).
- **Ghidra**: set up on Daniel's PC (see "Ghidra" above). 6,855 of 6,856 functions are exported as pseudocode; rebuild it after adding many symbols so the new names show up. Sony library signatures added 2026-10-13 (`ApplyPS2Signatures.py`, 707 names); not run on Daniel's PC yet.
