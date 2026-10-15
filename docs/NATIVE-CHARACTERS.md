# Native characters: inventory

What it would take for new characters to work like the game's own: no per-character hooks, every system finds them through the same tables it uses for everyone else. This is the inventory Daniel asked for on 2026-10-15 (after Eggusz, docs/PLAN-new-characters.md): every table indexed by person id, template id or preset, every hard-coded limit, and the code that touches them. Read from the decomp (`decomp/all.c`) and `codemap.py addr-refs` by Claude on 2026-10-15; nothing here is tested in-game. How it was found is at the end, so it can be redone after a decomp rebuild.

## Verdict

Doable, and the amount of code is bounded: about **45 functions** to replace or patch, **~150 address references** to repoint (mechanical, `addr-refs --move`), and **three research pieces** (saving, portraits, dialogue scripts). After that, a new character is data: a template, a preset, a name, a placement entry and optionally a portrait and dialogue.

The hard part is not B.LIST-style lists any more: it is that **person ids are a shared number space** (see below), so new characters need ids **above 601**, and every piece of code that assumes "a saved person is 0-199" has to learn about the new range.

## The id space today

| Ids | What | Record | Template | Saved |
|---|---|---|---|---|
| 0 | the player | `g_Persons[0]` | `g_PersonDefs[0]` (+ hero preset) | yes (game file) |
| 1-199 | named people: heroes, allies, bosses, recruitable street people | `g_Persons[id]` | `g_PersonDefs[id]` | yes |
| 51, 52 | the cut character editor's slots ("edit1p"/"edit2p"); Eggusz uses 51 | as above | as above | yes |
| 200-601 | **template ids** of street enemies and story extras; when one appears it is copied into a temporary record 200-209 whose `Person.id` (+0x3E) holds the template id | `g_Persons[200..209]`, found by searching +0x3E | `g_PersonDefs[id]` | no |

So "person id" = template id, and ids 200-601 are taken by templates even though they have no permanent record. **New characters must use ids 602 and up** (s16, so up to 32767). Every id is stored as s16 or s32 in the structures checked (`Fighter.person` s32, `AreaPerson.person` s16, `g_Party` s16, scripts s16); u8 copies were not seen but were not searched for exhaustively (open question 1).

`g_Persons` (`0x0060D360`, 210 x 0x43C) is followed directly by other data at `0x00644C38`, and `g_PersonDefs` (`0x00413130`, 602 x 0x48) directly by `g_PresetBody` (`0x0041DA40`), so neither table can grow in place.

## Inventory

### 1. Person records (`g_Persons`)

| Code | What | Change for ids 602+ |
|---|---|---|
| `Person_Get` `0x0013C960` (859 calls in 226 functions) | 0-199 direct, else search records 200-209 by +0x3E | hook: 602+ -> extension table |
| Same lookup **inlined** in `Fighter_DisplayName` `0x0013CA80`, `Person_SetMoney` `0x0013CC70`, `Person_AddMoney` `0x0013CDC0`, `Criminal_Recalc` `0x0013DFE0`, `Hero_ScaleToPlayer` `0x0013EB30`, `Fighter_GetPerson` `0x002F9250` | | rewrite in C (they are small or already understood) |
| Direct `id * 0x43C` indexing: `Person_Init` `0x0013B490`, `Person_Reset` `0x0013B840`, `Person_GetP2` `0x0013C9F0`, `0x00173170`, `VsMode_Main` `0x00340C60`, `VsMode_MakeFighters` `0x00344550` | index by slot or id with no lookup | hook or rewrite each |
| 216 `lui`/`addiu` references into `0x0060D360-0x00644C38` | mostly fixed fields of record 0 (the player: money, level...) | none: the table stays where it is |

### 2. Templates (`g_PersonDefs`)

57 functions index `g_PersonDefs` by id (140 address references into `0x00413130-0x0041DA40`). For ids 602+ the table must be **moved** to a bigger copy (the B.LIST method: `addr-refs 413130 41DA40 --move`). Watch `0x002F7740`, which reads `g_PresetBody` as `g_PersonDefs[601].start_entries[preset - 44]`: that is a read past the table's end and must keep pointing at `0x0041DA40`.

### 3. Per-person byte tables

