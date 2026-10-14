# Scripts, missions, jobs and events

How the game runs its story missions, side jobs, events and dialogue. Everything here was read from the code (2026-10-14) unless it says "tested". Names are in `symbols/symbols.tsv`, structs (`ScriptVM`, `ScriptHeader`, `Mission`, `MissionMgr`, `Job`, `MissionReq`) in `symbols/structs.tsv`.

Tools:

```
python tools/scriptkit.py missions ISO/SLUS_211.50 ISO/XAF/CDATA.XAF > dumps/missions.txt   # every mission: job, reward, when, how it starts
python tools/scriptkit.py dis ISO/SLUS_211.50 ISO/XAF/SCRIPT.XAF 1001                      # mission 1's script (entry 1000 + id)
python tools/scriptkit.py dis ISO/SLUS_211.50 ISO/XAF/SCRIPT.XAF 949 --lang en             # dialogue 949
python tools/scriptkit.py dis ISO/SLUS_211.50 ISO/XAF/SCRIPT.XAF missions --out dumps/scripts
python tools/scriptkit.py stats ISO/SLUS_211.50 ISO/XAF/SCRIPT.XAF > dumps/script_ops.txt  # how often each command is used
```

`dumps/scripts/mission_NNN.txt` has every mission script disassembled; `dumps/missions.txt` is the mission table. Dialogue scripts are not dumped into the repo (they are the game's dialogue text); run `dis` on one locally.

## Contents

1. [The big picture](#the-big-picture)
2. [Missions and the mission manager](#missions-and-the-mission-manager)
3. [How missions start](#how-missions-start)
4. [Side jobs](#side-jobs)
5. [Events: what makes a script page run](#events-what-makes-a-script-page-run)
6. [Script file format](#script-file-format)
7. [The event VM](#the-event-vm)
8. [Command reference](#command-reference)
9. [Example: mission 1, "Attack Bernard"](#example-mission-1-attack-bernard)
10. [Modding notes](#modding-notes)
11. [Open questions](#open-questions)

## The big picture

```
area loads / field frame / battle ends / dialogue ends ... ──► Mission_Post(code) ──► queue 0x0076EF9C
                                                                                         │
MissionMgr_Task (every frame) ── g_MissionEventHandlers[code] ──► event bits on each running mission
                                                                                         │
  g_MissionMgr: 2 slots ─ slot 0: the current mission ─────────► ScriptVM_Run ─ mission script (SCRIPT.XAF 1000 + id)
                        └ slot 1: missions 100 / 101               │  EXF_* commands change the game:
                                                                   │  fights, NPCs, money, items, flags, camera...
                                                                   └► EXF_MESSAGE n ──► Message_Start ──► Dialogue_Step
                                                                                         dialogue script n (SCRIPT.XAF n)
```

- **SCRIPT.XAF 1000 + n** is the script of **mission n** (148 entries, ids 0x00-0x93). "Mission" covers story chapters, the 50 side jobs, random events and background scripts alike: it is just a script the mission manager runs.
- **SCRIPT.XAF 0-999** are **dialogue scripts**: one conversation or caption each, stored six times (Japanese, English, French, German, Spanish, Italian). A mission plays one with `EXF_MESSAGE n` (or `EXF_CALL_TELPHONE`).
- Both kinds use the same 204-command instruction set (`g_ScriptOpcodes` `0x00411AC0`). Mission scripts run in the **event VM** (`ScriptVM_Run` `0x0039BDD0`, one handler per command in `g_ScriptOpHandlers` `0x005DACF0`); dialogue scripts run in the **dialogue player** (`Dialogue_Step` `0x00133B00`, one 16 KB switch). Each player implements the commands it needs; the others are empty stubs in it.
- The command names (`EXF_SET_BATTLE`, `JUMP_BEQUI`, `TEXTSET`, ...) are the developers' own, kept in the ELF for a script tool (the cut SCRIPT VIEWER, docs/CUTCONTENT.md). Some names don't match what the retail handler does (`EXF_ITEM_ADD` adds to `g_StoryVars`); the reference below says what the code does.

## Missions and the mission manager

`g_MissionMgr` `0x0076ED60` (`MissionMgr`, 0x2E4 bytes) has two slots (`Mission`, 0x110 bytes each, at `+0x1C`):

| Slot | Runs | Script buffer |
|---|---|---|
| 0 | every mission except 100 and 101 | `g_EventList` `0x0076F100` |
| 1 | missions 100 (0x64) and 101 (0x65), which run alongside the others | `g_BgMissionScript` `0x00776100` |

`+0xC` / `+0x10` hold the id running in each slot (-1 for none; `Mission_Current` `0x003A4400` reads them). A slot: `+0` mission id, `+4` loader state, `+8` pending event bits, `+0xC` script pointer, `+0x10` register block, `+0xA0` its `ScriptVM`.

Life of a mission:

1. `Mission_Start(id)` `0x003A3590` refuses when scripts are locked out or the slot is taken; otherwise it takes a free slot (`Mission_FreeSlot`), sets it up and raises event bit 1.
2. `Script_LoadEventList` `0x003A4F40` queues SCRIPT.XAF entry 1000 + id into the slot's buffer; `Mission_StartScript` `0x003A50B0` points the VM at it (`ScriptVM_Init` `0x0039BD20`, registers in the slot).
3. `Mission_Step` `0x003A4EA0` runs the VM every frame until the script ends (`EVENT_END` at the top level, or `/EVENT`).
4. `EXF_RESULT 0/1` records success (2) or failure (3) with `Mission_SetResult` `0x003A47D0`; `EXF_EVENT_END` ends the mission (`Mission_End` `0x003A3500`); `Mission_Cleanup` `0x003A4CD0` then resets the mission's state (`Mission_ResetState` `0x003A4020`: mission globals, and the mission's own block of story flags, below) and frees the slot.

**Story flags per mission.** `g_MissionFlagRanges` `0x0059995C` gives each mission id its first story flag; the flags up to the next mission's first one belong to it (10 to 40 flags each, from `0x800` for mission 1 up to `0xF66`). They are cleared when the mission ends (except flags 0xCE4, 0xCE5, 0xCE9, 0xCEA and 0xD71), so a mission keeps its in-progress state in its own flags (`SVFLAG_ON` / `SVFLAG_BRON` in the script). Flags outside the ranges (below `0x800`, story progress) persist. `dumps/missions.txt` lists each range.

**Results are saved.** `g_JobResults` `0x0076F0F0` (2 bits per job: 0 never done, 2 done, 3 failed) and `g_JobCleared` `0x0076F0E0` (2 = ever cleared) are the two 13-byte blocks the save file stores at `0x36590` (docs/CODEMAP.md, "Saves").

## How missions start

| Way | Code | Missions |
|---|---|---|
| **Job menu**: the player takes a job | `0x00141E30` calls `Mission_Start` with the chosen entry; `JobList_Build` `0x003A45B0` builds the menu from `g_JobListA` (34 jobs) or `g_JobListB` (16 jobs) | the 50 side jobs ([Side jobs](#side-jobs)) |
| **Area loads** | `Mission_AutoStart` `0x003B0030` (area): for each of the 26 `g_AutoMissions` `0x005DBD40`, if it is available (`Mission_Unavailable` == 0) and its own condition function (`g_AutoMissionChecks` `0x0059A9A0`) returns 0, start it. Not while the player has a party member following | 0x56, 0x59, 0x5B-0x5D, 0x66-0x70, 0x72, 0x86, 0x88-0x8A, 0x8D-0x8F, 0x91, 0x92: random encounters and recurring events |
| **Talking to someone** | `Mission_TalkStart` `0x003B0610` (person): `g_TalkMissions` `0x005DBD60`; with some people (person `+0x3C` = 2, outdoors area 0x19) only 20% of the time | 0x58, 0x85 |
| **A story flag gets set** | `Mission_FlagTrigger` `0x003B08A0` watches trigger records `{state ptr, s16 flag, u8 mission, u8 step}`; when the flag is set it starts the mission (and clears it again afterwards) | several story and timed missions |
| **Story code** | direct `Mission_Start` calls: 0x90 (`0x0038B4A0`, also from save loading), 7 (`0x0038CE00`), 0x57 and 0x75 (the field loop `0x002C97F0`) | story chapters |

**Requirements.** `Mission_Unavailable(id, chapter, percent)` `0x003B02C0` returns 0 when `g_MissionReq[id]` `0x0059A750` (`MissionReq`, 4 bytes per id) allows it:

- `chapters`: bit n set = allowed while `g_StoryChapter` `0x0060BE10` is n. That word is compared with 1, 5 and 11 by story code and the masks use bits 1-10, so it is very probably the story chapter; the side jobs open in chapters 6-10.
- `min_rank`: at least this value of `MissionRank_Get` (the u32 at `0x0060BADC`, meaning unknown; only mission 0x5B, 0x5C and 0x84 use it).
- `min_percent`: at least this % of the 50 jobs ever cleared (`Jobs_PercentCleared` `0x003A4A70`): 0, 20, 40 or 60.

plus special cases in the same function (0x4E, 0x4F, 0x50, 0x54, 0x75 check the party or the player's sex; a list of missions is blocked while `0x006004B8` counts down after another one).

## Side jobs

`g_Jobs` `0x005DB470`: 50 records of 12 bytes (`Job`): mission id, difficulty (stars 1-5), reward in dollars, title and description text ids (CDATA.XAF entries 403-408: 35000 "Attack Bernard", 35001 its description, ...). The reward shown is the job's; the script pays it with `EXF_ADD_MONEY` (mission 1 pays the same 1000). Job titles by kind: Attack / Revenge on / Payback (beat someone up), Clean Up / Take Out (a group), Return (an item), Escort, Rescue, Deliver, and list B's bigger jobs (Deal at the Park, Underground Fighting, Dangerous Delivery $8000...). `dumps/missions.txt` has all 50 with their chapters and % requirement.

Two lists: `g_JobListA` `0x005DB6D0` (34 jobs, missions 0x01-0x42) and `g_JobListB` `0x005DB760` (16 jobs, 0x45-0x54 and 0x63). `JobList_Build(0 or 1)` keeps the available ones (requirements met, not running, not already done). Which NPC or menu offers which list wasn't traced.

## Events: what makes a script page run

A mission script is a set of **pages** (numbered blocks, `PAGESET n ... /PAGESET`). Most pages start with `EXF_SET_TYPE mask, page`: the page only runs when one of the `mask` event bits is pending (`ScriptVM.events`, copied from the slot every frame); otherwise the VM goes back and waits. So a mission is written as event handlers: "when the area has loaded, place the target"; "when a fight ends, check who won"; "when the dialogue ends, finish".

The game posts event codes with `Mission_Post(code)` `0x003A34B0`; `MissionMgr_Task` `0x003A32E0` maps them through `g_MissionEventHandlers` `0x00599BB0` to bits:

| Code | Bit | Posted by | Meaning |
|---|---|---|---|
| 0 | 0x01 | `Mission_Start` | the mission just started (its first page) |
| 1 | 0x08 | every frame at the end of the field loop (`0x002C97F0`) | field tick: "check your conditions" |
| 2 / 3 | | | clear / set manager flag 1 |
| 4 | 0x04 | field loop, after an area is entered and the auto missions were checked | area loaded |
| 5 | 0x10 | field loop, when the in-battle bit of `0x0060C960` is cleared | probably: back in the field after a fight |
| 6 | 0x20 | field loop, as a fight ends (several places) | fight over: read the result with `EXF_CHECK_ST_BATTLE_END` |
| 7 | 0x40 | `Message_Task` `0x0033B3C0` | a dialogue (`EXF_MESSAGE`) ended |
| 8 | | `Mission_StartScript` | script started |
| 9 | | | cleanup (`0x003A3AB0`) |

Mission 1's pages use masks 1 (start), 8 (tick), 0x20 (fight over), 2 (fail), 4 (area loaded) and 0x40 (dialogue ended).

**Fight results** (`EXF_CHECK_ST_BATTLE_END` → `Battle_ScriptResult` `0x003A5350`): mission 1 treats 0 and 1 as won (pays, success), 4 and 6 as lost (`EXF_RESULT 1`), and 2, 3 and 11 as "try again" (back to waiting). 11 is forced when `0x006004C4` bit 2 is set.

## Script file format

A mission script (SCRIPT.XAF 1000 + id) is one script image. A dialogue entry (0-999) is `u32 count (6)`, `u32 offsets[6]`, then one script image per language (JP, EN, FR, DE, ES, IT); `Xaf_LoadLangPart` `0x001335A0` keeps the current language's.

Script image (`ScriptHeader`):

```
+0x00 u16 id            mission id / dialogue number
+0x02 u16 page_count
+0x04 u32 page_table    offset of u32 page offsets[page_count]
+0x08 u32 string_count
+0x0C u32 string_table  offset of u32 string offsets[string_count] (each from the table's own start), then the strings (UTF-8,
                        full-width ASCII; "\n" is a line break)
+0x14 u32 end
+0x20 code              all offsets above count from here
```

Code is a stream of instructions: `u16 opcode`, then arguments, `words x 4` bytes in all (`words` from `g_ScriptOpcodes`; `Script_OpSize` `0x00138CB0`). Arguments sit at fixed offsets per command: u16 values at +2, +6, +0xA, +0xE; s32 or float values at +4, +8, +0xC, ... (see the reference). Scripts are `EVENT id`, the pages, `/EVENT`.

`g_ScriptOpcodes` `0x00411AC0` (`ScriptOpInfo`, 20 bytes per command): `{u32 id, u32 words, u32 arg count, u8* arg types, char* name}`. The arg type bytes aren't decoded (they were for the script tool).

## The event VM

`ScriptVM` (0x70 bytes, at mission slot `+0xA0`):

| Offset | Field |
|---|---|
| `+0x00` | page count |
| `+0x04` / `+0x08` / `+0x0C` | page table, string table, end |
| `+0x10` | pending event bits |
| `+0x14` | 8 label pointers (`LABEL_SET` / `LABEL_JUMP`) |
| `+0x34` | register block: 16 registers, s32 at `regs + 0x40 + 4n`, a type byte at `regs + 0x80 + n` |
| `+0x38`, `+0x3C` | scratch word and 32 bytes of per-instruction state for blocking commands; cleared after every completed instruction |
| `+0x5C` | script id |
| `+0x5E` | current page; `+0x60` / `+0x62` page range for `EXF_SET_TYPE` |
| `+0x64` | script header; `+0x68` instruction pointer; `+0x6C` previous one |

`ScriptVM_Run` `0x0039BDD0` loop: call `g_ScriptOpHandlers[op].handler(vm)`, then by the command's flags:

- flags 0: always go to the next instruction;
- flags 1 (**jump**): the handler either moved `ip` itself (returns 0) or didn't (returns 1, go to the next instruction);
- flags 2 (**blocking**): returns 1 when done (next instruction), 0 to be called again next frame (the VM stops for this frame);
- a handler returning 2 ends the run (`/EVENT`, a page switch); `ScriptVM_Run` then returns 1.

Jumps always go to the start of a page, so pages double as labels (`PAGE_JUMP`, `JUMP_BEQUI page, value, reg`, `SVFLAG_BRON flag, page`, ...).

**Who an argument names** ("person" in the reference): 0 = the player, -1 / -2 = party member 1 / 2 (`g_Party`), anything else a person id, looked up among the fighters in NPC slots 2-12 (`Script_FighterByPerson` `0x0039BCA0`). Several commands take a register number too: when it's above 0, the person comes from that register instead.

**Generated jobs.** For 13 mission ids (0x27-0x29, 0x48, 0x54, 0x57, 0x58, 0x6A, 0x6E, 0x6F, 0x75, 0x85 and 0x55), `Script_UsesRegArgs` `0x0039BAA0` makes the main argument of `EXF_SET_BATTLE`, `EXF_JOIN_FRIEND`, `EXF_ITEM_*`, `EXF_ADD_MONEY`, `EXF_MESSAGE`, `EXF_SET_MOTION`, ... come from a register (the one the instruction names, register 9 by default). Those missions get their target, reward or item from registers at run time; `EXF_GEN_INIT` / `EXF_GEN_SET` fill a generator table at `0x0076EC60` (5 records of 24 bytes) and `EXF_SET_CALLER` / `EXF_BAININ` pick random people or items. These are the repeatable "random" jobs.

**Registers** live in the mission slot, so they last for one run of the mission. `EXF_TRANS_REG` copies a register to or from a global register array (`Script_GlobalRegs` `0x00139BD0`) that outlives the mission.

## Command reference

From the event VM handlers (`ScrOp_<name>` in symbols.tsv; `decomp/` has each one). "→ rN" stores a result in register N. "waits" = blocking. Offsets are bytes into the instruction. Commands marked "dialogue only" are empty stubs in the event VM (`Dialogue_Step` implements them; not decoded in detail yet). Counts are uses in mission / dialogue scripts (`dumps/script_ops.txt`).

**Structure and control flow**

| Op | Command | Arguments | What it does | Uses |
|---|---|---|---|---|
| 1 | `EVENT` | +2 id | start of a script | 153 / 1015 |
| 2 | `/EVENT` | | end of the script: back to the page table, stop | 147 / 984 |
| 101 | `PAGESET` | +2 page | start of page n (sets the current page) | 2033 / 3250 |
| 102 | `/PAGESET` | +2 next | end of a page: jump to page `next`, or fall through when 0xFFFF | 2033 / 3270 |
| 103 | `PAGE_JUMP` | +2 page | go to a page | 1128 / 228 |
| 63 | `EXF_PAGE_JUMP_EXIT` | +2 page | go to a page (and keep the EXF_SET_TYPE page range) | 259 / 0 |
| 62 | `EXF_SET_TYPE` | +4 event mask, +0xA page, +0xE page range start | run on only when one of the event bits is pending; else go to `page` (or back) and wait | 1737 / 0 |
| 104-117 | `JUMP_BEQ*` / `JUMP_BNE*` (I, UI, S, US, B, UB, F) | +2 page, +4 value (s32, u16, byte or float), +0xA register | if register ==/!= value, go to page | 1124 (BEQUI) |
| 118-121 | `JZE` / `JNZ` / `JMI` / `JPZ` | +2 page, +6 register | branch on register zero / non-zero / negative / not negative | few |
| 158 / 159 | `SVFLAG_ON` / `SVFLAG_OFF` | +2 flag | set / clear a story flag (`Flag_Set`, 8192 flags in `g_EventFlags`, saved) | 617+1165 / 713+48 |
| 160 / 161 | `SVFLAG_BRON` / `SVFLAG_BROFF` | +2 flag, +6 page | go to page if the flag is set / clear | 324 / 1363 |
| 71 / 72 | `EXF_SVFLAG_BRON` / `EXF_SVFLAG_BROFF` | +6 flag, +0xA page | the same with a different layout | |
| 173 / 174 | `LABEL_SET` / `LABEL_JUMP` | +2 label | remember the next instruction as label n / go there | |
| 37 | `EXF_WAIT` | +4 frames | wait (60 per second) | 197 |
| 202 | `CALLFUNC` | +4 n | call `g_ScriptCallFuncs[n]` `0x005B3360` until it returns 1 (waits) | |
| 203 | `EVENT_END` | | end of a handler: return to waiting for events | 1429 / 2703 |
| 31, 14, 38, 46, 77 | `EXF_LOG_MESSAGE`, `EXF_SET_MESNAMES`, `EXF_CHECK_BUSTED`, `EXF_CHECK_CAPTURE`, `EXF_KILL_RECRUITE` | | empty in the retail game | |

**Registers**

| Op | Command | Arguments | What it does |
|---|---|---|---|
| 181-187 | `SETREG_I` / `UI` / `S` / `US` / `B` / `UB` / `F` | +2 register, +4 value | set a register and its type (int, unsigned, short, ..., float) |
| 188 | `SETTYPE` | +2 register, +4 type 0-6 | convert a register to another type |
| 189-191, 193-195 | `REGADDNUM_*` / `REGSUBNUM_*` | +2 register, +4 value | add / subtract a constant |
| 192, 196-199 | `REGADDREG`, `REGSUBREG`, `REGMULREG`, `REGDIVREG_Q`, `REGDIVREG_R` | +2 dst, +4 a, +6 b | dst = a op b (quotient, remainder) |
| 200 | `REGCPYREG` | +4 src, +6 dst | copy |
| 201 | `RANDAM` | +2 register | random number |
| 15 | `EXF_ADD_REGS` | +6 register, +8 value, +0xC 1 = reverse | r += value (or r = value - r) |
| 9 | `EXF_ADD_REGS2` | +6 dst, +8 a, +0xA b, +0xC 1 = subtract | dst = a + b (or a - b) |
| 82 | `EXF_MUL_REG` | +6 register, +8 value, +0xC 1 = divide | r *= value (or /=) |
| 45 | `EXF_RANDOM` | +2 → register, +4 min, +8 max | random in [min, max] |
| 76 | `EXF_TRANS_REG` | +2 register, +4 global index, +8 0 = store / 1 = load | copy to / from the global registers |

**People, party and NPCs**

| Op | Command | Arguments | What it does |
|---|---|---|---|
| 34 | `EXF_SET_NPC` | +4 n | sets up the mission's NPC n (`0x003A3680`) |
| 57 | `EXF_HIDE_NPC` | +4 person, +8 show, +0xC slot, +0x10 | shows / hides a scripted NPC in slot n (`0x0076ECD8`) |
| 80 | `EXF_RECOVER_NPC` | +4 person, +8 register (if not 0), +0xC | revives / spawns a person as an NPC (`0x0039FE50`) |
| 70 | `EXF_SET_NPC_BEF` | +4 person, +8, +0xC, +0x10 slot | NPC behaviour record in slot n (`0x0076ED30`) |
| 69 | `EXF_KILL_NPC` | +4 slot, +8 value | `0x0076ED50[slot] = value` |
| 94 | `EXF_KILL_CHR` | +4 person (0 = the current target) | kills a person for good: status bit 0, HP 0, no longer an ally |
| 3 | `EXF_SET_POS` | +4 person, +8/+0xC/+0x10 x y z, +0x16 register | place someone |
| 16 / 17 | `EXF_NPC_WALK_POS` / `EXF_NPC_RUN_POS` | +4 person, +8.. x y z, +0x14, +0x1A register | walk / run to a point |
| 12 / 13 | `EXF_NPC_WALK_TARGET` / `EXF_NPC_RUN_TARGET` | (`0x0039CA10`) | walk / run to someone |
| 90 | `EXF_NPC_ROT` | +4 person, +8 angle, +0xE register, +0x10 | turn |
| 65 | `EXF_SET_MOTION` | +4 person, +8 animation, +0xC mode, +0x12 register | play an animation (mode 0/1), or 2/3 other states, 4/5 a global flag |
| 40 | `EXF_SET_EMOTION` | +4 person, +8, +0xC, +0x12 register | person `+0x3AA` (an emotion / mood value) |
| 5 | `EXF_JOIN_PARTY` | +4 person, +0xA register | waits; adds someone to the party (with a confirmation when the party is full) |
| 47 | `EXF_RELEASE_PARTY` | +4 person, +0xA register | removes someone from the party |
| 6 / 7 | `EXF_JOIN_FRIEND` / `EXF_RELEASE_FRIEND` | +4 person | recruit as an ally (person `+0x3A8` bits 0 and 1) / drop |
| 56 | `EXF_SET_SKILL` | +4 person, +8 bit, +0xC on | set or clear an ally skill (person `+0x388`; MECHANICS.md: PICKPOCKET, LOCKPICK, ...) |
| 48 | `EXF_CHECK_ABILITY` | +6 → register, +0xC skill 0-6, +0x10 → register (who) | does a party member have skill n (bits 0, 1, 2, 7, 4, 5, 31)? |
| 50 | `EXF_CHANGE_TARGET` | +4 register (who), +8 register (target) | make a fighter target another |
| 75 | `EXF_SET_CALLER` | +2 → register (person), +4 → register (kind) | pick a random ally (person `+0x3C` kind, by chance) |
| 93 | `EXF_CHECK_ARREST` | +4 mode, +0xA → register, +0xC register | 0: pick a random arrested ally (status bit 3); 1: release that one; 2: arrest someone |
| 95 | `EXF_GET_PARTY_ID` | +4 / +6 → registers | the two party members' ids |

**Checks** (result in a register)

| Op | Command | Arguments | Result |
|---|---|---|---|
| 21 | `EXF_CHECK_TOUCH_NPC` | +4 person | r0 = 1 if the player is within 20 units (and 10 in height) |
| 30 | `EXF_CHECK_TALK_NPC` | +4 person, +0xA → register | 1 if the player is talking to that person |
| 54 | `EXF_CHECK_POS` | +4 person, +8.. x y z, +0x14 radius, +0x18 area, +0x1E → register | 1 if the person is within the radius, in that area |
| 42 | `EXF_CHECK_LIFE` | +4 person, +8 register, +0xA → register | HP (-1 if not found) |
| 43 | `EXF_CHECK_MONEY` | +4 person (u16), +0xA → register | money |
| 67 | `EXF_CHECK_MONEY2` | +4 person, +0xA → register, +0xC amount, +0x10 register | -1 / 0 / 1 comparing money with an amount |
| 64 | `EXF_CHECK_SEX` | +4 person, +0xA → register, +0xC register | person `+4` |
| 39 | `EXF_CHECK_DRESS` | +4 item, +8 variant (-1 any), +0xE → register | 1 if the player wears it |
| 59 | `EXF_CHECK_DRESS_CATE` | +4 category (0x26, 0x27 special), +8 variant, +0xE → register | 1 if the player wears anything of that category |
| 58 | `EXF_CHECK_PARTY` | +0xA → register | number of party members (max 3) |
| 36 | `EXF_CHECK_STAGE` | +4 0 = area / 1 = sub-area, +0xA → register | where the player is |
| 25 | `EXF_CHECK_ST_BATTLE_END` | +6 → register | the fight's result code ([Events](#events-what-makes-a-script-page-run)) |
| 52 | `EXF_CHECK_PUNCHED_NPC` | +6 → register, +8 person | who hit / was hit (`0x00600474` / `0x00600478`) |
| 53 | `EXF_CHECK_NAKAMAWARE` | +4 / +8 registers (two people), +0xC frames, +0x12 → register | waits; which of two fighters went down first (0-3), keeps both at 1 HP |
| 49 | `EXF_WAIT_NPC` | +6 → register | id of a following NPC in the player's area |
| 81 | `EXF_GET_CRIME` | +6 → register | the Criminal title (`0x001B9810`) |
| 24 | `EXF_ITEM_CHECK` | +4 index, +0xA → register, +0xC register | `g_StoryVars[index]` |
| 18 | `EXF_GET_COUNTDOWN` | +6 → register | seconds left on the countdown (-1 when none) |
| 147 | `PAD_PRESS` | +2 → register, +4.. four button masks | waits for one of the buttons; stores which |

**Fights**

| Op | Command | Arguments | What it does |
|---|---|---|---|
| 4 | `EXF_SET_BATTLE` | +4 person / battle | start a fight (`Script_StartBattle(id, 0)`); missions 0x58 and 0x85 set `0x006004C4` bit 2 |
| 33 | `EXF_SET_BATTLE_PLURAL` | +4 register (< 1 = the person being talked to) | start a group fight with that person (`Script_StartBattle(id, 1)`) |
| 55 | `EXF_WAIT_BATTLE_END` | | waits until the player is free again |
| 79 | `EXF_EXIT_BATTLE` | | leave the fight |
| 51 | `EXF_SET_SUBBTL` | +4 on | a "sub-battle" flag in `0x006004C4` |
| 41 | `EXF_SET_ESCAPE` | +4 0 / else | allow or forbid running away (`0x0039A0C0` / `0x0039A0A0`) |
| 83 | `EXF_SET_GROW` | +4 | 0 turns on `0x006004C8` (probably whether the fight gives EXP) |

**Money, items, flags and results**

| Op | Command | Arguments | What it does |
|---|---|---|---|
| 35 | `EXF_ADD_MONEY` | +4 amount, +8 show, +0xE register | waits; gives (or takes) money; show = 1 with the money popup |
| 22 / 23 | `EXF_ITEM_ADD` / `EXF_ITEM_DEL` | +4 index, +8 count, +0xE register | `StoryVar_Add` / `StoryVar_Sub` on `g_StoryVars[index]`, count times |
| 97 | `EXF_ADD_DRESS` | +4, +8, +0xC | add an item to `g_Inventory` (`0x003492B0`) |
| 96 | `EXF_BAININ` | +6 → register, +8 mode | pick a random dealer item: `g_StoryVars` slots named by the letters "ZCDEFGHIVX" (`0x005DB370`) |
| 27 | `EXF_RESULT` | +4 0 = success / 1 = failure | `Mission_SetResult(2 or 3)` |
| 29 | `EXF_DISP_RESULT` | +4 0 = success / else failure | waits; the result screen |
| 28 | `EXF_EVENT_END` | | end the mission (`Mission_End`) |
| 10 | `EXF_GAMEOVER` | +6 kind 0 / 1 / 2 | game over variants |
| 11 | `EXF_SET_COUNTDOWN` | +4 1 = start / 0 = stop / 2 = pause, +8 seconds | the on-screen timer |
| 19 | `EXF_COUNT_CONTENT` | | if flag 799 is set, set flag 0x7E4 |
| 26 | `EXF_SET_CIRCUMSTANCE` | +4 0x14 / 0x15 | two special states |
| 99 | `EXF_SURI` | +4 | `gp-0x4770` byte (SURI = pickpocketing) |
| 91 / 92 | `EXF_REMOVE`, `EXF_EVSTAGE` | +4 value, +8 mode | two script globals (`gp-0x4730`, `gp-0x4734`) |
| 66 | `EXF_SET_MARK` | +4, +8 | map marker (`0x00386F10`) |
| 68 | `EXF_SET_NPC_MARK` | +4, +8, +0xC 1 = clear | marker over an NPC |

**Messages, calls, camera, screen**

| Op | Command | Arguments | What it does |
|---|---|---|---|
| 32 | `EXF_MESSAGE` | +4 dialogue number, +8 speaker (person), +0xE register | waits until it can start; plays dialogue script n (SCRIPT.XAF n) with that speaker; event bit 0x40 when it ends |
| 8 | `EXF_CALL_TELPHONE` | +4 caller, +0xA dialogue number, +0xE register | waits; a phone call: rings, then plays the dialogue |
| 98 | `EXF_CNTL_TEL` | +4 mode 0-3, +8 | phone on / off / ring someone (`0x00194430`, `0x0018F000`) |
| 61 | `EXF_CNTL_MES` | +4 mode 0-5 | message window and player control flags (`0x006004D8`, `0x006004C4`, `0x005FFAF4`) |
| 100 | `EXF_MESTURN` | +6 | message window orientation flag |
| 44 | `EXF_WAIT_ST` | | waits for a money popup / status window to close |
| 84 | `EXF_STOP_PLAYER` | +4 0 = release / 1 = freeze / 2 | player control |
| 60 | `EXF_MOVE_STAGE` | +4 area, +0xA register, +0xC | send the player to another area |
| 85 | `EXF_CAM_MODE` | +4 0 = scripted / else back | camera mode |
| 86-89 | `EXF_CAM_POS_START` / `_END`, `EXF_CAM_TRGPOS_START` / `_END` | +4.. x y z, (+0x10 frames, +0x14 1 = no easing) | camera position and target paths |
| 20 | `EXF_HEART` | +4.. x y z | effect 0x22 at a point |
| 78 | `EXF_SET_OUTLOW` | +4, +0xA, +0xC, +0x12 | (`0x003A3040`) |
| 168 / 169 | `FADEIN` / `FADEOUT` | +6 kind (1 = white) | screen fade |
| 170 / 171 | `FADEIN_CHK` / `FADEOUT_CHK` | | waits for the fade |
| 140-144 | `BGM_PLAY` / `STOP` / `FADE` / `SETVOLUME` / `PAUSE` | +2 channel, +4 track (< 0 = the area's) ... | music |
| 145 / 146 | `SE_PLAY` / `SE_STOP` | +4.. | sound effects |
| 165 | `WAIT_BGM` | +2 channel | waits for the music |
| 73 / 74 | `EXF_GEN_INIT` / `EXF_GEN_SET` | +2 slot, +4.. six values | the generated-job table (above) |

**Dialogue only** (empty in the event VM): `TEX_LOAD`, `TEX_RELEASE`, `SPRITE`, `SPRSET_*`, `SPRCNG_*`, `SPRDISP_ON/OFF`, `SPRCLEAR`, `SPRCALCSTART`, `SPRALLCALCSTART`, `WAIT_SPR`, `TEX_CHECK`, `PADBTN_SET`, `TEXTDISP_ON/OFF`, `TEXT_FADEIN/OUT` (+4 frames), `TEXTCLEAR`, `TEXT_CNG_XY`, `TEXT_CNG_COLOR`, `PROPORTIONAL`, `REG2STRBOX`, `GET_STATUS`, `SET_STATUS`, `WAIT_TEXT`, `WAIT_EXEC`, `STOP_EXEC`, `WAIT_BT` (+2 button mask: wait for a button), `FLAG_INT/UINT/FLOAT`, `PAUSE`, `DOOR_OPEN/CLOSE`. `TEXTSET` (+4 x, +8 y, +0xC/+0x10 scale, +0x14 colour, +0x18 string index) shows a line of text; in the event VM it only stores the string index.

A typical dialogue script (949, English):

```
EVENT id=949
@0: PAGESET 0
    PROPORTIONAL 1
    FLAG_INT 1
    TEXTSET x=174, y=352, scale 1, 1, colour, string 0   "Looks like you did your\njob just as instructed.\nGood job."
    TEXT_FADEIN 8
    WAIT_BT 0x200            (wait for the confirm button)
    TEXT_FADEOUT 8
    TEXTCLEAR
    EVENT_END
    /PAGESET
/EVENT
```

## Example: mission 1, "Attack Bernard"

Job 0 in list A: 1 star, $1000, chapter 6. `python tools/scriptkit.py dis ISO/SLUS_211.50 ISO/XAF/SCRIPT.XAF 1001`, abridged:

```
@0  (event 1: started)    EXF_SET_NPC 64; EXF_RECOVER_NPC person 200; EXF_HIDE_NPC person 200 show   -> Bernard is placed
                          PAGE_JUMP @1
@1                        flags 0x800 on, 0x801/0x802/0x7DA off; r0 = r1 = 0
                          EXF_SET_MARK 1, 200; EXF_SET_NPC_MARK 200   -> marker on the map and over him
@2  (event 8: tick)       if flag 0x803: go to @9
@3  (event 0x20: fight over)  r0 = fight result: 6, 4 -> @5 (lost); 3, 2, 11 -> @8; 1, 0 -> @4 (won)
@4  (won)                 flag 0x801; EXF_RESULT success; EXF_DISP_RESULT; EXF_ADD_MONEY 1000 (shown);
                          EXF_MOVE_STAGE 21; -> @6
@5  (event 2)             EXF_RESULT failure; EXF_EVENT_END
@6  (event 4: area loaded)  EXF_MESSAGE 949 from person 594   -> "Looks like you did your job just as instructed. Good job."
@7  (event 0x40: dialogue over)  EXF_EVENT_END
```

Bernard is person 200; his flags are 0x800-0x809 (mission 1's range).

## Modding notes

- **Job rewards, difficulty and names**: `g_Jobs` `0x005DB470` is in the ELF, so a cheat can change it like any table (the reward shown in the menu). The money actually paid is the script's `EXF_ADD_MONEY` amount, so change both.
- **When jobs are offered**: `g_MissionReq` `0x0059A750` (chapter mask, % cleared), `g_JobListA` / `g_JobListB`, and `g_AutoMissions` are plain tables too. Making every job available from the start is a table edit (set every job's chapter mask to `0x7FE` and its % to 0).
- **Scripts themselves** are loaded from the disc into `g_EventList` `0x0076F100` when a mission starts, so a plain pnach line can't patch one mission's script (it would write every frame whatever is loaded). Two ways in C (`tools/cmod.py`):
  - `@hook Mission_StartScript`: after the original, look at `mission->id` and patch or replace the loaded script (`mission->script`, `ScriptHeader`) before it runs. A whole new script can be built in the mod area and pointed to.
  - `@hook` a command handler (`ScrOp_EXF_ADD_MONEY`, ...) to change what one command does everywhere, or reuse a rarely used command number for a new command.
- **New missions** need a free mission id, a script, a `Mission_Start` call from somewhere (a hook on `Mission_AutoStart` or the job list), and a flag range. Ids with no script are listed in `dumps/missions.txt` (empty rows); entry 1000 (mission 0) is a minimal stub.
- **Dialogue** is SCRIPT.XAF 0-999; a mission can play any of them with `EXF_MESSAGE n`. New text needs a new dialogue script image (same format), loaded in place of an existing one.

## Open questions

- What `MissionRank_Get` (`0x0060BADC`) counts.
- Event codes 2, 3, 5 and 8 in detail; where `Mission_FlagTrigger` records come from.
- Which NPC or menu offers job list A or B (`0x00141E30` is the menu that calls `Mission_Start`).
- `g_StoryVars`: the `EXF_ITEM_*` and `EXF_BAININ` commands use it as item stock (letters as indexes, capped at 99, a total budget of 200), so it may hold dealer and key-item counts rather than plot variables.
- The dialogue player's commands (`Dialogue_Step`) in detail: sprites, text boxes, `PAD_PRESS`, choice menus.
- The battle result codes from `Battle_ScriptResult` beyond what mission 1 shows.
- `g_ScriptCallFuncs` (`CALLFUNC`): how many entries and what each does.
