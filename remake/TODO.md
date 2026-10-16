# Remake TODO

Work queued for when a running task finishes (running work is in [MEMORY.md](MEMORY.md), "Now"). Start at most one or two at a time: parallel work hits the usage limit and risks file conflicts. Each item becomes its own session or subagent with a fresh context.

## Done recently

- [x] Fight HUD with the game's font, colours and button icons (done 2026-10-16, checked: HUD test PASS, test_text PASS, screenshots hud_fight / hud_lowhp / hud_text)
- [x] M6 complete: subway + Downtown levels with doors both ways (done 2026-10-16, checked: level test PASS, screenshots of both areas and a door arrival)
- [x] M2+M3: Aaron rigged and animated in Godot (done 2026-10-15, checked: Blade Cut screenshot)
- [x] M6: abandoned subway station in Godot (done 2026-10-15, checked: walk test PASS, screenshot)
- [x] M4: animated Aaron replaces the capsule (done 2026-10-15, checked: smoke PASS with bone hit spheres, walk PASS, no-assets smoke PASS, screenshots of Blade Cut landing, the knockdown and Aaron in the subway)
- [x] M4a: Aaron's real moves on the capsule fighter (done 2026-10-15, checked: smoke test →P P P PASS, test_moves.py 862 checks PASS)

## Next, in order

0. [ ] **HUD follow-ups:** compare the HUD with an emulator screenshot of a story fight (positions are the code's constants, docs/HUD.md open questions); draw `GameInput.text_button()` labels instead of PS2 glyphs when a keyboard / Xbox pad is active; party members' bars (rows 1-2) once there is a party; the BATTLE RESULT panel (BA_PARTS*), READY / YOU LOSE / ESCAPED!; move Pride and TIRED from `FighterMeters` into Fighter when M7 needs them; taunts lowering Pride; Pride regen after 0 (`Fighter_PrideRegen` 0x313F90); kanji font pages for Japanese.

0. [ ] **Controller follow-ups:** wire `PlayerBrain.wants_run()` (L1 / full tilt) into the fighter's walk modes and `wants_escape()` (L1+R1) into a battle escape at doors (fight-feel / M6 own those files); taunt (#01), items (#4C/#4D) and grab (#1E) moves once their systems exist; the HUD draws `GameInput.text_button()` glyphs; find which buttons α, β, ⑰, ⑱ are (docs/CONTROLS.md open questions); V tries a real pad (list in MEMORY.md).

1. [ ] **M5 research: enemy AI (V: later).** How street fighters decide to attack, guard, circle and take turns, read from `decomp/` and documented in `docs/` (new section or `docs/AI.md`, symbols in `symbols.tsv`). Pure research, no Godot files, so it can't conflict with anything. M5 needs it.
2. [x] **Game text: done 2026-10-15** (`tools/textkit.py`, `remake/tools/conv_text.py` -> `assets_ripped/text/`, `GameText`; docs/FORMATS.md, "Text"). Left for later: the game's colour palette, the font, which buttons icons ①-⑥ are.
3. [ ] **M7 prep: negotiation and recruiting.** The post-fight menu (RECRUIT / ROB / INTERROGATE / BEATDOWN) as Godot UI and logic, with the Pride gauge and formulas from `docs/MECHANICS.md`, tested in the dev arena.

## After the running work lands

- [ ] **Running since 2026-10-16 (visible sessions):** "Controller controls like the PS2 game" (done 2026-10-16). Each updates MEMORY.md as it goes.
- [ ] **More playable heroes:** export the other heroes' models and styles, a character pick in the dev arena.
- [ ] **Sound and music research:** find and decode the music, sound effect and voice formats; a converter.


- [x] **M4a follow-ups (done 2026-10-16, "M4 follow-ups" session):** root motion vs body collision fixed (the game's body spheres, FUN_003072C0); hitstun / knockback from the game (no hitstop in the game: placeholder kept); grabs inputtable (R1 -> catch -> GRAB P/K, REAR GRAB P/K). Still open: motion-input time limits beyond the controller session's, where ↑/↓ come from, command conditions, Pride and TIRED, context moves (#23, #27: grabbing a lying fighter).

- [x] **M4 follow-ups (done 2026-10-16):** hitstun / knockdown from the reaction actions (release frames), direction, knockdown / KO / wall rows, blocked hits (guard 821 + guard-hit actions), multi-clip moves (action_sim.py), grabs, 8-way locked walk + run from g_WalkModes with planted feet, the game's root motion (FUN_002F0260) and body collision. Left open (docs/ANIMATION.md "Open leads"): the special reaction kinds 4-7 / 0x12 / 0x13 / 0x3E3-0x3E6, how long the lying loop lasts and getting up early, crouching guard (↓ + guard: actions 814-819; needs a brain call), rear / side catches (+0x4572), hold escape, grabbing a lying fighter, why the game's walk outruns its clip.
- [ ] **M6 follow-up (later):** the other areas and their doors; items as real pickups (markers now); interactive props (the subway drums); locked doors (`g_AreaDoorFlags` story flags, `Door_LockText` messages); the game's own arrival camera (the remake turns it to a clear angle); Downtown's variants picked at random like `Area_Load`; street fighters from `g_AreaPeople` instead of dummies at every spot.
- [ ] V plays M0 / M4 and gives feel feedback (timing, hitstop, camera).

- [x] **input_test "□ hit lands" fixed (2026-10-16, combat-feel session):** not reach or root motion: the R1 grab check earlier in the test caught Dummy 1, the hold ran out (`_release_hold`), and the victim kept `held_by` set (the release skips `_end_held`), so every later hit returned "miss" and body push skipped the pair. `_release_hold` now frees the victim. All tests PASS.
