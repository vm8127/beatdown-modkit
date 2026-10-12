# Beat Down: Fists of Vengeance modding kit

Everything learned so far about the US release (SLUS-21150), plus tools to extract files and make patches. Start here before any new mod.

**What's in this folder**

| Path | What it is |
|---|---|
| `bdkit.py` | Command-line tool (Python 3, no extra packages). Run `python bdkit.py -h`. |
| `movesets.md` | **Moveset map**: every fighting style ID, who uses it, each fighter's body and move groups, which swaps work, and every style's move list with names and inputs |
| `CODEMAP.md` | **Code map**: named functions, tables and structs in the main program (combat and damage, the command table, character loading, people and money, items, saves) |
| `MECHANICS.md` | **Game mechanics**: what the stats do and the formulas behind them (damage, Pride Gauge, EXP and levels, Stamina/Attack/Technique points, weapons, difficulty, Criminal Level and titles, records), plus a mod cheat sheet |
| `codemap.py`, `symbols.tsv`, `symbols/` | Code map helpers: symbol exports for the PCSX2 debugger and Ghidra, command tables with damage, person templates (`python codemap.py -h`) |
| `dumps/commands.txt` | Every style's command table: input, action ID, base damage and its address, move name (`codemap.py commands`) |
| `dumps/persons.txt` | All 602 person templates with level, HP, guard, attack rank and money (`codemap.py persons`) |
| `dumps/characters.txt` | Every fighter: class row, address, body size, style, animation groups |
| `dumps/fighters.txt` | Every fighter spawn record: outfit preset (model) and class row (`bdkit.py fighters`) |
| `dumps/anim_groups.txt` | All 317 animation groups: which STAGE.XAF pack and which animation IDs |
| `dumps/iso_files.txt` | Every file on the disc with sector (LBA) and size |
| `dumps/xaf_*.txt` | Index of every XAF archive: entry number, offset, size, asset type |
| `dumps/xaf_ARCHIVE.txt` | Outfit and body part names (HAI_ hair, EYE_, MOU_ mouth, WEA_ weapons...) |
| `mods/` | Finished patches (PCSX2 `.pnach`) |

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
+8  u32 skeleton    action remap table, one per body size (S 0x50C230, M 0x50B990, L 0x50BDE0); see CODEMAP.md
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

**To give fighter A the moves of fighter B**, copy B's `style` (+4) and `groups` (+C) into A's row. Keep A's body and skeleton. That only works cleanly when both have the same body size. `bdkit.py swap-moveset SLUS_211.50 A B` prints the patch lines for you and warns when the bodies differ.

**When the body sizes differ** (say Aaron M gets Jason G's L moves), use `bdkit.py swap-moveset SLUS_211.50 A B --keep-body`. Style move groups don't depend on body size (BOXER S/M/L all load group 166, and PERFECT loads every style group on an M body), so instead of borrowing B's list, A's own list is edited in place: A's move group is swapped for B's, B's extra groups are added into the zero padding after the 9999 terminator, and A keeps its own body groups. Each hero's list is used by that hero's row only (Aaron's list at `0x0050D100` has one reference, at `0x0050D8BC`).

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

### Move lists (names and inputs)

Table at `0x005CAB40`, 8 bytes per style, row = style - 1: `{u16 first input text, u16 last input text, u16 first name text, u16 last name text}` (`0xFFFF` = none; only style 0x09 TESTER). 47 rows cover styles `0x01`-`0x2F`: `0x1C`-`0x23` are short versions of the generic styles and `0x25`-`0x2F` are weapon lists, none of them used by a class row. The text lives in CDATA.XAF entries 397-402 (JP, EN, FR, DE, ES, IT), format `{u32 size, u16 count, u16 language, count x {u16 id, u16 len, u32 offset}}` then UTF-8 strings in full-width characters. Buttons in the inputs: 〆 punch, ◎ kick, ◇ guard, 4 action. `bdkit.py moves SLUS_211.50 CDATA.XAF 0x13` prints one style; `bdkit.py style-map SLUS_211.50 CDATA.XAF > movesets.md` regenerates the map. This is the in-game MOVE LIST screen; which animation each move plays is still unknown.

### Animation groups

