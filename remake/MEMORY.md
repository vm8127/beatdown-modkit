# Remake session memory

Read this first in every remake session, and update it before stopping (or whenever something is decided). It's the hand-off between sessions: what's true now, what's next, what's waiting on Daniel. The full plan and rules are in [PLAN.md](PLAN.md); game knowledge goes in `docs/`, never only here.

## Now

- **Milestone:** none started. Setup done: `remake/` created, plan moved here.
- **Next step:** get Daniel's answers to the open questions below, then start M0 (with him) and M1 (mesh format, Claude).
- **Waiting on Daniel:** the questions below.

## Decisions

| Date | Decision | By |
|---|---|---|
| 2026-10-15 | Everything remake-specific lives in `remake/` in this repo (no separate repo). Godot project: `remake/godot/`. Extraction tool: `remake/tools/remake_assets.py`. | Daniel |
| 2026-10-15 | Keep this file as the session memory so work can stop and resume anytime. | Daniel |
| 2026-10-15 | Incremental development with a developer scene (`remake/godot/dev/`); every feature lands there first (PLAN.md, "Incremental development"). | Daniel |

## Open questions for Daniel

1. GDScript or C#?
2. How hands-on for gameplay code (write it yourself with explanations and reviews / pair: Claude scaffolds, you fill in / Claude writes, you read)?
3. Godot editor: not installed (nothing in `__external_tools/`). OK to download Godot 4 stable (official godotengine.org / GitHub release; the .NET build if C#) into `__external_tools/godot/`?

## Environment

- Godot: not installed yet.
- Repo layout for the remake: see [README.md](README.md).

## Session log

Newest last. One or two lines per session: what was done, where it stopped.

- 2026-10-15: Created `remake/` (README, PLAN moved from `docs/PLAN-godot-remake.md`, this file, `.gitignore`). Added the developer-scene idea to the plan. Asked the first-session questions. Stopped before M0/M1.
