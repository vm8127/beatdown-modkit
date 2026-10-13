# Animation system: from a button press to the animation on screen

How a fighter's moves become animations, read from the Ghidra pseudocode and checked against the ELF's tables (2026-10-13). Nothing in this file was changed or tested in-game on its own, but every moveset cheat that works in-game (README.md, "Mods so far") depends on it, and the counts below were checked over every action in the ELF.

## Contents

1. [The chain in one picture](#the-chain-in-one-picture)
2. [Animation groups and the global animation slots](#animation-groups-and-the-global-animation-slots)
3. [Actions and their motion scripts](#actions-and-their-motion-scripts)
4. [Playing a motion](#playing-a-motion)
5. [Body sizes and the action remap tables](#body-sizes-and-the-action-remap-tables)
6. [What this means for moveset mods](#what-this-means-for-moveset-mods)
7. [Tools](#tools)
8. [Fighter fields](#fighter-fields)
9. [Open leads](#open-leads)

## The chain in one picture

```
input history ──Cmd_MatchSequence 0x2A6720──> command list of the fighter's style (g_StyleCommands 0x515C10)
                                                 └─> action id (global, 1-2003)
action id ──Fighter_SetAction 0x31F120──> g_ActionScripts[action] 0x5848E0 = {motion script, second stream}
                                          g_ActionHits[action]    0x580A40 = hit records (damage)
                                          g_ActionEvents[action]  0x582990 = event records
motion script ──Action_Step 0x31FAE0──> "play anim 34, frames 0-54, blend 8"
anim id ──Fighter_PlayMotion 0x2F0900──> g_AnimSlots[anim id + 1] 0x6C55F0
                                          filled when an animation group that lists that id was loaded
class row +C (group list) ──Anim_LoadClassGroups 0x2DC680──> groups ──> STAGE.XAF packs ──> g_AnimSlots
```

So there are three independent numbers: the **style** picks which actions your buttons start, each **action** names the **animation ids** it plays, and the class row's **group list** decides which animation ids are in memory. A move works when the animation it names has been loaded by some group.

## Animation groups and the global animation slots

- `g_AnimGroups` `0x004FB4C0`: 317 groups of `{s16 STAGE.XAF entry, s16 0, s16 *anim ids ending -1}` (`dumps/anim_groups.txt`). The pack's animations are numbered by the id list, in order.
- **Animation ids are global**, 0-1742. `g_AnimSlots` `0x006C55F0` holds one pointer per id, at index **id + 1** (index 0 is never filled by the group loader). The same id appears in many groups: 3, 49 and the walk/guard/damage ids are in every hero group.
- **Reference counted.** `Xaf_LoadAnimPack` `0x0029ED70` loads a group's pack and, for each id, either stores the animation (`Anim_SetSlot` `0x002DC280`) or, if the slot is already filled, frees the new copy and only counts the reference. Counts: `g_AnimSlotRefs` `0x006C7140` (per slot) and `g_AnimGroupRefs` `0x006C7860` (per group). Loading a group that's already loaded only bumps the counts. So loading two styles' groups at once costs memory only for the ids the first one didn't have.
- **Loading for a fighter**: `Anim_LoadClassGroups` `0x002DC680` copies the class row's list (row `+C`, 9999-terminated) to `0x006C8080` and loads it group by group through `Anim_LoadGroupList` `0x002DC550` and `Anim_LoadGroup` `0x002DC360` (state machines, a few animations per frame). Other callers load fixed lists for talk scenes (`Talk_Update`), cutscenes and menus.
- **Unloading**: `Anim_UnloadGroup` `0x002DC790`, `Anim_UnloadGroupList` `0x002DC880` and `Anim_UnloadClassGroups` `0x002DC990` drop one reference per group and free an animation when its slot count reaches 0. `Anim_ResetAll` `0x002DC1E0` frees everything except slots marked resident (`0x006C79A0`, set while the loader's resident flag `0x005FFC58` is on).
- The developer overlay (cut content switch 5, README) has an `[ ANIM RESOURCE ]` page that sums the size of every loaded slot.

## Actions and their motion scripts

`g_ActionScripts` `0x005848E0` has one `{u32 motion script, u32 second stream}` pair per action. `Fighter_SetAction` `0x0031F120` copies both to the fighter (`+0x3FD4`, `+0x3FD8`), sets the current action `+0x4346`, playback speed `+0x3FE8` = 1.0 and flags 4 (action running) and 8 (ready for the next motion).

`Action_Step` `0x0031FAE0` runs the **motion script**, a list of s16 words. It executes opcodes until it plays a motion or the action ends, then waits until flag 8 comes back (the motion finished) before reading on:

| Op | Words | Meaning |
|---|---|---|
| `0` | 5 | **play** anim id, start frame, end frame (-1 = to the end), blend frames → `Fighter_PlayMotion`; waits for it |
| `1` | 1 | end of the action (clears flag 4) |
| `2` | 2 | loop start, count (-1 = forever) |
| `3` | 1 | loop end: jump back while the count lasts |
| `4` | 1 | clears fighter `+0x3FD0` |
| `5` | 2 | playback speed = value / 1000 |
| `6` | 2 | continue with another action (`Action_Next` `0x0031F650`; usually 1, the stance) |
| `7` | 2 | start another action (`Fighter_StartAction` `0x00307E40`) |
| `0x34` | 2 + n | random: count n, then n actions; picks one and continues with it |
| `8`, `9`, `0x13`, `0x15`, `0x16` | 1, 3, 5, 1, 2 | handled but not traced (0x13 calls `0x00324F80` with a float, 0x16 is a condition) |

Any other opcode is skipped as one word. In the ELF, 1,952 of the 2,004 actions have a script, and all of them decode with only opcodes 0, 1, 2, 3, 4, 6 and 0x16 and end with op 1. The other 52 have no script in the ELF; `Action_Register` `0x00301D80` can fill an action's script, hit and event records at run time from a loaded record, and `Action_LoadMtd` `0x00301CD0` loads such records from `%s/%04d.mtd` files (probably for cutscenes; not traced).

Examples, from `codemap.py actions`:

```
action 1805 (Aaron, P, Blade Cut):     play 34 [0-54, blend 8]; goto 1
action 1809 (Aaron, →PPP, Triple...):  play 1125 [0-end, blend 8]; goto 1
action 1 (stance):                     play 4 [0-end, blend 8]; reset; loop -1; play 4 [0-end, blend 0]; reset; next
```

So a move's frame range and which animation it plays are in its script; the frame data (when the hit is active) is probably in the second stream or the event records (not decoded yet).

The **second stream** (`+0x3FD8`) is a different format (it starts `53, 1, 19, ...` for most attacks) and isn't read by `Action_Step`.

## Playing a motion

`Fighter_PlayMotion` `0x002F0900` (fighter, anim id, start frame, end frame, blend frames):

- slot = anim id + 1; if `Anim_IsLoaded(slot)` fails it uses slot 0 instead, which the group loader never fills, so a move whose animation isn't loaded plays the wrong animation or none (inferred from the code; this is what a missing group looks like in-game).
- stores the motion at fighter `+0x3FA4` (the overlay's `MOT` line prints this minus 1) and the previous one at `+0x3FA6`;
- times are frames at 60 per second: start `+0x3FE0`, end `+0x3FE4` (capped at the animation's length, a float at its `+0xC`), blend `+0x3FA8`.

## Body sizes and the action remap tables

Command lists hold positive action ids, which play as they are. Generic actions (stance, walk, guard, damage, grabs started by the system) are often started with a **negative** id, which `Fighter_RemapActionNeg` `0x002F8A60` and `Fighter_StartAction` look up in the class row's `+8` table (`g_ActionRemap_S/M/L` `0x50C230/0x50B990/0x50BDE0`, one s16 per generic action, at most 0x225). That's how the same "walk" request plays a small, medium or large body's animation. A class row's body groups (S `164,165`, M `160,161`, L `162,163`) hold those per-body animations, so a fighter must keep the groups that match its remap table: that's why `swap-moveset --keep-body` keeps A's body groups.

## What this means for moveset mods

- **Whole swap** (`swap-moveset`, roster): style + groups move together, so every animation the new style's actions name is loaded. Check a planned swap with `codemap.py anim-check ISO/SLUS_211.50 A 0xSTYLE`: for example Aaron's own groups miss 22 of the 44 animations Raven's style plays, so Raven's groups must come along.
- **Mix** (`mix-moveset`): the borrowed commands' actions keep their own animation ids, so B's style groups are added to A's list. The extra groups only cost memory for ids A didn't already load.
- **Cross-body moves**: style move groups don't depend on body size (a style's move animations are the same for S, M and L; PERFECT loads every style group on an M body), which is why Jason G's moves (L) play on Aaron (M) when Aaron keeps his own body groups. Tested in-game (README, "Mods so far").
- Every class row in the game loads all the animations its style's commands play, except TESTER (style 0x09), which misses 55, 387 and 695 (`anim-check`). The TESTER cheat still worked in-game, so those few moves probably just play the fallback.
- **A move's animation or speed** can be changed without touching code: the motion scripts are in the ELF (read-only data at `0x0051A...` and `0x0057...`), so a pnach can rewrite an action's `play` words (anim id, frames, blend) or add a speed op. Remember actions are shared: changing a generic action changes it for everyone who uses it.

## Tools

```
python tools/codemap.py actions ISO/SLUS_211.50 1805 1809     # decode actions' motion scripts, with the groups holding each animation
python tools/codemap.py actions ISO/SLUS_211.50 0x13          # every command of style 0x13
python tools/codemap.py anim-check ISO/SLUS_211.50            # classes whose groups miss an animation their style plays
python tools/codemap.py anim-check ISO/SLUS_211.50 AARON 0x11 # what AARON would miss with style 0x11 and his own groups
python tools/bdkit.py groups ISO/SLUS_211.50                  # every group's STAGE.XAF entry and anim ids
```

`anim-check` only follows the first motion script of each command (not actions reached through `goto`).

In PCSX2, the developer overlay (README, cut content switch 5) shows `TASK` (current action, `+0x4346`) and `MOT` (current animation id), which is the quickest way to find the action and animation behind a move you see.

## Fighter fields

| Offset | What |
|---|---|
| `+0x000` | flags: bit 2 action running, bit 3 ready for the next motion, bit 1 motion playing |
| `+0x3FA4` / `+0x3FA6` | current / previous animation slot (anim id + 1) |
| `+0x3FA8` | blend time (seconds) |
| `+0x3FD0` | cleared by op 4 |
| `+0x3FD4` / `+0x3FD8` | motion script pointer / second stream |
| `+0x3FDC`, `+0x3FEC` | loop start pointer, loop counter |
| `+0x3FE0` / `+0x3FE4` | motion start / end time (seconds) |
| `+0x3FE8` | playback speed (1.0) |
| `+0x4346` | current action id |
| `+0x46C0` | class row (picks the remap table) |

## Open leads

- The second stream at `+0x3FD8` and `g_ActionEvents`: probably hit timing, sounds and effects (frame data).
- Opcodes 8, 9, 0x13, 0x15, 0x16, and `Action_Next`'s special negative ids (-3 picks one of actions 0x84-0x87 depending on the target).
- The `.mtd` action records: who loads them and which 52 actions they fill.
- Where flag 8 is set when a motion ends (the motion update), and what slot 0 holds in practice.
