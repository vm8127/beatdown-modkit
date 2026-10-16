# Controls: pad reading, button jobs, layouts, vibration

How Beat Down reads the DualShock 2 and what every button does, in the field and in fights. Read from the code (`decomp/`, the ELF tables) and the game's own help text (CDATA.XAF text ids in brackets, `python tools/textkit.py get ISO/XAF/CDATA.XAF <id>`), 2026-10-16. **Not checked in the emulator** unless a line says so. Confidence per fact: **read** = read in the code or a table; **text** = the game's help text says so; **guess** = inferred, not traced.

## Default layout (TYPE 1)

| Button | Job | Where it's from |
|---|---|---|
| □ | PUNCH (P) | `g_PadLayouts` layout 0 (read); help [30232] |
| △ | KICK (K) | layout 0 (read); [30232] |
| × | GUARD (G): hold to guard high, ↓ + × low guard [30269]; tap at the moment you land to get up quickly [29067]; with a direction: Weaving / Sway Back (codes 0x47-0x4A) | layout 0 (read) |
| ○ | SPECIAL (S): DEVASTATOR [30283], threaten [30295], negotiate when the opponent's Pride is 0 [30293], pickpocket on bumping into someone [35216], sends surrounding enemies flying [29072]; with directions, codes 0x40-0x46 | layout 0 (read) |
| L1 | ① **RUN** (with the stick) and **free movement** while locked on: L1 cancels the lock-on facing (`Fighter_TaskWalk` 0x0030CA90) [30281]; with R1: **ESCAPE** [30287] | read (job 0 = L1) + text |
| L2 | ② use / draw the item equipped to ② (input code 0x4C, slot 0) [30233, 32240] | read (job 2 = L2, code 0x4C) + text; which icon is L2 is a guess from the order ①-⑥ = L1 L2 L3 R1 R2 R3 |
| L3 | ③ (no use found) | guess |
| R1 | ④ **GRAB** (code 0x1E: `Fighter_PickWeaponMove`), **PICK UP** an item, **SEARCH** a downed foe [30299], grab a weapon from an enemy [30279], call an ally's backup while grabbing [29111]; with L1: ESCAPE | read (jobs 5 and 8 = R1) + text |
| R2 | ⑤ use / draw the item equipped to ⑤ (code 0x4D, slot 1) [30233, 32241] | read + text |
| R3 | ⑥ **TAUNT** (input code 0x01 = R3 press): wears down your own Pride gauge [30292] | read (job 6 = R3, code 0x01) + text; R3 = ⑥ is a guess from the order |
| Left stick | walk; lightly = walk, fully = run [30270]; read as the d-pad bits too | read |
| D-pad | same as the left stick (digital) | read |
| Right stick | camera (CAMERA TYPE X / Y options = normal / reverse); also 4 direction bits 0x100000-0x800000 that a few grab-state codes (0x37-0x3B) use | read (bits), guess (camera) |
| START | pause menu (`0x00300390`: START on pad 1 or 2 opens it) | read |
| SELECT | in a battle: a request to the battle (`0x002E3390` sets `g_Battle` +0xCC) when the player is free; meaning not traced | read / open |
| α | opens the field menu when not talking to anyone ("Just press α", dialogue scripts 201, 211, 220) | text; which button α is: open (START or △ likely) |

**Lock-on is automatic**: "Approach an enemy to lock on. They become your target for movement and attack" [30297]. Every direction in an input code is relative to that target (`Pad_ReadCommand` `0x002A42E0`; docs/ANIMATION.md, "Input matching").

## The six layouts (CONTROL CONFIG)

OPTIONS > CONTROL CONFIG has **TYPE (PLAYER 1)**, **VIBRATION (PLAYER 1)**, the same for player 2, CAMERA TYPE (X), CAMERA TYPE (Y), CAMERA FOLLOW (texts 9046-9060, 30101-30104, 30119-30125). The type is `g_SystemData` +5 (player 1) / +6 (player 2), vibration +7 / +8 (1 = on). Layout x action -> pad bit is `g_PadLayouts` `0x005CF7C0` (read):

