# Modding rules (PS2 cheats and C mods)

Read this, then README.md, before any mod task (pnach cheats, C mods, new characters, PCSX2 tests). Remake sessions don't need it. Shared rules (docs, symbols, commits, output) are in CLAUDE.md.

## Current project: new characters (start here)
V wants brand-new characters in story mode that you meet, fight and recruit, and that appear in the blacklist and VS mode, more than two of them over time. The first is **Eggusz**: bald, black mustache, red leather jacket, jeans, black sneakers; Jason G's fighting style (class row 37) and Wendel's second-encounter stats (template 77: level 12, 3000 HP, Pride 200, attack x1.0, $1000; not a boss). He must be a **normal street person** (no mission, no forced encounter) in the **ABANDONED SUBWAY STATION during Chapter 2 (Fatima's Saints)**, recruited with the usual negotiation RECRUIT. **[PLAN-new-characters.md](PLAN-new-characters.md)** has the spec, every lead (item text ids, preset format, free person slots 51 and 52, how to get past two characters) and the agreed order: (1) Eggusz as a fighter, tested in a VS slot; (2) a script assembler in `tools/scriptkit.py` if step 3 needs scripts; (3) find how street people are spawned per area and chapter, and add him there; (4) recruiting through the normal RECRUIT; (5) dialogue if needed; (6) blacklist and VS roster. Keep that file up to date as the work goes. Earlier work this builds on: docs/SCRIPTS.md (missions, script format, every command), docs/UNLOCKS.md (how hero recruits are triggered; Gina's encounter tested), [MEMORY-MAP.md](MEMORY-MAP.md) (mod areas, 95 MB extended RAM), README.md "Mods in C" (`@hook`, `@bss`, structs) and "Testing in a sandbox PCSX2" (`tools/pcsx2.py`, teleport, flags).

## Making a mod
1. Find what to change using README.md, the docs and the dumps first; only then go to the code.
2. Ship it as a PCSX2 cheat, never a patched ISO: a new `[Name]` section of `patch=1,EE,2XXXXXXX,extended,VALUE` lines in `mods/SLUS-21150_C9F6EF9A.pnach`. Keep the existing sections; PCSX2 reads one file per game.
3. Install by copying that file to `C:\Games\Emu\PCSX2\cheats\SLUS-21150_C9F6EF9A.pnach` (portable PCSX2; back it up before replacing it). The two copies must stay identical.
4. Pick addresses from [MEMORY-MAP.md](MEMORY-MAP.md): prefer changing a table entry; new code goes only in a listed free range. Record what you used there, and run `python tools/codemap.py pnach-map mods/SLUS-21150_C9F6EF9A.pnach` to check for overlaps.
5. If the mod needed a new kind of change, add a command for it to `tools/bdkit.py` (or `codemap.py` for read-only analysis).
6. Add it to README.md's "Mods so far" as untested, and ask the user to test it (in PCSX2: the game's Properties, then Cheats; a renamed section has to be ticked again; restart the game). Record their result there, saying who tested it. Nothing counts as working until it has been tested in-game.
7. Keep the mod's own plan and progress in `docs/mods/` (one file per mod); what you learned about the game itself goes in the game docs in `docs/` (CODEMAP for addresses, MECHANICS for rules, ANIMATION for the animation system), not only the mod itself.

## Common recipes
- Moveset: `python tools/bdkit.py swap-moveset ISO/SLUS_211.50 A B`. Add `--keep-body` when the body sizes differ (the tool warns). See docs/movesets.md for body sizes and compatible swaps.
- Mixed moveset: `python tools/bdkit.py mix-moveset ISO/SLUS_211.50 A B --take grab` keeps A's moves and takes B's grabs. See README.md, "To mix two movesets".
- Model: `python tools/bdkit.py swap-model ISO/SLUS_211.50 A B`. See README.md, "Fighter records: the model switch".
- Several mods write the same row (all the Aaron cheats do), so only one of those may be on at a time; say so in the section name. Only one `mix-moveset` cheat can be on at a time (fixed code space).
- Any change to a fighting style must also make the in-game MOVE LIST show the right moves (the user's rule). Whole-style swaps get that for free; `mix-moveset` hooks the MOVE LIST; anything new must do the same.
- Big data (tables, scripts, text, models) can go in PCSX2's Extended RAM (`0x02000000`-`0x07EFFFFB`, needs the per-game `ExtraMemory` setting; check `ExtRam_Present()`), never code; [MEMORY-MAP.md](MEMORY-MAP.md).
- New code: write it in C (`mods/c/`, `tools/cmod.py`; README.md, "Mods in C"), not hand-assembled MIPS. Small mods go in the C mod cave, anything bigger in the mod area `0x000A0000`-`0x000DFFFF` with globals (`@bss`) in `0x000E0000`-`0x000EFFFF`; claim the range in MEMORY-MAP.md. Prefer `@hook FUNC` (call the original as `orig_FUNC`) to hand-picked call sites. Use the structs and typed symbols instead of raw offsets: add fields to `symbols/structs.tsv` and types to `symbols.tsv`'s fifth column, then rerun `codemap.py symbols`. Check the output with `--asm`.
- Before a moveset swap or mix, check the animations with `python tools/codemap.py anim-check ISO/SLUS_211.50 A 0xSTYLE` (docs/ANIMATION.md).

## Testing in PCSX2
- PCSX2 (portable) is `C:\Games\Emu\PCSX2\pcsx2-qtx64-avx2.exe`.
- Only when the user says the PC is free, one emulator session at a time, with `tools/pcsx2.py` (its sandbox copy never touches their settings, memory cards or save states; keys go only to the sandbox window); `stop` it when done and stop at once if asked. Save states can be read without the emulator (`pcsx2.py show ... --state`, `ram`, `freeram`).
- Ask the user for a save state near what you need to test rather than walking the map. To reach a place quickly, use the sandbox teleport (`pcsx2.py cheats --c tools/debug/teleport.c`, then `pcsx2.py w32 0x000F0000 <area + 1>`), and `pcsx2.py flag` / `w16` to set up conditions; put new test helpers in `tools/debug/` (C, built by `cheats --c`).
- The developer overlay (cheat "developer debug mode (switch 5)": hold L2 + press R2, L2 + click L3 to page) shows the current action (TASK) and animation (MOT).
