# Story roster: recasting the playable heroes

`tools/bdkit.py roster` turns one small file, `mods/roster.json`, into one PCSX2 cheat section that changes who you play in story mode. It replaces one-off cheats like "Aaron uses Ignacy's moveset and Chester's model": you list what each hero should look like and fight like, and the tool works out every address.

```
python tools/bdkit.py roster ISO/SLUS_211.50 mods/roster.json
```

## The idea: keep the hero's identity, change what you see and play

Story mode has five hero slots. The hero select table `0x004334B0` holds their fighter IDs: Raven 107, Jason G 53, Aaron 68, Lola 22, Gina 108. A lot of the game asks "which hero is this?" (`Person_GetHeroDefId` `0x002F9930`): cutscenes, dialogue, the starting inventory, story flags and the HP bar name. It answers from the hero's outfit preset number. So a slot can't simply point at another fighter: the story would stop recognising it, which is what happened to the HP bar name in the first Chester model swap.

The roster keeps each slot's fighter ID, preset number and class row, so all story code still sees "Aaron". It changes only the parts the player experiences:

| Part | Field | How the roster changes it |
|---|---|---|
| Model and outfit | outfit preset (fighter record `+0`) | Fighter init (`0x0013B490`) is pointed at a lookup table, so it builds the hero from another fighter's preset. The hero's own preset number is untouched. |
| Moves | class row (style and animation groups) | The hero's class row gets the other fighter's style and groups, the same as `swap-moveset`. When the body sizes differ, `keep_body` keeps the hero's own body animations. |
| Starting stats | hero template HP (`+0xC`) and attack rank (`+0x11`) | Copied from another fighter. Takes effect on a new game only, because the player's record is saved. |
| HP bar name | `jal Fighter_DisplayName` at `0x0031B3E4` in `HpBar_Build` | That one call goes through a second table hook, so the hero's line on the HP bar shows the chosen fighter's name. `Person_GetHeroDefId` and the other 47 uses of the name function are untouched. |

## The roster file

```json
{
  "name": "Story roster: Aaron is Chester with Ignacy's moves",
  "author": "Claude for V",
  "heroes": {
    "AARON": {"model": "CHESTER", "moves": "IGNACY"},
    "LOLA":  {"model": "FATIMA", "moves": "GREGOLIO", "name": "keep", "stats": "GREGOLIO"}
  }
}
```

- Hero keys: `AARON`, `RAVEN`, `JASON_G`, `LOLA`, `GINA`.
- `model`, `moves` and `stats` take a class name from `python tools/bdkit.py chars` (the fighter's most common record is used), or `fighter:ID` for one exact record from `python tools/bdkit.py fighters` (useful when a character has several looks).
- `name` defaults to the `model` fighter's name, so the HP bar follows the look. Use `"keep"` to keep the hero's own name, or give another fighter.
- `keep_body` defaults to true when the two body sizes differ. Set it yourself to override.
- Leave a field out to keep the hero's own.

The output is one `[name]` section. Paste it into `mods/SLUS-21150_C9F6EF9A.pnach` and the PCSX2 cheats copy. Turn off any other cheat that writes the same heroes (all the older Aaron cheats), and restart the game after switching.

## How the model hook works

Both lookups in fighter init (`jal 0x002A8720` at `0x0013B54C` for the outfit parts and `0x0013B55C` for the body parameters) are redirected to 15 instructions at `0x00216538`. These walk a table of `{s16 from_preset, s16 to_preset}` pairs ending in -1, swap the preset if it matches, then jump to the real `Preset_Get`. Every hero in the roster adds a row for each of its presets (Aaron has three: 78, 79 and 153), so the code never changes, only the table.

## How the name hook works

The HP bar (`HpBar_Build` `0x0031B210`) draws one line per team member, and gets each line from `Fighter_DisplayName` at `0x0031B3E4`. That call is pointed at 23 instructions at `0x00216638`. They read the person's preset (`Person_Get`, `+0x44`), look it up in a `{s16 preset, s16 text id}` table at `0x002166B8`, and return that text, or fall through to the normal name. A fighter's name is text 11001 + its fighter ID, so Chester (fighter 20) is 11021. The hook matches by preset, so the hero shows the new name wherever the new model shows, including when that hero appears as a story enemy.

In story mode the line under the hero's name is a recruited party member ("McQueen" is one), not a surname, so it stays as it is.

## The code space

`0x00216538` is a 10,936-byte library function (DMA/GS upload code) that nothing in the program calls, jumps to or points at, so its space is free for hooks. The older `swap-model` hook at `0x003E0130` uses the same two call sites, so don't turn on both at once.

## Status

- The model and moves parts write what the tested "Aaron uses Ignacy's moveset and Chester's model" cheat does, but through the table hook in the new code space.
- The HP bar name was traced live in PCSX2 (2026-10-13). An equivalent fixed-value hook written into memory during a VS fight made the player's bar read "Chester / Lola / Gina" and left the CPU side unchanged.
- The roster section as a whole, loaded from the pnach at boot, is **untested** in-game.

## Beyond the five slots

Adding a sixth story hero, rather than recasting one of the five, needs more than tables: the hero select screen's list and graphics, `Person_GetHeroDefId` and the roughly nine functions that switch on hero presets, the per-hero starting inventories (`Inventory_InitForHero` `0x0013D000`), and per-hero cutscene and dialogue choices. Recasting covers "play this character in story mode" without touching any of that, so it's the base to build on. A real extra slot would be a separate project.
