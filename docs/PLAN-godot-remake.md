# Beat Down remake in Godot: brief for a new session

Read this first, then `CLAUDE.md` and `README.md`. This file starts a new project next to the modding work: a **remake of Beat Down: Fists of Vengeance in Godot 4**, built on everything this repo has already reverse engineered.

## Goal and who it's for

- Daniel is a fintech programmer who wants to **learn how video games work** by building one for fun. It's a private hobby project: **never released, never distributed**.
- The approach is an **engine reimplementation** (like OpenMW or OpenGOAL): a new Godot game that loads the original models, textures and animations from Daniel's own disc (`ISO/`), and re-implements the game logic natively from what we documented. It isn't a matching decompilation and doesn't run the PS2 code.
- "Similar" is the target, not exact. Faithful where the research makes it easy (stats, damage formulas, move lists, negotiation), free to simplify or improve elsewhere.

## How to work with Daniel

- **He wants to code and learn, not just receive a finished game.** For the Godot gameplay code, ask how hands-on he wants to be. By default, explain the game concept (game loop, `delta`, state machines, hitboxes, cancel windows...), scaffold, and review, and let him write the core gameplay pieces. The reverse-engineering and asset-conversion tooling (Python, in this repo) you can do yourself.
- Ask once whether he prefers **GDScript or C#** (he's from fintech, so C# may feel familiar; GDScript has more tutorials).
- He prefers short, direct answers. Keep a task list, explain what each milestone teaches.
- Animation authoring isn't his skill. Use the original Beat Down animations (once decoded), Mixamo, or AI video-to-mocap. Focus on the code that makes moves *feel* good (timing, hitstop, cancels, reactions).

## Rules

- **Never commit game data or anything converted from it**: not in this repo, not in the Godot project's repo. Converted assets (glTF, PNG, animation files) go in a gitignored folder (e.g. `assets_ripped/`) and are regenerated from `ISO/` by a script. Same rules as `CLAUDE.md` for `ISO/`, `decomp/` and the ELF.
- Ripped assets from other games (e.g. Yakuza moves) are okay **only as private, uncommitted placeholders**. Prefer original or freely licensed assets for anything that might be shared.
- The Godot project is its **own folder and git repo**. Suggested: `C:\Users\V\source\_personal\claude\BeatdownGodot`. Confirm with Daniel before creating it. Converters and format docs stay in **this** repo (`tools/`, `docs/`), so all the RE knowledge stays in one place.
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

1. **Mesh format**: XAF chunk type `0x10`, contains Softimage user data like `BONETAG=29`. Street people use a low-poly mesh at CDATA.XAF entry preset + 7; fighters build their look from 22 outfit slots (`g_ItemTable` `+0x10` → DATA.XAF mesh). Probably VIF/GIF packet data: find the loader and renderer in `decomp/` (start from `Pack_Load` `0x0029E500`).
2. **Skeleton and skin weights** (body sizes S/M/L have different skeletons).
3. **Animation format** (STAGE.XAF packs, loaded per group by `Xaf_LoadAnimPack` `0x0029ED70`).
4. **Stage geometry and collision.**
5. Frame data: cancel windows and active frames (see above).

## Milestones

Each one ends with something playable or viewable. Do them roughly in this order; M0 can run in parallel with M1–M3.

| # | Milestone | Done when | Teaches |
|---|---|---|---|
| M0 | Godot basics: capsule brawler | A capsule walks with a third-person camera, punches a dummy (hitbox on for a few frames), hitstop and knockback | Game loop, scene tree, input, physics, state machines |
| M1 | Mesh + textures → glTF (converter in this repo) | One street person and one fighter render textured in Godot | Asset pipelines |
| M2 | Skeleton and weights | Aaron loads rigged and can be posed | Skinning |
| M3 | Animation decoder | Aaron plays his stance, walk and his real Blade Cut | Animation playback, retargeting |
| M4 | Fighter from the tables | Aaron's whole style works: command list → actions → clips with blend 8 → back to stance; damage from hit records and the MECHANICS formula | Move trees, input buffering, cancels |
| M5 | Enemies | Street fighters with simple AI, taking turns to attack | AI state machines |
| M6 | Stage | One real area (e.g. the abandoned subway station) with collision | Level loading |
| M7 | Fight → negotiate → recruit, party | The Beat Down loop works in one area | Game state, UI |
| M8 | Story | Mission scripts run (port the event VM or convert scripts) | Scripting systems |

## First session checklist

1. Read `CLAUDE.md`, `README.md`, docs/ANIMATION.md and docs/MECHANICS.md.
2. Ask Daniel: GDScript or C#? How hands-on for gameplay code? Where should the Godot project live? Is the Godot editor installed (current stable 4.x; put it in `__external_tools/` if you install it)?
3. Start M0 with him, and/or M1 (mesh format) in this repo.
4. Keep this file up to date as the progress log: what's done, what was learned, open questions.

## Progress log

- 2026-10-15: Plan written. Nothing started.
