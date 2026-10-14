# Memory used by our cheats

Which addresses every cheat in `mods/SLUS-21150_C9F6EF9A.pnach` writes, which free code space ("caves") is taken and what's left, and which cheats can't be on together. Read this before a new mod picks an address, and update it in the same commit.

Regenerate the per-cheat list with:

```
python tools/codemap.py pnach-map mods/SLUS-21150_C9F6EF9A.pnach
```

It prints every section's address ranges and every pair of sections that write the same bytes.

## Code caves

The game has no free memory set aside, so new code goes in places nothing runs or reads.

| Cave | Size | Why it's free | Used by | Free |
|---|---|---|---|---|
| `0x003E0130`-`0x003E017F` | 20 words | zero padding between the last code and the VU microcode | `0x003E0130`-`0x003E0167` model hook (`swap-model`, and the cheat "Aaron uses Ignacy's moveset and Chester's model"); `0x003E0168`-`0x003E017F` negotiation on knockout (KO hook) | none |
| `0x00216538`-`0x00218FEF` | 10,936 bytes | a DMA/GS library function nothing calls or points to (checked over the whole ELF) | see the next table | `0x00216838`-`0x00216FFF` (1,992 bytes, for C mods) and `0x00218F44`-`0x00218FEF` (172 bytes) |

Inside `0x00216538` (constants `ROSTER_CAVE` and `MIX_*` in `tools/bdkit.py`):

| Range | Used by | Layout |
|---|---|---|
| `0x00216538`-`0x00216737` | **roster** (`bdkit.py roster`), reserved | `+0x00` model hook code, `+0x40` preset remap table, `+0x100` name hook code, `+0x180` name table. The current roster writes up to `0x002166C7`. |
| `0x00216738`-`0x00216FFF` | **C mods** (`tools/cmod.py`): each C file claims a range with `@org` and `@max` | `0x00216738`-`0x00216837` "Aaron uses Ignacy's moveset and Chester's model (C version)" (`mods/c/aaron_chester_model.c`, 48 bytes used of 0x100). Free: `0x00216838`-`0x00216FFF` |
| `0x00217000`-`0x002175FF` | **mix-moveset**: the mixed command list (up to 191 commands) | `MIX_LIST` |
| `0x00217600`-`0x002179FF` | mix-moveset: renumbered condition records, 16 bytes each | `MIX_CONDS` |
| `0x00217A00`-`0x00217BFF` | mix-moveset: MOVE LIST hook code | `MIX_HOOKS` |
| `0x00217C00`-`0x00218EFF` | mix-moveset: move list override table and its lines | `MIX_MOVELIST`, `MIX_LINES` |
| `0x00218F00`-`0x00218F43` | **negotiation on knockout** (CANCEL hook, v2) | |
| `0x00218F44`-`0x00218FEF` | **free** | |

Because mix-moveset always writes the same addresses and its move list table has one style row, **only one mixed-moveset cheat can be on at a time**, whichever style it changes. A second simultaneous mix would need its own area (the free `0x00216738` block) and a move list table with two rows, taken out of the C mod area.

## Every cheat's writes

