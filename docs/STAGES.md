# Stages (areas): files, geometry, collision, doors, spots

How Beat Down stores and loads its areas (the free-roam places and the fight arenas, which are the same thing), found 2026-10-15 for the remake's M6 from the decomp and the disc. `tools/stagekit.py` reads all of it:

```
python tools/stagekit.py areas ISO                      every area id: name, FSTAGE entries, music, sound banks, far clip
python tools/stagekit.py pieces ISO 5                   what area 5 (ABANDONED SUBWAY STATION) is made of
python tools/stagekit.py collision ISO 5 [--json F] [--obj F] [-v]   walls, camera and floor meshes, doors, spots, objects
python tools/stagekit.py world ISO 5 --obj F            the render geometry as OBJ (for a quick look in Blender)
```

JSON and OBJ output is converted game data: write it outside the repo (or to `remake/godot/assets_ripped/`), never commit it.

Confidence: **read** = read from the decomp and checked against the disc data; **seen** = only seen in the data; **guess** = an interpretation. Nothing here was tested in the emulator yet.

## Area ids

The area id is the number `Area_Current` `0x002FD630` returns (area state `+8`) and `Area_ChangeTo` / `EXF_MOVE_STAGE` / `Location_Current` `0x002E7A50` pass to `Area_Load` `0x002FE3D0` (read: `Location_Current` reads `0x006CBB04`, which `Area_ChangeTo` sets through `0x002E7A60`, and the mission manager passes it straight to `Area_Load`). It indexes `g_AreaDefs` `0x005170F0` and, before variants, FSTAGE.XAF.

**Correction (read, 2026-10-15):** the name of an area is `AreaDef.name_text`, not text 18000 + id. Area 5 is the ABANDONED SUBWAY STATION (text 18002), which matches the sandbox observation that `Area_Current()` returns 5 there (docs/CODEMAP.md). The "Location ids" table in docs/UNLOCKS.md numbers places by their text id (18000 + n), which is a different numbering; where code compares an area id, read it with the table below. For example the teleport test "`w32 0x000F0000 18` = PLATFORM" sends the player to area 17, which by this table is STORAGE BASEMENT (PLATFORM is area 46): worth re-checking in the sandbox.

| Id | Area | Id | Area | Id | Area |
|---|---|---|---|---|---|
| 1, 2, 3 | DOWNTOWN STREET (three variants) | 20 | SHOPPING DISTRICT | 39 | NORTH FACTORY ZONE |
| 4 | SOUTHSIDE PARK | 21 | SCREAMIN' TUNES RECORDS | 40 | REFINERY |
| 5 | ABANDONED SUBWAY STATION | 22 | KILLER GEAR | 41 | CHIEF'S OFFICE |
| 6 | LAS SOMBRAS CANTINA | 23 | DICK'S BARBERSHOP | 42 | RAILYARD |
| 7, 11 | GAS STATION | 25 | THE HOLE | 43 | SECURITY ROOM |
| 8 | SLAUGHTERHOUSE | 26 | BASKETBALL COURT | 44 | CONSTRUCTION SITE |
| 9 | RAG SHACK | 29 | TOWN SQUARE DISTRICT | 45 | NARCOTICS FACTORY |
| 10 | CLINIC | 30 | HOTEL ZONE | 46 | PLATFORM |
| 12 | WHARF | 31 | HOTEL BAR | 47 | POLICE STATION |
| 13 | HARBOR GATE | 32 | HOTEL LOUNGE | 48 | UNDERGROUND PARKING GARAGE |
| 14 | WAREHOUSE No.13 | 33 | HOTEL ROOM | 49 | POLICE STATION LOBBY |
| 15 | WAREHOUSE No.10 | 34 | HOTEL LOBBY | 50 | EMPLOYEE PASSAGE |
| 16 | WAREHOUSE No.12 | 35 | HOSPITAL | 51 | CELL |
| 17 | STORAGE BASEMENT | 37 | HOSPITAL ZONE | 52 | STORAGE ROOM |
| 18 | TRAIN STATION AREA | 38 | SOUTH FACTORY ZONE | 53 | CHIEF'S OFFICE |
| 19 | STATION ZONE | | | 54 | RUMORS |

