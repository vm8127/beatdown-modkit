# Code map: SLUS_211.50

What the main program does and where, worked out by hand from the US release (no symbols in the ELF; compiler string: "MW MIPS C Compiler 2.4.1.01", i.e. Metrowerks CodeWarrior). All addresses are EE addresses as PCSX2 shows them. ELF offset = address - 0x100000 + 0x80.

Status words used below: **confirmed** means the code was read and the data checked against something known (move names, hero stats, save file size). **Probably** means the name fits the code but wasn't proven. Several of these were since confirmed in-game by the cheats built on them (class table, command lists, move list functions, fighter init, HP bar name, battle talk scenes; see README.md, "Mods so far"); the rest is from reading the code.

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

`symbols/symbols.tsv` is the list of every name in this file (address, kind, name, comment, and the C type when known: `void (Fighter *fighter, int damage)` for a function, `Person[210]` for a table). `symbols/structs.tsv` holds the structs field by field (`Fighter`, `Person`, `PersonDef`, `Preset`, `OutfitSlot`, `ClassRow`, `Command`, `CmdInput`, `HitRecord`, `ActionScript`, `AnimGroup`, `ItemDef`, `Inventory`, `SystemData`, `ScriptOpcode`, `TitleMenuElement`, `Battle`); the tables in this file are the prose version, and a new field goes in both. `python tools/codemap.py symbols ISO/SLUS_211.50 symbols` regenerates three exports in `symbols/` plus the C mod headers `tools/cmod/structs.h` and `tools/cmod/symbols.h`:

