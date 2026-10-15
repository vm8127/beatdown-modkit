# Remake session memory

Read this first in every remake session, and update it before stopping (or whenever something is decided). It's the hand-off between sessions: what's true now, what's next, what's waiting on Daniel. The full plan and rules are in [PLAN.md](PLAN.md); game knowledge goes in `docs/`, never only here.

## Now

- **M0 (capsule brawler): built, smoke test passes, not yet played by Daniel.** Dev arena with fighter state machine, 6 placeholder moves with combos, input buffer, hitstop, knockback, knockdown, guard, dummy AI modes, debug overlay, pause / frame step / slow-mo. remake/README.md explains the code.
- **M1 (mesh format + `remake_assets.py`): done 2026-10-15, not yet seen by Daniel.** `python remake/tools/remake_assets.py ISO remake/godot/assets_ripped` checks the disc MD5s and writes `models/street_089.glb` (preset 89's street look) and `models/fighter_aaron_078.glb` (Aaron's fight look from his outfit slots), textured, static bind pose. Godot imports them without errors; `res://dev/model_viewer.tscn` shows them (Left/Right/Up/Down, `-- --shot=x.png`). Formats: docs/FORMATS.md (RenderWare 3.x clumps, plain geometry, Skin + HAnim, outfit assembly); decoder `tools/rwkit.py`; converters `remake/tools/conv_models.py` + `gltf_writer.py`. For M2: skin weights, inverse bind matrices and the 22-node skeleton are already decoded in rwkit (FORMATS.md, "Skeleton and skinning"); only the glTF skin export is missing.
- **M3 research (animation format + frame data): done 2026-10-15** (read from code + disc, not tested in the emulator). Animations are RenderWare `RtAnimAnimation` chunks with compressed keyframes (float16 quaternions, translation = float16 x scale + offset, 30 Hz keys, 22 nodes, LZSS-packed in STAGE.XAF): docs/ANIMATION.md, "Animation file format"; decoder `tools/animkit.py` (`list`, `dump --json/--sample`, `check`: all 4,927 decode). Frame data = the action's second stream ("timeline"): attack window (active frames + attack spheres), combo cancel point, early release; docs/ANIMATION.md, "Frame data", and `python tools/codemap.py framedata ISO/SLUS_211.50 0x13`. Aaron: stance anim 4 (group 160), walk anim 5 (group 161), Blade Cut anim 34 (group 184, active 19-25, cancel 24). Next for M3: glTF animation export in `remake_assets.py` bound to rwkit's skeleton (node order = HAnim index; only nodes 1 and 8 have translation keys, so keep the skeleton's offsets).
- **M6 research (stage geometry + collision): done** (read from code + disc, not tested in the emulator). docs/STAGES.md, `tools/stagekit.py` (`areas`, `pieces`, `collision --json/--obj`, `world --obj`). An area = FSTAGE.XAF entry = area id (RpWorld render geometry, separate wall / camera / floor collision meshes, doors clump = exits, props + PB placements) + `g_AreaDefs` row (lights, music, battle spots, wall kinds) + `g_AreaObjects` (items per story stage). Area ids are not UNLOCKS.md's location ids (subway = area 5). Next for M6: a stage converter in `remake_assets.py` (world → glTF, collision → Godot trimesh) once M1's texture side handles PS2-native textures (0x15).
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
| 2026-10-15 | Big independent tasks go to separate sessions or subagents (fresh context), e.g. M1 (session), M3/M6 research (subagents: the app refused to start more sessions from that turn). Each writes its own docs/tool files; shared files (symbols.tsv, CODEMAP.md, this file) only by small edits. | Daniel |
| 2026-10-15 | Keep this file current at every step (Daniel: "keep your thinking cache"), so an interrupted session restarts from here, not from scratch. | Daniel |
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
- 2026-10-15 (M1 session `m1-mesh-extract`): decoded the model format (RenderWare 3.x, docs/FORMATS.md), wrote `tools/rwkit.py`, `remake/tools/remake_assets.py` (+ `conv_models.py`, `gltf_writer.py`) and `remake/godot/dev/model_viewer.*`. Both models import and render textured (screenshot checked by Claude). Next for models: M2 (skin export), more people (a converter list in `conv_models.MODELS`).
- 2026-10-15 (same session): Daniel asked for more RE meanwhile; started M3 animation research and M6 stage research as background subagents. Waiting on them, on the M1 session, and on Daniel's M0 feedback.
- 2026-10-15 (M6 research subagent): decoded the area packs (docs/STAGES.md, `tools/stagekit.py`): loader chain, RpWorld, wall/camera/floor collision, doors with destination tags, battle spots, per-stage objects, lights/music; corrected the area id numbering (UNLOCKS.md note). Open: wall kinds, door lock meaning, PS2-native textures for the world.
- 2026-10-15 (M3 research subagent): decoded the animation format (RenderWare compressed keyframes, docs/ANIMATION.md) and the frame data timeline (active frames, cancel points, release); wrote `tools/animkit.py` and `codemap.py framedata`; named 20+ functions/tables (symbols.tsv, Fighter fields in structs.tsv). Open: skeleton binding of key translations, root motion, untraced timeline ops, in-game check of a cancel.
