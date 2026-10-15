# Remake TODO

Work queued for when a running task finishes (running work is in [MEMORY.md](MEMORY.md), "Now"). Start at most one or two at a time: parallel work hits the usage limit and risks file conflicts. Each item becomes its own session or subagent with a fresh context.

## Done recently

- [x] M2+M3: Aaron rigged and animated in Godot (done 2026-10-15, checked: Blade Cut screenshot)
- [x] M6: abandoned subway station in Godot (done 2026-10-15, checked: walk test PASS, screenshot)
- [x] M4a: Aaron's real moves on the capsule fighter (done 2026-10-15, checked: smoke test →P P P PASS, test_moves.py 862 checks PASS)

## Next, in order

1. [ ] **M5 research: enemy AI.** How street fighters decide to attack, guard, circle and take turns, read from `decomp/` and documented in `docs/` (new section or `docs/AI.md`, symbols in `symbols.tsv`). Pure research, no Godot files, so it can't conflict with anything. M5 needs it.
2. [ ] **Game text.** Extract names, move names, menu text and negotiation lines through `remake/tools/remake_assets.py` (new converter), so the remake shows the game's own text. Text banks: see docs/SCRIPTS.md. M7 needs it.
3. [ ] **M7 prep: negotiation and recruiting.** The post-fight menu (RECRUIT / ROB / INTERROGATE / BEATDOWN) as Godot UI and logic, with the Pride gauge and formulas from `docs/MECHANICS.md`, tested in the dev arena.

## After the running work lands

- [ ] **M4a follow-ups:** root motion pushes the capsule into the dummy (applied past body collision; seen in the smoke screenshot); hitstun / hitstop / knockback are placeholders (not in the hit records: find where the game keeps them); motion-input time limits (`g_InputPatterns`) and where ↑/↓ come from; grabs and context moves can't be input yet; command conditions, Pride and TIRED unused.

- [ ] **M4 (unblocked now):** animated Aaron replaces the capsule: each move plays its clip (blend 8), hit spheres attached to the hitting body parts' bones.
- [ ] **M6 follow-up:** doors as exits between areas (Downtown <-> subway), battle spots, props.
- [ ] Daniel plays M0 / M4 and gives feel feedback (timing, hitstop, camera).