| TYPE | PUNCH | KICK | GUARD | SPECIAL |
|---|---|---|---|---|
| 1 (default) | □ | △ | × | ○ |
| 2 | □ | × | △ | ○ |
| 3 | × | □ | △ | ○ |
| 4 | × | ○ | □ | △ |
| 5 | △ | ○ | □ | × |
| 6 | △ | × | □ | ○ |

With the Japanese language the TYPE is first remapped through `g_PadLayoutJP` `0x0050ADC0` {3, 0, 4, 1, 2, 5} (TYPE 1 -> row 3: × punch, ○ kick, □ guard, △ special). Only the four face buttons move; the shoulder jobs are fixed (`Pad_BuildButtonJobs` `0x003045C0` copies them from `0x005D04A0`).

## Button jobs: `g_PadJobBits`

`Pad_BuildButtonJobs` `0x003045C0` fills `g_PadJobBits` `0x005FFE48` (`u32[11][2]`, per port, gp-0x4DA8) with each job's pad bit; everything in a fight tests jobs, never raw buttons (read):

| Job | Address | Bit (TYPE 1) | Used for |
|---|---|---|---|
| 0 | `0x005FFE48` | L1 0x400 | run / free movement (`Fighter_TaskWalk`), escape with R1 |
| 1 | `0x005FFE50` | R2 0x2000 | item ⑤ (code 0x4D, 0x36) |
| 2 | `0x005FFE58` | L2 0x800 | item ② (code 0x4C, 0x35) |
| 3 | `0x005FFE60` | special (○) | special |
| 4 | `0x005FFE68` | special (copy) | special in the input patterns (bit 0x40) |
| 5 | `0x005FFE70` | R1 0x1000 | code 0x4E (pattern bit 0x20) |
| 6 | `0x005FFE78` | R3 0x8000 | taunt (code 0x01); Pad_ReadCommand reads it as a command button |
| 7 | `0x005FFE80` | guard (×) | guard (held), get-up, Weaving |
| 8 | `0x005FFE88` | R1 0x1000 | grab / pick up (code 0x1E, pattern bit 4) |
| 9 | `0x005FFE90` | kick (△) | K |
| 10 | `0x005FFE98` | punch (□) | P |

The CPU fighters use the same jobs: `AI_MakePad` `0x001541E0` turns an AI request (abstract bits 0x80 punch, 0x200 kick, 0x100 guard, 0x40 special, 0x1000 R1, 0x800 L2, 0x2000 R2, 0x8000 R3) into its controller slot's pad bits, and adds L1 when it wants to circle (read).

## Reading the pad