| Table | Size | Saved | What (how sure) | Accessors |
|---|---|---|---|---|
| `g_PersonAbsent` `0x0060BBB0` | u8[600] | no | non-zero = not present in the area (a countdown; `Person_IsPresent` reads it) | `0x0013DA30`, `0x0013DA60`, `0x0013DBC0` (clear), `0x0013DC80`, `0x0013DCA0` (tick) |
| `g_SaveBlock_369AC` `0x0060BAE0` | u8[200] | game file | per-person countdown, ticked by `0x0013EA40` | `0x0013E9D0`, `0x0013E9F0` |
| `g_PersonLocState` `0x0060D1AD` | u8[200] | game file (inside the `0x60CA90` block) | ally assignment state (3 = assigned to a location, 4, 5-8...; `Person_IsState3`) | `0x001C3750`, `0x001C3CA0` (clear), `0x001C3DB0`-`0x001C4040` |
| `g_PersonLocation` `0x0060D275` | u8[200] | game file | the location an ally is assigned to (docs/UNLOCKS.md) | `0x001C3750`, `0x001C3E80`, `0x001C3FE0`, `0x001C4080` |
| `g_CarryAllyFlags` `0x0060B480`, `g_CarryBlistInfo` `0x0060B550` | u8[200], u16[200] | ? | probably the new-game-plus carry-over of ally bit 1 and `blist_info` | `0x0013AD20` (store), `0x0013AC70` (restore) |
| Blacklist bits `g_SystemData +0x54` `0x0060C754` | 600 bits | **system file** | beaten = unlocked in VS; read by 8 VS functions | `Blacklist_IsSet` `0x0013D8E0`, `Blacklist_Set` `0x0013E7E0`, `0x0013D890` |
| Second bit array `g_SystemData +0x9F` | | system file | set and cleared by the ending | `0x0013D940`, `0x0013D990`, `0x0013D9E0` |

All of these are indexed by id with no bound check: ids 602+ need a bigger table or a hook on each accessor (all are small accessor functions, which helps: about 20 accessors).

### 4. Code that walks persons 0-199

Every loop `for id in 0..199` misses new characters. Found (each is small unless noted):

- set-up and new game: `Persons_InitAll` `0x0013BB10`, `0x0013BED0`, `Persons_ResetAll` `0x0013BAC0`, `Persons_SetStartAllies` `0x0013BB60`, `0x0013AC70`, `0x0013AD20`, `0x002D7CB0`, `0x00173170` (case in a bigger switch), `0x002B4A90` (loops 0-599 through `Person_Get`)
- allies: `Allies_Count` `0x0013BD00`, `Allies_Strongest` `0x0013BDA0`, `Allies_ListByStatus` `0x00142F90`, `Allies_AnyArrested` `0x002FD280`, `Allies_Arrested` `0x003A0510`, `Allies_FirstFree` `0x001C44A0`, `0x001C4550`, `0x00398000` (picks 3 allies by max HP), `ScrOp_EXF_CHECK_ARREST` `0x003A05E0`, `Criminal_Recalc` `0x0013DFE0` (ally count and average level feed Leadership)
- locations: `0x001A2620`, `0x003AAB50`
- lists: `BList_Build` (already replaced: templates 1-200), `VsMode_SelectScreen` `0x00370620` (builds `g_VsCustomIds` from templates 1-199), `0x003C6F40`, `0x003DBAD0`

A few more may hide behind other loop shapes; the scan only finds comparisons with the literal limits.

### 5. "Saved person" checks (`id < 200`)

Code that tells a saved person from a street enemy by `id < 200` treats ids 602+ as street enemies: `Area_PeopleLayer` `0x002E7130` (only saved people are skipped when in the party or dead), `Area_SpawnPeople` `0x00139E50` (ids 200+ get `Person_Init` into a temporary record: a new character would be **re-created from the template every time**), `VsMode_MakeFighters` `0x00344550` (ids < 200 come from the save, others from the template). Each needs "saved = id < 200 or a new character".

### 6. Name text

