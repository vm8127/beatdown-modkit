# Animation system: from a button press to the animation on screen

How a fighter's moves become animations, read from the Ghidra pseudocode and checked against the ELF's tables (2026-10-13). Nothing in this file was changed or tested in-game on its own, but every moveset cheat that works in-game (README.md, "Mods so far") depends on it, and the counts below were checked over every action in the ELF.

## Contents

1. [The chain in one picture](#the-chain-in-one-picture)
2. [Animation groups and the global animation slots](#animation-groups-and-the-global-animation-slots)
3. [Actions and their motion scripts](#actions-and-their-motion-scripts)
4. [Playing a motion](#playing-a-motion)
5. [Animation file format](#animation-file-format)
6. [Frame data: the action timeline](#frame-data-the-action-timeline)
7. [Body sizes and the action remap tables](#body-sizes-and-the-action-remap-tables)
8. [What this means for moveset mods](#what-this-means-for-moveset-mods)
9. [Tools](#tools)
10. [Fighter fields](#fighter-fields)
11. [Open leads](#open-leads)

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

Attack spheres: `g_SphereTables` `0x00516050` = {body `0x00515CC0` (9), **attack `0x00515D90` (12)**, hurt `0x00515EA0` (18)}, each `{s8 skeleton node, f32 offset[3] in the node's space, f32 radius}`; attack spheres count with radius x 2. Attack parts: 0/1 nodes 14/19, 2/3 nodes 4/7, 4/5 nodes 13/18, 6/7 nodes 3/6, 8/9 nodes 11/16, 10 node 10, 11 node 1 (which limb is which is for M2 to name; pairs are probably left/right). Bit 12 is the held weapon.

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
python remake/tools/remake_assets.py ISO remake/godot/assets_ripped --only models,anims   # glTF clips (remake/tools/conv_anims.py)
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
- Root motion: does the fighter's position follow node 1's translation (saved at `+0x3FB0` on each new motion), or is the movement scripted (timeline ops 0x17-0x19)? Blade Cut's hips end 0.73 m forward, so something must carry that over (or the next motion blends back).
- Opcodes 8, 9, 0x13, 0x15, 0x16, and `Action_Next`'s special negative ids (-3 picks one of actions 0x84-0x87 depending on the target).
- The `.mtd` action records: who loads them and which 52 actions they fill.
- Where flag 8 is set when a motion ends (the motion update), and what slot 0 holds in practice.
