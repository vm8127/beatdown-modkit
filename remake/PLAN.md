# Beat Down remake in Godot: brief for a new session

Read `remake/MEMORY.md` first (where we are, what's next), then this, then `CLAUDE.md` and `README.md`. This file starts a new project next to the modding work: a **remake of Beat Down: Fists of Vengeance in Godot 4**, built on everything this repo has already reverse engineered.

## Goal and who it's for

- V is a fintech programmer who wants to **learn how video games work** by building one for fun. It's a private hobby project: **never released, never distributed**.
- The approach is an **engine reimplementation** (like OpenMW or OpenGOAL): a new Godot game that loads the original models, textures and animations from V's own disc (`ISO/`), and re-implements the game logic natively from what we documented. It isn't a matching decompilation and doesn't run the PS2 code.
- "Similar" is the target, not exact. Faithful where the research makes it easy (stats, damage formulas, move lists, negotiation), free to simplify or improve elsewhere.

## How to work with V

- **V wants to code and learn, not just receive a finished game.** For the Godot gameplay code, ask how hands-on they want to be. By default, explain the game concept (game loop, `delta`, state machines, hitboxes, cancel windows...), scaffold, and review, and let them write the core gameplay pieces. The reverse-engineering and asset-conversion tooling (Python, in this repo) you can do yourself.
- Ask once whether V prefers **GDScript or C#** (V is from fintech, so C# may feel familiar; GDScript has more tutorials).
- V prefers short, direct answers. Keep a task list, explain what each milestone teaches.
- Animation authoring isn't V's skill. Use the original Beat Down animations (once decoded), Mixamo, or AI video-to-mocap. Focus on the code that makes moves *feel* good (timing, hitstop, cancels, reactions).

## Rules

- **Use anything this repo has researched**: every doc, dump, tool, symbol, struct and the decomp. Extend the existing tools (`bdkit.py`, `codemap.py`, `scriptkit.py`, `pcsx2.py`) rather than starting over.
- **Don't touch the existing mods.** The remake must never change, remove or break anything in `mods/` (the pnach sections, `mods/c/*.c`, `mods/roster.json`), the installed cheat file `C:\Games\Emu\PCSX2\cheats\SLUS-21150_C9F6EF9A.pnach`, `tools/debug/`, or the mod plans in `docs/mods/`. Tools and docs may be **extended** (new commands, new sections, new symbols, corrections backed by evidence), but existing commands keep working with the same arguments and output, so the mod workflow in `CLAUDE.md` still works. If an extension needs to change shared code (e.g. a parser in `bdkit.py` that the mods rely on), check that the mod commands still produce the same output, and ask V first if anything they produce would change.
- **Outside tools and skills are welcome** (Godot addons, Blender and its plugins, glTF libraries, PS2 format tools, mocap tools, community RE tools, Claude skills...). **Ask V before installing or downloading anything**, saying what it is and where it comes from. Third-party tools go in `__external_tools/` (README.md, "External tools").
- **Document everything you find out about the game, here, in the same commit.** Every format, address, function, struct field, mechanic or table you decode for the remake goes into this repo's docs exactly as in the modding work (`CLAUDE.md`, "Working rules"): formats in README.md or `docs/FORMATS.md`, names in `symbols/symbols.tsv` with types, fields in `symbols/structs.tsv`, functions in `docs/CODEMAP.md`, rules in `docs/MECHANICS.md`, animation facts in `docs/ANIMATION.md`, open questions in each doc. Say how sure each fact is. The remake and the mods share this knowledge, so nothing learned may stay only in the Godot project or in a chat.
- **Extracting assets from the disc is fine and expected.** Use the original models, textures, animations, stages, text and data tables as much as you like.
- **But the repos hold only the tool, never its output.** Build one reproducible extraction tool, `remake/tools/remake_assets.py`:
  - `python remake/tools/remake_assets.py ISO remake/godot/assets_ripped` rebuilds **every** game asset the remake uses from V's `ISO/`, and nothing else is needed. A fresh clone plus V's disc plus this one command gives a working project.
  - Deterministic and re-runnable: same disc, same output; it overwrites its own output folder; it checks the disc's MD5s (README.md) first and stops on a mismatch.
  - Every new asset type the remake needs is added to this tool, never copied by hand or exported once from Blender. Each converter (mesh, skeleton, animation, stage, text, tables) is a subcommand or module it calls.
  - `assets_ripped/` (and Godot's `.godot/` import cache) are in the Godot project's `.gitignore`. Its README says to run the tool first.
- **Never commit game data or anything converted from it**, in either repo: no glTF, PNG, animation or table dumps generated from the disc. Same rules as `CLAUDE.md` for `ISO/`, `decomp/` and the ELF. Data the remake needs from the ELF (move lists, stats, templates) is extracted by the tool too, not pasted into the Godot code.
- Ripped assets from other games (e.g. Yakuza moves) are okay **only as private, uncommitted placeholders**. Prefer original or freely licensed assets for anything that might be shared.
- **Everything remake-specific lives in `remake/`** in this repo (V, 2026-10-15; replaces the earlier idea of a separate repo): this plan, `remake/MEMORY.md` (session memory), the Godot project `remake/godot/`, and `remake/tools/` (the extraction tool and the glTF/Godot writers). Game knowledge stays where it always was: format decoders the mods could use too go in `tools/` (new `bdkit.py` commands or modules), and what they teach goes in `docs/`.
- Document every format you decode here (README.md's format sections, or a new `docs/FORMATS.md`), with symbols in `symbols/symbols.tsv` and `docs/CODEMAP.md`, like any other RE work.

## What we already have (use it)

| Research | Where | Use in the remake |
|---|---|---|
| Disc layout, XAF archives, chunk types | README.md, `tools/bdkit.py` | Asset extraction |
| Textures | `bdkit.py tex`, docs/PARTS.md | Texture export to PNG |
| Character, class rows `{body, style, skeleton, groups}`, outfit presets | README.md "Characters and movesets", docs/PARTS.md | Character definitions |
| Styles, command lists, move lists | docs/movesets.md, `codemap.py actions` | Each style's move tree (input string → action) |
| Actions, motion scripts, animation groups and ids | docs/ANIMATION.md | Which animation each move plays, frame ranges, blend |
| Hit records, damage formula, combo scaling, stats | docs/MECHANICS.md, `codemap.py` | Combat numbers |
| Negotiation (RECRUIT / ROB / INTERROGATE / BEATDOWN) | docs/MECHANICS.md | Post-fight menu |
| Person templates, street-people placement per area and chapter | docs/CODEMAP.md, docs/mods/PLAN-new-characters.md | NPC spawning |
| Missions, script format, event VM commands | docs/SCRIPTS.md, `tools/scriptkit.py` | Story and dialogue (port the VM or convert scripts) |
| Unlocks, recruits, chapters | docs/UNLOCKS.md | Story progression |
| Cut content | docs/CUTCONTENT.md | Optional extras |
| Full pseudocode (about 7,000 functions, 620+ named symbols) | `decomp/` (local only) | Read the logic of anything not yet documented |

Facts settled while planning this (2026-10-15):

- Input → move: `Cmd_MatchSequence` `0x2A6720` matches the recent input history against the style's command list, whose entries are whole input strings (`P`, `PP`, `PPP`, `PP↓P`...). Each names an action.
- Most combo steps are **separate short clips** (about 28–56 frames at 60 fps), each started with a fixed **8-frame blend**, and each script ends with `goto 1` (back to stance, also blended). Some multi-hit moves are **one long animation** (Boxer action 1601: 132 frames; Aaron's `→PPP` action 1809: animation 1125), with several hits from the hit records.
- Combo-step clips start from the previous hit's end pose, so they look abrupt from guard.
- **Not known yet:** when the next input is accepted (cancel windows) and the hit's active frames. They're probably in the action's second stream (`+0x3FD8`) or its event records (`g_ActionEvents` `0x582990`). Open lead in docs/ANIMATION.md.

## What's missing (reverse engineering still needed)

1. **Mesh format** (done in M1, docs/FORMATS.md): XAF chunk type `0x10`, contains Softimage user data like `BONETAG=29`. Street people use a low-poly mesh at CDATA.XAF entry preset + 7; fighters build their look from 22 outfit slots (`g_ItemTable` `+0x10` → DATA.XAF mesh). Probably VIF/GIF packet data: find the loader and renderer in `decomp/` (start from `Pack_Load` `0x0029E500`).
2. **Skeleton and skin weights** (body sizes S/M/L have different skeletons).
3. **Animation format** (STAGE.XAF packs, loaded per group by `Xaf_LoadAnimPack` `0x0029ED70`).
4. **Stage geometry and collision.**
5. Frame data: cancel windows and active frames (see above).

## Incremental development and the developer scene

V's idea (2026-10-15): grow the game in small playable steps, and keep a **developer scene** (`remake/godot/dev/`) to try things without building real levels or the story.

- One flat test arena from M0 on: floor, a few walls and ramps, a spawn point, good lighting, a free camera toggle.
- A dev menu / console overlay: spawn any character or street person from the extracted tables, pick their style, set stats (level, HP, Pride), give a weapon, teleport, slow motion and frame step, toggle hitbox and hurtbox drawing, show the current action and animation (like the PS2 developer overlay, docs/CUTCONTENT.md), reload assets.
- Viewers that grow with the milestones: model viewer (M1), skeleton and pose viewer (M2), animation browser by anim id (M3), move tester that fires any action of a style (M4).
- Each milestone first lands in the dev scene and is played there; real areas (M6) and the story (M8) only use what already works there. The game stays runnable after every step.

## Milestones

Each one ends with something playable or viewable. Do them roughly in this order; M0 can run in parallel with M1–M3.

| # | Milestone | Done when | Teaches |
|---|---|---|---|
| M0 | Godot basics: capsule brawler | A capsule walks with a third-person camera, punches a dummy (hitbox on for a few frames), hitstop and knockback | Game loop, scene tree, input, physics, state machines |
| M1 | `remake/tools/remake_assets.py` with its first converters: mesh + textures → glTF | Running the tool on a fresh clone puts one street person and one fighter in `assets_ripped/`, and they render textured in Godot | Asset pipelines |
| M2 | Skeleton and weights | Aaron loads rigged and can be posed | Skinning |
| M3 | Animation decoder | Aaron plays his stance, walk and his real Blade Cut | Animation playback, retargeting |
| M4 | Fighter from the tables | Aaron's whole style works: command list → actions → clips with blend 8 → back to stance; damage from hit records and the MECHANICS formula | Move trees, input buffering, cancels |
| M5 | Enemies | Street fighters with simple AI, taking turns to attack | AI state machines |
| M6 | Stage | One real area (e.g. the abandoned subway station) with collision | Level loading |
| M7 | Fight → negotiate → recruit, party | The Beat Down loop works in one area | Game state, UI |
| M8 | Story | Mission scripts run (port the event VM or convert scripts) | Scripting systems |

## First session checklist

1. Read `CLAUDE.md`, `README.md`, docs/ANIMATION.md and docs/MECHANICS.md.
2. Ask V: GDScript or C#? How hands-on for gameplay code? Where should the Godot project live? Is the Godot editor installed (current stable 4.x; put it in `__external_tools/` if you install it)?
3. Start M0 with V, and/or M1 (mesh format) in this repo.
4. Keep this file up to date as the progress log: what's done, what was learned, open questions.

## Progress log

- 2026-10-15: Plan written.
- 2026-10-15: Moved to `remake/PLAN.md`; `remake/` holds everything remake-specific, `remake/MEMORY.md` is the session memory (V asked for both). First-session questions asked.
- 2026-10-15: **M0 built** (not yet played by V): `remake/godot/` dev arena, fixed-frame fighter state machine, placeholder moves with cancel windows, 10-frame input buffer, sphere-vs-hurtbox hits with hitstop, hitstun, knockback, knockdown and guard, dummy AI modes, debug overlay, pause / step / slow-mo, and a smoke test (`-- --smoke`, passes: jab, jab, straight = 3-hit combo, 50 damage). GDScript, Godot 4.7.2. M1 started in its own session.
- 2026-10-15: **M1 done** (not yet seen by V): models are RenderWare 3.x clumps with plain geometry (docs/FORMATS.md); `tools/rwkit.py` decodes them and assembles street models (CDATA preset + 7, retextured) and fight models (outfit slots: placeholder textures swapped, rigid parts hung on skeleton nodes); `remake/tools/remake_assets.py ISO remake/godot/assets_ripped` checks the MD5s and writes two textured .glb (street preset 89, Aaron preset 78), deterministic; Godot 4.7.2 imports them with no errors and `dev/model_viewer.tscn` renders them (screenshot checked).
- 2026-10-15: **M6 research done** (not tested in the emulator): docs/STAGES.md and `tools/stagekit.py` decode an area (FSTAGE.XAF entry = area id: RpWorld geometry, three collision meshes, doors/exits, props; `g_AreaDefs` lights, music, battle spots). The subway (area 5) dumps as a 25 x 13 m platform with two stairs and doors to Downtown.
- 2026-10-15: **M3 research done** (not tested in-game): animation format decoded (docs/ANIMATION.md, `tools/animkit.py`; Aaron's stance 4, walk 5 and Blade Cut 34 dump cleanly, all 4,927 animations check out) and the frame data found in the action timeline (`codemap.py framedata`: active frames, combo cancel, release). Left for M3: export clips to glTF once M2's skeleton is in.
- 2026-10-15: **M2 and M3 done** (not yet seen by V): models export rigged (22-node skeleton, skin weights, clothes bound by bone tag, rigid parts on their node) and `anims/aaron.glb` holds Aaron's stance, walk and Blade Cut as glTF animations; any clip plays on any rigged model (same bone names). `dev/model_viewer.tscn` plays, pauses and frame-steps them; screenshots show correct poses. Learned: key rotations replace the local rotation, only hips/spine take key translations, the rest keep the skeleton's offsets; Blade Cut has root motion (0.73 m) whose in-game handling is still open (docs/ANIMATION.md).
- 2026-10-15: **M6 stage export done** (not yet walked by V): `tools/ps2tex.py` decodes the PS2-native textures (GS swizzle emulation; all 3,225 FSTAGE textures), `remake/tools/conv_stages.py` exports the subway (area 5) as an unlit glTF with prelit vertex colours and its props, a collision glTF (walls, floor, camera, door panels) and a JSON (lights, battle spots, doors, spawn); `dev/stage_test.tscn` walks the M0 fighter around it with trimesh collision (`--walk` test passes, screenshots checked). Left for M6: door exits, the interactive props (drums), the other areas (`conv_stages.AREAS`).
- 2026-10-15: **M4a done** (not yet played by V): the capsule fighter uses Aaron's real style from the game's tables (`remake/tools/conv_moves.py` -> `assets_ripped/moves/aaron.tres`): whole-sequence commands, frame data in game frames, cancel points and release, hit records with the MECHANICS damage formula; smoke test plays →P P P (280 damage) and `test_moves.py` checks every action against `codemap.py framedata`. Input matching and hit record fields documented (docs/ANIMATION.md, MECHANICS.md).
- 2026-10-15: **Game text done**: `remake_assets.py` `text` writes every text bank and script string in six languages (`assets_ripped/text/*.json`, markup for colours, placeholders and buttons; docs/FORMATS.md, "Text"); `game/text/game_text.gd` (`GameText`) looks them up; `test_text.py` checks them against the MOVE LISTs and known names (PASS).
- 2026-10-15: **M4 done** (not yet played by V): animated Aaron replaces the capsule. Every clip of his style plus stance, walk, guard, the game's hit reactions, knockdown, lying and getup are exported (`conv_anims.py`, clips by anim id); the fighter samples them per game frame with the game's blend frames, plays the reaction Combat_TakeHit would pick, and checks hits with spheres on the attacking bones (g_AttackSpheres). Smoke, walk and framedata tests pass; screenshots checked. Learned: the reaction tables (sets, kinds, directions), guard action 10, walk mode table (docs/ANIMATION.md).
- 2026-10-16: **M6 complete** (not yet played by V): `levels/subway.tscn` and `downtown.tscn` play the ABANDONED SUBWAY STATION and DOWNTOWN STREET with all props, lights, collision, camera collision, battle spots, Chapter 2 items as markers, animated Aaron and dummies at the battle spots (fights start the `Battle_PlaceFighters` way), and the doors between them both ways (fade, unload, load, the game's arrival point and facing). `levels/level_test.gd` passes; screenshots of both areas, a fight and a door arrival checked. Door functions named (symbols.tsv, docs/STAGES.md).
