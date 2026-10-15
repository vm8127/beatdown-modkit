# Plan: new characters you can meet, fight and recruit

Started 2026-10-15. Goal: add brand-new characters to story mode: they appear somewhere, you fight them, you can recruit them, and they show up in the blacklist and VS mode. The first one is **Eggusz**. Status (2026-10-15): **Eggusz is built and installed** (`mods/c/new_characters.c`, cheat "New characters: Eggusz (person 51) in the subway, chapter 2"). Tested by Claude in the sandbox: free-roam look, fight look, name, Jason G's moves, RECRUIT, joining the party, blacklist bit. **B.LIST and VS CUSTOM done** (2026-10-15, sandbox, see the last log entry). **Open:** a fresh boot with a memory card save, Daniel's test. See "Progress log" at the end. Update this file as the work goes (what was found, what was tested, by whom).

## Eggusz (the first new character)

| What | Wanted | Leads |
|---|---|---|
| Name | **Eggusz** (HP bar, menus, blacklist) | names come from `Text_Get(11001 + person +0x3E)` (`Fighter_DisplayName` `0x0013CA80`); new text needs a `Text_Get` hook returning our string for his id |
| Head | **bald**, **black mustache** | item names are text 16000 + item index (CDATA.XAF 392): HAIRSTYLE:BALD = 16094; FACIAL HAIR types 1-6 = 16063-16068 (which one is a mustache: look in the game) |
| Top | **red leather jacket** | TOP:LEATHER = 16137, TOP:LEATHER 2 = 16138 (check which is a jacket) |
| Pants | **jeans** | PANTS:JEANS = 16154 (others 16155-16161) |
| Shoes | **black sneakers** | SHOES:SNEAKERS = 16346 (2 = 16348, 3 = 16345, 4 = 16347) |
| Colours | red jacket, black shoes, black mustache | probably the variant in bits 12-15 of an appearance code (`g_Appearance` `0x0060BE50`: code = category x 100 + n, variant << 12) and/or the outfit slot parts; confirm |
| Moves | **Jason G's fighting style** (Daniel, 2026-10-15) | simplest: template class row **37** (Jason G's row: large body, style 0x12, his animation groups), so moves, animations and the MOVE LIST all match. His outfit must suit a large body (copy a large-body preset as the base) |
| Strength | **Wendel's second-encounter stats** (Daniel, 2026-10-15; he first asked for Jason G's free-roam stats, then changed it): template **77** = level 12, max HP 3000, Pride 200, attack rank 1 (x1.0), money 1000. Copy these fixed values into template 51 (no level scaling). Keep `kind` (`+0x0D`) at 0, not 77's 5: kind 5 makes a story boss, and bosses skip the after-KO talk, so RECRUIT would never be offered | `PersonDef` level `+0x0E`, max_hp `+0x10`, pride `+0x12`, attack_rank `+0x15`, money `+0x18`; Wendel's templates in dumps/persons.txt: 5 (ally copy), 77 and 72 (story bosses, kind 5), 133 (other outfit) |
| Where and when | **a normal street person, not a mission or forced encounter**: he stands around in the **ABANDONED SUBWAY STATION** (location 2) during **Chapter 2, "Decimate Fatima's Saints!"** (objective text 31074), like the other people you can walk up to, threaten, fight and recruit | how the game picks which people appear in an area per chapter / story stage is **not found yet**: that is the main research of step 3. Story stage of chapter 2 unknown (known: stage 8 = chapter 4; docs/UNLOCKS.md) |

How a look is built: an outfit **preset** (CDATA.XAF entry 0, 189 presets, `Preset_Get` `0x002A8720`) is 22 slots `{u32 item, s16 parts[16]}` (ARCHIVE.XAF part names: `bdkit.py archive-names`) plus body params; the person template's `+4` picks the preset. A new look = a new preset image in the mod area (or extended RAM) returned by a `Preset_Get` hook for a new preset number, the same trick as the Aaron/Chester model swap (`mods/c/aaron_chester_model.c`). Find the item indexes and parts by reading `g_ItemTable` `0x004F2400` (52-byte records, parts list at +0x12) for the items above, and copy a similar existing preset (an NPC in jeans and sneakers) as the starting point.

## Where new characters live

