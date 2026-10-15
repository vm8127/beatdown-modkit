# Beat Down remake (Godot)

A private, never-distributed hobby remake of Beat Down: Fists of Vengeance in Godot 4, built on this repo's research. It loads the original assets from your own disc (`ISO/`) and re-implements the game logic.

| Path | Contents |
|---|---|
| [MEMORY.md](MEMORY.md) | Session memory: where we are, decisions, what's next. **Read first, update before stopping.** |
| [PLAN.md](PLAN.md) | The brief: goal, rules, what research to reuse, milestones, progress log |
| `godot/` | The Godot project (not created yet) |
| `godot/dev/` | Developer scene: test arena and tools to try features without real levels |
| `godot/assets_ripped/` | Assets extracted from the disc; generated, never committed |
| `tools/` | `remake_assets.py` (rebuilds every asset from `ISO/`) and the glTF/Godot writers |

Game formats and mechanics learned for the remake are documented in the main docs (`README.md`, `docs/`), not here.

## Getting started (once the project exists)

```bash
python remake/tools/remake_assets.py ISO remake/godot/assets_ripped
```

Then open `remake/godot/project.godot` in Godot.
