# Beat Down remake (Godot)

A private, never-distributed hobby remake of Beat Down: Fists of Vengeance in Godot 4 (GDScript), built on this repo's research. It loads the original assets from your own disc (`ISO/`) and re-implements the game logic.

| Path | Contents |
|---|---|
| [MEMORY.md](MEMORY.md) | Session memory: where we are, decisions, what's next. **Read first, update before stopping.** |
| [TODO.md](TODO.md) | Queued work: what to start when a running task finishes |
| [PLAN.md](PLAN.md) | The brief: goal, rules, what research to reuse, milestones, progress log |
| `godot/` | The Godot project (open `godot/project.godot`) |
| `godot/dev/` | Developer arena (the main scene): test level, debug overlay, smoke test; model viewer; stage test |
| `godot/game/` | The game: `fighter/` (fighter scene and state machine, move resources, player and dummy brains), `moves/` (one `.tres` per move, plus the style), `camera/`, `text/` (`GameText`: the game's text by id, from `assets_ripped/text/`) |
| `godot/assets_ripped/` | Assets extracted from the disc; generated, never committed |
| `tools/` | `remake_assets.py` (rebuilds every asset from `ISO/`; checks the disc MD5s first), its converters (`conv_models.py`: character models, `conv_moves.py`: fighting styles, `conv_text.py`: text banks and dialogue as JSON) and `gltf_writer.py`; `test_moves.py` checks the generated moves, `test_text.py` the text (`python remake/tools/test_text.py ISO remake/godot/assets_ripped`) |

Game formats and mechanics learned for the remake are documented in the main docs (`README.md`, `docs/`), not here.

## Running

Godot 4.7.2 lives in `__external_tools/godot/` (README.md, "External tools").

```bash
python remake/tools/remake_assets.py ISO remake/godot/assets_ripped
```

Then open `remake/godot/project.godot` in the editor and press F5, or run it directly:

```bash
__external_tools/godot/Godot_v4.7.2-stable_win64.exe --path remake/godot
```

Controls and dev keys are listed on screen (Tab hides them). The F-keys: F1 hitboxes, F2 slow motion, F3 pause, F4 step one frame, F5 spawn a dummy, F6 dummy mode (stand, guard, counter-jab, fight), F7 reset.

## Model viewer

Shows every model in `assets_ripped/models/` (run the asset tool first) and plays the clips of `assets_ripped/anims/` on them (clips are named by anim id: `a34` = Blade Cut; Tab / P / Comma / Period browse, play, step; `--clip=a34 --frame=22`). Left/Right turn, Up/Down zoom, Space stops the turntable; `-- --shot=<file.png>` saves a screenshot and quits (`--dist=`, `--height=` move the camera).

```bash
__external_tools/godot/Godot_v4.7.2-stable_win64.exe --path remake/godot res://dev/model_viewer.tscn
```

## Stage test

Walk around the ABANDONED SUBWAY STATION (area 5) converted from the disc (`assets_ripped/stages/`, run the asset tool first): the M0 fighter with the third-person camera, the area's own wall and floor collision (trimesh), its two lights on the fighter. `-- --area=N` picks another converted area, `--shot=<file.png> --view=player|overview|stairs` saves a screenshot and quits, `--walk` walks into each wall and a stairwell door and checks the player stays inside (exit code 0 = pass).

```bash
__external_tools/godot/Godot_v4.7.2-stable_win64.exe --path remake/godot res://dev/stage_test.tscn
```

## Smoke test

Runs a scripted combo on Dummy 1 (exit code 0 = pass). With the assets extracted it's Aaron's Triple Snake Fang, →P P P (actions 1807, 1808, 1809): each chain must start on the previous move's cancel frame, all 3 hits must combo, and the damage must match the MECHANICS formula (60 + 70 + 150 = 280). Without them, the placeholder jab, jab, straight for 50 damage. `--headless` skips the window; drop it and add `--shot=<file.png>` for a screenshot. `--press=P` instead plays one move on Dummy 1 (passes if it hits; prints the hit spheres; with `--shot=` a side view on the hit), `--shot-down=<file.png>` saves Dummy 1 knocked down after the combo.

```bash
__external_tools/godot/Godot_v4.7.2-stable_win64_console.exe --headless --path remake/godot -- --smoke
```

The first run on a fresh clone needs `--import` once (`... --headless --path remake/godot --import`) so Godot registers the script classes.

## How the M0 code works

- **Scenes for what's hand-made, code for what comes from the game data.** `dev/dev_arena.tscn` (level boxes, light, sky, the player, three dummies, camera, overlay), `game/fighter/fighter.tscn` (body, limbs, collision, hurtbox, debug views, HP label) and `game/camera/third_person_camera.tscn` are normal scenes: open them in the editor. Code spawns extra fighters (F5) from `fighter.tscn`; later, stages, characters and moves extracted from the disc will be assembled by code the same way.

- **Fixed frames.** All game logic runs in `_physics_process` at 60 frames per second and counts frames, never seconds, like the PS2 game. `Dev.tick` (autoload `dev/dev.gd`) says whether this frame advances; that's how pause, single-frame step and slow motion work without touching the logic.
- **State machine.** `Fighter` is in exactly one state (idle, move, attack, guard, hitstun, blockstun, knockdown, getup) with a frame counter. Each state has its own tick function.
- **Moves are resources** (`game/moves/*.tres`, class `MoveData`; the style `placeholder_style.tres`, class `MoveSet`): startup, active and recovery frames, damage, hitstop, hitstun, knockback, and a cancel window with the next move per button. Click one in the FileSystem dock to edit it in the Inspector. M4 generates them from the real tables.
- **Real moves (M4a).** `remake/tools/conv_moves.py` (run by `remake_assets.py`, or alone: `python remake/tools/conv_moves.py ISO remake/godot/assets_ripped`) writes Aaron's style to `assets_ripped/moves/aaron.tres`: a `MoveSet` whose `commands` are the game's whole input sequences (`["P", "P", "↓P"]` -> Comet Blow), each `MoveData` with its hit windows (`MoveHit`: frames, attack parts, damage, hit level, reaction), cancel point, release frame, root motion and the clip ids for the animated fighter. Every fighter loads it when present (`Fighter.ripped_style`), else the placeholder style. Input codes are relative to the opponent (→ toward, ← away, ↑ / ↓ the stick to your left / right, motions →→, ↓→, →↓→); from neutral one code starts a move, and a press made during a move chains at that move's cancel point if history + press is a whole command, as in the game (docs/ANIMATION.md, "Input matching"). Damage uses the game's formula with placeholder stats. `python remake/tools/test_moves.py ISO remake/godot/assets_ripped` checks the .tres against `codemap.py framedata` in headless Godot.
- **Input buffer.** `PlayerBrain` keeps presses for 10 frames, so a press slightly before the fighter is free still counts.
- **Hits.** On active frames the attacker queries a sphere against hurtbox areas (exact on that frame), hits each target once per move, and both fighters freeze for the hitstop. Hitstun longer than the attacker's recovery makes a true combo; the overlay counts them.
- **Brains.** The fighter asks its brain child for a direction, guard and presses. The player and the dummies use the same `Fighter` code; only the brain differs.
- **Animated fighter (M4).** With the assets extracted, `Fighter` shows a rigged model (`model_name`, default Aaron's `fighter_aaron_078`; the dev arena's dummies use `street_089`) posed by `FighterModel` (`game/fighter/fighter_model.gd`) from `assets_ripped/anims/aaron.glb` + `.json` (`remake/tools/conv_anims.py`). Each game frame `_animate()` picks the clip for the state (stance, walk, guard, the move's clips at its speeds, the hit reaction the game would play, knockdown, lying, getup) and the model blends into it like the game (freeze the pose, blend over the clip's blend frames). The model only follows the state, so pause, frame step and slow motion work. Hit spheres sit on the attacking bones (`hit_spheres`), and F1 draws them. Without the assets the capsule and its fixed sphere stay. The stage test's `--view=aaron` takes a close screenshot.