| Cheat (pnach section) | Writes | Kind |
|---|---|---|
| Aaron uses Raven's moveset | `0x0050D8B4`, `0x0050D8BC` | Aaron's class row: style, group list pointer |
| Aaron uses Jason G's moveset | `0x0050D8B4`, `0x0050D8BC`; `0x0050D13C`-`0x0050D14B` | class row; Aaron's group list at `0x0050D100` (swaps group 184 for 183, adds 209 in the padding) |
| Aaron uses Ignacy's moveset and Chester's model | `0x0050D8B4`, `0x0050D8BC`; `0x0013B54C`, `0x0013B55C`; `0x003E0130`-`0x003E0167` | class row; both `jal Preset_Get` in fighter init; model hook code |
| Story roster: Aaron is Chester with Ignacy's moves | `0x0050D8B4`, `0x0050D8BC`; `0x0013B54C`, `0x0013B55C`; `0x0031B3E4`; `0x00216538`-`0x002166C7` | class row; fighter init hooks; HP bar name call in `HpBar_Build`; roster cave |
| Aaron uses the cut TESTER moveset | `0x0050D8B4`, `0x0050D8BC` | class row |
| Aaron keeps his moves but grapples like Jason G | `0x0050D8B4`, `0x0050D8BC`; `0x0050D100`-`0x0050D14F`; `0x00515C5C`; `0x001C5BA0`, `0x001C5BF0`, `0x001C5C30`, `0x001C5C70` (8 bytes each); `0x00217000`-`0x00218EFF` (parts) | class row; Aaron's whole group list; `g_StyleCommands[0x13]`; the four MOVE LIST functions' first two instructions; mix area |
| Aaron uses Ignacy's moveset and Chester's model (C version) | `0x0050D8B4`, `0x0050D8BC`; `0x0013B54C`, `0x0013B55C`; `0x00216738`-`0x00216767` | class row; both `jal Preset_Get` in fighter init, now `jal Mod_PresetGet`; the C code |
| Negotiation menu on knockout (test v2) | `0x002DE478`-`0x002DE48B`; `0x002DEF70`-`0x002DEF77`; `0x003E0168`-`0x003E017F`; `0x00218F00`-`0x00218F43`; `0x005990FC` | after-KO talk hook; CANCEL hook; two caves; negotiation menu descriptor (Triangle → CANCEL) |
| Cut content: DEBUG on the title screen | `0x0058969C`, `0x005897D0` | title menu item action and label |
| Cut content: all six languages in the debug LANGUAGE menu | `0x003B75D0`, `0x003B75F0` | two clamp instructions |
| Cut content: developer debug mode (switch 5) | `0x00599014` | `g_DebugSwitches[5]` |
| Cut content: DIFFICULTY in the pause menu options | `0x00509DA8` | option record byte `+27` (written as a word) |
| Cut content: boxers use the short boxer style 0x1C | `0x0050D6A4`, `0x0050D6B4`, `0x0050D6C4` | BOXER S/M/L class rows' style |

All 426 writes are 32-bit (`patch=1,EE,2...`) and `patch=1`, so PCSX2 rewrites them every frame while the cheat is on, and the values stay in memory after the cheat is turned off until the game restarts.

## Which cheats can be on together

From `pnach-map`'s overlap list:

- **The seven Aaron cheats** (Raven, Jason G, Ignacy + Chester and its C version, roster, TESTER, Jason G grabs) all write Aaron's class row, so only one may be on. The roster and both Ignacy + Chester cheats also share the fighter init hooks.
- Everything else writes separate addresses, so the negotiation cheat, the five cut content cheats and any one Aaron cheat can be on together.
- The roster cheat writes every hero it recasts; once it recasts other heroes, it also conflicts with any cheat for those heroes.

## Other patches

PCSX2's bundled **Widescreen 16:9** patch (Game Properties, Patches) writes `0x00375388`, `0x00375394` and `0x0037539C` plus `gsaspectratio=16:9`. None of our cheats are near those addresses (checked 2026-10-13), so it can be used with all of them. Not yet tried together in-game.

## Picking an address for a new mod

1. Prefer changing data (a table entry) over code. The data tables we change are listed above; `docs/CODEMAP.md` lists the rest.
2. For new code, use the free ranges above, then record the new range in both tables here and in the README's "Known code addresses".
3. A hook replaces a `jal` (or the first instructions of a function) with a jump into the cave. Put the original instruction back in the cave code, and check with `codemap.py pnach-map` that no other cheat writes the same words.
4. A C mod (`tools/cmod.py`) picks its `@org` range from the C mod area and is recorded in the cave table above.
5. If a new tool command writes fixed addresses (like `mix-moveset`), name the constants in `tools/bdkit.py` and say here that only one cheat made by it can be on.
