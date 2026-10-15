# Beat Down remake (Godot)

A private, never-distributed hobby remake of Beat Down: Fists of Vengeance in Godot 4 (GDScript), built on this repo's research. It loads the original assets from your own disc (`ISO/`) and re-implements the game logic.

| Path | Contents |
|---|---|
| [MEMORY.md](MEMORY.md) | Session memory: where we are, decisions, what's next. **Read first, update before stopping.** |
| [PLAN.md](PLAN.md) | The brief: goal, rules, what research to reuse, milestones, progress log |
| `godot/` | The Godot project (open `godot/project.godot`) |
| `godot/dev/` | Developer arena (the main scene): test level, debug overlay, smoke test; model viewer; stage test |
| `godot/game/` | The game: `fighter/` (fighter scene and state machine, move resources, player and dummy brains), `moves/` (one `.tres` per move, plus the style), `camera/` |
| `godot/assets_ripped/` | Assets extracted from the disc; generated, never committed |
| `tools/` | `remake_assets.py` (rebuilds every asset from `ISO/`; checks the disc MD5s first), its converters (`conv_models.py`: character models) and `gltf_writer.py` |

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

Shows every model in `assets_ripped/models/` (run the asset tool first). Left/Right turn, Up/Down zoom, Space stops the turntable; `-- --shot=<file.png>` saves a screenshot and quits (`--dist=`, `--height=` move the camera).

```bash
__external_tools/godot/Godot_v4.7.2-stable_win64.exe --path remake/godot res://dev/model_viewer.tscn
```

## Stage test

Walk around the ABANDONED SUBWAY STATION (area 5) converted from the disc (`assets_ripped/stages/`, run the asset tool first): the M0 fighter with the third-person camera, the area's own wall and floor collision (trimesh), its two lights on the fighter. `-- --area=N` picks another converted area, `--shot=<file.png> --view=player|overview|stairs` saves a screenshot and quits, `--walk` walks into each wall and a stairwell door and checks the player stays inside (exit code 0 = pass).

```bash
__external_tools/godot/Godot_v4.7.2-stable_win64.exe --path remake/godot res://dev/stage_test.tscn
```

## Smoke test

Runs a scripted jab, jab, straight on Dummy 1 and checks it's a 3-hit combo for 50 damage (exit code 0 = pass). `--headless` skips the window; drop it and add `--shot=<file.png>` for a screenshot.

```bash
__external_tools/godot/Godot_v4.7.2-stable_win64_console.exe --headless --path remake/godot -- --smoke
```

The first run on a fresh clone needs `--import` once (`... --headless --path remake/godot --import`) so Godot registers the script classes.

## How the M0 code works

- **Scenes for what's hand-made, code for what comes from the game data.** `dev/dev_arena.tscn` (level boxes, light, sky, the player, three dummies, camera, overlay), `game/fighter/fighter.tscn` (body, limbs, collision, hurtbox, debug views, HP label) and `game/camera/third_person_camera.tscn` are normal scenes: open them in the editor. Code spawns extra fighters (F5) from `fighter.tscn`; later, stages, characters and moves extracted from the disc will be assembled by code the same way.

- **Fixed frames.** All game logic runs in `_physics_process` at 60 frames per second and counts frames, never seconds, like the PS2 game. `Dev.tick` (autoload `dev/dev.gd`) says whether this frame advances; that's how pause, single-frame step and slow motion work without touching the logic.
- **State machine.** `Fighter` is in exactly one state (idle, move, attack, guard, hitstun, blockstun, knockdown, getup) with a frame counter. Each state has its own tick function.
- **Moves are resources** (`game/moves/*.tres`, class `MoveData`; the style `placeholder_style.tres`, class `MoveSet`): startup, active and recovery frames, damage, hitstop, hitstun, knockback, and a cancel window with the next move per button. Click one in the FileSystem dock to edit it in the Inspector. M4 generates them from the real tables.
- **Input buffer.** `PlayerBrain` keeps presses for 10 frames, so pressing slightly before a combo window still counts.
- **Hits.** On active frames the attacker queries a sphere against hurtbox areas (exact on that frame), hits each target once per move, and both fighters freeze for the hitstop. Hitstun longer than the attacker's recovery makes a true combo; the overlay counts them.
- **Brains.** The fighter asks its brain child for a direction, guard and presses. The player and the dummies use the same `Fighter` code; only the brain differs.
