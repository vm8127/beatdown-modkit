# Code map: SLUS_211.50

What the main program does and where, worked out by hand from the US release (no symbols in the ELF; compiler string: "MW MIPS C Compiler 2.4.1.01", i.e. Metrowerks CodeWarrior). All addresses are EE addresses as PCSX2 shows them. ELF offset = address - 0x100000 + 0x80.

Status words used below: **confirmed** means the code was read and the data checked against something known (move names, hero stats, save file size). **Probably** means the name fits the code but wasn't proven. Nothing here has been tested in-game yet.

## Contents

1. [Using the symbols](#using-the-symbols)
2. [Memory map](#memory-map)
3. [Combat and damage](#combat-and-damage)
4. [The command table: input to move to damage](#the-command-table-input-to-move-to-damage)
5. [Character loading](#character-loading)
6. [People: stats, level, money](#people-stats-level-money)
7. [Fighter struct](#fighter-struct)
8. [Items and inventory](#items-and-inventory)
9. [Saves](#saves)
10. [Menus, shops, scripts, text](#menus-shops-scripts-text)
11. [Handy addresses for mods](#handy-addresses-for-mods)
12. [Open leads](#open-leads)

## Using the symbols

`symbols/symbols.tsv` is the list of every name in this file (address, kind, name, comment). `python tools/codemap.py symbols ISO/SLUS_211.50 symbols` regenerates three exports in `symbols/`:

| File | For |
|---|---|
| `SLUS_211.50.sym` | PCSX2 debugger. One `ADDRESS name` per line (the no$ format PCSX2's symbol importer reads). In PCSX2 2.x: Settings, Debug, Analysis, add it as a symbol file, then reboot the game. Not tried on Daniel's PCSX2 yet. |
| `ImportBeatdownSymbols.py` | Ghidra. Load `SLUS_211.50` at 0x00100000 (MIPS R5900, or the emotionengine-reloaded extension), then run it from the Script Manager. Creates functions, labels and plate comments. |
| `beatdown_symbols.csv` | Anything else (spreadsheets, IDA, scripts). |

Other `codemap.py` commands: `commands` (a style's command table with damage), `hits` (one action's hit records), `persons` (all 602 person templates). Their output for every style and person is in `dumps/commands.txt` and `dumps/persons.txt`.

## Memory map

| Range | What |
|---|---|
| `0x00100000-0x0016FFFF` | Sony libraries and libc (libpad, libmc, libcdvd, libmpeg, printf/scanf, memcpy `0x12BA38`, memset `0x12BBF0`) |
| `0x00170000-0x0040D880` | Game code. Rough neighbourhoods: people and money `0x138000-0x13E000`, Capcom memory card system `0x1D8000-0x1E2000`, XAF loading `0x29B000-0x29F000`, fighters, combat and AI `0x2A4000-0x325000`, ZenFS / ZenAudio (XPEC's file and sound layer) `0x34B000-0x34F000`, text `0x387000` |
| `0x0040D880-0x005FE000` | Read-only data: tables listed in this file, strings |
| `0x005FE000-0x00788180` | RAM globals (gp = `0x00604BF0`) |

Main RAM globals:

| Address | Name | What |
|---|---|---|
| `0x0060A680` | g_EventFlags | 1024 bytes = 8192 story flags. `Flag_Get/Set/Clear` = `0x138E20/0x138E70/0x138EC0` |
| `0x0060BEF0` | g_Inventory | `u32 count, u32 items[512]` |
| `0x0060C700` | g_SystemData | 584 bytes, the separate system save: `+4` difficulty (`0x60C704`), `+0x10` language (`0x60C710`) |
| `0x0060D19C` | g_TotalMoneyEarned | s32 |
| `0x0060D360` | g_Persons | 210 person records of 0x43C bytes; record 0 is the player |
| `0x005FEBD0` | g_Party | s16 person IDs of the party |
| `0x005FFDD8` | g_PresetData | pointer to CDATA.XAF entry 0 once loaded |
| `0x006CFB70` | g_Fighters | fighter structs, 0x4730 bytes each; slot 0 = player, NPCs use slots 2-12 |

## Combat and damage

How a hit becomes lost HP (**confirmed** by reading the code):

1. The attacker's current action (`fighter+0x4348`) and hit number (`fighter+0x4570`) select a 16-byte hit record: `*(0x00580A40 + action*4) + hit*16`. Its u16 at `+8` is the **base damage**; `+14` holds flags.
2. `Combat_ResolveHit` `0x00305CC0` (attacker, defender) scales it:
   - plus the held weapon's power (item data `+96`; divided by 3 against some targets; weapons with `+145` set always do 1),
   - times the attacker's attack multiplier (`fighter+0x4414`, float),
   - times the defender's defense multiplier (`fighter+0x4418`, float, normally 1.0),
   - times a situation factor from `0x314D30` (a float: low HP, counter hit, combo scaling; see MECHANICS.md),
   - times 1.2 when the defender's Pride Gauge (`fighter+0x4420`) is empty and `0x2E37E0` holds, minimum 1.
   The result goes into the defender's pending damage, `fighter+0x44B0`.
3. `Combat_TakeHit` `0x0030DFD0` adds the pending damage to the damage/stagger meter (`+0x4426`, capped at max HP; `+0x4428` = 500), counts the hit (`+0x44EE`), and calls:
4. `Fighter_ApplyDamage` `0x002FB880` (fighter, damage): `HP -= damage`, floored at 0. It does nothing while bit 13 of `fighter+0x471C` is set (an invulnerability flag).

Where the multipliers come from, in `Fighter_Spawn` `0x00304B60`:

- Attack multiplier = `g_AttackRankMul[person+0x51]` at `0x005D04D0` = `{0.5, 1.0, 1.3, 1.6, 1.8, 1.9, 2.0}`. All five heroes start at rank 1 (x1.0); bosses are 3-4.
- Then times `person+0x380` / 100 (normally 100).
- Enemies only: times `g_EnemyDamageByDifficulty[difficulty]` at `0x005D04F0` = `{1.0, 0.8, 1.0, 1.5}`.
- HP = person `+0x54`, max HP = person `+0x4E` plus bonus `+0x382`, both capped at 9999. Tired meter max = 1.5 x max HP. The Pride Gauge (called guard here before; see MECHANICS.md) comes from person `+0x3A6` capped by the template's value (`Fighter_SetGuard` `0x2FB780`).

A debug overlay, `Debug_FighterInfo` `0x00302260`, prints most of these (HP, DAMAGE, TIRED, REV, LENGTH, motion category such as "ATTACK DAMAGE"); it isn't reachable in normal play; developer debug switch 5 enables it, then hold L2 and press R2 to show it and hold L2 and click L3 to page (seen in-game; 10 pages, listed in docs/CUTCONTENT.md). Its TASK line is the current action id (`+0x4346`) and MOT the motion id.

## The command table: input to move to damage

This is the missing link between a style and what each button does (**confirmed**: decoding Aaron's list gives his MOVE LIST in order, with the right inputs).

```
style ──> g_StyleCommands[style]          0x00515C10, one pointer per style (0x01-0x24)
            list of { u32 condition ptr (0 = always), u32 sequence ptr }, ends at sequence ptr 0
            sequence = { u32 input code, s16 action, s16 0 } ..., ends at input 0xFFFFFFFF
            the last element's action is the result; earlier elements hold 0
action ─> g_ActionHits[action]             0x00580A40, 2004 pointers: hit records (damage, see above)
       ─> g_ActionEvents[action]           0x00582990, 2004 pointers: 16-byte event records, each starting
                                           with a handler address (0x30BF10, 0x30BFA0, ...)
       ─> g_ActionScripts[action]          0x005848E0, 2001 x { header ptr, bytecode ptr }
                                           Fighter_SetAction 0x0031F120 loads these into the fighter
                                           (+0x3FD4/+0x3FD8) and sets +0x4346 = action
```

The matching is done by `Cmd_MatchSequence` `0x002A6720` (input history at `+0`, count at `+256`) and `Cmd_MatchSingle` `0x002A68B0`. Weapon moves probably use a second set of lists chosen by weapon kind, `Style_GetWeaponCommandList` `0x00317BE0` (28 lists).

Input codes, from Aaron's list:

| Code | Input | Code | Input | Code | Input |
|---|---|---|---|---|---|
| `0x0E` | P | `0x1C` | K | `0x47` | →G |
| `0x0A` | →P | `0x18` | →K | `0x48` | ←G |
| `0x0B` | ←P | `0x19` | ←K | `0x49` | ↑G |
| `0x0C` | ↑P | `0x1A` | ↑K | `0x2F` | grab P |
| `0x0D` | ↓P | `0x1B` | ↓K | `0x32` | grab K |
| `0x05` | →→P | `0x13` | →→K | `0x6B` / `0x6C` | rear grab P / K |
| `0x16` | ↓→K | `0x12` | →↓→K | `0x46` | Devastator (Aaron's Dragon Tail) |

Higher codes (`0x59`-`0x87`) are the situational moves: running, enemy down, mounted, back turned, getting up, near a wall.

Aaron's first commands, as `codemap.py commands` prints them:

```
  0   P        action 1805  damage [100]  @0x00574B68  Blade Cut
  1   K        action 1806  damage [120]  @0x00574C38  Back Kick
  2   →P       action 1807  damage [60]   @0x00574D08  Snake Fang
  4   →P P     action 1808  damage [100]  @0x00574DE8  Double Snake Fang
  6   →P P P   action 1809  damage [250]  @0x00574EE8  Triple Snake Fang
```

The `@` address is the u16 base damage of the first hit, so changing a move's damage is a 16-bit write there (`patch=1,EE,1XXXXXXX,extended,VALUE`). Several styles share generic actions (grabs, throws), so changing one of those changes it for everyone who uses it.

Why style swaps work: the style picks the command list, the command list picks action IDs, and the actions play animations from the groups in the class row's group list. Swapping style plus groups (what `swap-moveset` does) keeps those in step. The class row's `+8` pointer, called "skeleton" in the README, is really a per-body **action remap table** (`g_ActionRemap_S/M/L` at `0x50C230/0x50B990/0x50BDE0`): one s16 per generic action, mostly the same number back, 0 where that body lacks the action, and a few substitutions. `Fighter_RemapAction` `0x002F8A30` reads it.

## Character loading

From a person to a fighter on screen (**confirmed**):

1. **Person template** `g_PersonDefs` `0x00413130`, 602 records of 72 bytes (bdkit's `FIGHTER_TABLE` = this + 4). `Person_Init` `0x0013B490` (slot, template id) copies it into a person record in `g_Persons`.
2. **Appearance preset**: template `+4` picks one of 189 presets in CDATA.XAF entry 0 (1176 bytes each, `Preset_Get` `0x002A8720`). A preset is 22 outfit slots `{u32 item, s16 parts[16] ending -1}` (792 bytes; the parts are mostly ARCHIVE.XAF entries: HAI_ hair, PAN_ trousers...), then body parameters at `+792` (`+0` and `+4` go to person `+5`/`+6`, `+8` to person `+4`, `+12` is the preset's own number). `Person_Init` copies the 22 slots to person `+0x68`.
3. **Fighter**: `Fighter_AssignPerson` `0x002A89D0` (slot, person id) sets `fighter+0x46C0` = class row (from template `+6`, via person `+0x52`), `+0x46C8` = body size from the class table, copies the 22 outfit slots to `fighter+0x3FF8`, then builds the body (`0x2F7740`).
4. **Animations**: `Anim_LoadClassGroups` `0x002DC680` loads the class row's group list (see README).
5. **Spawn**: `Fighter_Spawn` `0x00304B60` sets HP, attack multiplier, guard and meters (see Combat).

So the **model/outfit** comes from the template's preset (`+4`), and the **moveset** from the template's class row (`+6`). They are independent, which is why a model swap and a moveset swap can be done separately. One catch: about nine functions also test preset numbers to recognise the heroes (`Fighter_DisplayName` `0x0013CA80`, `Person_GetHeroDefId` below), so changing a hero's preset number loses its name; the README's model-swap section has the workaround.

**HP bar names** (traced live in PCSX2, 2026-10-13): `HpBar_Build` `0x0031B210(side)`, called from `0x003184D4`, draws one name line per team member. The person IDs come from `Team_GetMember` `0x0013C5C0(side, i)` (team lists at `0x0076EAC8` and `0x0076EAD0`, s16 ending -1), and the name from `jal Fighter_DisplayName` at `0x0031B3E4`. `Fighter_DisplayName` `0x0013CA80(person)` returns text(11001 + `Person_GetHeroDefId`) for hero presets (154, 113, 157, 24, 153, 78, 156, 63, 155, 115) and text(11001 + person `+0x3E`) for everyone else, so a boss shows its own name (Chester = 11021). In story mode the second line under the hero is a recruited party member, not a surname ("McQueen" is template 43's name). `bdkit.py roster` hooks only the call at `0x0031B3E4`.

`Person_GetHeroDefId` `0x002F9930` maps hero presets back to the hero templates: preset 78 or 153 → 68 (Aaron), 115/155 → 107 (Raven), 113/154 → 108 (Gina), 63/156 → 53 (Jason G), 24/157 → 22 (Lola). Templates 153-157 are second copies of the five heroes.

## People: stats, level, money

`g_Persons` `0x0060D360`, 0x43C bytes each. IDs 0-199 index the array directly; IDs 200-209 are looked up by the id stored at `+0x3E` (`Person_Get` `0x0013C960`, the most-called function in the game). Record 0 is the player.

| Offset | Type | What | From template |
|---|---|---|---|
| `+0x00` | u32 | flags | |
| `+0x3E` | s16 | person id | |
| `+0x40` | s32 | **money**, 0-99,999,999 | `+0x18` |
| `+0x44` | s16 | appearance preset | `+0x04` |
| `+0x4C` | s16 | **level** | `+0x0E` |
| `+0x4E` | s16 | **max HP** (cap 9999) | `+0x10` |
| `+0x51` | s8 | attack rank (index into g_AttackRankMul) | `+0x15` |
| `+0x52` | u16 | class row (moveset) | `+0x06` |
| `+0x54` | s16 | **current HP** (cap 9999) | `+0x10` |
| `+0x68` | 22 x 36 | outfit slots | preset |
| `+0x380` | s16 | attack percent (100) | |
| `+0x382` | s16 | bonus max HP | |
| `+0x390` | 16 bytes | two starting entries applied at spawn (`0x2FBC50`), probably weapons | `+0x34` |
| `+0x3A6` | s16 | Pride Gauge max ("guard" in dumps/persons.txt) | `+0x12` |
| `+0x3B4` | s16 | bonus max HP (Person_RecalcMaxHP) | |

`Person_RecalcMaxHP` `0x002AFD60`: for NPCs, max HP = base + (level - template level) x 80 + bonus; for the player, base + n x (100n + 200) + (level - 1) x 30 + bonus, where n is the byte at `0x60D355` (probably a max-HP-up count).

Money (**confirmed**): `Person_AddMoney` `0x0013CDC0` (id, delta) and `Person_SetMoney` `0x0013CC70` (id, value) clamp to 0-99,999,999; when the player gains money, the gain is also added to `g_TotalMoneyEarned` `0x0060D19C`. The player's money is `0x0060D3A0`. Enemies carry the template's money (`+0x18`), presumably as the reward.

Template fields not listed above: `+8` u8, `+0x0B` s8, `+0x0C` s8, `+0x0D` kind (2 and 5 are tested), `+0x16` s16, `+0x30` s32, `+0x46` u16. `dumps/persons.txt` lists every template's preset, class row, level, HP, guard, rank and money.

## Fighter struct

`g_Fighters` `0x006CFB70`, 0x4730 bytes each. `Fighter_FindByPerson` `0x2FD300` searches slots 0-12; `Fighter_FindNpcSlot` `0x176130` searches 2-12.

| Offset | What |
|---|---|
| `+0x000` | flags (bit 0 active) |
| `+0x004`, `+0x008` | person id |
| `+0x018` | in use |
| `+0x2AC` | position, float x3 |
| `+0x3FD4`, `+0x3FD8` | current action header / bytecode |
| `+0x3FF8` | outfit slots (copy of the person's 792 bytes) |
| `+0x432C` | held weapon item, -1 = none |
| `+0x4346` | current action id |
| `+0x4348` | attack action used for hit lookup |
| `+0x4388` | flags (`0x4000` = holding a weapon) |
| `+0x4414` | attack multiplier, float |
| `+0x4418` | defense multiplier, float |
| `+0x441C` | **HP**, s16 (player: `0x006D3F8C`) |
| `+0x441E` | **max HP**, s16 (player: `0x006D3F8E`) |
| `+0x4420` / `+0x4424` | Pride Gauge (float) / max |
| `+0x4426` / `+0x4428` | damage/stagger meter (capped at max HP) / 500 |
| `+0x442A` / `+0x442C` | tired meter / max |
| `+0x44B0` | pending damage |
| `+0x44EE` | hit counter |
| `+0x451C` / `+0x451E` | REV meter / max |
| `+0x4570` | current hit number within the action |
| `+0x4683` | target fighter slot |
| `+0x46C0` | class row (type id - 1) |
| `+0x46C8` | body size |
| `+0x471C` | flags (bit 13 = no damage) |

## Items and inventory

- `g_ItemTable` `0x004F2400`: about 488 records of 52 bytes `{u32 category, u32 ?, u32 flags, u32 use handler, u16 ?, s16 parts[] ending -1}`. Outfit items list their ARCHIVE.XAF parts; usable items have a handler (`0x2F26F0`, `0x2F43F0`). The outfit slots in presets and persons hold indexes into this table.
- `g_Inventory` `0x0060BEF0`: `u32 count`, then up to 512 u32 entries (bits 0-11 item, 12-15 quantity).
- `Inventory_InitForHero` `0x0013D000` fills it from a start list chosen by the hero template: Aaron `0x41DBF0`, Raven `0x41DB10`, Jason G `0x41DB70`, Lola `0x41DC60`, Gina `0x41DCD0`. Lists are `{s16 code, s16 qty}` ending -1, where code = category x 100 + n, converted by `0x13DE00` using the category table at `0x412F40`.
- Item names are in CDATA.XAF entries 391-396 (English 392, ids `0x2EE0`-`0x446A`: "DRINK R", "CHICKEN", "CASH", weapons...). How an item index maps to its name id isn't pinned down yet.

## Saves

The memory card code is Capcom's "RD3 Memory Card System 1.11". `MemCard_SetupFiles` `0x001DA020` registers directory `BASLUS-21150XXX` with a 584-byte system file (`g_SystemData`), a 0x36A74-byte game file and three icons.

The game file is built by `SaveData_Pack` `0x0013A950` and read back by `SaveData_Unpack` `0x0013AAB0` (**confirmed**: the pieces add up to exactly 0x36A74):

| File offset | Size | From |
|---|---|---|
| `0x00000` | `0x34EE0` | `g_Persons` 0-199 (so money, levels, HP and outfits are saved per person) |
| `0x34EE0` | 2256 | `0x60CA90` |
| `0x357B0` | 56 | `0x60BE10` |
| `0x357E8` | 8 | `g_Party` |
| `0x357F0` | 2052 | `g_Inventory` |
| `0x35FF4` | 156 | `0x60BE50` |
| `0x36090` | 256 | `0x60C990` (`g_StoryVars`, 128 script variables) |
| `0x36190` | 1024 | `g_EventFlags` |
| `0x36590` | 13 + 13 | `0x76F0F0`, `0x76F0E0` |
| `0x365AC` | 1024 | `0x60B6E0` |
| `0x369AC` | 200 | `0x60BAE0` |

The save is a plain copy of RAM, so a save editor only needs these offsets (whether the card file adds a checksum around it wasn't checked).

## Menus, shops, scripts, text

Less mapped so far; pointers for the next pass:

- **Save/load screens**: memory card state machine `MemCard_Step` `0x1D8CA0` (jump table `0x5CB2F0`), `Save_BuildGameFile` `0x1DB720`, `Load_ApplyGameFile` `0x1DD1F0`.
- **Title, VS mode and debug menus**: `Title_Main` `0x33D7A0` (items `0x589680`, handlers `0x5D7890`), `VsMode_Main` `0x340C60` (earlier mislabeled SaveLoadScreen; calls `VsMode_CharacterSelect` `0x3404B0` and `VsMode_StageSelect` `0x3409C0`), the cut `DebugMenu_Main` `0x340220`, and the debug switch table `g_DebugSwitches` `0x599000`. See docs/CUTCONTENT.md.
- **Shops**: the per-shop logic isn't found yet. Leads: the `SHOP_AD` entries near `0x423690`, a debug shop picker `Debug_ShopSelect` `0x3340D0` ("[SELECT SHOP]", "LEVEL : %d"), and a heap named "ShopGlobal" set up at `0x32FEE0`.
- **Scripts**: `g_ScriptOpcodes` `0x00411ACC` names all 118 EXF script commands with argument counts (EXF_ADD_MONEY = 0x24, EXF_CHECK_MONEY = 0x2C, EXF_SET_SKILL = 0x39, EXF_ITEM_ADD = 0x17, EXF_ADD_DRESS = 0x62, ...). The interpreter that runs SCRIPT.XAF entries 0-999 isn't located yet; `Script_LoadEventList` `0x3A4F40` loads the event lists (entries 1000+).
- **Text**: `Text_Get` `0x387980` (688 callers). CDATA.XAF entries 385-432 are 8 text banks x 6 languages: 385-390 UI and menus (ids `0x2328`-), 391-396 items, 397-402 move lists, 403-408 mission names, 409-414 partner lines, 415-420 town rumours and hints ("There's a record store in town that doesn't sell records at all."), 421-426 system messages (save prompts), 427-432 credits.
- **GRAPH.XAF names**: `g_GraphNames` `0x005AB0D0` gives a name to each of the 602 GRAPH.XAF entries (BA_PARTS01, ...), looked up by `Graph_FindName` `0x138D20`.

## Handy addresses for mods

Untested starting points. RAM values are rewritten by the game, so a pnach cheat that writes them every frame acts like a freeze.

| Goal | Where |
|---|---|
| Money | `0x0060D3A0`, s32 (player record +0x40). Max 99,999,999 = `0x05F5E0FF`. |
| Player HP / max HP in a fight | `0x006D3F8C` / `0x006D3F8E`, s16 |
| A move's damage | the `@` address in `dumps/commands.txt`, u16 |
| Hero starting stats | templates 68 (Aaron), 107 (Raven), 108 (Gina), 53 (Jason G), 22 (Lola): HP at template +0x10, rank at +0x15, money at +0x18. Mostly takes effect on a new game, because person records are saved; max HP is also recalculated from the template's base HP by `Person_RecalcMaxHP`. |
| Enemy damage by difficulty | `0x005D04F0`, float[4] |
| Attack rank multipliers | `0x005D04D0`, float[7] |
| A person's outfit or model | person +0x44 preset / +0x68 slots; template +4 preset |

## Open leads

- **Action event and script formats**: `g_ActionEvents` records start with a handler address (`0x30BF10` and `0x30BFA0` both call `Fighter_SetAction` on the fighter's `+0x4348`); `g_ActionScripts` bytecode is a stream of u16s that includes small numbers like `0x35` that look like animation slots. Decoding these gives frame data and which animation each action plays.
- **Hit record fields** other than damage (`+0` kind, `+4` maybe stun or knockback, `+10`, `+12`, `+14` flags).
- **Script interpreter** for SCRIPT.XAF 0-999, so EXF commands can be traced to their handlers.
- **Shops** (see above) and level-up / EXP code (strings "LEVEL: ", "EXP: " near `0x5B83F8`).
- **Item index to name** mapping, and the item table's remaining fields.
