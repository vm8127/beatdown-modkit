# Animation system: from a button press to the animation on screen

How a fighter's moves become animations, read from the Ghidra pseudocode and checked against the ELF's tables (2026-10-13). Nothing in this file was changed or tested in-game on its own, but every moveset cheat that works in-game (README.md, "Mods so far") depends on it, and the counts below were checked over every action in the ELF.

## Contents

1. [The chain in one picture](#the-chain-in-one-picture)
2. [Animation groups and the global animation slots](#animation-groups-and-the-global-animation-slots)
3. [Actions and their motion scripts](#actions-and-their-motion-scripts)
4. [Playing a motion](#playing-a-motion)
5. [Animation file format](#animation-file-format)
6. [Frame data: the action timeline](#frame-data-the-action-timeline)
7. [Hit reactions, guard and locomotion](#hit-reactions-guard-and-locomotion)
8. [Body sizes and the action remap tables](#body-sizes-and-the-action-remap-tables)
9. [What this means for moveset mods](#what-this-means-for-moveset-mods)
10. [Tools](#tools)
11. [Fighter fields](#fighter-fields)
12. [Open leads](#open-leads)

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

So a move's frame range and which animation it plays are in its script. The frame data (active frames, combo cancel point, when control returns) is in the **second stream** (`+0x3FD8`), a different format that `Action_Timeline` runs next to `Action_Step`: see [Frame data](#frame-data-the-action-timeline).

## Playing a motion

`Fighter_PlayMotion` `0x002F0900` (fighter, anim id, start frame, end frame, blend frames):

- slot = anim id + 1; if `Anim_IsLoaded(slot)` fails it uses slot 0 instead, which the group loader never fills, so a move whose animation isn't loaded plays the wrong animation or none (inferred from the code; this is what a missing group looks like in-game).
- stores the motion at fighter `+0x3FA4` (the overlay's `MOT` line prints this minus 1) and the previous one at `+0x3FA6`;
- times are frames at 60 per second: start `+0x3FE0`, end `+0x3FE4` (capped at the animation's length, a float at its `+0xC`), blend `+0x3FA8`.
- Motion scripts usually ask for 2 frames more than the animation has (Blade Cut: `play 34 [0-54]`, anim 34 is 50 frames; most of style 0x13's plays are length + 2), so the cap decides; a few ask for less and cut the animation short (action 85 plays frames 0-62 of anim 80's 80; action 77 plays 0-102 of 110). Checked with `animkit.py` and `codemap.py framedata`, 2026-10-15.
- `Fighter_UpdateMotion` `0x002F1610` advances the motion by frame time x speed (`+0x3FE8`; x1.2 more when `0x0060C960` bit 0 is set), so a speed of 1.4 plays 1.4 animation frames per game frame. The timeline and the cancel points count **animation** frames (`+0x2D4`), not game frames (read from code).
- **Blending**: the fighter has three RenderWare interpolators: `+0x2D8` (output), `+0x2DC` (previous motion, frozen at the time it had) and `+0x2E0` (new motion); for `blend` seconds the output is blended from the old pose to the new one (RenderWare's interpolator blend; read from code, the exact curve not traced). Motion slot 0 or a blend longer than the motion turns it off.
- On a new motion it reads node 1's and node 8's translation of the new animation, multiplies them by the fighter's per-axis body scale (`+0x28`, `+0x88`, `+0xE8`) and keeps them at `+0x3FB0`: probably the start point for root motion (the hips move forward in attacks: Blade Cut's node 1 goes 3.6 units forward). Not traced further.

## Animation file format

Read from the loader (`Xaf_LoadAnimPack` `0x0029ED70`, `AnimPack_OpenItem` `0x0029EC00`, `Lzss_Decode` `0x0029E3C0`) and RenderWare's animation code (`RtAnimAnimationStreamRead` `0x002503B0`, the compressed-keyframe callbacks at `0x00253400`-`0x00254B90`), 2026-10-15. `tools/animkit.py` decodes all 4,927 animations of the 250 STAGE.XAF entries the groups use without an error.

**STAGE.XAF entry** (one per animation group): `u32 count`, then `count` words `{bits 28-31 compression, bits 0-27 offset in the entry}` (and one more word). Compression 8 = LZSS: the item starts with `u32 unpacked size`, then Okumura LZSS (4 KB window, writing starts at `0xFEE`, a flag byte per 8 items, flag bit 1 = literal byte, 0 = 2-byte match `{offset low 8 bits, high nibble = offset bits 8-11, low nibble = length - 3}`). Compression 0 = raw. Every item in the game is LZSS. Entry 0 is one bare animation (no pack). The pack's items are numbered by the group's id list (item k = `anim_ids[k]`).

**Item** = one RenderWare 3.x `RtAnimAnimation` chunk (Beat Down runs on Criterion's RenderWare; docs/FORMATS.md has the models):

```
+0x00  u32 0x1B, u32 size, u32 library id (0x1C02000A)   chunk header
+0x0C  s32 0x100         version
+0x10  s32 2             interpolator type: 2 = RpHAnim compressed keyframes (the only one used)
+0x14  s32 n             keyframe count
+0x18  s32 0             flags (always 0)
+0x1C  f32 duration      seconds; x 60 = frames (2 to 992 frames)
+0x20  n x 22 bytes      f32 time, u16 qx, qy, qz, qw, u16 tx, ty, tz, s32 previous key
       24 bytes          custom data: f32 offset x, y, z, f32 scale x, y, z
```

- **u16 values are RenderWare 16-bit floats**: bit 15 sign, bits 11-14 exponent (IEEE exponent - 112), bits 0-10 mantissa; 0 is 0. In C: `bits = (v & 0x8000) << 16 | ((v & 0x7800) << 12) + 0x38000000 | (v & 0x7FF) << 12` (from `RpHAnimCmpKeyInterpolate` `0x00253660`).
- **Rotation**: the quaternion `(x, y, z, w)`, the bone's local rotation. All of them come out unit length (worst error 0.0002).
- **Translation** = float16 x scale + offset, per axis.
- **Previous key**: a byte offset in units of the in-memory key size (24), so index = value / 24. The keys are in RenderWare's order: keys 0 to N-1 are every bone's key at time 0, keys N to 2N-1 every bone's second key, then the rest in the order playback needs them; each key names the previous key of the same bone, so following the links splits the keys into one track per bone. The first N keys' links are garbage (they had none). N, the bone count, isn't stored: it's the number of keys at time 0 at the start, and it is **22 for every animation in STAGE.XAF** (S, M and L bodies alike), the HAnim node count of the skeleton. Node order = the skeleton's HAnim node index order (M2).
- **Key rate**: every key time is on a 30 Hz grid (3.5 million keys checked), so keys are at most 2 game frames apart; bones that hold still have only 2 keys (start and end). Playback is slerp (rotation) and lerp (translation) between the two keys around the time, as RenderWare's interpolator does.
- **Translations**: only nodes 1 and 8 move (both start near y = 9.5, hip height, so the unit is probably the decimetre: hips at 0.95 m); all other nodes' translations decode to 0 (up to the float16 noise, about 0.01). So the bone lengths come from the skeleton, not the animation, and nodes 1 and 8 carry the body's motion (an attack's lunge, a fall). How these bind to the skeleton: next section.
- Node 0 is always identity: the skeleton's root above the hips.

Animations named in this doc, decoded (`python tools/animkit.py dump ISO/SLUS_211.50 ID --group G`):

| Anim | What | Frames | Notes |
|---|---|---|---|
| 4 | stance (action 1), M body, group 160 | 46 | loops (first and last pose within 5 degrees); hips still |
| 5 | walk (action 2 = `Fighter_RemapAction(2)` from `Fighter_TaskWalk` `0x0030CA90`, read from code), M body, group 161 | 32 | in-place cycle (the hips don't move forward: the code moves the fighter), loops within 8 degrees |
| 34 | Aaron's Blade Cut (P, action 1805), group 184 | 50 | node 1 lunges forward (+Z) and drops to y 7.6, ends 7.3 forward (0.73 m) back at y 9.56 (corrected 2026-10-15: 3.6 is the position at frame 12, not the total) |
| 7, 8, 9 | knocked down, rolling on the ground, lying (group 184; from the hip motion) | 88, 58, 18 | node 1 falls from y 9.6 to 1.3 |

## Skeleton binding

Worked out 2026-10-15 for the remake (M2/M3) by applying the keys to the model's skeleton and rendering stance, walk and Blade Cut on Aaron's fight model and preset 89's street model in Godot (poses look right: feet on the ground, guard, the lunge). Not traced in the game's code (the keyframe apply callback `0x00253550` is still unread), so this is a working rule, high confidence from the renders.

- **Track k drives HAnim node k** of the body clump (docs/FORMATS.md, "Skeleton and skinning"): the same order as the skin bones.
- **Rotation**: the key quaternion replaces the node's local rotation. Its convention is the standard one for the *column* matrix, i.e. the transpose of RenderWare's row matrix (right, up, at): converting the bind pose frames that way gives quaternions close to the animations' (hips bind (-0.5, 0.5, -0.5, 0.5), stance frame 0 (-0.39, 0.30, -0.65, 0.58)). So a glTF/Godot rotation is the key as it is.
- **Translation**: every node keeps its skeleton offset (the bone lies along its parent's local +X: thigh 4.0, shin 4.3, upper arm 2.4...) except **nodes 1 (hips) and 8 (spine)**, both children of the root, whose key translation replaces it (bind y 10.6, stance 9.6, walk 9.1-9.6: the knees bend). Node 0 (root) and 21 stay at identity.
- **Root motion**: the animations do move the body away from the origin (Blade Cut ends with the hips 7.3 units = 0.73 m forward, walk stays in place). The remake plays them as they are; how the game moves the fighter's position afterwards (follows node 1? scripted by timeline ops 0x17-0x19?) is still open (Open leads).
- Clothes' partial skeletons have the body's bind pose exactly (by bone tag; checked on Aaron's top and pants), so binding them by tag needs no extra matrices.
- Playback in the remake: the keys are written as they are (30 Hz grid, LINEAR = slerp/lerp like `RpHAnimCmpKeyInterpolate`), with consecutive quaternions flipped into the same hemisphere.

## Frame data: the action timeline

Read from `Action_Timeline` `0x00320310` (the second stream's interpreter), `Fighter_AttackCollide` `0x002EC560`, `Action_TryCombo` `0x0031F250`, `Fighter_TaskAction` `0x0030AEB0` and the developer overlay's bit names (`Debug_FighterInfo` `0x00302260`), 2026-10-15. Not tested in-game.

Every frame, after `Action_Step`, `Action_Timeline` runs the action's second stream (`+0x3FD8`, from `g_ActionScripts[action]` +4): opcodes of s16 words executed until a wait. The clock is the **current motion frame** `+0x2D4` (animation time x 60, so playback speed stretches it). Op `0x0A n` waits until that frame reaches n; ops before the first wait run on frame 0. Each op's size is fixed except 0x12, 0x1C and 0x24; unknown opcodes are one word. `codemap.py framedata` decodes it.

| Op | Words | Meaning (read from code) |
|---|---|---|
| `0x01` | 1 | end of the timeline (stays there) |
| `0x02` / `0x03` | 2 / 1 | loop start (count, -1 forever) / loop end |
| `0x05` | 2 | playback speed = n / 1000 (same as the motion script's op 5) |
| `0x0A` | 2 | **wait until motion frame >= n** (`+0x3FD0`; while fighter flag 0x800 is set it counts down in seconds instead) |
| `0x11` | 2 | wait until the current motion slot is n |
| `0x15` | 1 | **combo window**: combo count `+0x450C` = 1 if it was 0 (this move can chain) |
| `0x16` | 2 | **cancel point**: if a button was pressed during the move (`+0x450D` > 0, counted by `Pad_ReadCommand` `0x002A42E0` while state & 6), the combo count is below the limit (Person `+0x384` + 1, a per-person stat) and the fighter isn't NOT CONTROL, `Action_TryCombo` matches the last input `+0x4510` against the style's command list and starts the follow-up now. Checked once, at that frame |
| `0x24` | 4 + list | **attack window**: centre c, before b, after a, then attack sphere numbers ending -1: those spheres are live from motion frame c - b to c + a (`+0x44F4`, `+0x44F6`, mask `+0x44F0`) |
| `0x30` | 2 | hit record index `+0x4570` = n (multi-hit moves take their damage from `g_ActionHits[action][n]`), new attack id |
| `0x2B` | 2 | throw damage now: applies the current hit record to the held target (grabs) |
| `0x2D` | 4 | set (1) / clear (0) status bits `+0x438C` (`hi, lo` = 32-bit mask): MATCHLESS (invincible), NOT HORMING, HIT... |
| `0x2E` | 4 | set / clear control bits `+0x4388`: CONTROL, GUARD, NOT CONTROL, ATTACK... |
| `0x3C` | 3 | release frame r, guard frame g: at motion frame r - 1 `Fighter_ReturnControl` `0x0030BC40` gives control back (new moves can start before the animation ends); at g - 1 control bit GUARD is set (the command handler `0x002A4DB0` then only takes guard-type input codes 4, 5, 0x12, 0x13, 0x40) |
| `0x32`, `0x33` | 5, 3 | branch to another action (0x32 only when status bits match) |
| `0x1A` | 2 | turn/track timer `+0x43E8` = n / 60 s |
| `0x0B`, `0x0D`, `0x0E`, `0x10`, `0x13`, `0x17`-`0x19`, `0x1C`, `0x1D`, ... | | sub-commands (a 9-entry jump table at `0x005D4640`), effects (`0x0031DE90`), weapon effects, movement, voice (0x1C picks by HP: > 80 %, > 40 %, else), camera; not traced |

Attack spheres: `g_SphereTables` `0x00516050` = {body `0x00515CC0` (9), **attack `0x00515D90` (12)**, hurt `0x00515EA0` (18)}, each `{s8 skeleton node, f32 offset[3] in the node's space, f32 radius}`; attack spheres count with radius x 2. Attack parts: 0/1 nodes 14/19, 2/3 nodes 4/7, 4/5 nodes 13/18, 6/7 nodes 3/6, 8/9 nodes 11/16, 10 node 10, 11 node 1 (bone names: [Hit reactions, guard and locomotion](#hit-reactions-guard-and-locomotion); pairs are right/left). Bit 12 is the held weapon.

Aaron's (style 0x13) first moves, `python tools/codemap.py framedata ISO/SLUS_211.50 0x13` (animation frames; game frames in brackets, from the speed ops):

| Input | Action | Anim (frames) | Speed | Active | Cancel point | Damage |
|---|---|---|---|---|---|---|
| P (Blade Cut) | 1805 | 34 (50) | 1.4, 1.0 from 26 | 19-25 (13.6-17.9), parts 1, 5 | 24 (17.1) | 100 |
| K | 1806 | 344 (66) | 1.2 | 18-23 (15.0-19.2), parts 2, 6 | 42 (35.0) | 120 |
| →P | 1807 | 1124 (42) | 1.1 | 10-12 (9.1-10.9), parts 0, 4 | 20 (18.2) | 60 |
| →P P | 1808 | 1126 (56) | 1.4, 0.2 at 28, 1.0 at 30 | 16-18 (11.4-12.9) | 28 (20.0) | 100 |
| →P P P | 1809 | 1125 (78) | 1.2, 0.5 at 28 | 18-20 (15.0-16.7), parts 0, 1, 4, 5 | none (finisher) | 250 |
| ↑P | 1810 | 0 (54) | 1.0 | 24-29 | 44; control back at 49 | 150 |

So a hit's active frames and the combo cancel are frame-exact data per action, and recovery is the rest of the animation unless op 0x3C hands control back earlier. Generic actions (stance, walk) have looping timelines with only effects and sounds.

### Input matching: from a button press to an action

Read from `Cmd_MatchSequence` `0x002A6720`, `Cmd_MatchSingle` `0x002A68B0`, `Action_TryCombo` `0x0031F250`, the command handler `Fighter_HandleCommand` `0x002A4DB0`, `Pad_ReadCommand` `0x002A42E0` and `Fighter_StartAction` `0x00307E40` (which resets `+0x4510`), 2026-10-15, for the remake (M4a). Not tested in-game; the remake implements it (`remake/godot/game/fighter/`) and its smoke test plays Aaron's →P P P this way.

- **History**: per fighter, `u32 codes[64]` + `u16 count` at `+0x100` (in the struct from `FUN_00301C50(fighter) + 0x18`). `Cmd_HistoryReset` `0x002A6330` sets it to one code, `Cmd_HistoryAppend` `0x002A6360` adds one, `Cmd_HistoryClear` `0x002A6320` empties it.
- **From neutral** (the fighter is free): the handler matches **one** input code with `Cmd_MatchSingle`, which only looks at one-input commands; when none matches it retries with `g_InputFallback[code]` `0x005CD9B0` until -1: →→P (0x05) → →P (0x0A) → P (0x0E), ↑P / ↓P → P, →→K / ↓→K / →↓→K → →K → K, and so on. The action starts and the history becomes **[the pressed code]** (not the fallback that matched), so a fallback start can't continue into the pressed code's chains.
- **During a move**: `Pad_ReadCommand` keeps the last input code read at `+0x4510` and counts presses at `+0x450D`. Starting an action resets `+0x4510` to -1, so only presses made **after the current move started** count; a later press replaces an earlier one (the last press wins).
- **At the cancel point** (timeline op 0x16, checked once): if there's a last input, `Action_TryCombo` appends it to the history and calls `Cmd_MatchSequence`, which needs a command whose **whole** sequence equals the history (same length, same codes) and whose condition passes, and returns the action of its last step. So `P P ↓P` (Comet Blow) is Blade Cut, a P during Blade Cut, then a ↓P during Blade Hook, each before that move's cancel frame. On a match the next action starts at once and the combo count `+0x450C` goes up by 1 (the cancel needs it below Person `+0x384` + 1). On a miss the move plays out (the appended code stays, but nothing checks again before the next neutral start resets the history). A few codes (0x21-0x28, 0x39, 0x3A, 0x84-0x87: context attacks) also try `Cmd_MatchSingle`; with a weapon, the weapon's command list is tried first.
- **Directions are relative to the opponent** (when fighter `+0x471C` bit 14 is set): `Pad_ReadCommand` turns the d-pad bits into an angle (`Pad_DirAngle` `0x002A6210`: up 0, right 90, down 180, left -90) and measures it against the line to the target (or 100 units ahead of the fighter): within ±80° gives the Right bit (→, toward), beyond ±100° the Left bit (←, away), and the up/down bits are cleared. Where ↑ / ↓ codes come from in that mode isn't traced (open lead); motions (→→, ↓→, →↓→) are matched by `Pad_MatchPatterns` `0x002A30F0` against `g_InputPatterns` `0x004FC580` (64-byte entries with time limits, not decoded).
- **Conditions**: commands with a condition (Aaron's `←K K`, `←K K K`, `P P →P`, `P P ↓P`, `→→K`, `↓→K`, `→↓→K`) need the fighter's stat levels (`Cmd_CheckCondition`); the remake ignores them for now.
- **Release**: op 0x3C's release frame calls `Fighter_ReturnControl`, after which a new neutral command can start; inputs read while busy are otherwise not queued for later (the remake keeps a press from the last 10 frames of a move as a convenience).

**Timing in game frames** (the remake's converter, `remake/tools/conv_moves.py`): step the animation frame by the current speed every game frame (exact fractions) and fire each timeline op on the first game frame whose whole animation frame reaches its wait, with speed ops taking effect from the next step. Blade Cut (action 1805, speed 1.4 then 1.0 at 26): active animation frames 19-25 = game frames 14-18, cancel 24 = game frame 18, end 50 = game frame 43. `codemap.py framedata`'s "game" column assumes the speed switches at the exact frame, so moves with several speed changes (Weaving 587-589, Triple Snake Fang) differ by 1-2 game frames; which order the game runs the timeline and the motion update in within a frame isn't traced.

## Hit reactions, guard and locomotion

Read from `Combat_TakeHit` `0x0030DFD0`, `Combat_SituationFactor` `0x00314D30`, `Fighter_HandleCommand` `0x002A4DB0` and the walk task `0x0030CA90`, and the tables in the ELF, 2026-10-15, for the remake's M4 (`remake/tools/conv_anims.py` exports these animations; the remake plays them). Not tested in-game.

**Which reaction a hit plays.** `Combat_TakeHit` picks an action from `g_ReactionSets` `0x005FE260` (u32[4]; only the first two are used here): `set = Combat_SituationFactor(...)`'s return value, `g_HitSituationSet` `0x005D0630`[situation] = {normal 0, HP < 1000 1, HP < 300 1, counter hit (defender attacking) 1, reeling 0, held 1}, kept at fighter `+0x4554`. A set is 0x16 pointers (one per reaction kind) to 4 x `{s16 action, s16 angle}` in the order **from behind (180), front (0), left (-90), right (90)**; the direction is chosen from where the attacker stands. Set 0 is `0x005161C0`, set 1 (heavier staggers: 643/646/654 instead of 703/669/679) `0x00516300`. The kind, in the code's order:

| Condition (record +8 reaction = R, record +6 level = L, record +4 detail = D; L and D read as those fields from how they are tested) | Kind | Set 0 front action (anim) | Then |
|---|---|---|---|
| `Fighter_IsDown(defender)` (`FUN_002FABC0`: posture `+0x4390` bit 4, on the floor; also makes the situation factor 1.0) | 9 face up / 10 face down (`Fighter_LyingFaceDown` `0x00308E10`) | 119 (114) / 708 (614) | lying 20 / 19 |
| R & 0x800 | 0x14 | 1682 (1647) | 20 |
| R & 0x1000 | 0x15 | 1687 (1646) | 20 |
| R & 0x100 | 8 | 726 (632) | 20 |
| R & 0x10 | 0xE | 340 (317) | 20 |
| R & 0x200 | 0xD | 393 (279) | 20 |
| R & 0x400 | 0xF | 753 (662) | 20 |
| L & 4 (mid) | 3 | 722 (628) | stance |
| L & 8 (low) | 0xB | 710 (616); the detail bits 0x10 / 0x20 turn the direction | stance |
| D & 0x10 / 0x20 / 8 / 4 | 1 / 2 / 0x10 / 0x11 | 679 (593) / 669 (585) / 687 (597) / 689 (599) | stance |
| otherwise | 0 | 703 (521, 34 frames) | stance |

A few special cases set the kind to 4, 5, 6, 7, 0xC, 0x12, 0x13 (same target, status bits `+0x4390`, holds, a low-HP variant from `0x005FE268`) and 999 / 0x3E3-0x3E6 (action 0x290, or the class row's remap entries 0xF0 / 0xEF / 0xEE / 0x50). Every reaction action's script is one `play` then `goto 1` (stance: the reaction's length is the hitstun) or `goto 20` / `goto 19` (knocked down). **Lying**: action 20 loops anim 22 (face up), action 19 anim 9 (face down); each is a `loop -1` whose `goto` names the **getup**: 20 -> 22 (anim 24, 54 frames), 19 -> 21 (anim 23, 72 frames). So hitstun and knockdown lengths come from these animations, not from the hit records (MECHANICS.md said so; now the animations are known). Medium-high confidence (code and tables read; the meaning of `FUN_002FABC0` and the exact direction rule are not traced).

**How a hit lands, in full** (read from `Combat_TakeHit`, `Combat_ResolveHit`, `Fighter_UpdateTargetDir` `0x00308EC0`, `Action_Timeline` and the two streams of every reaction action, 2026-10-16, for the remake's M4 follow-ups; implemented in `remake/godot/game/fighter/fighter.gd` and checked by its `--fight` test; not tested in-game):

- **Direction.** Every frame `Fighter_UpdateTargetDir` measures where each fighter's target (or holder) stands: the game angle `atan2(dx, dz)` minus the fighter's facing (`+0x2D0`; forward is `(sin f, cos f)`), into `+0x4393` = 4 front (-45°..45°), 1 (45°..135°), 2 (-135°..-45°), 8 behind (also `+0x4391` side, `+0x4392` octant bits, `+0x4394` front half). `Combat_TakeHit` maps 4 -> table entry 1 (front), 8 -> 0 (behind), 1 -> 3 ("right", angle word 90), 2 -> 2 ("left", -90). The victim is **not** turned to face the attacker. Checked against the data: entry 2's reaction (action 651, anim 570) moves the hips toward +x, away from an attacker at a negative angle. Big reactions (kinds 0xD, 0xF) and hits on the floor (9, 10) turn sideways by the detail bits when hit from the front (0x10 -> entry 2, 0x20 -> 3) or behind (0x10 -> 3, 0x20 -> 2); on the floor detail bit 4 means front. High confidence (code + data).
- **Knockdowns and KOs** don't use the kinds: a hit with reaction bit 0x20 on a standing fighter, or any hit that empties HP, takes its action from `g_KnockdownReactions` `0x00516390`: row 0 knocked down (649 behind, 650 front, 651, 652), row 1 KO (5, 680, 681, 682), row 2 KO while lying (230 face up, 231 face down), by direction. These are multi-clip actions (650 = anim 321 frames 0-42, then anim 1074, then lying 20). Bit 0x20 is checked **before** the big-reaction bits.
- **Wall hits.** For kinds other than 8, 0x15, 0xE, 0x14, 6 and 0xB on a standing fighter, `Combat_TakeHit` looks for a wall within 11 units (`FUN_00160790`); when its normal is within 60° of the attacker's facing, the reaction is kind 0xC from `g_ReactionSets[2]` / `[3]` (`0x005163A0` above half HP: 746 behind, 169 front, 748, 747; `0x005163B0` at or below half: 750, 749, 750, 750). These actions push with timeline op 0x18 (`move18 speed, angle x 100, frames`: 746 = `-1460, 18000, 5`), not with hip travel. Medium confidence (the wall query function isn't traced).
- **Hitstun** = the reaction action's own length: every stagger's timeline has op 0x3C with a release frame (703: release 28 of anim 521's 34 frames, so control returns on game frame 27; 722 mid hit: 39 of 90; getup 22: 39 of 54), and the rest of the animation plays out unless the fighter acts. Knockdowns have no release: the fall plays all its clips (650: 78 game frames), then the lying loop. The **lying** loop (20 / 19) waits on frame 999, so how long a fighter stays down is decided by code (input or a timer), not by data: not traced. Getting up (22 / 21) sets MATCHLESS from its first frame; so do the falls (status bit 1 at frame 0).
- **Knockback is root motion.** No hit code pushes the victim: the reaction animations move the hips (node 1) themselves: the plain stagger anim 521 goes 0.33 m back, 585 / 593 0.2 m, big reactions 1-1.6 m (317, 279), the knockdown 632 4.2 m, 321 1.6 m; sideways reactions push sideways (570: 0.82 m). So the game must carry node 1's floor travel into the fighter's position (the `+0x3FB0` start point); the remake moves the body by the clip's hip travel every frame. High confidence for the data, medium for the mechanism.
- **No hitstop found.** Neither `Combat_ResolveHit`, `Combat_TakeHit`, the motion update (`Fighter_UpdateMotion` `0x002F1610`: frame time x `+0x3FE8` speed) nor the frame clock (`fGpffffae60`, only scaled by the debug slow / fast keys and a global x0.5 mode `FUN_003BDB90`) pauses fighters on impact. The impact effect is the camera: `Camera_HitPunch(5, 15, 0.7)` (`0x00378120`) when the damage is over 14 moves the fight camera toward the fighters for 5 frames and back over 15. The remake keeps its tuned hitstop placeholder (MoveHit.hitstop from the strength byte). Medium confidence (a hitstop could hide in an effect or sound task).
- **Fighter state category** (`+0x4378`) is the action's hit table header word: `Fighter_StartAction` sets `state = g_ActionHits[action]->kind`. So the "attack kind" of the hit records is the category the overlay prints as CAT (1 NORMAL, 2 ATTACK, 4 HOLD, 0x10 DOWN, 0x20 ATTACK DAMAGE, 0x40 HOLD DAMAGE, 0x100 OTHER DAMAGE, 0x200 DOWN DAMAGE?, 0x400 GUARD: the guard test reads `state & 0x400`, so the overlay's last two names are GUARD = 0x400 and 0x200 = the one `Combat_TakeHit` sets on a knockdown). Over all actions: 1142 NORMAL, 458 ATTACK, 141 HOLD, 124 HOLD DAMAGE, 31 x 0x200, 30 GUARD.

**Blocking** (`Combat_ResolveHit`, the guard tasks `0x0030FF20` standing and `0x00310690` crouching, read 2026-10-16): a hit is blocked when the attacker is in ATTACK, the defender's category is GUARD (0x400) and the attacker is in front (`+0x4393` bit 4, within 45°). A standing guard (`Fighter_IsStandGuard` `0x002FAB40`) lets low hits (level 8) through, a crouching one (`Fighter_IsCrouchGuard` `0x002FAB80`) lets mid hits (4) through. A blocked hit does **no damage** and no hit reaction: it sets status HIT (0x400), counts the guard (`+0x44EC`) and returns. The guard task sees HIT and plays a guard-hit action from `g_GuardActions` `0x005166C0` (per weapon class: none, class 3, class 10; a standing and a crouching list, each `s16[6]` = guard loop, then guard-hit actions 1-5): unarmed standing = loop **821** (anim 724, blend 10), hits 822 (default), 826 (detail 0x10), 825 (detail 0x20), 823 (detail 4), 824 (detail 8); unarmed crouching = loop 814, hits 815 / 819 / 817. Each guard-hit action plays its anim (24 frames) and goes back to the loop. The guard task starts the loop on entry, switches to the crouching guard on ↓ (`g_ActionRemap` index 0x214) and to the stance (index 1) when the guard button is released; the generic remap indexes 0x72 / 0x73 and 0x1F1-0x1F6 / 0x214-0x225 hold the same actions. Category GUARD actions: 114/115/323/324/774/776 (class 3), 539/540/729/730 (its crouch), 862-867 / 868-871 (class 10), 814-826 (unarmed). High confidence (code + tables).

**Grabs** (read from `Fighter_HandleCommand` `0x002A4DB0`, `Fighter_PickWeaponMove` `0x002A5B80`, `Combat_ResolveHit`'s HOLD branch, `Action_Timeline` ops 0x17 / 0x2B and the tables, 2026-10-16; implemented in the remake, `--fight` test; not tested in-game):

- **R1** is input code 0x1E. With no item to pick up and no downed target close by, `Fighter_PickWeaponMove` returns generic action **10** (9 for styles 0x12 and 2), started as `Fighter_RemapAction(10)` = action 10 for every body: `play 13 [0-36]`, a lunge with both hands out (hips 1 m forward), attack window parts 1 and 5 at frames 4-16, category HOLD (4). Its hit-table header byte +6 (0x0F) is the grab-direction mask tested against the target's `+0x4393`: every direction. So the "special move" reading of action 10 in the correction below is only half the story: the ○ codes 0x40-0x46 reach it too (through `0x002FA5C0`), but its data is a grab. Next to a downed target (within 15 units and 10° ) R1 picks 0x177 / 0x175 instead (grab a lying fighter, face up / down; not followed).
- **The catch.** A HOLD-category window that touches a fighter calls the HOLD branch of `Combat_ResolveHit` instead of damage: the target must stand (posture bit 1, `FUN_002FABB0`, or crouch-guard), not have status NOT THROW (8; getups set it), be within the window's direction mask, and be in line of sight (`FUN_002FA8C0`: two collision rays, attacker to target at foot and 60 % height). Then both get actions through `FUN_003084E0` / `FUN_00308670`: for a front catch (`+0x4393` 4) of a medium-body target the code hard-codes `g_ActionRemap` 0x181 / 0x182 (S 0x17B / 0x17C, L 0x187 / 0x188) = attacker **126** (anim 121, the catch) and **124** (anim 119, the hold loop, 64 frames), the victim their partners **127** (anim 122) and **125** (anim 120) (`g_ActionEvents[action]` +8 = the partner's action). Other directions read the per-fighter table `+0x4572` (s16 per input code, cleared at spawn; indexes 99-104 for the catch directions; who fills it is not traced). The side and rear holds 122/123, 128/129, 130/131 use anims 117/118, 123-126, which no group Aaron loads holds.
- **Placement** is timeline op **0x17** (REVISION POS, control bit 0x200): `x, y, z` / 100 (game units) and angle / 100 into `+0x43CC`-`+0x43E0`, applied to the fighter against its partner: the catch victim 127 goes 12 units (1.2 m) in front of the holder, turned 180°, and its own anim walks it in 0.71 m; the hold victim 125 sits at 4.75 units; the GRAB P victim 380 at 4.5; the rear throws' victims (305, 292) at `x 1, z 2.5`, angle 0 (facing away).
- **Throws.** While holding, P / K are the style's GRAB P (code 0x2F) / GRAB K (0x32) commands, from behind REAR GRAB P (0x6B) / REAR GRAB K (0x6C). Aaron: GRAB P 379 (anim 352) with victim 380 (anim 353, 196 frames, then lying 20), GRAB K 11 / 12, REAR GRAB P **304 Sleeper Hold** (3 clips 286-288, 181 game frames) / 305 (3 clips, 299 frames, back to the stance), REAR GRAB K 291 / 292 (4 clips, then lying). The damage lands at timeline op **0x2B** (throw damage: the current hit record on the held fighter; GRAB P 500, Sleeper Hold 800). The victim's motion during a throw is its own animation's hip travel from the placement.
- The hold's end without a throw (escape, timeout) is not traced; 132 / 133 (anims 127 / 128, partner placed 5 units away) look like a release pair (low confidence).

**Guard.** The guard-type input codes 0x40-0x46 (`Fighter_HandleCommand`, the branch after the command table lookup) start `Fighter_RemapAction(fighter, 10)`: action 10 = `play 13 [0-36, blend 8]` (group 15, which Aaron loads), a raised-forearms pose (render checked in the remake). Medium confidence that this is the guard (from the code path, not seen in-game). Blocked hits: see "Blocking" above (the guard is action 821, not 10). **Correction (2026-10-16, read from `g_InputPatterns`):** codes 0x40-0x46 are the SPECIAL button (○ in TYPE 1) with a direction, not guard codes, so action 10 is the special move (DEVASTATOR / threaten), not the guard; the guard is the held guard button and codes 0x47-0x4B (docs/CONTROLS.md, "Input patterns").

**Locomotion.** The walk task reads `g_WalkModes` `0x00516560`: 14 rows of 6 pointers, `[mode * 6 + i]` = actions for 8 directions (front, back, left, right, and diagonals), `[mode * 6 + 3 + i]` = speeds in units per frame (scaled by frame time / (1/60)); `i` = `FUN_002F8D60(fighter)` (probably the body size). Mode 0 = actions 797-804 at 0.48 (run of style group 210), mode 2 = 674-678, 683-685 at 0.30 / 0.16 (anim 588: a jog), mode 5 = 444-451, 6 = 353-360 at 0.14. The default case moves at 11.5 units/s with actions 0x249 / 0x25A; action 3 (anim 515, group 159) is the run used when the fighter is far from its target (`0x0030D970`, distance > 13). Low-medium confidence: the mode numbers aren't named.

**Locomotion in full** (read from `Fighter_TaskWalk` `0x0030CA90`, `FUN_003155D0`, `g_WalkModes` and the walk actions, 2026-10-16; the remake does it, `--fight` test; not tested in-game):

- **Walk mode** (`FUN_003155D0`): 0 unarmed; 2 when status FEAR (0x40000) and hurt; 5, 6, 7, 9, 10, 0xB by the held weapon's class; 0xC in a special state. The row is `mode * 6 + body` (`FUN_002F8D60`: the body size), actions and speeds side by side (speeds in game units per 1/60 s, scaled by frame time).
- **Locked on** (a battle target), the fighter keeps facing it and the stick's angle against the facing (game angle) picks one of 8 entries: 0 front (-25..25), 4 (25..65), 2 (65..115), 6 (115..155), 5 (-65..-25), 3 (-115..-65), 7 (-155..-115), 1 back; a hysteresis variant uses only 0-3 (±55, ±125) when the direction barely changed. Medium body, mode 0: actions **2** front, 693 back, 694 / 695 sides, 696 / 697 front diagonals, 698 / 699 back diagonals; speeds 0.359 front, sides and front diagonals (2.16 m/s), 0.198 back and back diagonals (1.19 m/s). Small 0.484 / 0.266, large 0.234 / 0.129. Mode 2 (afraid): 674-678, 683-685 at 0.296 / 0.163 for every body. The walk actions loop one clip each; the back walk (693) plays at 0.7.
- **Run**: with the job mask `0x005FFE48` (L1) or the stick past 0.998, the fighter faces the way it goes and runs at **54 units/s** (5.4 m/s; 60 outside a battle) with action **3** (anim 515, 52 frames), or a weapon class's own run (0x438, 0x467, 0x37D, 0x2DB, 0x69B). Outside a lock (the field), the default is 11.5 units/s with action 0x249 / 0x25A.
- **The feet slide in the data**: the front walk clip (anim 5, 32 frames) moves its planted foot back under the hips at about 1.35 m/s at speed 1.0, but the game moves the body 2.16 m/s. Either the PS2 game slides, or the motion speed is raised somewhere not traced (the walk timelines have no speed op except 693's 0.7). The remake keeps the game's speeds and plays each walk clip at speed / its measured stride (FighterModel.stride_speed: about 1.6 for the front walk), so the feet stay planted (0.11 m/s left). Medium confidence for the stride figure (measured in the remake on the rigged model).
- **Root motion** (`FUN_002F0260`, read): every frame the hips' floor offset (x, z) from the point saved when the motion started (`+0x3FB0` / `+0x3FB8`, `Fighter_PlayMotion`) is turned into world space by the fighter's frame and added to the fighter's position, and the same offset is taken off the hips (and the other root matrices), so the skeleton stays over the fighter and the travel accumulates; height is untouched. So moves, reactions, knockdowns, getups and grabs move the fighter by their own hips. High confidence (code read; the vector transform `FUN_00267870` not traced).
- **Body collision** (`FUN_003072C0`, read): every frame, for every pair of fighters, each body sphere of one (`g_BodySpheres` on the posed bones: 0/1 nodes 12/13, 2/3 nodes 17/18 at 0.09 m; 4 hips 0.22 m; 5/6 nodes 3/6 0.15 m; 7 node 9 (chest) 0.22 m; 8 node 10 (head) 0.12 m) that overlaps the other's (`FUN_003052A0` gives the depth) pushes both apart along the floor line between them, half each when both have the same `+0x4724` bit 0, else only the movable one. So bodies can come as close as the hips and chest spheres allow (about 0.44 m), not a fixed capsule. The remake does this with the deepest overlap of each pair per frame (its capsules no longer collide with each other).

**Attack sphere bones** (`g_AttackSpheres`, with the M2 bone names): part 0 hand_r, 1 hand_l, 2 foot_r, 3 foot_l, 4 forearm_r, 5 forearm_l, 6 shin_r, 7 shin_l, 8 shoulder_r, 9 shoulder_l, 10 head, 11 hips; offsets 0.4-1.8 units along the bone, radii (x 2 when attacking) 1.6 (hands) to 4.4 units (hips). Blade Cut's parts 1 and 5 are Aaron's **left** hand and forearm; rendered in the remake, the spheres sit on the extended left fist when it lands (side names from the bind pose; high confidence for the nodes, medium for left/right).

**Blending and root motion as the remake plays them** (M4, remake choices where the game isn't traced): a new motion freezes the current pose and blends to the new clip linearly over its blend frames (counted in game frames); blend 0 snaps (most reactions use 0, knockdowns and most moves 8, a few moves 4). The body moves by the move's hip travel (node 1 forward), and the drawn model pins the hips' forward travel to the body, so collision decides the position and the animation never pulls the model through a wall or an opponent; sideways and vertical hip motion stay in the animation. The game's own handling (node 1's start translation saved at `+0x3FB0`) is still open.

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
python tools/codemap.py framedata ISO/SLUS_211.50 0x13        # per command: action, anim, speed, active frames, cancel point, damage
python tools/codemap.py framedata ISO/SLUS_211.50 1805        # one action's timeline
python tools/animkit.py list ISO/SLUS_211.50 --group 184      # a group's animations: frames, bones, keys
python tools/animkit.py dump ISO/SLUS_211.50 34 --group 184   # one animation's keys per bone (--json, --bone N, --sample 60)
python tools/animkit.py check ISO/SLUS_211.50                 # decode everything: unit quaternions, key links
python remake/tools/remake_assets.py ISO remake/godot/assets_ripped   # every asset; anims/aaron.glb (clips "a<anim id>") + aaron.json (conv_anims.py)
```

`animkit.py` (standard library) is also a module: `Library(elf).anim(id, group)` returns an `Anim` with `tracks()` (per bone: time, quaternion, translation) and `sample(t)`, for the remake's converter. An anim id can be in several groups with different data; pass the group the fighter loads (Aaron's style group is 184).

`anim-check` only follows the first motion script of each command (not actions reached through `goto`).

In PCSX2, the developer overlay (README, cut content switch 5) shows `TASK` (current action, `+0x4346`) and `MOT` (current animation id), which is the quickest way to find the action and animation behind a move you see.

## Fighter fields

| Offset | What |
|---|---|
| `+0x000` | flags: bit 2 action running, bit 3 ready for the next motion, bit 1 motion playing |
| `+0x3FA4` / `+0x3FA6` | current / previous animation slot (anim id + 1) |
| `+0x2D0` | facing angle (degrees) |
| `+0x2D4` | current motion frame (int, the timeline's clock) |
| `+0x2D8`, `+0x2DC`, `+0x2E0` | output, previous and new motion interpolators (RenderWare) |
| `+0x3FA8` | blend time (seconds) |
| `+0x3FD0` | timeline wait frame (op 0x0A) |
| `+0x3FD0` | cleared by op 4 |
| `+0x3FD4` / `+0x3FD8` | motion script pointer / second stream |
| `+0x3FDC`, `+0x3FEC` | loop start pointer, loop counter |
| `+0x3FE0` / `+0x3FE4` | motion start / end time (seconds) |
| `+0x3FE8` | playback speed (1.0) |
| `+0x4346` | current action id |
| `+0x4388` | control bits (CONTROL 1, GUARD 2, NOT CONTROL 4, ATTACK 0x20, WEAPON 0x4000...) |
| `+0x438C` | status bits (MATCHLESS 1, STIFF 0x200, HIT 0x400, NOT HORMING 0x2000, REVERSAL 0x8000, GUARD 0x20000...) |
| `+0x43A8`, `+0x43AA` | release frame and guard frame (op 0x3C) |
| `+0x44F0`, `+0x44F4`, `+0x44F6` | live attack spheres, first and last active frame (op 0x24) |
| `+0x450C`, `+0x450D`, `+0x4510` | combo count, buttons pressed while busy, last input code |
| `+0x4570` | hit record index (op 0x30) |
| `+0x46C0` | class row (picks the remap table) |

## Open leads

- Timeline ops not traced: 0x0B's nine sub-commands, the effect ops (0x0D, 0x0E, 0x10), movement (0x17-0x19), 0x13 (weapon), 0x35 (`+0x4390`), and which control/status bits each move sets. Status bit 2 (set by some moves, e.g. action 1670) has no overlay name.
- `g_ActionEvents` records (`+8` = the action id `FUN_003084E0` queues, `+0xC` a reaction action): not decoded.
- The combo limit Person `+0x384`: which stat it is (probably the combo skill that grows with training).
- Frame data isn't tested in-game yet: in PCSX2, press P twice and watch TASK change at frame 24 of Blade Cut (overlay FRAME).
- Skeleton binding: answered by rendering ("Skeleton binding" above); still worth confirming in the keyframe apply callback `0x00253550` (not decompiled as a function) and `0x002F0260`. Group 7's anim 731 does translate other nodes (a prop or another skeleton?).
- Root motion: answered (2026-10-16): `FUN_002F0260` carries the hips' floor offset from `+0x3FB0` into the position every frame ("Locomotion in full"). Timeline ops 0x17 (placement against a partner) and 0x18 (`move18`: a push, used by the wall reactions) also move fighters; 0x19 not traced.
- Walking: why the walk clips' stride (1.35 m/s) is slower than the walk speed (2.16 m/s), the hysteresis rule of the 4-way walk, and the run trigger mask `0x005FFE48`.
- Opcodes 8, 9, 0x13, 0x15, 0x16, and `Action_Next`'s special negative ids (-3 picks one of actions 0x84-0x87 depending on the target).
- Input: where the ↑ / ↓ codes come from when `Pad_ReadCommand` converts the stick relative to the target (it clears up/down), the motion pattern table `g_InputPatterns` `0x004FC580` (time limits for →→, ↓→, →↓→), and the order of the timeline and the motion update within a frame (decides ±1 game frame for the cancel point).
- The `.mtd` action records: who loads them and which 52 actions they fill.
- Grabs: who fills `+0x4572` (the per-code generic action table: rear and side catches), the hold's escape and timeout, grabbing a lying fighter (0x175 / 0x177), the meaning of op 0x2B's argument.
- Reactions (answered 2026-10-16: `FUN_002FABC0` = on the floor, the direction rule, blocked hits, hitstun, knockback; see "How a hit lands"). Still open: the special kinds 4-7, 0x12, 0x13 and 0x3E3-0x3E6, the wall query `FUN_00160790`, how long the lying loop lasts, and the walk modes' meaning (`g_WalkModes` rows 0-13).
- Where flag 8 is set when a motion ends (the motion update), and what slot 0 holds in practice.