Table at `0x004FB4C0`, 8 bytes per group: `{s16 STAGE.XAF entry, s16 0, u32 pointer to s16 animation IDs ending in -1}`. Group N loads STAGE.XAF entry `stage_entry`, and the animations in that pack are numbered by the ID list in order. The loader is `0x002DC360`, and the per-fighter loop is `0x002DC550`. See `dumps/anim_groups.txt`.

## Known code addresses

The full map of functions, tables and structs is in `CODEMAP.md`; this is the short list.

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
| `0x001107C8` | Debug print (probably printf) |
| `0x0013B490` | Fighter init `(slot, fighter_id, 0)`: reads the fighter table at `0x00413134`, copies the outfit preset |
| `0x002A8720` | Outfit preset record `(preset, 1 = parts, 2 = params)` from CDATA.XAF entry 0 |
| `0x0013CA80` | Fighter display name; hero presets (`0x18, 0x3F, 0x4E, 0x71, 0x73, 0x99-0x9D`) get the hero name |
| `0x002F9930` | Preset number to name/fighter ID (Aaron's presets 78 and 153 give 68 = text 11069 "Aaron") |
| `0x003E0130` | 20 unused zero words before the VU microcode; used as the code cave for `swap-model` |

## Addresses, offsets and patching

- The ELF has one LOAD segment: EE address `0x00100000` = file offset `0x80`. So **ELF offset = address - 0x100000 + 0x80**.
- `SLUS_211.50` starts at ISO sector 1156876, so **ISO offset = 1156876 x 2048 + ELF offset**.
- `python bdkit.py addr 0x50D8B4` does both conversions.
- PCSX2 pnach line for a 32-bit write: `patch=1,EE,2XXXXXXX,extended,VALUE`, where `XXXXXXX` is the address without its top digit. A `[Section name]` header makes it a cheat you can toggle under Game Properties, Cheats.

## Mods so far

| Mod | File | Status |
|---|---|---|
| Aaron uses Raven's moveset | `mods/SLUS-21150_C9F6EF9A.pnach` | Works in-game (tested by Daniel, 2026-10-12) |
| Aaron uses Jason G's moveset (keeps Aaron's medium body groups) | `mods/SLUS-21150_C9F6EF9A.pnach` | Works in-game (tested by Daniel, 2026-10-12). Confirms `--keep-body` works for M-body heroes using L-body styles. |
| Aaron uses Ignacy's moveset and Chester's model (all medium bodies; first model swap) | `mods/SLUS-21150_C9F6EF9A.pnach` | First version (Aaron's records set to Chester's preset) showed Chester but lost the HP bar name (Daniel, 2026-10-12). Replaced by the init hook, which keeps Aaron's preset number: works in-game with name and model (tested by Daniel, 2026-10-12) |

When adding a new mod, add a new `[section]` to that same pnach file, because PCSX2 reads one file per game. All the Aaron cheats write Aaron's row, so turn on only one of them, and restart the game after switching (a cheat that is turned off leaves its last values in memory).

## Open questions and next targets

- **What a style ID controls.** Found: the style picks a command list (`0x00515C10`) that turns inputs into action IDs, and each action has hit records with its base damage. See CODEMAP.md, "The command table". Frame data and which animation each action plays are still open.
- **Fighter stats**: found (HP, level, attack rank, money in the person templates at `0x00413130` and person records at `0x0060D360`). See CODEMAP.md.
- **Game mechanics**: damage formula, Pride Gauge, EXP, ability points and Criminal Level are mapped. See MECHANICS.md; its "Open leads" lists what is left (status effects, disguises, item effects, negotiation outcomes).
- **CDATA.XAF entry 0**: 189 appearance presets of 1176 bytes: 22 outfit slots `{u32 item, s16 parts[16]}` then body parameters. See CODEMAP.md, "Character loading".
- **CDATA.XAF entries 1-4**: blocks starting with `f21b`, probably compressed.
- **SCRIPT.XAF**: entries 0-999 are 964+ byte bytecode files and 1000+ are indexed event lists. The ELF has opcode names like `EXF_SET_SKILL`, `EXF_SET_MOTION` and `EXF_MOVE_STAGE` near `0x004101E8`.
- **Ghidra**: couldn't be downloaded in Claude's environment. If you install it locally with the `ghidra-emotionengine-reloaded` extension, load `SLUS_211.50` at `0x00100000` and import the addresses above as labels.
