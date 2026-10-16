# Remake session memory

**Rule: keep this file under 5 KB.** Read it first in every remake session; update it before stopping. Details go in README.md, docs/ (game facts), TODO.md (follow-ups) or [LOG.md](LOG.md) (session log and the full old status notes; not read at startup). Plan and rules: [PLAN.md](PLAN.md).

## Now
All done and tested headless, none yet played by V (status; details; next):
- **M0 capsule brawler:** README.md. Next: V plays and gives feel feedback.
- **M1 models, M2+M3 rigged Aaron + animation:** FORMATS.md, ANIMATION.md; `remake_assets.py`. Next: more people (`conv_models.MODELS`).
- **M4 animated Aaron, real moves, game hit reactions, grabs, walk/run:** README.md, ANIMATION.md, MECHANICS.md; tests `-- --fight`, test_moves.py. Next: TODO.md "M4 follow-ups" (hitstop, grab release guess, Pride/TIRED).
- **M6 levels (subway + Downtown, doors, props, battle spots):** README.md "Levels (M6)", STAGES.md. Next: TODO.md "M6 follow-up" (more areas, interactive props).
- **Controller controls (GameInput, TYPE 1-6, F8 screen):** CONTROLS.md. Next: V tries a real pad.
- **Fight HUD, game text and font:** HUD.md, FORMATS.md "Text"; hud_test.tscn, test_text.py. Next: TODO.md "HUD follow-ups"; compare positions with the game.
- **Bug:** `game/input/input_test.tscn` fails 1 check: Blade Cut whiffs from 1.2 m since 629519d/694709d (TODO.md has the trace). Fix first.
- **Next candidates (V picks):** that bug, M7 negotiation + recruiting, more heroes, sound research. Later: M5 enemy AI, other areas.


## Decisions
- Remake lives in `remake/` of this repo; Godot 4.7.2 in `__external_tools/godot/`; GDScript (Claude's choice, V OK). V reads and plays; Claude writes the code.
- Scenes (.tscn) for hand-made parts, resources (.tres) for move data, code only for what is built from game data.
- Incremental: every feature lands in `remake/godot/dev/` first (PLAN.md).
- Areas: subway (area 5) and Downtown (area 1) with doors; more later. Enemy AI (M5) later.
- Big independent tasks go to separate sessions with fresh context. Shared files (symbols.tsv, CODEMAP.md, this file) only by small edits.
- The main session plans, briefs and checks; work runs in visible sessions (start_session in the turn of V's own message, one per task, exact-file briefs; model per PLAN.md). Check each result yourself (tests + screenshots sent to V), then archive the session. V works remotely often: tests and screenshots are the evidence.
- Keep this file current at every step, so an interrupted session restarts from here.

## Open questions for V
- Replace "V plays M0" with "V plays the subway/Downtown levels with a controller and gives feel feedback"? (Asked 2026-10-16; no answer yet.)

## Environment
- Godot: `__external_tools/godot/Godot_v4.7.2-stable_win64.exe` (editor), `..._console.exe` (headless). Fresh clone: `--headless --path remake/godot --import`.
- Tests and how to run them: PLAN.md "Rules"; each prints one summary line.
- Several sessions may share the checkout: commit by path, never `git add -A`.