- `Pad_Update` `0x001D0B90` (read) runs once per frame for ports 0 and 1: `scePadRead`, the 16 button bits through `Pad_RemapButtons` `0x001D02B0` (libpad's bits -> the game's: Left 1, Right 2, Up 4, Down 8, START 0x10, SELECT 0x20, △ 0x40, × 0x80, □ 0x100, ○ 0x200, L1 0x400, L2 0x800, R1 0x1000, R2 0x2000, L3 0x4000, R3 0x8000; the libpad side matches the SDK's `PAD_*` constants, so this is certain), into `g_Pad1` `0x00685450` / pad 2 `0x006854D0` (struct `Pad`, 0x80 bytes): held, newly pressed, released, auto-repeat (after 20 frames, then every 4th frame), the time each button has been held, and the sticks.
- **Analog sticks** (read): only in analog mode (pad type 7). Centre 0x80; dead zone = **half the stick's radius** (radius 127, dead zone 64), and the output is rescaled so it goes from 0 at the dead zone edge to 1 at full tilt (a radial dead zone with rescaling), clamped to length 1: `Pad` +0x70/+0x74 left X/Y, +0x78/+0x7C right X/Y, floats -1..1 (X is positive to the **left**, Y positive **up**: the code computes centre - raw). The left stick also sets digital bits when the d-pad is idle: beyond 0x20 / 0xDF (about 75 %) it adds 0x10000 left, 0x20000 right, 0x40000 up, 0x80000 down to the held word.
- **Fighter pads**: `Fighter_ReadPad` `0x0030A5A0` copies a port's pad into `g_FighterPads` `0x007241D0` (0x80 per controller slot, the fighter's +0x17; `Fighter_Pad` `0x002F92A0` returns it). There the left stick becomes **d-pad bits** in 8 sectors (each direction covers 135 degrees, so diagonals set two bits; stick dead zone 0.1 after the pad's own) and the right stick becomes 4 bits 0x100000 up, 0x200000 down, 0x400000 left, 0x800000 right (90-degree sectors). So the fighter code only sees digital directions plus the analog floats (+0x70-0x7C).
- **Masks** (`Fighter_MaskPad` `0x0030A9F0`, read): while a message box is up, every job except L1, special (job 3), R3 and the d-pad is cleared, and the right stick too; in the field outside a battle (`0x0060C960` bit 0 clear) R1, guard and special (jobs 4, 5, 7, 8) are cleared. Mode 0 clears the whole pad (cutscenes).
- **Input codes**: `Pad_ReadCommand` `0x002A42E0` turns the fighter pad into input codes with `Pad_MatchPatterns` `0x002A30F0` and `g_InputPatterns`, below; directions relative to the target (toward ±80 degrees = →, beyond ±100 = ←).

## Input patterns: `g_InputPatterns` `0x004FC580`

One 64-byte entry per input code (index = code, 83 entries, ends at the first entry whose +4 is -1): `{s32 time limit in ms, u32 cond[6], u32 steps[9], -1 terminated}`. The steps are newest first; step bits are jobs (1 P, 2 K, 4 R1 grab, 8 G, 0x10 R3, 0x20 R1 (job 5), 0x40 S, 0x80 L2, 0x100 R2), directions relative to the target (0x200 →, 0x400 ←, 0x800 ↑, 0x1000 ↓), 0x10000 = held instead of pressed, 0x8000 = released. `cond[0]` is matched against the fighter's state (3 = free / walking, 4 = grabbing, 0x1E3 = can guard, 1 = idle); the others against the target and status words (not traced). `python tools/codemap.py input-patterns ISO/SLUS_211.50` prints the table. Read from the code and the table; the codes not in `codemap.INPUTS` are named here from their steps only.

**Time limits** (read): a direction + button within **166 ms (10 frames)**; two directions + button (→→P, ↓→K) within **316 ms (19 frames)**; three (→↓→K) within **350 ms (21 frames)**; directional guard (→G) 500 ms; a single button 16 ms (one frame).

Selected codes: 0x01 R3 (taunt); 0x02-0x04 / 0x10-0x12 three-step motions; 0x05-0x09 / 0x13-0x17 two-step; 0x0A-0x0E / 0x18-0x1C dir + P/K; 0x0F / 0x1D P/K released; 0x1E R1 (grab, pick up); 0x1F-0x3F grab-state inputs (P, K, G, S, L2, R2, held directions, 0x29/0x30 a P/K after step 0x20000, probably the rapid press "∬"); 0x40-0x46 S with directions; 0x47-0x4B guard + held direction (Weaving, Sway Back...; also re-targets the nearest enemy in front when not locked, `Fighter_HandleCommand`); 0x4C L2 / 0x4D R2 (items); 0x4E R1 (job 5); 0x4F →→, 0x50 ←← (dashes / steps, state 1).

**Correction to docs/ANIMATION.md, "Guard"**: codes 0x40-0x46 are the SPECIAL button (○) with a direction, not guard codes; `Fighter_HandleCommand` starts `Fighter_RemapAction(fighter, 10)` for them when `0x002FA5C0` allows it, so action 10 is the special move (DEVASTATOR or the threaten), not the guard pose (read).

## Vibration

Read: `Fighter_Vibrate` `0x002FC1B0` (fighter, kind) rumbles the fighter's port (only for controller slots 0-1, not in replays) when VIBRATION is on for that player (`g_SystemData` +7 + port). It drives both motors: the small one on, the large one at `g_VibrationStrength` `0x005CF930` {64, 128, 255}[kind] for `g_VibrationTime` `0x005CF938` {0.05, 0.08, 0.09}[kind] seconds (`Pad_Vibrate` `0x001D2130`, `Pad_UpdateVibration` `0x001D21D0` counts down and stops through `scePadSetActDirect`).

| Kind | Large motor (0-255) | Time | When |
|---|---|---|---|
| 0 | 64 | 0.05 s (3 frames) | **every hit that lands**, on both the attacker (`0x00320310`, after `Fighter_ApplyDamage`) and the one hit (`Combat_TakeHit`) |
| 1 | 128 | 0.08 s | a wall / hazard hit (`0x002EC920`) |
| 2 | 255 | 0.09 s | `0x001B96A0` when the counter at `0x0060CB68` rises (kind 0 below 100, kind 2 from 100) and several callers in `0x001BB290`-`0x001BEFC0` (not traced), and action timeline op **0x50** (kind = its argument: moves that rumble on a given frame) |

## Battle escape (L1 + R1), not the door button

`Fighter_TaskAction` `0x0030AEB0` calls `Battle_RequestEscape` `0x002E2660` when the fighter pad holds **L1 (job 0) and R1** (read). That function only works during a battle (`g_Battle` +0x144 bit 2) and when the side may run (`EXF_SET_ESCAPE`, the target not a boss: `Person.skills` bit 31) and sets `g_Battle` +0xA0 + side x 12; `0x002E2930` then needs the player standing in a door zone facing the door (the blinking icon 0x3DD) and counts down `+0xA8` before the escape flag `+0x144` bit 6. So docs/STAGES.md's "door request on bit 0x1000" is the **ESCAPE** (①+④ [30287]) through a door during a fight. How the field (no battle) takes a door is not traced: most likely walking into the zone (the remake does that).

## Menus

Menus test `g_SystemData` +0x24 (confirm buttons) and +0x28 (cancel / back) against the newly pressed bits (`0x00300390`, `0x00368120`, ScenePlayer): the confirm / cancel buttons are a saved setting (US: probably × / △; not read from the defaults). Text 9066-9078 asks for a DUALSHOCK 2 (analog required). The text banks also hold an unused Xbox port's messages (19085-19106: "thumbstick", memory units, "Press A").

## Icons in the text

docs/FORMATS.md, "Text", lists the icon glyphs. Meaning (text + code): ① run / escape = L1; ② item = L2 (guess by order); ④ grab, pick up, search = R1; ⑤ item = R2; ⑥ taunt = R3 (guess by order); ∬ rapid press; α open the menu. ③, ⑰, ⑱, β: no help text uses them in English. The face buttons in help text are layout-aware (`{btn:punch}` ... `Pad_ActionButton` `0x002EBD40`).

## Open questions

- ~~Which buttons α, β, ⑰, ⑱ are~~: the font's icon sheet shows α β = START, ③ = L3, ⑥ = R3, ⑰ ⑱ = crime icons (sheriff star, skull), not buttons (docs/HUD.md, 2026-10-16).
- What SELECT in a battle requests (`0x002E3390`, `g_Battle` +0xCC / +0xD0).
- How a door is taken in the field without a battle.
- The default confirm / cancel masks (`g_SystemData` +0x24 / +0x28).
- `cond[1-5]` of `g_InputPatterns` and the step bits 0x20000, 0x40000-0x400000 in grab-state codes.
- The camera's right-stick speed and the CAMERA FOLLOW option.
