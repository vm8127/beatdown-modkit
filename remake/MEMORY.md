# Remake session memory

Read this first in every remake session, and update it before stopping (or whenever something is decided). It's the hand-off between sessions: what's true now, what's next, what's waiting on Daniel. The full plan and rules are in [PLAN.md](PLAN.md); game knowledge goes in `docs/`, never only here.

## Now

- **M0 (capsule brawler): built, smoke test passes, not yet played by Daniel.** Dev arena with fighter state machine, 6 placeholder moves with combos, input buffer, hitstop, knockback, knockdown, guard, dummy AI modes, debug overlay, pause / frame step / slow-mo. remake/README.md explains the code.
- **M1 (mesh format + `remake_assets.py`): running in its own session** "M1: mesh format + remake_assets.py" (name `m1-mesh-extract`, shares this checkout). Check its MEMORY entry/commits before redoing anything.
- **Next step:** Daniel plays M0 and says how it feels (timing, hitstop, camera); tune. Then M2 (skeleton) after M1 lands.
- **Waiting on Daniel:** feedback on M0.

## Decisions

| Date | Decision | By |
|---|---|---|
| 2026-10-15 | Everything remake-specific lives in `remake/` in this repo (no separate repo). Godot project: `remake/godot/`. Extraction tool: `remake/tools/remake_assets.py`. | Daniel |
| 2026-10-15 | Keep this file as the session memory so work can stop and resume anytime. | Daniel |
| 2026-10-15 | GDScript (Daniel likes C# but left it to Claude; GDScript: no .NET SDK, hot reload, most tutorials). | Claude, Daniel OK |
| 2026-10-15 | Claude writes the gameplay code ("I want to see what you're capable of"); Daniel reads and plays. | Daniel |
| 2026-10-15 | Godot 4.7.2 stable (standard build) installed in `__external_tools/godot/`, SHA512 checked. | Daniel allowed |
| 2026-10-15 | Big independent tasks go to separate sessions (fresh context), e.g. M1. | Daniel |
| 2026-10-15 | Incremental development with a developer scene (`remake/godot/dev/`); every feature lands there first (PLAN.md, "Incremental development"). | Daniel |

## Open questions for Daniel

- None open.

## Environment

- Godot 4.7.2: `__external_tools/godot/Godot_v4.7.2-stable_win64.exe` (editor), `..._console.exe` (headless). First run on a fresh clone: `--headless --path remake/godot --import`.
- Smoke test: `... _console.exe --headless --path remake/godot -- --smoke` (exit 0 = pass).
- Several sessions may share this checkout: commit by path, never `git add -A`.
- Repo layout for the remake: see [README.md](README.md).

## Session log

Newest last. One or two lines per session: what was done, where it stopped.

- 2026-10-15: Created `remake/` (README, PLAN moved from `docs/PLAN-godot-remake.md`, this file, `.gitignore`). Added the developer-scene idea to the plan. Asked the first-session questions. Stopped before M0/M1.
- 2026-10-15 (same session): Daniel chose: Claude writes the code, GDScript, sub-tasks in separate sessions. Installed Godot 4.7.2. Built M0 in `remake/godot/` (dev arena, fighter, brains, camera, overlay, smoke test: PASS, screenshot checked). Started the M1 session.