- **Persons 51 and 52** are unused placeholders (template and saved person record: preset 0, 1 HP, level 1; no script or code refers to them). A recruitable character must be a saved person (ids 0-199), so these are the first two slots: **Eggusz = person 51**.
- **More than two is wanted** (Daniel: "2 characters is not really enough"). Research options before building the second one:
  1. Other unused or cut templates among 0-199 (dumps/persons.txt; check that no script/code uses them, like 51/52). Note: every person 0-199 is saved, so reusing a minor one costs that NPC.
  2. Extend `g_Persons` past 210: `Person_Get` `0x0013C960` (the most-called function) could map new ids (210+) to records in extended RAM (`0x02000000`+, docs/MEMORY-MAP.md "Extended RAM"); `g_PersonDefs` copies also there. Needs: every loop over persons (ally lists, recruit checks `0x003A08D0`, `0x00398BA0`...), the save file (fixed `0x36A74` bytes, `SaveData_Pack` `0x0013A950` copies persons 0-199) and the system data bits (`+0x54`, 600 bits, fine). The save is the hard part: extra persons would need their own storage (a spare save block, or a second memory card file).
  3. Temporary persons 200-209 are reused street enemies (not saved): fine for one-off fights, not for recruits.

## Steps (agreed order)

1. **Eggusz as a fighter**: fill template 51 (`g_PersonDefs[51]` `0x00413F88`, 72 bytes: preset, class row, level, HP, Pride, attack rank, money; struct `PersonDef`), build his preset (look above), name hook, moves. Test by putting person/template 51 into one slot of the VS roster (`g_VsRoster` `0x00589A40`, 84 ids ending -999) and fighting him in VS mode in the sandbox. Also check that the person record (`g_Persons[51]`) gets rebuilt from the template on a new game / or set it directly.
2. **Script assembler** (only if step 3 needs scripts): `tools/scriptkit.py asm` (text from `dis` back to bytes; docs/SCRIPTS.md has the format). Prove it by rebuilding mission 1 byte-for-byte.
3. **On the street**: Daniel wants him met **normally on the street**, not through a mission or a forced encounter. Find how street people are spawned per area and story stage (the people standing around that you walk up to: NPC placement / spawn tables per area and chapter; leads: the NPC slots 2-12 in `g_Fighters`, `Fighter_FindNpcSlot` `0x00176130`, `Fighter_AssignPerson` `0x002A89D0`, `Person_Init` `0x0013B490`, the area-entry code `Story_AreaEvents` `0x0038CE00` and what it calls, `0x003A3680` behind `EXF_SET_NPC`, and the function trace: `pcsx2.py trace` while entering an area with people). Then add Eggusz to the ABANDONED SUBWAY STATION's list for the Chapter 2 (Fatima's Saints) stage, preferably as a data table that can take more characters and places later. Fighting him then starts like any street fight (walk up, threaten or attack). Step 2 (the assembler) is only needed if this turns out to go through scripts; dialogue (step 5) may not be needed at all for a street person.
4. **Recruiting**: the normal negotiation RECRUIT after beating him or while threatening him, like any street person (how a person decides to accept isn't traced: `Talk_Update` `0x002DE850` steps 1000+; his template's Pride, level and kind probably matter). Don't make him a boss (`PersonDef.kind` 5) or the after-KO talk is skipped. Then he's an ally (person `+0x3A8` bit 0) and can join the party.
5. **Dialogue**: a new dialogue script (same format as SCRIPT.XAF 0-999) with our own text, played by `EXF_MESSAGE`; needs the assembler and a text source.
6. **Blacklist and VS**: beating him sets his bit in system data `+0x54` automatically (docs/CODEMAP.md, "Blacklist and VS unlocks"); adding him to VS needs a longer copy of `g_VsRoster` (find whether the VS select screen can show more than 84). Trace the B.LIST screen (pause menu state 13) to confirm it reads the same bits.

## Testing

Sandbox PCSX2 (`tools/pcsx2.py`, README "Testing in a sandbox PCSX2"): Daniel's save state 1 (Aaron, stage 8) loads with 32 MB RAM (`pcsx2.py ram128 off`, the current setting). Teleport with `tools/debug/teleport.c`; debug cheats go in `tools/debug/` (`@org 0x000DF000`-`0x000DFFFF`, one hook per function: two debug cheats hooking `MissionMgr_Task` at once don't work). If the mod needs extended RAM, new 128 MB save states are needed (ask Daniel).

