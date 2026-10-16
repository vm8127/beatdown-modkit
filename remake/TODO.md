# Remake TODO

Work queued for when a running task finishes (running work is in [MEMORY.md](MEMORY.md), "Now"). Start at most one or two at a time: parallel work hits the usage limit and risks file conflicts. Each item becomes its own session or subagent with a fresh context.

## Done recently

- [x] M6 complete: subway + Downtown levels with doors both ways (done 2026-10-16, checked: level test PASS, screenshots of both areas and a door arrival)
- [x] M2+M3: Aaron rigged and animated in Godot (done 2026-10-15, checked: Blade Cut screenshot)
- [x] M6: abandoned subway station in Godot (done 2026-10-15, checked: walk test PASS, screenshot)
- [x] M4: animated Aaron replaces the capsule (done 2026-10-15, checked: smoke PASS with bone hit spheres, walk PASS, no-assets smoke PASS, screenshots of Blade Cut landing, the knockdown and Aaron in the subway)
- [x] M4a: Aaron's real moves on the capsule fighter (done 2026-10-15, checked: smoke test →P P P PASS, test_moves.py 862 checks PASS)

## Next, in order

1. [ ] **M5 research: enemy AI (V: later).** How street fighters decide to attack, guard, circle and take turns, read from `decomp/` and documented in `docs/` (new section or `docs/AI.md`, symbols in `symbols.tsv`). Pure research, no Godot files, so it can't conflict with anything. M5 needs it.
2. [x] **Game text: done 2026-10-15** (`tools/textkit.py`, `remake/tools/conv_text.py` -> `assets_ripped/text/`, `GameText`; docs/FORMATS.md, "Text"). Left for later: the game's colour palette, the font, which buttons icons ①-⑥ are.
3. [ ] **M7 prep: negotiation and recruiting.** The post-fight menu (RECRUIT / ROB / INTERROGATE / BEATDOWN) as Godot UI and logic, with the Pride gauge and formulas from `docs/MECHANICS.md`, tested in the dev arena.

## After the running work lands

- [ ] **Running since 2026-10-16 (visible sessions):** "Fight feel: reactions, grabs, walk" (M4 follow-ups), "Fight HUD with the game's font and colours", "Controller controls like the PS2 game". Each updates MEMORY.md as it goes.
- [ ] **More playable heroes:** export the other heroes' models and styles, a character pick in the dev arena.
- [ ] **Sound and music research:** find and decode the music, sound effect and voice formats; a converter.


- [ ] **M4a follow-ups:** root motion pushes the capsule into the dummy (applied past body collision; seen in the smoke screenshot); hitstun / hitstop / knockback are placeholders (not in the hit records: find where the game keeps them); motion-input time limits (`g_InputPatterns`) and where ↑/↓ come from; grabs and context moves can't be input yet; command conditions, Pride and TIRED unused.

- [ ] **M4 follow-ups:** hitstun / knockdown lengths from the reaction animations (now known: docs/ANIMATION.md "Hit reactions") instead of the strength placeholders; reaction direction (behind / left / right) and set 1 cases beyond HP and counter; blocked-hit reaction; what `FUN_002FABC0` means (kinds 9/10); walk playback speed vs walk_speed (feet may slide) and the walk modes (`g_WalkModes`: side-steps, run, action 3 run when far); multi-clip moves end at the first clip (conv_moves.Timing covers only the first play op); the game's own root motion (`+0x3FB0`); a dummy in the subway stage.
- [ ] **M6 follow-up (later):** the other areas and their doors; items as real pickups (markers now); interactive props (the subway drums); locked doors (`g_AreaDoorFlags` story flags, `Door_LockText` messages); the game's own arrival camera (the remake turns it to a clear angle); Downtown's variants picked at random like `Area_Load`; street fighters from `g_AreaPeople` instead of dummies at every spot.
- [ ] V plays M0 / M4 and gives feel feedback (timing, hitstop, camera).