Names are `Text_Get(11001 + id)` in 6 functions: `Fighter_DisplayName`, `BList_EntryName` `0x0018D020`, `0x0018EDC0`, `0x00198A10`, `0x001B2BE0`, `0x003DF430`. `Text_Get` `0x00387980` picks one of three resident banks by id range (bank 1: 40000-49999, bank 2: 12000-17999, bank 0 or the language bank otherwise), binary-searches it (`0x00387D20`) and falls back to text 10201 when the id is missing. New ids 602-998 give text ids 11603-11999 (bank 0's range). **A native fix is a fourth "mod bank"** searched by the `Text_Get` hook: any text id the mod defines wins. That also serves dialogue lines. Whether 11603-11999 are already used is open question 2.

### 7. Presets (looks)

- 189 presets in CDATA.XAF entry 0 (`g_PresetData`, `Preset_Get` `0x002A8720`, already replaced by the Eggusz mod). 11 unused numbers remain (1, 19, 20, 87, 94, 97, 127, 129, 132, 141, 143).
- Per-preset tables with 189 entries: `g_PresetFlagA` `0x00431B60`, `g_PresetValueB` `0x00431C20` (both read only by `NpcSpawn_Step` `0x00178700` and `0x00178E60`), `g_PresetBody` `0x0041DA40` (`0x002F7740`), `g_StreetTextures` `0x00430C90` (`NpcSpawn_Step`, `0x00178E60`).
- **Street model** = CDATA.XAF entry **preset + 7**. Presets 189+ would load CDATA entries 196+, which are other data. So past the 11 free numbers, new presets need `NpcSpawn_Step` to load the street model from somewhere else (or reuse an existing preset's street model, which is what Eggusz does).
- **Fight model** = prebuilt ARCHIVE.XAF entry = preset number, except for persons 51/52 (`Fighter_UsesPresetModel` `0x002F52C0`), which build the model from the outfit slots. New characters would use the 51/52 path (already hooked for Eggusz); no new ARCHIVE entries needed.

### 8. Portraits

Two hard-coded `if` chains map a **person id** to a cell of a portrait atlas, cell 0x80 = "?":
- VS select: `VsSelect_DrawPortrait` `0x003B2700` (cells 0-0x7F, xy table `g_VsPortraitCells` `0x005B81F0`, 4 bytes per cell)
- B.LIST detail panel: inside `BList_DetailPanel` `0x001A8550` (xy table `0x005B8150`)

Native portraits need: a hook on both mappings that looks the id up in a table, and new pixels, either in free cells of the atlas texture (if there are any) or a second texture. Which texture the atlas is and whether it has room is open question 3.

### 9. Where people stand (placement)

`g_PeoplePlacement` (loaded from disc, layers x areas x **7** `AreaPerson` entries) is the game's own spawn data; `Area_BuildPeople` `0x002E67C0` overlays the layers. A native character is one more entry in a layer. But each area has **7 slots at most** (`g_AreaPeople`), so a new character has to take an empty slot in the area and layer where he should appear (Eggusz's subway slot was free in stage 6). The data is in RAM after loading, so a loader can patch entries in after `Area_Load` instead of the current per-character hook.

### 10. Dialogue

`AreaPerson +6` names a dialogue script (SCRIPT.XAF 0-999). New lines need script ids the game doesn't use, served from our RAM by a hook on the script loader, and text from the mod text bank (6). Needs the script assembler (plan step 2) and the loader's address (not looked up yet).

### 11. Saving

Researched 2026-10-15 (Claude, read from the code; not tested). Details of the card format are in docs/CODEMAP.md, "Saves".

**How the game saves.** The RD3 library keeps a table of 5 files (`g_McFiles` `0x0069C2B0`, 0x40 bytes each; the register functions refuse index 5+): file 0 is one big data file `BASLUS-21150XXX/BASLUS-21150XXX`, files 1-4 are the icons and `icon.sys`. The data file is fixed-size and holds everything: the system block (0x248), then 6 slot headers (0x80 each), then 6 game blocks (0x36A74 each), every block followed by a 4-byte trailer with a 16-bit checksum (`MemCard_SetChecksum` `0x001DE320`, checked by `MemCard_TestChecksum` `0x001DE440` on load). A slot is read and written in place with seek + read/write (`MemCard_ReadFile` `0x001E0AD0`, `MemCard_WriteFile` `0x001E0F40`).

**Can it take a third file?** Not through the library: the table is full (5 of 5) and its state lives right after it. Two ways remain:

| Option | How | Pros | Cons |
|---|---|---|---|
| **A. Space the game already has** (recommended first) | `@hook SaveData_Pack`: after the original, write the new characters' data over **persons 51 and 52's records** in the save image (2 x 1084 = 2168 bytes, unused once Eggusz moves to an id 602+). `@hook SaveData_Unpack`: read it back, then rebuild 51/52 from their templates. Blacklist bits of new characters go in the system file's reserved **`dummy[228]`** (`g_SystemData +0x164`-`+0x247`, named by the game's own debug print in `Boot_LoadModules` `0x001D1810`, "dummy[228] = %d"; no code reads or writes it): 1824 bits. | No card code at all; covered by the game's checksum; copies, deletes and backs up with the save; saves made before the mod load fine (no magic word = new characters start from their templates); no extra card space | Fixed room: a record without its outfit slots (which come from the template) is 292 bytes plus ~4 table bytes, so **7 characters**; with a simple zero-run compression probably about 20 |
| B. Own file in the save directory | Our own small state machine with `sceMcOpen` / `sceMcSeek` / `sceMcWrite` / `sceMcClose` + `sceMcSync` (the library's pattern), run after the library reports a finished save (`MemCard_SaveSlot` `0x001DED10` reaching state 200) and before the menu continues; path e.g. `BASLUS-21150XXX/BDMODCHR`, 6 slots | No size limit | Needs the save/load menus' flow (when the card is idle, error handling, card full); extra card space (32 full records x 6 slots = about 210 KB); not checksummed unless we add it |

Recommendation: **A now, B only if we ever need more than ~20 characters.** The blob format starts with a magic word and a version so B can take over later without breaking saves.

Things A must handle:
- VS CUSTOM reads player 2's save straight from a buffer (`g_VsP2Persons`): a P2 new character must be read from the blob in that buffer, and P2's persons 51/52 cleaned up the same way.
- A save made with the mod and loaded without it: persons 51/52 hold the blob. Vanilla never lists them (no blacklist number) and VS CUSTOM overwrites 51 with the player record, so this is probably harmless (not tested).
- The slot header (0x80 bytes, used up to `+0x1F` by `Save_BuildGameFile`) has 96 more unused bytes, if a version field is ever needed outside the game block.

### 12. Already done (Eggusz work)

B.LIST and VS CUSTOM lists (no 110 limit), name via `Text_Get` hook, `Preset_Get` replacement, fight model from outfit slots for 51/52, subway placement hook. These become the generic versions above.

## Proposed design

1. **New id range 602+** with an extension table for records (`g_PersonsExt`, in the mod `@bss` area or Extended RAM) and a moved, bigger `g_PersonDefs`.
2. **One C module** (`mods/c/native_chars.c`) that replaces the ~45 functions above with versions that know the extension, the same way `new_characters.c` replaced the `BList_*` functions. Grouped: lookups (sections 1, 5), per-person tables (3), loops (4), names and text bank (6), portraits (8), placement (9).
3. **Save storage** (section 11, option A: the unused records 51/52 in each game slot and `dummy[228]` in the system file).
4. **Character data** as a table the module reads (`NewChar` records: template, preset, name, placement, portrait, dialogue), generated from `chars/*.json` by a `bdkit.py` command and put in the pnach (or later read from a file, see the loader discussion in PLAN-new-characters.md).
5. Move Eggusz to id 602 as the first native character and delete his special cases.

Order of work: 1 + 2 (lookups, tables, loops) and test that an id-602 Eggusz spawns, fights, is recruited and survives an area change; then 3 (saving), then 6 and 8-10.

## Open questions

1. Are person ids ever stored in a byte (u8) anywhere? Ids 602+ would be cut. Known u8 lists (`g_PhoneOrderAllies`, `g_AutoMissions`) hold specific story people, not new ones; a full search is still needed.
2. Are text ids 11603-11999 used by the game? (Dump bank 0's ids.)
3. Which texture holds the portrait atlas, how big is a cell, and is anything free?
4. ~~Can the memory card code take a third file?~~ Answered in section 11: not through the library (its file table is full); use the unused records 51/52 and `dummy[228]`, or our own card code later.
5. Which code reads `g_PersonAbsent` past 200 (it is u8[600], so street enemy templates use it too) and whether new ids should have entries there.
6. `0x002B4A90` calls `Person_Get(0..599)`: ids 210-599 aren't in the temporary records, so `Person_Get` returns record 210, one past the table (`0x00644C38`), and writes `+0x432` there. Harmless today; an extension must not put anything at `0x00644C38`.

## How this was found (to redo it)

- Limits: scan `decomp/all.c` for comparisons with 199, 200, 0xD2, 600, 189, 602 and 110 (functions grouped, then read one by one).
- Per-person tables: tables indexed by a function's first parameter in the person code (`0x0013A000-0x0013F000`, `0x001C3000-0x001C5000`).
- Inline `Person_Get`: functions containing `0x642240` (the address of record 200).
- Reference counts: `python tools/codemap.py addr-refs ISO/SLUS_211.50 60D360 644C38` (216) and `413130 41DA40` (140).
- `python tools/codemap.py const-uses decomp/all.c 199 200 0xd2` repeats the first scan.
