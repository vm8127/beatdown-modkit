# Plan: new characters you can meet, fight and recruit

Started 2026-10-15. Goal: add brand-new characters to story mode: they appear somewhere, you fight them, you can recruit them, and they show up in the blacklist and VS mode. The first one is **Eggusz**. Status: **planning; nothing built yet.** Update this file as the work goes (what was found, what was tested, by whom).

## Eggusz (the first new character)

| What | Wanted | Leads |
|---|---|---|
| Name | **Eggusz** (HP bar, menus, blacklist) | names come from `Text_Get(11001 + person +0x3E)` (`Fighter_DisplayName` `0x0013CA80`); new text needs a `Text_Get` hook returning our string for his id |
| Head | **bald**, **black mustache** | item names are text 16000 + item index (CDATA.XAF 392): HAIRSTYLE:BALD = 16094; FACIAL HAIR types 1-6 = 16063-16068 (which one is a mustache: look in the game) |
| Top | **red leather jacket** | TOP:LEATHER = 16137, TOP:LEATHER 2 = 16138 (check which is a jacket) |
| Pants | **jeans** | PANTS:JEANS = 16154 (others 16155-16161) |
| Shoes | **black sneakers** | SHOES:SNEAKERS = 16346 (2 = 16348, 3 = 16345, 4 = 16347) |
| Colours | red jacket, black shoes, black mustache | probably the variant in bits 12-15 of an appearance code (`g_Appearance` `0x0060BE50`: code = category x 100 + n, variant << 12) and/or the outfit slot parts; confirm |
| Moves, strength | not decided yet: ask Daniel | any class row / style (`swap-moveset`, `mix-moveset`) |

How a look is built: an outfit **preset** (CDATA.XAF entry 0, 189 presets, `Preset_Get` `0x002A8720`) is 22 slots `{u32 item, s16 parts[16]}` (ARCHIVE.XAF part names: `bdkit.py archive-names`) plus body params; the person template's `+4` picks the preset. A new look = a new preset image in the mod area (or extended RAM) returned by a `Preset_Get` hook for a new preset number, the same trick as the Aaron/Chester model swap (`mods/c/aaron_chester_model.c`). Find the item indexes and parts by reading `g_ItemTable` `0x004F2400` (52-byte records, parts list at +0x12) for the items above, and copy a similar existing preset (an NPC in jeans and sneakers) as the starting point.

## Where new characters live

- **Persons 51 and 52** are unused placeholders (template and saved person record: preset 0, 1 HP, level 1; no script or code refers to them). A recruitable character must be a saved person (ids 0-199), so these are the first two slots: **Eggusz = person 51**.
- **More than two is wanted** (Daniel: "2 characters is not really enough"). Research options before building the second one:
  1. Other unused or cut templates among 0-199 (dumps/persons.txt; check that no script/code uses them, like 51/52). Note: every person 0-199 is saved, so reusing a minor one costs that NPC.
  2. Extend `g_Persons` past 210: `Person_Get` `0x0013C960` (the most-called function) could map new ids (210+) to records in extended RAM (`0x02000000`+, docs/MEMORY-MAP.md "Extended RAM"); `g_PersonDefs` copies also there. Needs: every loop over persons (ally lists, recruit checks `0x003A08D0`, `0x00398BA0`...), the save file (fixed `0x36A74` bytes, `SaveData_Pack` `0x0013A950` copies persons 0-199) and the system data bits (`+0x54`, 600 bits, fine). The save is the hard part: extra persons would need their own storage (a spare save block, or a second memory card file).
  3. Temporary persons 200-209 are reused street enemies (not saved): fine for one-off fights, not for recruits.

## Steps (agreed order)

1. **Eggusz as a fighter**: fill template 51 (`g_PersonDefs[51]` `0x00413F88`, 72 bytes: preset, class row, level, HP, Pride, attack rank, money; struct `PersonDef`), build his preset (look above), name hook, moves. Test by putting person/template 51 into one slot of the VS roster (`g_VsRoster` `0x00589A40`, 84 ids ending -999) and fighting him in VS mode in the sandbox. Also check that the person record (`g_Persons[51]`) gets rebuilt from the template on a new game / or set it directly.
2. **Script assembler**: `tools/scriptkit.py asm` (text from `dis` back to bytes; docs/SCRIPTS.md has the format). Prove it by rebuilding mission 1 byte-for-byte.
3. **Meeting and fight**: a mission script that, when you enter an area, places Eggusz (`EXF_SET_NPC`, `EXF_RECOVER_NPC`, `EXF_HIDE_NPC`, `EXF_SET_POS`; how scripted NPC placement works is still open, read the handlers) and starts the fight (`EXF_SET_BATTLE 51`). Load it with a C hook on `Mission_StartScript` for a free mission id, started from `Mission_AutoStart` or a story flag.
4. **Recruiting**: either the normal after-KO RECRUIT (ordinary people; how they decide to accept isn't traced: `Talk_Update` `0x002DE850` steps 1000+) or straight from the script after a win (`EXF_JOIN_FRIEND 51`, like Gina's cutscene recruits her). Then he's an ally (person `+0x3A8` bit 0) and can join the party.
5. **Dialogue**: a new dialogue script (same format as SCRIPT.XAF 0-999) with our own text, played by `EXF_MESSAGE`; needs the assembler and a text source.
6. **Blacklist and VS**: beating him sets his bit in system data `+0x54` automatically (docs/CODEMAP.md, "Blacklist and VS unlocks"); adding him to VS needs a longer copy of `g_VsRoster` (find whether the VS select screen can show more than 84). Trace the B.LIST screen (pause menu state 13) to confirm it reads the same bits.

## Testing

Sandbox PCSX2 (`tools/pcsx2.py`, README "Testing in a sandbox PCSX2"): Daniel's save state 1 (Aaron, stage 8) loads with 32 MB RAM (`pcsx2.py ram128 off`, the current setting). Teleport with `tools/debug/teleport.c`; debug cheats go in `tools/debug/` (`@org 0x000DF000`-`0x000DFFFF`, one hook per function: two debug cheats hooking `MissionMgr_Task` at once don't work). If the mod needs extended RAM, new 128 MB save states are needed (ask Daniel).