| File | For |
|---|---|
| `SLUS_211.50.sym` | PCSX2 debugger. One `ADDRESS name` per line (the no$ format PCSX2's symbol importer reads). In PCSX2 2.x: Settings, Debug, Analysis, add it as a symbol file, then reboot the game. Not tried on V's PCSX2 yet. |
| `ImportBeatdownSymbols.py` | Ghidra. Load `SLUS_211.50` at 0x00100000 (MIPS R5900, or the emotionengine-reloaded extension), then run it from the Script Manager. Creates functions, labels and plate comments, maps the zero-initialized globals, creates the structs and applies the types. |
| `beatdown_symbols.csv` | Anything else (spreadsheets, IDA, scripts). |

To see a struct's known fields with real values, `python tools/pcsx2.py show Fighter g_Fighters --state <save state>` (or live from the sandbox PCSX2 without `--state`).

Other `codemap.py` commands: `infer-types` (struct pointer parameters for Ghidra, see README "Ghidra"), `commands` (a style's command table with damage), `hits` (one action's hit records), `persons` (all 602 person templates), `actions` (an action's motion script: which animations it plays), `anim-check` (animations a class's groups don't load), `pnach-map` (addresses each cheat writes, and overlaps). Their output for every style and person is in `dumps/commands.txt` and `dumps/persons.txt`.

## Memory map

| Range | What |
|---|---|
| `0x00100000-0x0016FFFF` | Sony libraries and libc (libpad, libmc, libcdvd, libmpeg, printf/scanf, memcpy `0x12BA38`, memset `0x12BBF0`). Every function the SDK signatures identify is in `dumps/ps2_sdk_functions.tsv` |
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
| `0x006C55F0` | g_AnimSlots | loaded animation per global animation id + 1 (ref counts at `0x006C7140`, group counts at `0x006C7860`); see docs/ANIMATION.md |

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
       ─> g_ActionScripts[action]          0x005848E0, 2001 x { motion script ptr, second stream ptr }
                                           Fighter_SetAction 0x0031F120 loads these into the fighter
                                           (+0x3FD4/+0x3FD8) and sets +0x4346 = action; Action_Step
                                           0x0031FAE0 runs the motion script (which animations play,
                                           frame ranges); Action_Timeline 0x00320310 runs the second
                                           stream (active frames, combo cancel, effects): docs/ANIMATION.md
```

Frame data (docs/ANIMATION.md, "Frame data"): the timeline waits on the motion frame `+0x2D4`; op 0x24 sets the attack window (`+0x44F4`-`+0x44F6`, spheres `+0x44F0` from `g_AttackSpheres` `0x00515D90`) that `Fighter_AttackCollide` `0x002EC560` checks; op 0x16 is the combo cancel point (`Action_TryCombo` `0x0031F250`); op 0x3C hands control back early (`Fighter_ReturnControl` `0x0030BC40`). `python tools/codemap.py framedata ISO/SLUS_211.50 0x13` prints it per command. Animation data (STAGE.XAF, RenderWare compressed keyframes): docs/ANIMATION.md, "Animation file format", and `tools/animkit.py`.

Hit reactions (docs/ANIMATION.md, "Hit reactions, guard and locomotion"): `Combat_TakeHit` `0x0030DFD0` plays an action from `g_ReactionSets` `0x005FE260` (set 0 `0x005161C0`, set 1 `0x00516300`; the set is `g_HitSituationSet` `0x005D0630`[situation] from `Combat_SituationFactor`), by reaction kind and direction; knockdowns continue with lying action 20 / 19 and getup 22 / 21. Guard-type codes 0x40-0x46 start remapped action 10 (anim 13). The walk task `0x0030CA90` takes its actions and speeds from `g_WalkModes` `0x00516560`.

The matching is done by `Cmd_MatchSequence` `0x002A6720` (input history at `+0`, count at `+256`) and `Cmd_MatchSingle` `0x002A68B0`. From neutral the command handler `Fighter_HandleCommand` `0x002A4DB0` uses `Cmd_MatchSingle` (one-input commands, retrying with `g_InputFallback` `0x005CD9B0`: →→P → →P → P) and resets the history to the pressed code (`Cmd_HistoryReset` `0x002A6330`); at a cancel point `Action_TryCombo` appends the last input (`Cmd_HistoryAppend` `0x002A6360`) and needs a whole-sequence match (docs/ANIMATION.md, "Input matching"). Hit record fields (cost, Pride, hit level, reaction): docs/MECHANICS.md, "Damage". A non-zero condition is a 16-byte record `{u16 move list index, then required stat levels}`; `Cmd_CheckCondition` `0x002A63A0` (fighter, condition) compares bytes `+2`.. with the fighter's stat levels from `0x002F8B40`, so these are the "learn at level" gates on hero moves (read from the code, not tested). They don't name a hero, so a command keeps working when copied into another style's list (`bdkit.py mix-moveset`). `Fighter_RemapAction` only touches negative action IDs, and command lists hold positive ones.

The MOVE LIST screen (`0x001C6200` area) reads a style's lines only through `MoveList_Count` `0x001C5BA0` (?, style), `MoveList_NameText` `0x001C5BF0` and `MoveList_InputText` `0x001C5C30` (?, style, line), and `MoveList_Color` `0x001C5C70` (style, line; 1 picks the second text colour, from the input text plus a few hard-coded lines of styles 0x12-0x14). A line is listed only if `MoveList_IsLearned` `0x00317E50` (fighter, style, line) passes: it looks for a command in the style's list whose condition starts with that line number and checks the condition. `bdkit.py mix-moveset` hooks the four functions to show mixed lists and renumbers copied conditions. Weapon moves probably use a second set of lists chosen by weapon kind, `Style_GetWeaponCommandList` `0x00317BE0` (28 lists).

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

**Free character slots**: templates and persons **51 and 52** are blank placeholders (preset 0, 1 HP, level 1, class row 1) that no mission script and no `Person_Get` constant in the code refers to (checked 2026-10-15). Persons 0-199 are saved and one per template, so these two are the natural slots for new characters (a recruitable person must be 0-199). Persons 200-209 are temporary street enemies (ids from templates 200+, looked up through `+0x3E`).

**Id space** (read from the code 2026-10-15): person ids and template ids are the same numbers. 0-199 have saved records; 200-601 are templates only (street enemies, story extras), copied into the temporary records 200-209 when they appear. `Person_Get`'s lookup is also inlined in 6 functions. Per-person tables outside the record: `g_PersonAbsent` `0x0060BBB0` (u8[600]), `g_SaveBlock_369AC` `0x0060BAE0`, `g_PersonLocState` `0x0060D1AD`, `g_PersonLocation` `0x0060D275` (u8[200] each, saved), `g_CarryAllyFlags` / `g_CarryBlistInfo`, the blacklist bits. Full list, with every loop over 0-199: docs/mods/NATIVE-CHARACTERS.md.

Template fields not listed above: `+8` u8, `+0x0B` s8, `+0x0C` s8, `+0x0D` kind (2 and 5 are tested), `+0x16` s16, `+0x30` s32, `+0x46` u16. `dumps/persons.txt` lists every template's preset, class row, level, HP, guard, rank and money.

## Fighter struct

`g_Fighters` `0x006CFB70`, 0x4730 bytes each. `Fighter_FindByPerson` `0x2FD300` searches slots 0-12; `Fighter_FindNpcSlot` `0x176130` searches 2-12.

| Offset | What |
|---|---|
| `+0x000` | flags (bit 0 active) |
| `+0x004`, `+0x008` | person id |
| `+0x018` | a heap pointer in a fight (0x01694A20 in a save state; was listed as "in use") |
| `+0x2AC` | position, float x3 |
| `+0x3FA4` / `+0x3FA6` | current / previous animation (id + 1; the overlay's MOT) |
| `+0x3FD4`, `+0x3FD8` | current action's motion script / second stream (docs/ANIMATION.md has the other motion fields) |
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

## Blacklist and VS unlocks

Read from the code on 2026-10-14; not tested. The pause menu's **B.LIST** item (text 39523 / 52120, help text 52124 "Take a look at the blacklist.") opens the blacklist. The system save (`g_SystemData`, 584 bytes, kept across playthroughs; the save prompt says it holds "blacklist information") has a bit per person id at `+0x54` (`0x0060C754`, up to `+0x9E`: 600 bits):

- `0x0013E7E0(person)` sets the bit, plus a few special bits at `+0x4C`-`+0x52` for persons 0x39, 0x3C, 0x3F, 0x4A-0x4E, 0x6A, 0x6D. It is called after a fight from `0x00350AB0` with the person of the fighter in the battle record (any person but 185), from `0x002D75B0`, and twice by the ending (`0x002AF790`) for persons 0x6A and 0x6D.
- `0x0013D8E0(person)` reads it. VS mode's character select (`0x00363B30` "Select up to 3 characters", cursor `0x00368120`, and `0x003653A0`, `0x00365E30`, `0x003674A0`, `0x0036D060`, `0x0036F090`) skips people whose bit is clear: **beating someone in story mode unlocks them in VS mode**. `g_VsRoster` `0x00589A40` holds the 84 VS fighters.
- `0x0013D890(person)` (set `+0x54` too) is used by `0x0013B110` on the five heroes; `0x0013D940` / `0x0013D990` / `0x0013D9E0` set, clear and read a second bit array at `+0x9F` (called by the ending and the post-ending new game).

**Adding someone to the blacklist / VS roster** is: set their bit (`0x0060C754 + id / 8`, bit `id % 8`), and for someone new to VS, add their id to `g_VsRoster`. The pause menu's B.LIST does **not** read these bits (below).

### The B.LIST screen

Read from the code on 2026-10-15 for the new characters (docs/mods/PLAN-new-characters.md); the moved list is built into `mods/c/new_characters.c`. Names are in symbols.tsv (`BList_*`).

- **The list** `g_BList` `0x006614A0`: 110 s16 person ids and a -1 at `0x0066157C`; the row text handles follow at `0x00661580`. `BList_Build` `0x0018D250` (sort) fills it: template t (1-200) goes to place `PersonDef.blacklist_no` (`+0x44`, 1-110; all 110 are used, 0 = not listed). So **the list holds every listed person from the start**; what you have learned about each one is `Person.blist_info` (`+0x430`, copied from `PersonDef +0x46`; bits 0x8 skills, 0x20 group, 0x200 level, 0x1000 name, else "???"; most code sets it to 0xFFFF, e.g. after a fight; meanings read from the code, not tested). People with `ally_flags` bit 1 get 0xFFFF when the list is built.
- **Order**: first by level (people whose level is known, highest first; the rest after them in place order), then by the sort: 0 = group (the player's hero; allies, split into `Person_IsState3` `0x001C3DD0` (byte `0x0060D1AD[id]` == 3), in hospital, arrested, the rest; story bosses (kind 5); other non-zero kinds; then `PersonDef.blist_group` (+0x00, low byte) 1, 3, 4, 6, 7, 8, others; unknown group last), 1 = skills (`Person.skills` bit 4, 8, 2, any of 0x3E0, 0x10, none; unknown last), 2 = name (`Text_ToAscii` `0x0033A670` + `Str_CompareBytes` `0x00186A30`; unknown names last), anything else (VS mode passes 3) = level only. Nine persons are shown as their other record unless they are allies: 0x58->0x6E, 0x52->0x6D, 0x51->0x6A, 0x12->0x3C, 0x0F->0x4C, 0x0D->0x39, 0x0B->0x4A, 0x09->0x3F, 0x03->0x4B (also in `BList_EntryName` `0x0018D020`).
- **Size**: `BList_Build` sets `g_BListCount` `0x005FEEB8` = 110 and `g_BListMaxTop` `0x005FEEB4` = count - 11; the cursor is `g_BListRow` `0x005FEEDC` (on screen) + `g_BListTop` `0x005FEEE0` (first visible), the sort `g_BListSort` `0x005FEECC`; `BList_Open` `0x001883E0` restores row/top from `0x0060CAB4`/`0x0060CAB6`. Everything else reads the count: `BList_Input` `0x0018A3F0` (scrolling), `BList_DetailPanel` `0x001A8550` (person, blacklist_no, count: the "No. n" page) and the scroll bar. The hard-coded 110s are only in `BList_Build` (and its 13 stack buckets of 110), `BList_Clear` `0x0018EBC0`, `BList_GetList` `0x0018EC00` (a 0xE0-byte copy to `0x006613C0`), `BList_IndexOf` `0x0018EDE0`, `BList_Percent` `0x0018EA90` (completion %, see below) and VS mode's `0x00371160`.
- **55 references** to the list (`python tools/codemap.py addr-refs ISO/SLUS_211.50 6614A0 661580`), all plain `lui`+`addiu` pairs in the `BList_*` functions (0x00187EC0-0x0018EDE0).
- **VS mode uses the same buffer** (read from the code 2026-10-15; V saw Eggusz missing from VS before this): `VsMode_SelectScreen` `0x00370620` (every frame of `VsMode_Main` states 3-10) calls `BList_Clear`, `BList_Build(3)`, then `BList_SetList` `0x0018EC80` with `g_VsNormalIds` `0x005DA080` (VS NORMAL: 16 heroes and bosses) or, in **VS CUSTOM** (`g_VsCustom` `0x006000D4`, set from the title menu), `g_VsCustomIds` `0x0076A970`: every template 1-199 with a blacklist number, in template order. The select screen skips people whose blacklist bit (`0x0013D8E0`) is clear. `VsCustom_SetupLists` `0x00371160` makes one list per side (`BList_GetList(0/1)`), moves the side's own story hero (`g_VsSaveHero` `0x006000D0`) to the front and counts allies, in loops that stop at 110; `BList_IndexOf` finds the cursor's person. So **a template with a blacklist number is in VS CUSTOM**. The list length is `g_VsSelect +0x58` (`g_VsSelect` `0x006005F4` points at `0x00783070`; picks at `+0x20` (P1) and `+0x2C` (P2), 3 s32 each).
- **VS CUSTOM's hero marks**: `VsMode_Main` state 0xB replaces a side's pick that equals its save's hero by **0x33 (P1) / 0x34 (P2)**, and `VsMode_MakeFighters` `0x00344550` copies those from the player record (P1: `Person_Get(0)`; P2: `g_VsP2Persons[0]`, `0x005FEBC8`), any other id < 200 from the save's record (P2 through `Person_GetP2` `0x0013C9F0`), others with `Person_Init`, into the temporary persons `g_VsTempPersons` `0x00589BE8` (134, 136, 137, 142, 145, 146). 0x33 and 0x34 are persons 51 and 52, the cut character editor's "edit1p"/"edit2p": that is why `Fighter_UsesPresetModel` and the old select treat 51/52 specially. A real person 51/52 picked in VS CUSTOM would get the player's record, so the new-characters mod changes the marks to 0x10033/0x10034. Also, right after `SaveData_Unpack` of P1's save, `VsMode_Main` copies the player record (person 0) into **person 51** (tested 2026-10-15: in VS, person 51 = the player's Raven), so the mod keeps the new characters' records from the unpack and swaps them back in while `VsMode_MakeFighters` runs. P2's fighters come from its save buffer `g_VsP2Persons`, which keeps person 51. Tested in the sandbox 2026-10-15 (V's save 2, V picking): Eggusz picked on both sides fights with his own record, look and Jason G's style.
- **`g_VsRoster` `0x00589A40` is not the VS select's list**: it is read by `VsMode_CharacterSelect` `0x003404B0` (the old "CHARACTER SELECT", `VsMode_Main` state 8, reached from state 7 only when the new select isn't used), `DebugMenu_Main` and `VsMode_Main` state 0xB, which, for `g_VsRoster[old cursor]` = 51/52, sets the person's class row from the editor tables `0x00589BC8` / `0x00589BD8` by body build.
- `Fighter.person` (+4) is the person id, or the record's `Person.id` when `0x0060C960` bit 1 is set (`Fighter_AssignPerson`); `Fighter_UsesPresetModel` reads it.
- `BList_Percent` `0x0018EA90`: the share of places 1-110 whose person has `ally_flags` bit 1, 0-100; read by the ending `0x002AF790` and `0x003D5860`. Places over 110 don't count (kept that way by the new-characters mod).
- **Moved by `mods/c/new_characters.c`**: the list lives at `0x000E1C00` (200 + 1 entries; places come from templates 1-200, so 200 is the most), the copy at `0x000E1E00`; `BList_Build`, `BList_Clear`, `BList_GetList` and `BList_IndexOf` are replaced by C versions without the 110, and the other 28 `lui`/`addiu` pairs point at the new list. New characters set `blacklist_no` 111, 112, ...

## Saves

The memory card code is Capcom's "RD3 Memory Card System 1.11". `MemCard_SetupFiles` `0x001DA020` registers directory `BASLUS-21150XXX` with a 584-byte system file (`g_SystemData`), a 0x36A74-byte game file and three icons.

The game file is built by `SaveData_Pack` `0x0013A950` and read back by `SaveData_Unpack` `0x0013AAB0` (**confirmed**: the pieces add up to exactly 0x36A74):

| File offset | Size | From |
|---|---|---|
| `0x00000` | `0x34EE0` | `g_Persons` 0-199 (so money, levels, HP and outfits are saved per person) |
| `0x34EE0` | 2256 | `0x60CA90` |
| `0x357B0` | 56 | `0x60BE10` (first word: `g_StoryChapter`) |
| `0x357E8` | 8 | `g_Party` |
| `0x357F0` | 2052 | `g_Inventory` |
| `0x35FF4` | 156 | `0x60BE50` |
| `0x36090` | 256 | `0x60C990` (`g_StoryVars`, 128 script variables) |
| `0x36190` | 1024 | `g_EventFlags` |
| `0x36590` | 13 + 13 | `g_JobResults` `0x76F0F0`, `g_JobCleared` `0x76F0E0` (docs/SCRIPTS.md) |
| `0x365AC` | 1024 | `0x60B6E0` |
| `0x369AC` | 200 | `0x60BAE0` |

The save is a plain copy of RAM, so a save editor only needs these offsets and the checksum below.

**Card file layout** (read from the code 2026-10-15, not tested). The library has a 5-entry file table (`g_McFiles` `0x0069C2B0`; `MemCard_RegisterFile` `0x001DD7B0` refuses index 5+). `MemCard_SetupFiles` fills all five: file 0 is the data file `BASLUS-21150XXX/BASLUS-21150XXX` (`MemCard_RegisterDataFile` `0x001DD850`), files 1-4 are `icondata.ico`, `cpyicon.ico`, `delicon.ico` and `icon.sys`. The data file is fixed-size (1,344,468 bytes):

| Offset | Size | What |
|---|---|---|
| `0x0` | 0x248 + 4 | system block (`g_SystemData`) |
| `0x24C` + 0x84 x slot | 0x80 + 4 | slot header, 6 slots: `+0` date and time, `+8` 0x97, `+9` level, `+0xA`, `+0xC` mission rank, `+0xE`, `+0x10` hero, `+0x12` ally count, `+0x14` play time, `+0x18` money, `+0x1C`; `+0x20`-`+0x7F` unused (`Save_BuildGameFile` `0x001DB720`) |
| `0x564` + 0x36A78 x slot | 0x36A74 + 4 | game block (`SaveData_Pack`), 6 slots |

Every block ends in a 4-byte trailer whose second half is a 16-bit ones'-complement checksum of the block (`MemCard_SetChecksum` `0x001DE320`; `MemCard_TestChecksum` `0x001DE440` checks it when a slot is loaded). Saving (`MemCard_SaveSlot` `0x001DED10`) writes the system block, the slot's game block and its header in place with `MemCard_WriteFile` `0x001E0F40` (open, seek, write, close); loading uses `MemCard_LoadSlot` `0x001DFC50` / `MemCard_ReadFile` `0x001E0AD0`. A save editor must recompute the checksum.

`g_SystemData +0x164`-`+0x247` is reserved padding: the debug print in `Boot_LoadModules` shows it as "dummy[228]" and no code touches it. New characters can keep data there (docs/mods/NATIVE-CHARACTERS.md, section 11).

## Menus, shops, scripts, text

Less mapped so far; pointers for the next pass:

- **Save/load screens**: memory card state machine `MemCard_Step` `0x1D8CA0` (jump table `0x5CB2F0`), `Save_BuildGameFile` `0x1DB720`, `Load_ApplyGameFile` `0x1DD1F0`.
- **Title, VS mode and debug menus**: `Title_Main` `0x33D7A0` (items `0x589680`, handlers `0x5D7890`), `VsMode_Main` `0x340C60` (earlier mislabeled SaveLoadScreen; calls `VsMode_CharacterSelect` `0x3404B0` and `VsMode_StageSelect` `0x3409C0`), the cut `DebugMenu_Main` `0x340220`, and the debug switch table `g_DebugSwitches` `0x599000`. See docs/CUTCONTENT.md.
- **Shops**: the per-shop logic isn't found yet. Leads: the `SHOP_AD` entries near `0x423690`, a debug shop picker `Debug_ShopSelect` `0x3340D0` ("[SELECT SHOP]", "LEVEL : %d"), and a heap named "ShopGlobal" set up at `0x32FEE0`.
- **Scripts, missions, jobs, events and dialogue**: mapped in docs/SCRIPTS.md. SCRIPT.XAF 1000 + n is mission n's script, run by the event VM (`ScriptVM_Run` `0x39BDD0`, handlers `g_ScriptOpHandlers` `0x5DACF0`, all named `ScrOp_*`); 0-999 are dialogue scripts played by `Dialogue_Step` `0x133B00`. Both use the 204 commands of `g_ScriptOpcodes` `0x411AC0` (it was listed at `0x411ACC` with the wrong layout before). The mission manager is `g_MissionMgr` `0x76ED60`; the 50 side jobs are `g_Jobs` `0x5DB470`. `tools/scriptkit.py` disassembles scripts and lists missions.
- **Text**: `Text_Get` `0x387980` (688 callers). CDATA.XAF entries 385-432 are 8 text banks x 6 languages: 385-390 UI and menus (ids `0x2328`-), 391-396 items, 397-402 move lists, 403-408 mission names, 409-414 partner lines, 415-420 town rumours and hints ("There's a record store in town that doesn't sell records at all."), 421-426 system messages (save prompts), 427-432 credits. Format, Text_Get's id routing, and the control codes (`Text_Encode` `0x001B2BE0`: colours, placeholders `Text_Set*` `0x001B7D80`-, button glyphs `Pad_ActionButton` `0x002EBD40`): docs/FORMATS.md, "Text"; `tools/textkit.py`.
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

- **Action event records**: `g_ActionEvents` records start with a handler address (`0x30BF10` and `0x30BFA0` both call `Fighter_SetAction` on the fighter's `+0x4348`), `+8` is the action `FUN_003084E0` queues. The motion script and the second stream (the timeline with the frame data) are decoded (docs/ANIMATION.md, `codemap.py actions` / `framedata`); the event records aren't.
- **Hit record fields** other than damage (`+0` kind, `+4` maybe stun or knockback, `+10`, `+12`, `+14` flags).
- **Scripts**: found (docs/SCRIPTS.md); its "Open questions" lists what is left.
- **Shops** (see above) and level-up / EXP code (strings "LEVEL: ", "EXP: " near `0x5B83F8`).
- **Item index to name** mapping, and the item table's remaining fields.

## Battle flow and the talk scene

Traced 2026-10-13 for the negotiation-on-knockout mod; full notes in docs/mods/PLAN-auto-negotiation.md. `g_Battle` (`gp-20356`, `0x005FFC6C`; gp is `0x00604BF0`) points at the battle context. `Battle_Update` `0x002DD500` is the battle state machine (state at `+0x10`), `Battle_OnFighterDown` `0x002E2F60` records a knockout, `Battle_RequestTalk` `0x002DE540` is the threaten button, `Battle_StartTalk` `0x002DE6E0` starts a talk scene (kind 0 threaten menu, 1 after a knockout, 3 beg for your life) and `Talk_Update` `0x002DE850` runs it. `Battle_PrideHudShown` `0x002E3A20` decides whether Pride bars are shown.


## Area people, street looks and fight models

Found 2026-10-15 for the new characters (docs/mods/PLAN-new-characters.md, docs/PARTS.md); tested in the sandbox.

- **Who stands in an area**: `Area_Load` `0x002FE3D0` calls `Area_BuildPeople` `0x002E67C0`, which fills `g_AreaPeople` `0x006CB920` (7 `AreaPerson` slots of 64 bytes) from `g_PeoplePlacement` (pointer at `0x005FEBB8`): s32 layer offsets, each layer an offset per area id to 7 entries. Layer 0 = base, 0-3 by time/state, the story stage's layer from `g_StageLayer` `0x00509AA0` (stages 6-10 use layers 6-10; 1-5 use 5, which is empty), plus mission layers. `Area_PeopleBase` `0x002E6DC0` and `Area_PeopleLayer` `0x002E7130` apply them (type 1 person, 2/3 copied, 4/5 clear). `Area_SpawnPeople` `0x00139E50` spawns them, one `NpcSpawn_Step` `0x00178700` per person. `AreaPerson +6` is the dialogue script played when you talk to them.
- **Area ids**: `Area_Current()` returns 5 in the ABANDONED SUBWAY STATION and 1 on DOWNTOWN STREET. Settled 2026-10-15 (read): `Area_ChangeTo`, `Location_Current` and `Area_Load` all use these area ids, the index of `g_AreaDefs` `0x005170F0` (0x104 bytes, `AreaDef`), whose `+0` is the name text (area 5 = text 18002). docs/UNLOCKS.md's location table numbers places by text id instead. Full table in docs/STAGES.md.
- **Stages** (docs/STAGES.md, `tools/stagekit.py`): `Area_Load` `0x002FE3D0` reads FSTAGE.XAF entry = area id (random variants for 1, 7, 0x13, 0x2F) with `Xaf_ReadEntry` `0x001594E0`; `Stage_Parse` `0x00168100` loads its sections: textures, RpWorld (`RpWorldStreamRead` `0x0022FFD0`), wall / camera / floor collision clumps, doors clump + animation (`Doors_Load` `0x00351230`), props (`Stage_LoadProps` `0x0015B5A0`) and PB placements (`Stage_PlacePB` `0x0015C680`). Collision queries: `Collision_Query` `0x00160190`, `Collision_SphereWalls` `0x00160790`, `Collision_Segment` `0x00160960` (camera), `Collision_FloorHeight` `0x00160610`, `Collision_FloorList` `0x0015E430`; current collision `Area_Collision` `0x002FD5F0`. Wall kind per material `Area_MaterialKind` `0x0031D040`. Battle spots `Area_PickBattleSpot` `0x0031D0C0`, used by `Battle_PlaceFighters` `0x002D9AB0`. Per-area tables `g_AreaObjects` `0x00422850` (items, weapons, props per story stage; `Stage_PlaceObjects` `0x0015B7E0`) and `g_AreaDoorFlags` `0x0058BDB4` (`Door_State` `0x003515A0`).
- **Street look**: `NpcSpawn_Step` loads CDATA.XAF entry preset + 7 (8 texture chunks + mesh) with `Pack_Load` `0x0029E500`, using `g_StreetTextures[preset]` `0x00430C90` as the textures' cache keys. Texture cache: `Tex_Request` `0x0029C420`, `Xaf_Service` `0x0029C190`, `Tex_Collect` `0x0029C810`, `Tex_Release` `0x0026EAC0`; DATA.XAF and CDATA.XAF share the name table `0x0059AE30`.
- **Fight model**: `Fighter_LoadModel` `0x002F53A0` loads the prebuilt ARCHIVE.XAF entry = preset number when `Fighter_UsesPresetModel` `0x002F52C0` says the outfit matches the preset; that function always says no for persons 51 and 52 (the cut character editor's "edit1p"/"edit2p"), whose model is built from their outfit slots.
- **B.LIST**: see "The B.LIST screen" under "Blacklist and VS unlocks".
- **Model formats** (2026-10-15, for the remake; docs/FORMATS.md): entries are RenderWare 3.x streams. `Pack_Load` walks the chunks with `RwStreamReadChunkHeaderInfo` `0x0025B5F8` and reads clumps with `RpClumpStreamRead` `0x00231EE8`, images with `RwImageStreamRead` `0x00269E38`, texture dictionaries with `RwTexDictionaryStreamRead` `0x00264500`, textures with `RwTextureStreamRead` `0x00264138`, animations with `RtAnimAnimationStreamRead` `0x002503B0`. RenderWare helpers seen: `RpClumpForAllAtomics` `0x00232998`, `RpGeometryForAllMaterials` `0x00235F50`, `RpMaterialSetTexture` `0x00237878`.
- **Street retexture** (read): when `g_PresetFlagA[preset]` `0x00431B60` is 1, `NpcSpawn_Step` runs `Street_RetextureAtomic` `0x001755A0` / `Street_RetextureMaterial` `0x001754B0` on the body clump (a material with texture `g_NpcSpawnTextures[i]`, i < 4, gets `[i + 4]`) and `Street_HairAtomic` `0x00175650` / `Street_HairMaterial` `0x001755E0` on the hair clump (every material gets `[7]`).
- **Outfit parts** (read): `Fighter_AttachPart` `0x002F4BF0(item, fighter, part slot, clump, ?)`: the body (category 0) becomes the fighter's clump with the HAnim skeleton; any other item is hung on body node `ItemDef.attach_node` (+4; part slot `+0x5F0` = that node's frame). `Fighter_LoadModel` loads each item's pack from ARCHIVE.XAF entry item + 0x3A6 (clump if `ItemDef +0x10` ≠ 0, animation if `+0x12` ≠ 0). `ItemDef` corrected: `+0x10` u16 DATA.XAF mesh, `+0x12` u16 animation, `+0x14` the placeholder texture ids (was listed as `+0x12 parts`). Texture names: `g_TexNames` `0x0059AE30`, per archive `g_ArchiveTexNames` `0x004EC950`.