Ids 0, 24, 27, 28, 36, 55 and 56 have no definition (0 and 57+ are turned into 4 by `Area_Load`). VS mode's stage list `g_VsStages` `0x00589A30` is area ids too: 1, 4, 6, 7, 12, 13, 14 (read).

## Which files make an area (read)

`Area_Load(area, flags)` is a step machine (state `0x005FE160`):

0. `Stage_LoadCommon` `0x002FFA50`: once, FSTAGE.XAF entry 56 (a texture dictionary of 37 shared textures) into `0x0071D830`.
1. Unloads the old area (`0x002FEAD0`), then picks the **FSTAGE.XAF entry**: the area id, except for random variants (never the same twice in a row): area 1 → 1, 2 or 3 (or 24 when bit 1 of `0x0060C960` is set and `0x003B6260` agrees); 7 → 7 or 11; 19 → 19, 18 or 27; 47 → 47, 28 or 36. The variants are different builds of the same place (area 1's three entries share most textures; 24 has 33 sectors instead of 31). The area state gets `+8` area, `+0xC` entry, `+0x10` previous area. `Xaf_ReadEntry` `0x001594E0(5, entry, ...)` reads the whole entry (archive 5 = FSTAGE).
3. `Area_LoadStage` `0x002FE010` runs `Stage_Parse` `0x00168100` on the pack (one section per frame) into a 0x39C0-byte stage struct in a staging copy at `0x00713B20`, then copies 0x9C10 bytes to the area state (pointer `0x005FFDE0`) and makes the stage current (`Stage_SetCurrent` `0x001679D0`; the stage is at area state `+0x6230`, its collision at `+0x6270`, returned by `Area_Collision` `0x002FD5F0`).
4. Copies `g_AreaDefs[area]` to area state `+0x1C`, sets the three lights from it (`0x002C2AA0` rotation, `0x002C2B60` colour), runs `Area_BuildPeople` (docs/CODEMAP.md, "Area people"), sets the camera far clip (2500 for area 47; 1800 for 1, 19, 39, 46; 350 for 8; else 1500; near 1.0).
5-12. Story bits, the two SOUND.XAF banks (`AreaDef +4`, `+6` through the table `0x004337D0`), and `0x001D35F0(AreaDef +0xE)`.

So one area = **one FSTAGE.XAF entry + its `g_AreaDefs` row + its `g_AreaObjects` row + its `g_AreaDoorFlags` row** (plus the people placement, docs/CODEMAP.md). Nothing else on the disc is per area, as far as read.

### The FSTAGE.XAF area pack (read)

Entries 1-54: `u32 count` (9 or 10), then `count x {u32 offset, u32 size}` from the entry start. Each section is a RenderWare stream (docs/FORMATS.md) except 7 and 8. `Stage_Parse` handles them by position:

| # | Contents | Loaded into (stage struct) | Subway (entry 5) |
|---|---|---|---|
| 0 | **Textures**: RwTexDictionary (0x16) of PS2-native textures (0x15) | `+0x1C` | 36 textures (ER03_*, SB01DRUM...) |
| 1 | **Render geometry**: RpWorld (0x0B), see below | `+0x18` (`RpWorldStreamRead` `0x0022FFD0`) | 1505 triangles, 2559 vertices, 2 sectors, 21 materials |
| 2 | **Wall collision**: clump (0x10), one atomic | `+0x44`, atomic `+0x50` | 30 triangles, 2 materials |
| 3 | **Camera collision**: clump | `+0x48`, `+0x54` | 36 triangles |
| 4 | **Floor collision**: clump | `+0x4C`, `+0x58` | 10 triangles |
| 5 | **Doors**: clump, two atomics per door | `+0xB0` (`Doors_Load` `0x00351230`) | 2 doors |
| 6 | **Door animation**: RtAnimAnimation (0x1B) for section 5's HAnim hierarchy | with 5 | 14 keys, 1.63 s |
| 7 | **Props**: `u32 count, count x {u32 offset, u32 size}`, each a clump | `+0x450` (`Stage_LoadProps` `0x0015B5A0`, 0x48-byte slots) | 15 props |
| 8 | **Prop placements** "PB": `char "PB", s16 count`, then `count x {s32 prop (1-based), f32 x, y, z, f32 quaternion x, y, z, w}` | `Stage_PlacePB` `0x0015C680` | 18 placements (prop 9 eight times along the end walls) |
| 9 | (10-section entries) up to 16 animations (0x1B) for props | `+0xB28` | none |

The three collision clumps are plain RenderWare clumps with untextured, coloured materials (the colours only tell the materials apart). Their vertices are already in area space (frames at the origin). After loading, each one's flags are set to 0x71 and its bounding box is kept (`0x001CD7A0`, at collision `+0x4C`...).

### Render geometry: RpWorld (read, checked on entries 1-54)

Standard RenderWare 3.7 world, `rwkit` doesn't read it, `stagekit.read_world` does:

- Struct (0x40 bytes): `s32 root is a sector, f32 inverse origin[3], s32 triangles, s32 vertices, s32 plane sectors, s32 atomic sectors, s32 collision sector size (0), u32 format, f32 bbox max[3], f32 bbox min[3]`. Format is `0x4001007D` everywhere: tristrip, textured, prelit, normals, light, modulate, one UV set.
- MaterialList (0x08) of textured materials (texture names match section 0's dictionary).
- A BSP tree: PlaneSector (0x0A: struct `{s32 axis 0/4/8, f32 value, s32 left is atomic, s32 right is atomic, f32 left value, f32 right value}`, then the left and right children) and AtomicSector (0x09: struct `{s32 material base, s32 triangles, s32 vertices, f32 min[3], f32 max[3], s32 0, s32 0}`, then `f32 position[3]` per vertex, `s8 normal[3] + pad` per vertex, `u8 prelit RGBA` per vertex, `f32 uv[2]` per vertex, then triangles `{u16 v0, v1, v2, material}` with material relative to the base; then an Extension with BinMesh (0x50E, the triangle strips) and a collision plugin 0x11D, a per-sector collision tree the game's own collision doesn't use as far as read).
- Lighting is baked into the prelit vertex colours (seen); the area's three lights (below) light the fighters and props.

## Collision (read)

Each area has three separate low-poly meshes (sections 2-4), queried through `Collision_Query` `0x00160190(collision, mesh, query, result, flags)`:

| Mesh | Query | Who uses it |
|---|---|---|
| 0 walls | `Collision_SphereWalls` `0x00160790(radius, collision, pos, result, flags)`: a sphere at the position, pushed out of the wall triangles (and door panels with flag 4); result `+4` pushed-out position, `+0x10` normal | fighters (radius 5.5 in `0x00314FD0`, which starts the wall-slam action 0x2ED; 11, 15 and 40 in other fighter code), `Combat_TakeHit`, props physics `0x00161730` (radius 1) |
| 1 camera | `Collision_Segment` `0x00160960(collision, from, to, result, flags)`: a segment | the camera, `0x00376AF0` and `0x0037A400` (from/to at `0x0076B4A8` / `0x0076B4B8`) |
| 2 floor | `Collision_FloorHeight` `0x00160610(collision, pos, result)`: a vertical ray between the floor mesh's bounding-box min and max y at pos x, z; `Collision_FloorList` `0x0015E430` returns every floor under a point and `FloorList_Pick` `0x00160B40(y, 5.0, list)` takes the highest one at most 5 units above y (so stairs and two-level floors work) | item placement, props, fighters (`0x00347550`, `0x0037AA80`...) |

There is **no separate "area bounds" box**: the walls mesh closes every area (seen on the subway: the walls are a closed outline of the platform with the stairs; guess for other areas), so a fighter is kept inside by the sphere-vs-walls push-out. While debug switch 5 is on and the buttons word `0x00685454` has bits 0x400 and 0x1000 and one of 0x4100 (L1 + R1 + Square, going by `Pad_RemapButtons`; guess), `Collision_SphereWalls` returns no hit: a cut no-clip cheat (read).

**Wall kinds**: when the wall sphere hits a wall triangle, its material index picks `AreaDef +0xE8[material] & 0x1F` (`Area_MaterialKind` `0x0031D040(area, material, 1)`), stored in fighter `+0x34A`. The subway's walls have two materials with kinds 8 and 19; the second one is on the two short end walls of the platform (x = -107 and x = 155). What the kinds do (sounds? which wall moves are allowed?) is open. `AreaDef +0xC4[material]` is the same for the floor materials (`which` 0), but no caller with 0 was found.

### The subway's collision (stagekit, seen)

One unit is about 10 cm (a street person is 17.6 units tall). y is up. The platform is about 255 x 130 units (25 x 13 m): floor at y 0 from x -197..241, z -8..161; walls 30.6 high along z 3 (back, with two stairwell openings) and z 128 (front), end walls at x -107 and 155; two stairwells at x -106..-73 and x 97..130 going up to y 16 at z -31, each with a door at its top back to DOWNTOWN STREET. Battle spots at (-72.7, 0, 50.2), (95.4, 0, 50.2), (-59.6, 0, 45.6), (36.2, 0, 54.6). The render world is bigger (x -232..224, z -70..228): the tracks and the far side are outside the walls.

## Doors and exits (read)

Exits are **doors** (section 5). The clump's HAnim hierarchy has one top frame per door, under the root; its Softimage `BONETAG` is the destination: a positive tag is an area id, a negative tag is `-(area x 10 + entrance)` (so -17 = area 1, entrance 7). The atomic on the top frame is the door's **zone**, a flat quad on the floor in front of the door; the atomic on its child frame (same tag) is the **panel**, the door leaf that section 6's animation swings open. `Doors_CollectAtomic` `0x003510B0` stores the tag (`+0x54` area, `+0x58` entrance, raw tag `+0x56`), up to 9 doors (collision `+0x70` count, `+0x80` 0x60-byte records).

The collision query with flag 4 first casts a short vertical ray (y + 20 to y - 15) at the zone, and only when the point is over the zone it tests the panel (so you collide with a closed door only next to it); flag 8 skips doors whose destination area has `Area_DefFlag100` != 1.

Cross-checked in both directions (seen): the subway's doors are -17 and -16 (DOWNTOWN STREET entrances 7 and 6), and DOWNTOWN STREET's doors include -51 and -52 (subway entrances 1 and 2), plus 47 POLICE STATION, 25 THE HOLE, 7 GAS STATION, 19 STATION ZONE, 9 RAG SHACK (14 atomics = 7 doors). The street ends are wide "doors" (150 units).

**Door state**: `g_AreaDoorFlags` `0x0058BDB4` (0x14 bytes per area): `{u8 *allowed (count, destination ids), s16 first story flag, s16 count, s16 *raw tags}`. `Door_State` `0x003515A0(door)` finds the door's raw tag in the list: if story flag `first + index` is set it returns 0; otherwise 0 when the destination is in the allowed list, else 1. Subway: flags 808-809 for tags -17, -16; downtown: flags 800-806, allowed 19, 47, 7 (the street ends). Whether 1 means locked or usable, and where the entrance number picks the arrival point in the destination, is open (guess: the destination's door with the matching tag).

**Arrival points** for `Area_ChangeTo` `0x002D9890(from, to)`: a fixed point per destination in `g_AreaSpawnPoints` `0x00509700` (`{f32 x, y, z, 0}` and an angle in the code): default (-15.8, 10.5, 11.7) angle 96.1; areas 0x2F, 0x19, 0x2A, 0xC, 0x15, 0xF, 7, 0x1D and two each for 1 and 0x1A (by mission) have their own (read). Door arrivals are probably separate (open).

## Battle spots (read)

When a street fight starts, `Battle_PlaceFighters` `0x002D9AB0` puts the player at a **battle spot** and the opponent 25 units in front, facing back:

- `AreaDef +0x14` points at `{s32 count, s16 *spots}`, each spot `{x, y, z, angle}` in tenths. `Area_PickBattleSpot` `0x0031D0C0(mode, area, pos)`: mode 0 = the spot nearest the player among spots 1..n-1; mode 1 = spot 0 (story fights: area/stage 5/7, 0xE/8, 0x19/4, 0x1A/6, 0x21/10, 0x25/10, 0x2D/9, 0x33/3, 0x36/11, 0xD/1; and whenever the opponent is person 22, 53, 57, 60, 63, 68, 74-78, 107 or 108: heroes and bosses); mode -1 = `g_BattleSpotDefault` `0x00516980[area]`. Areas 0x13, 0x1E, 0x26 have special rules (by x or z, or y within 15).
- Areas without spots use `g_FixedBattlePos` `0x00509930[area]` (two `{x, y, z, angle}` floats, one per fighter).

The fight happens in the same area geometry; nothing extra is loaded.

## Objects placed per story stage (read)

`g_AreaObjects` `0x00422850` (0x28 bytes per area):

| Off | Type | Meaning |
|---|---|---|
| 0x00 | s16 | number of prop descriptors |
| 0x02 | s16 | number of extra placements (`+0xC`) |
| 0x04 | fn | called before the props load |
| 0x08 | ptr | prop descriptors, 0x28 bytes each, copied into the prop slots (byte 0 non-zero = an interactive prop: breakable or usable; the rest open) |
| 0x0C | fn | returns extra placements `s16[8] {prop, x, y, z, rot x, y, z}` in tenths (`Stage_PlaceExtra` `0x0015C190`) |
| 0x10-0x13 | s8 x 4 | prop ids used by object types 1/3, 2 and 3, 1/2, 1/1 |
| 0x14 | u32 | object record count |
| 0x18 | ptr | object records, 0x24 bytes: `{u8 type, u8 sub, s16 story flag, s16 x, y, z, s16 rot y (tenths), then 12 x {s8, s8}}`; pair `n` is for story stage `n + 1` (pair 11 in a special mode, bit 1 of `0x0060C960`), first byte -1 = not placed in that stage |

`Stage_PlaceObjects` `0x0015B7E0` places them: type 4 = an **item** pickup of kind `sub` at floor height + the item's lift (`0x00589C40` table, 0x84 bytes per kind), type 3 = a **weapon** from the shared FSTAGE 56 models (`0x002FF390`), type 2 = a **special** object (10 handlers at `0x005B5840`), type 1 = a **prop**. A story flag 6000-7499 hides the record once set (picked up). The subway has three items (kinds 8, 18, 17) at different stages.

## People, talk spots and spawn points

Street people, their paths and their talk scripts come from `g_PeoplePlacement`, not from the area pack (docs/CODEMAP.md, "Area people"; `AreaPerson` in symbols/structs.tsv). Talking needs no trigger zone: you talk to a person. Mission scripts check positions with `EXF_CHECK_POS` (person, x y z, radius, area; docs/SCRIPTS.md). So the only trigger volumes in the area data are the door zones (read; other script-only triggers may exist).

## Lights, sky, music (read)

From `AreaDef` (symbols/structs.tsv):

- **Lights**: `+0x3C` ambient colour; two directional lights with rotation in degrees `+0x58` / `+0x80` and colour `+0x64` / `+0x8C`. Subway: ambient (0.40, 0.40, 0.35), light 1 at (40, 0) colour (0.92, 1, 1), light 2 at (-32, 180) colour (0.35, 0.52, 0.75). Downtown: ambient (0.37, 0.37, 0.34), (35, -45) (1, 0.95, 0.84), (-22, 130) (0.36, 0.54, 0.60).
- **Far clip** by area (above). No fog setting was found in `Area_Load` (open).
- **Sky**: no sky object is loaded separately; outdoor worlds have far textures in the world itself (A1FAR, ER02SKY, A6_FAR_*; seen).
- **Music**: `+8` track (403 subway and downtown, 401 harbor, 13 station, 21 police...), `+0xA` second channel (`+0xC` instead while story flag 0xB is set), played by `0x0031D8B0`. Sound banks `+4`, `+6`.

## Other FSTAGE.XAF entries

- 0: 1 byte. 55, 56: texture dictionaries (56 = the shared one, `Stage_LoadCommon`; 55 loaded by `0x00155E70(0)` from `0x0031E2E0`).
- 57-127 (71 entries, about 36 KB each, first words 0x1F-0x21): **not stage data**. `0x00154BB0(slot, ?, n)` loads entry 57 + n for each of the two fighters at a fight start, n = the person's `+0x46` (from `PersonDef +8`, 0-70); parsed by `0x00154AF0` (header counts, then 148-byte and 272-byte records). Meaning open (per-character data for fights).
- 122-180: texture dictionaries (20 KB to 700 KB), users not found (open). They include 512x256 32-bit sheets named `STG_nn_MCAR` / `NCAR` / `SCAR` (nn = 03..53, close to the area ids) that decode as **car textures** (entry 130: a yellow taxi; `tools/ps2tex.py`, seen), so probably the traffic cars per area (guess).

## Converted for the remake (M6, 2026-10-15)

`remake/tools/conv_stages.py` (run by `remake_assets.py`) turns area 5 into glTF + JSON in metres, and `res://dev/stage_test.tscn` loads it. What that showed (**rendered** = seen in Godot screenshots, checked by Claude; **walked** = the scripted `--walk` test):

- **Textures**: the area's dictionary (section 0) holds every texture the world and the props use (rendered; nothing from the shared FSTAGE 56). Decoder: `tools/ps2tex.py` (docs/FORMATS.md, "PS2-native textures").
- **Coordinates**: RenderWare's right-handed y-up space is glTF's: positions copied as they are (x 0.1), signs and texts read the right way round, and the world triangles' winding faces the camera with back-face culling on (rendered).
- **Lighting**: the world and props are prelit (vertex colours, median about 84 of 255) and look right **unlit** with colour = prelit x 2 x material colour (the PS2's 0x80 = 1.0 convention; scale picked by eye, guess). Materials have colour 255 or 179 (rendered).
- **Glows**: the props `ER03SPARK01-07` and `ER03COVEF` (light covers) are opaque textures on black that only look right with **additive** blending. Nothing in the clump says so (no MatFX or other material plugin; seen), so the game sets it in code, probably from the prop descriptor (`g_AreaObjects +0x08`; open). The converter flags textures that are more than half black as additive (guess that happens to pick exactly those 8).
- **Props**: PB places props 1-11 (18 placements: the shutters 9 eight times along the end walls, lights 2-8 near the ceiling at y 3.9 m, the static set pieces 1-5 at the origin). Props 12-15 (the three `SB01DRUM` oil drums and an untextured quad) are not in PB: probably the interactive props placed by `g_AreaObjects` (15 descriptors; open). The PB quaternions (0, ±0.71, 0, 0.71) turn the end-wall shutters to face the platform (rendered).
- **Collision** (walked, fighter capsule radius about 0.35 m): the walls mesh stops the player at the back wall (z 0.63 m for a wall at 0.3), the front edge (12.51 for 12.8) and the ends (x 15.13 for 15.5; -9.83 near the front, where the left end is not straight); the floor holds the player at y 0. **The doors are the roller shutters at platform level**: each stairwell's door panel (z -0.96 m) closes it at the bottom, and the player stops at z -0.60 in front of the shutter; the stairs behind it are scenery, and walking into the door zone is what leaves the area (guess from the layout; door use not implemented yet).
- The camera collision mesh is kept separate (only the camera's spring arm collides with it).

## Doors in use: order, arrival points, locks, the button (read, 2026-10-15)

Read from the decomp for the remake's M6 (not tested in the emulator); `stagekit.door_records(section 5)` returns the doors this way.

- **Door order** (read + seen): `Doors_Load` walks the doors clump with `RpClumpForAllAtomics`, which visits atomics in **reverse stream order** (RenderWare links each new atomic at the list head). `Doors_CollectAtomic` files a zone, then its panel, into record `count` and counts the record once both are in. So the subway's doors are 1 = -16 (right stairwell), 2 = -17; DOWNTOWN STREET's are 1 = 9, 2 = 19, 3 = 7, 4 = 25, 5 = 47, 6 = -51, 7 = -52. Cross-check: subway -16 -> downtown entrance 6 = door -51 -> subway entrance 1 = door -16, and -17 <-> -52 the same way (stream order would send entrance 7 to RAG SHACK).
- **Entrance -> arrival point** (read): `Door_FindArrival` `0x00351CF0(doors, previous area, entrance)`: entrance >= 1 = door record `entrance - 1` of the destination; entrance < 1 (positive tags) = the destination's door whose destination is the previous area (`0x006CBB00`). `Door_ArrivalPoint` `0x002E7B10(?, pos, angle)` puts the player at that record's +0x10 matrix position (+0x40) facing `atan2(at.x, at.z)` (+0x30, +0x38) in degrees; with no door, door 0. The matrix is the LTM of the **panel frame's child frame** (an atomic-less marker; `0x00351060` copies it while the panel is collected). Subway arrivals: (11.21, 0, 1.81) m and (-8.81, 0, 1.93) m, both facing +z (angle 0). While story flag 998 (0x3E6) is set the point moves 70 units along -at (open why). `0x002E7A60(area, entrance)` stores the target (`0x006CBB04`, `0x006CBB08`) and the previous area (`0x006CBB00`); `0x00176E10` gives the arrival door index the same way.
- **Using a door** (read): `0x002E2930` each frame tests the player against the zones (`Door_ZoneTest` `0x00351A70`, radius 5) and the facing: the player's angle (fighter +0x2D0) must be within 90 degrees of the zone frame's `atan2(at.x, at.z) + 180` (its modelling matrix, frame +0x30). Then `Door_Destination` `0x002E7900` returns the destination area (0 = unusable) and the entrance, and a blinking icon (texture 0x3DD) is drawn. The door is taken by a **button press**: `0x0030AEB0` calls `0x002E2660` when the pad word from `0x002F92A0(fighter) + 4` has bit 0x1000 (R1 by `Pad_RemapButtons`; guess) and a per-pad mask; that sets the request (+0xA0) that the mission manager turns into `0x002E7A60` + an area change. **Correction (2026-10-16, docs/CONTROLS.md):** the mask is job 0 = **L1**, so the press is **L1 + R1**, the help text's ESCAPE (①+④, text 30287), and `0x002E2660` (`Battle_RequestEscape`) and `0x002E2930` only run during a battle (`g_Battle` +0x144 bit 2): this is running away from a fight through a door. How the field takes a door outside a battle is not traced (probably walking into the zone).
- **Locks** (read): `Door_Locked` `0x00351480(door)`: the door's raw tag is looked up in `g_AreaDoorFlags` (`first_flag + index`); if that story flag is **set**, the door is locked and `0x00351280(flag)` gives the message: text 30456 "You can't get any further.", 30457 "You can't run away now." (the subway's 808, 809), 30451 "It's locked.", 30452 "...locked from the other side.", 30450 "The gate is locked.", 30461 "{area} is closed." and others (0x76F2-0x7701). Flag clear: usable if the destination's bit is set in a per-area bit set at gp-0x4F08 (`0x002E8E60`; meaning of the bit set open, probably areas opened by the story), else nothing happens. `g_AreaDoorFlags` really starts 4 bytes earlier (0x0058BDB0, 0x14 bytes): `+0` destinations whose doors are disabled (`0x00351810` clears its "usable" byte), `+4` the allowed list, `+8` first flag, `+0xA` count, `+0xC` tags, `+0x10` a per-door u32 table (`0x003513F0`; open). `Door_State` (0x003515A0) returns 0 = locked or allowed, 1 = the destination is not in the allowed list (one more caller, not identified; meaning still open).
- **Wall kinds** (read): `Area_MaterialKind` values in the area tables are 0, 4, 5, 8, 12-15, 17-19, 22, 23 (subway 8, 19): no area wall uses the **hazard kinds 9, 11, 28, 29**, which only come from objects (hit type 2: the object's own kind). A fighter touching a hazard (`0x002EC920`) takes damage and starts action 0x6B4 (kinds 9, 11), 0x6D6 (28) or 0x6D5 (29) with effect `0x001D2480(4, 6, 0x2B)` / `(1, 6, 4)`; kind 23 is set for door hits, 24-25 count as no wall. What the plain kinds change (sound, dust?) is open.
- **Props 12-15 of the subway** (read): no PB placement and no `g_AreaObjects` type-1 record uses them (the subway's records are three items). Their descriptors (`g_AreaObjects +8`): 12-14 have byte 0 = 3 (interactive), 12 and 13 with +2 = 400 / 300 (probably durability; guess) and float 10.0 at +0xC: the oil drums. The area's type-1 sub-2 prop is 12 and its weapon/special carrier prop (+0x11) is 15, so a drum appears only when something places a type-1 sub-2 object (a script or the saved-prop restore `0x0015CD20`; open which).
- **DOWNTOWN STREET variants** (seen): FSTAGE 1, 2 and 3 have the same world, collision, doors and placements; only the textures (section 0) and prop models (7) differ. 24 (the special mode) has its own world and props and no prop animations. Its type-1 records place prop 32 (sub 3) at four spots, each in two story stages.

## Open questions

- What the wall kinds (`AreaDef +0xE8`) and floor kinds (`+0xC4`) do; who reads `+0xC4`.
- `Door_State`'s 1 (destination not in the allowed list): what uses it. The gp-0x4F08 area bit set. Story flag 998 moving arrivals. Which button exactly takes a door (bit 0x1000 of `0x002F92A0`'s pad word).
- The prop descriptors (0x28 bytes): which props break, which can be picked up or used.
- FSTAGE.XAF 57-127 and 122-180.
- `AreaDef +0x0E`, `+0x10`, `+0x18`, `+0x1C` (bytes 8, 8, 8), `+0x20` (0.8), `+0xA0` (20.0), `+0x100`, `+0x101`.
- Where `g_PeoplePlacement` (RAM `0x01431EB0` in V's chapter-2 save) is loaded from.
- Test in the sandbox: the area ids (teleport to 5 and 46), and a fighter against the subway's walls (done in the remake's stage test, not in the game).
- Where the game turns on additive blending for glow props (sparks, light covers), and how bright prelit colours are on the PS2 (x 2 assumed).
- Props 12-15 of the subway (drums): placed by `g_AreaObjects`? When, and can they be broken or picked up?