## Progress log

### 2026-10-15 (Claude, sandbox PCSX2, Daniel's save state 2 = start of chapter 2, Raven)

**Built:** `mods/c/new_characters.c` (C mod, `@org 0x000A1000`, `@bss 0x000E1000`; not installed in Daniel's PCSX2 yet, not in `mods/*.pnach` yet). One table row per character (`new_chars[]`: person, preset number, base template + stat overrides, name, fight outfit slots, street model) and one per placement (`new_places[]`: person, area, story-stage mask, slot, `AreaPerson` entry). Hooks:
- `Person_Init` hook writes the templates into `g_PersonDefs` (copy of template 83, a normal street person, with preset 87, class row 37, level 12, 3000 HP, Pride 200, rank 1, $1000, kind 0, no start weapon).
- `Preset_Get` is replaced (`@jump`; it starts with a branch so it can't take `@hook`): preset 87 returns a preset image built in `@bss` from the table's slot list plus the body params of `body_preset`.
- `Text_Get` hook: text 11001 + 51 (person 51's name, was "edit1p") returns "Ｅｇｇｕｓｚ" (full-width UTF-8 like the game's text).
- `Area_BuildPeople` hook: after the game fills the area's 7 people slots, adds Eggusz's entry in the subway in stage 6 if that slot is empty and he passes the game's own checks (present, HP > 0, not in the party, not an ally); a save made before the mod gets person 51 rebuilt from the template there.
- `NpcSpawn_Step` hook (street look): the first version **paused PCSX2**. Cause: cmod built 24-byte stack frames, and the game's code saves registers with 128-bit `sq`, which needs a 16-byte aligned sp. Fixed in `tools/cmod.py` (frames rounded up to 16); this matters for every C mod that calls game code. (Superseded below.)

**Tested (sandbox, Claude):** Eggusz appears in the ABANDONED SUBWAY STATION in stage 6, at person 128's spot (-27.6, 11.8). Walking up and pressing Cross talks to him: the HP bar says "Eggusz", he plays dialogue 67 ("Hey, there. How ya doin'?") and offers NEGOTIATION (Circle) / BATTLE (Square). BATTLE starts "Raven VS Eggusz", a 1-on-1 street fight; in it he is fighter slot 1, person 51, HP 3000/3000, class row 37 (Jason G's style). Not yet tried: winning, RECRUIT, his moves in action, VS mode.

**Found (read from code, checked in the sandbox):**
- **Who stands where**: `Area_BuildPeople` `0x002E67C0` (called by `Area_Load` `0x002FE3D0`) fills `g_AreaPeople` `0x006CB920` (7 x 64-byte `AreaPerson`) from the placement data at `g_PeoplePlacement` (pointer `0x005FEBB8`, in RAM): 12 layer offsets, each layer = an offset per **area id** to 7 entries. Layer 0 is the base, layers 0-3 also by time/state, the story-stage layer comes from `g_StageLayer` `0x00509AA0` (stages 1-5 -> layer 5, which is empty; 6-10 -> 6-10), and mission layers. Entry type 1 = person (ids < 200 saved persons, 200+ templates made into temporary persons), 4/5 clears a slot. `Area_PeopleBase` `0x002E6DC0` / `Area_PeopleLayer` `0x002E7130` apply them; `Area_SpawnPeople` `0x00139E50` spawns them (`NpcSpawn_Step` `0x00178700` per person).
- **Area ids differ from the docs' location table**: the subway is `Area_Current()` **5** (the docs say 2). Downtown street = 1. The location table in docs/UNLOCKS.md needs re-checking.
- **Chapter 2 starts at story stage 6** (Daniel's chapter-2 save). Stage 6's subway layer adds person 83 in slot 6; the base layer has temps 313-316.
- `AreaPerson +6` is the **dialogue script** (SCRIPT.XAF 0-999) played when you talk to the person: 67 = generic tough guy, 433 = "There used to be a subway down here". `+4` and `+0x10` go to the fighter (`+0x470A`, `+0x4708`; `+0x10` is the idle motion, 571 etc.). Interaction radius = template `+0x1C` (float, 30.0 for 83).
- **Positions from type-4 entries are not usable** (the first try put him inside a wall).
- **Three different models per person**: walking around = low-poly street model CDATA.XAF entry preset + 7 with the textures in `g_StreetTextures` `0x00430C90` (10 per preset); fights = the prebuilt ARCHIVE.XAF entry = preset number (`Fighter_LoadModel` `0x002F53A0`), **except persons 51 and 52** (`Fighter_UsesPresetModel` `0x002F52C0` returns 0 for them: they were the cut character editor's "edit1p"/"edit2p" slots), whose fight model is built from the outfit slots (head pieces from ARCHIVE.XAF combinations, clothes = ARCHIVE.XAF item + 0x3A6, textures = DATA.XAF ids). So a new look works in fights only for persons 51/52, and walking around only through a street model.
- **Outfit slot format**: `{item, parts[16]}` where item indexes `g_ItemTable` (its `+0x10` is a DATA.XAF mesh) and parts are **DATA.XAF texture ids** (not ARCHIVE.XAF entries, as the README said). First bug: I copied `g_ItemTable`'s default part lists (meshes) as textures, and the fight load waited forever for a mesh as texture (state 0xC). Use the preset's own slot parts.
- `bdkit.py tex DATA.XAF out ids...` (new) writes textures as PNG (8-bit with CSM1-swizzled 256-colour palette, or 4-bit stored one pixel per byte with 16 colours).
- **Eggusz's fight look** (now in the table, not yet seen in a fight): preset 56's body 195 and head 84 (texture 336 = light skin with a black mustache), preset 89's red leather jacket (top item 208, texture 3419), trousers item 227 with preset 27's blue denim texture 5902, black sneakers (items 35/36, texture 1870), bald scalp (hair item 23, texture 1650 from preset 55), body build params of preset 56 (1, 6). Street look planned: preset 89's street model (bald, red leather jacket) with face atlas 7567 (mustache), jeans 4535, jacket 5236, scalp 1650.
- Character editor tables: appearance records (`g_AppearanceItems` `0x0075B330`, 485 x 0x70) `+0x2C` group, `+0x30` kind and `+0x24` index pick an item from `g_EditorItems` `0x00503514` (HAIRSTYLE:BALD -> item 23, SLICKED BACK -> 335). Tops and trousers go through per-body-build lists instead.
- Unused preset numbers (no template uses them): 1, 19, 20, 87, 94, 97, 127, 129, 132, 141, 143; their entries in the per-preset tables (`g_PresetFlagA`, `g_PresetValueB`, `g_PresetBody`) are normal, so new characters use these (Eggusz = 87). Preset numbers 189+ would read past those tables.
- `PersonDef.level` is a byte (`+0x0E`), not s16; `+0x0C` goes to `Person.kind`, `+0x30` to `Person.skills` (bit 31 hides the Pride bar: Wendel's template 77 has it, so his template is not copied).

**Next:** (1) find why the street-model override pauses PCSX2; (2) see the composed look in a fight and in free roam, show Daniel; (3) win the fight and RECRUIT (or negotiate); (4) VS roster slot + blacklist bit; (5) install, README "Mods so far", MEMORY-MAP ranges, docs.

Sandbox tips learned: `pcsx2.py resume` (new) unpauses; face a person by pressing the stick briefly toward them (camera-relative) before Cross; the fighter's facing angle is `+0x2D0` (degrees); `pcsx2.py cheats --trace` now leaves out functions that enabled cheats already hook.

### 2026-10-15, later (Claude, sandbox; Daniel's save slot 10 = chapter 2 in the subway with the mod on)

- **Street look done**: the street pack is CDATA.XAF preset + 7 (texture chunks + mesh), not a model with free textures. `NpcSpawn_Step` is held in step 1 until Eggusz's own DATA.XAF textures (face 7567, jeans 4535, scalp 1650) are loaded with `Tex_Request` (cache key = id); then preset 89's pack is loaded with those ids as keys, so it reuses them; the extra references are released after the spawn. The row `g_StreetTextures[87]` is written too. Result in free roam: bald, black mustache, red leather jacket, blue jeans, black shoes.
- **Fight look done** (persons 51/52 are built from the outfit slots): bald, mustache, red leather jacket, jeans, black sneakers, Jason G's stance. He beat Raven once (Jason G's style, rank x1.0 and 3000 HP is strong against Raven at level 4).
- **RECRUIT works**: knockout, negotiation menu (RECRUIT, ROB, INTERROGATE, BEATDOWN, CANCEL; with only the no-damage test cheat on, not the negotiation-on-KO cheat), RECRUIT, "OK, I'll do what you say.", battle result, "Add Eggusz to the party / Keep on call", then he is in the party (`g_Party` = {0, 51}), person `+0x3A8` = 3, blacklist bit set (`0x0060C75A` bit 3). Once he is an ally he is no longer placed in the subway (the hook skips allies).
- **B.LIST**: the pause menu blacklist (`0x0018D250`) has **110 fixed places**; each person's place is template `+0x44` (`PersonDef.blacklist_no`), and all 110 are used. Eggusz is not listed yet (place 0). Adding new characters there means a longer list: 110 (`0x6E`) is hard-coded in that function and its neighbours, and the list buffer `0x006614A0` is 0xDC bytes. Next step.
- **VS roster**: `g_VsRoster` had room for two more ids after its -999 (then the name table at `0x00589AF0`), so Eggusz is entry 84 (`@word 0x00589AE8`). VS mode only offers people whose blacklist bit is set. The VS code has special cases for persons 51/52 (it reads their saved record). Not tested yet.
- Robustness: the templates (and the street row) are installed from every hook, so a memory card load straight into the subway works without a `Person_Init` first (not tested).
- Parts found while building him are in docs/PARTS.md.

**Next:** test VS mode and a fresh boot (ask Daniel whether to do it together); extend B.LIST past 110; then the second character (person 52; for more than two see "Where new characters live").

### 2026-10-15, Daniel's test in his own PCSX2

- **Works** (Daniel): fresh boot, memory card save at the start of chapter 2, Eggusz in the subway with the right look, recruited through RECRUIT.

- **Eggusz is not in VS mode** (Daniel). Cause (read from code): the VS character select (`0x00371160`) does not use `g_VsRoster`; it takes its two lists from the same 110-entry blacklist list as B.LIST (`0x0018EC80`, `0x0018EC00(0/1)`) and greys out people whose blacklist bit is clear (`0x0013D8E0`). So VS mode needs the B.LIST extension; the `g_VsRoster` `@word` probably does nothing (who reads `g_VsRoster`, maybe only the cut select in `VsMode_Main`, is open). Handed to the B.LIST session.
- Also noted: `VsMode_Main` overwrites the class row of persons 51/52 from the cut editor's tables (`0x00589BC8` / `0x00589BD8`, by body params); if that path runs, Eggusz would lose Jason G's style in VS mode.

### 2026-10-15, B.LIST and VS CUSTOM (Claude, sandbox; Daniel drove the VS select)

**Built** into `mods/c/new_characters.c` (details in docs/CODEMAP.md, "The B.LIST screen"):
- **B.LIST takes any number of people**: `g_BList` moves from `0x006614A0` (110 + -1) to `0x000E1C00` (200 + -1; places come from templates 1-200); `BList_Build`, `BList_Clear`, `BList_GetList`, `BList_IndexOf` are replaced by C versions without the 110, and the other 28 `lui`/`addiu` pairs that address the list are repointed (`codemap.py addr-refs ... --move`, new). Scrolling, the "No. n/count" panel and the scroll bar already read `g_BListCount`. New characters get `blacklist_no` from the table (`NewChar.blacklist_no`, Eggusz 111).
- **VS CUSTOM** lists every template with a blacklist number (from the same buffer), so Eggusz is there once beaten. Three VS fixes: `VsCustom_SetupLists` rewritten without its 110 limit (hero then all allies to the front; RANDOM picks among those); VS CUSTOM's hero marks 0x33/0x34 (= persons 51/52!) become 0x10033/0x10034, so a picked 51/52 is the character; and because `VsMode_Main` copies P1's player record into person 51 after loading the save, each new character's record is kept at every `SaveData_Unpack` (`0x000E2000`) and swapped back while `VsMode_MakeFighters` runs. `Fighter_UsesPresetModel` is hooked so a new character's VS copy builds his model from the outfit slots (no prebuilt ARCHIVE.XAF model for his preset).
- The `g_VsRoster` `@word` is dropped: only the old CHARACTER SELECT (`VsMode_Main` state 8) reads that table, and its class-row code for 51/52 would have taken Jason G's style away.

**Tested (sandbox, Daniel's memory card save 2: chapter 2, Raven, Eggusz recruited):**
- B.LIST, all three sorts (FACTION, SKILL, NAME): the new list equals the game's original list (captured with no cheats from the same save) with only Eggusz added (FACTION: 2nd, among the allies; SKILL 59th; NAME 24th). Count "n/111". His entry: "Eggusz", level 12, life 3000/3000, TYPE JASON G, ally of RAVEN, RECRUITED, No. 111/111; portrait "?" (no portrait for preset 87). Sort 3 (VS only) not compared.
- VS CUSTOM, PLAYER vs CPU, save 2 on both sides: lists of 111, Eggusz at index 32, selectable on both sides (Daniel). First build froze on RANDOM (allies were not moved to the front; fixed). Fight with P1 Raven + Eggusz + Felipe: P1's Raven is the saved player record, P1's Eggusz is person 51's record (preset 87, level 12, 3000 HP, class row 37), and with P2 the CPU's Eggusz was right too (P2 reads its save buffer). The fight runs.
- Second run (after the person-51 fix): P1's Eggusz is his own record; on screen he has his look (bald, red leather jacket, jeans, black sneakers) and Jason G's guard stance. Installed in both pnach copies.
- Not checked: VS NORMAL (unchanged: 16 fixed fighters, he isn't one).

**Open:** B.LIST portrait for new characters; `BList_Percent` (ending completion %) still counts places 1-110 only (on purpose); VS NORMAL doesn't offer new characters (its 16 ids are fixed, `g_VsNormalIds`).

### 2026-10-15, native characters: inventory (Claude, read from the decomp)

Daniel asked whether new characters could work like the game's own instead of through per-character hooks. The inventory is **docs/NATIVE-CHARACTERS.md**: every table indexed by person id, template id or preset, every hard-coded limit and the code touching them. Main findings:
- Person ids are shared with template ids: 0-199 are saved people, **200-601 are street-enemy templates** (temporary records 200-209 hold them, found by `Person.id`). So beyond persons 51/52, new characters need **ids 602+**, not 200+.
- About 45 functions to replace or patch: `Person_Get` plus 6 functions with the lookup inlined, 6 that index `g_Persons` directly, ~25 loops over persons 0-199 (allies, new game, arrests, locations, VS list), ~5 `id < 200` "saved person" checks, ~20 accessors of per-person byte tables (`g_PersonAbsent` u8[600], `g_PersonLocState`/`g_PersonLocation` u8[200], the blacklist bits). `g_PersonDefs` has to move to a bigger copy (140 references, mechanical).
- Research still needed: saving the new records (a third memory card file, or ~7 characters in the unused records 51/52), portraits (hard-coded person -> atlas cell chains, `VsSelect_DrawPortrait` `0x003B2700`), dialogue scripts above 999, whether text ids 11603+ are free (names are `Text_Get(11001 + id)`; proposal: a "mod text bank" in the `Text_Get` hook).
- Each area has 7 people slots: a new character needs a free slot in his area and stage.
- New tool: `codemap.py const-uses decomp/all.c 199 200 0xd2` lists functions comparing with given constants.

Not started: the native module itself. Proposed order in NATIVE-CHARACTERS.md ("Proposed design").

### 2026-10-15, saving new characters (Claude, read from the code)

Question: can the memory card code take a third file for the new characters? **Not through the game's library**: its file table has 5 entries and all 5 are used (the data file and four icon files), and the save is one fixed-size data file (system block, 6 slot headers, 6 game blocks, each checksummed). Found instead: room the game already saves but never uses: **persons 51 and 52's records** in every game block (2168 bytes, free once Eggusz moves to an id 602+) and the system file's reserved **`dummy[228]`** (`g_SystemData +0x164`, 1824 bits, for blacklist bits). Hooks on `SaveData_Pack` / `SaveData_Unpack` can keep 7 full characters there (about 20 compressed), checksummed and copied with the save, and old saves keep loading. Our own card file (sceMc calls after the game's save) stays possible if that's ever too small. Details: docs/NATIVE-CHARACTERS.md section 11; card layout in docs/CODEMAP.md "Saves".

