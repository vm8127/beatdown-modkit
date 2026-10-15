# File formats: models, textures and text

How Beat Down's character models are stored and put together, decoded 2026-10-15 for the Godot remake (milestone M1, `remake/`). The archive layout (XAF) is in README.md, "XAF archive format"; animations are in docs/ANIMATION.md. Tools: `tools/rwkit.py` (decoder, chunk dumps, model assembly) and `remake/tools/remake_assets.py` (glTF export).

How sure: **read** = read from the game's code in `decomp/`; **checked** = verified on the data (all entries, or the ones named); **rendered** = the converted model looks right in Godot (2026-10-15: preset 89's street model and Aaron's fight model, preset 78; screenshot checked by Claude, not yet by V); **guess** = inferred, not confirmed.

## Contents

1. [RenderWare streams](#renderware-streams)
2. [Textures (Image chunks)](#textures-image-chunks)
   - [PS2-native textures (0x15)](#ps2-native-textures-0x15)
3. [Clumps: frames, geometry, materials](#clumps-frames-geometry-materials)
4. [Skeleton and skinning](#skeleton-and-skinning)
5. [Street models (walking around)](#street-models-walking-around)
6. [Fight models built from outfit slots](#fight-models-built-from-outfit-slots)
7. [Other model entries](#other-model-entries)
8. [Text](#text)
9. [Tools](#tools)
10. [Open questions](#open-questions)

## RenderWare streams

Every model, texture and animation entry is a **RenderWare 3.x binary stream** (Criterion's engine; checked, and read: `RwStreamReadChunkHeaderInfo` `0x0025B5F8` unpacks the version exactly like RenderWare). Each chunk is

```
u32 type      chunk id; the "asset type" in README.md's table is the first chunk's id
u32 size      bytes of payload after this 12-byte header
u32 libid     library id: 0x1C02000A on clumps (version 3.7.0.2), 0x1803FFFF on images (3.6.0.3), 0x1C02000F on PS2 textures
```

Containers hold more chunks; the leaves usually start with a `Struct` (0x01) chunk. An XAF entry can hold several top-level chunks in a row (a street pack is 8 images then 2 clumps). The rest of the 2048-aligned entry is zero.

| Id | Chunk | Where seen |
|---|---|---|
| `0x01` | Struct | everywhere |
| `0x02` | String | texture and mask names |
| `0x03` | Extension | holds the plugin chunks of its parent |
| `0x06` | Texture | inside materials: filter flags, name, mask name |
| `0x07` / `0x08` | Material / MaterialList | |
| `0x0E` | FrameList | |
| `0x0F` / `0x1A` | Geometry / GeometryList | |
| `0x10` | **Clump** (README's "mesh") | DATA.XAF 486 entries, CDATA.XAF street packs and 196-384, FSTAGE |
| `0x14` | Atomic | `{frame, geometry, flags, 0}` |
| `0x15` | Texture native (PS2 platform, "PS2" tag) | inside 0x16 |
| `0x16` | **Texture dictionary** (README's "model") | CDATA.XAF 196-384, FSTAGE, FSCENE, GRAPH 1 |
| `0x18` | **Image** (README's "texture") | DATA.XAF 7529 entries, the street packs |
| `0x1B` | **Animation** (RtAnimAnimation) | DATA.XAF 261 entries, STAGE.XAF packs (docs/ANIMATION.md) |
| `0x116` | Skin plugin | skinned geometry |
| `0x11E` | HAnim plugin | on frames |
| `0x11F` | User data plugin | on frames: Softimage `BONETAG=nn` |
| `0x50E` | BinMesh plugin | triangle strips per material |

How the game loads them (read): `Pack_Load` `0x0029E500` walks an entry's top-level chunks and dispatches on the type: 6 `RwTextureStreamRead` `0x00264138`, 0x10 `RpClumpStreamRead` `0x00231EE8`, 0x16 `RwTexDictionaryStreamRead` `0x00264500`, 0x18 `RwImageStreamRead` `0x00269E38` (then a texture is made of it, named after the next cache key in the request's list, see below), 0x1B `RtAnimAnimationStreamRead` `0x002503B0`, 0x23 `0x00259980` and 0x0C `0x0022B9A0` (not identified).

## Textures (Image chunks)

`0x18` Image: `Struct {u32 width, u32 height, u32 depth (4 or 8), u32 stride}` then `width*height` bytes, one palette index per byte (4-bit images too), then the palette: 16 or 256 RGBA entries. 256-colour palettes are in the PS2's CSM1 order (entries 8-15 and 16-23 of every 32 swapped). So the header offsets `bdkit.py tex` uses (width at +0x18) are the Struct's fields after the two 12-byte headers. (Checked on every texture `bdkit.py tex` was used on, and all 8 images of street pack 96.)

**Alpha.** Palette alpha is full range (0-255 seen, not the GS's 0-0x80). On hair textures (`HAI_*`) it is real transparency (soft edges). On clothes it is not: Aaron's vest `WEA_M48AAF` (6662) has a noise-like alpha that would punch holes in the vest, so it is most likely a **specular/gloss mask**: every item's placeholder list starts with texture 0, named `SPECULAR` (guess, rendered: the vest looks right opaque). The remake treats alpha as cutout transparency on `HAI_*` textures only.

**Names.** Textures are cached by name. `g_TexNames` `0x0059AE30` holds `{u32 ?, char *name}` for each of the 8276 DATA.XAF entries (checked), and `g_ArchiveTexNames` `0x004EC950` points each archive id at its name table: DATA and CDATA (and archive 5) use the same one, so a CDATA street-pack image takes a DATA id's name. Names follow `KIND_LNNVVV`: a 3-letter part kind (`SKI` skin, `HAI` hair, `PAL` pants, `WEL` wear (street), `WEA` wear/top (fight), `PAN` pants (fight), `LEG`, `ARM`, `HAN` hand, `BRE` breast, `ABD` abdomen, `BAC` back, `BRO` brow, `NOS` nose, `MOU` mouth, `EYE`, `ACS`/`ACB`/`ACW`/`ACN`/`ACH`... accessories), then a model code. **`*_A01AAA`-style names are placeholders** the meshes reference (`LEG_A01AAA`, `LEG_A01BAA` for the second leg material...); real textures have other codes (`LEG_B01AAA`).

## PS2-native textures (0x15)

The world textures (FSTAGE.XAF section 0 of every area pack, shared entries 55 and 56) and the texture dictionaries in CDATA.XAF 196-384 and FSCENE.XAF are **RenderWare PS2 "texture native" chunks**: ready-made GS upload packets. Decoded 2026-10-15 for the remake's M6 with `tools/ps2tex.py` (checked: all 36 subway textures look right as PNGs, and all 3,225 textures in FSTAGE.XAF decode without error; 519 have some alpha). Layout (seen on all of them):

```
0x16 TexDictionary  Struct {u16 count, u16 device 6}, then count x 0x15, then an empty Extension
0x15 TextureNative
  Struct (8)        char platform[4] "PS2\0", u32 filter/addressing (0x1102 seen)
  String            name (ER03_W_D2...), String mask name (empty seen)
  Struct
    Struct (64)     raster info: u32 width, height, depth (4, 8 or 32), u32 raster format,
                    u64 TEX0, u32 palette offset, u32 TEX1 low, u64 MIPTBP1, MIPTBP2,
                    u32 pixel size, u32 palette size (each including its 0x50-byte GS header), u32 total GS size, u32 0xFF0
    Struct          pixel packet, then palette packet
  Extension         empty
```

- **Raster format**: low 16 bits 0x2504 (PAL8 + 8888 + texture), 0x4504 (PAL4) or 0x0504 (32-bit, no palette); high 16 bits 2 = the data has GS headers. Only these three, and **no mipmaps** (flag 0x8000 never set) anywhere in FSTAGE.XAF (seen: 2,688 4-bit, 489 8-bit, 48 32-bit). 47 textures have no GS headers (high half 0): the 512x256 32-bit `STG_nn_MCAR/NCAR/SCAR` sheets in FSTAGE 122-180, which are **car textures** (a yellow taxi in 130; so those entries are the traffic cars, probably one per area: open), stored as plain rows.
- **GS header** (0x50 bytes before the pixels and before the palette): a GIFtag (NLOOP 3, A+D) setting TRXPOS, **TRXREG** (u32 width, height at header `+0x20`) and TRXDIR, then the IMAGE GIFtag. There is no BITBLTBUF: the driver adds the destination at upload time.
- **TEX0**: TBP0 and CBP are 0 (relative), TBW = width / 64 (at least 2 for 4/8-bit), PSM 0x13 (PSMT8), 0x14 (PSMT4) or 0 (PSMCT32), CPSM 0 (32-bit palette), CSM 0 (CSM1).
- **Swizzle**: 4- and 8-bit pixels are uploaded as a **width/2 x height/2 rectangle** in another format, so the bytes are in GS-memory order, not row order. 8-bit: the rectangle is PSMCT32 (w x h bytes); 4-bit: PSMCT16 (w x h / 2 bytes; the format is not in the data, deduced from the size and confirmed by the decoded images). To decode, write the rectangle into emulated GS memory in that format with buffer width TBW / 2, then read the texture back as PSMT8 / PSMT4 with TBW (`ps2tex.unswizzle`, GS block/column tables). 32-bit textures are uploaded as themselves (linear rows).
- **Palette**: 8-bit: 256 colours uploaded as a 16x16 PSMCT32 rectangle, so in CSM1 order (entries 8-15 and 16-23 of every 32 swapped, as for Image chunks). 4-bit: an 8x3 rectangle of which the first 16 entries are the palette (the rest is padding; seen). Alpha 0x80 = opaque (the tool doubles it to 0-255).
- Texture names match the world's material texture names (section 1) one to one (checked on the subway: 19 textured materials, all found).

## Clumps: frames, geometry, materials

All character geometry is **plain RenderWare geometry, not PS2-native** (no VIF packets; checked on all 486 DATA.XAF clumps and the street packs): the PS2 driver builds the GS data at load.

- **Clump** Struct: `{u32 atomics, u32 lights, u32 cameras}`; then FrameList, GeometryList, the Atomics.
- **FrameList** Struct: `u32 count`, then per frame 56 bytes `{f32 right[3], up[3], at[3], pos[3]; s32 parent; u32 flags}` (row vectors, relative to the parent; parent -1 = root). One Extension per frame follows, with the HAnim and user data plugins.
- **Geometry** Struct (version ≥ 3.4, so no surface properties): `{u32 flags, u32 triangles, u32 vertices, u32 morph targets}`. Flags seen: `0x00010035` (tristrip, textured, normals, modulate, 1 UV set) on every textured geometry; the positions flag 2 is **not set** but positions are present. Then: prelit colours if flag 8 (never seen), the UVs (`f32 u, v` per vertex, top-left origin like glTF), the triangles (8 bytes: `u16 v1, v0, material, v2`, RenderWare's file order), then one morph target `{f32 sphere x y z r, u32 has positions, u32 has normals}` and `f32 xyz` positions and normals.
- **MaterialList**: Struct `{u32 count, s32 index[count]}` (-1 = a new Material chunk follows; seen only -1), then the Materials. **Material** Struct `{u32 flags, u8 rgba[4], u32 ?, u32 textured, f32 ambient, specular, diffuse}`, then a Texture `{Struct u32 filter flags (0x00011102), String name, String mask}` when textured. A few hair and accessory textures have a mask name (`HAI_A01AAAm`); most don't (checked over all DATA meshes).
- **BinMesh** plugin: `{u32 1 = strips, u32 meshes, u32 total indices}`, then per mesh `{u32 count, u32 material, u32 indices[count]}`. The triangle list holds the same faces, so the converter uses the triangles.
- **Atomic** Struct `{u32 frame, u32 geometry, u32 flags (5), u32 0}`.
- **Marker geometries**: next to the real ones, most clumps have one-triangle untextured geometries (flags `0x71`, grey or black, bounding radius 0.001-0.1) on their own frames: in the body clump on frames 21, 17, 10, 8 (bone tags 14 and 13, the points beside the hands, and 20 and 19, the feet). Probably attachment or contact points; the converter skips them (guess).
- **Units**: a man is about 18 units tall (body bounding sphere centre y = 8.8, radius 9.4; the hip frame is at y = 10.6), so a unit is about 10 cm; the converter scales by 0.1 to metres. Y is up, the model faces +Z (rendered).

## Skeleton and skinning

Used by the remake's rigged export (M2, 2026-10-15: `remake/tools/skeleton.py`, `conv_models.py`; rendered with the game's animations in Godot, poses right).

- **Bones are frames with an HAnim plugin** `{u32 version 0x100, s32 node id, u32 count}`; the skeleton root frame (frame 1, node id 29) also has the hierarchy: `{u32 flags 0, u32 key frame size 36}` and `count` x `{s32 node id, s32 node index, u32 flags}` (flags 1 = pop, 2 = push, as in RpHAnim). Each bone frame also has user data `Softimage User Data = ["BONETAG=nn"]` with the same id (checked).
- **The full skeleton has 22 nodes** (frames 1-22 of 23; frame 0 is the clump root). Node index → bone tag, from the body clump (DATA.XAF 2650, item 7) and street pack 96 (identical):

  | Node | Tag | Frame | Parent tag | Likely bone |
  |---|---|---|---|---|
  | 0 | 29 | 1 | - | root (at the origin) |
  | 1 | 3 | 4 | 29 | hips (y 10.6) |
  | 2, 3, 4 | 15, 17, 19 | 6, 7, 8 | 3 | one leg: thigh, shin, **foot** (node 4) |
  | 5, 6, 7 | 16, 18, 20 | 5, 9, 10 | 3 | other leg: thigh, shin, **foot** (node 7) |
  | 8 | 1 | 3 | 29 | spine (y 10.6) |
  | 9 | 2 | 11 | 1 | chest |
  | 10 | 4 | 14 | 2 | **head** (neck end) |
  | 11, 12, 13 | 5, 7, 9 | 13, 15, 16 | 2 | one arm: shoulder, upper arm, forearm |
  | 14, 15 | 11, 13 | 18, 17 | 9 | **hand** (node 14) and a second point beside it (a marker sits on it) |
  | 16, 17, 18 | 6, 8, 10 | 12, 19, 20 | 2 | other arm: shoulder, upper arm, forearm |
  | 19, 20 | 12, 14 | 22, 21 | 10 | **hand** (node 19) and the second point |
  | 21 | 28 | 2 | 29 | extra (y 10.6), no children |

  Sides aren't confirmed (left/right untested). The node index order is the hierarchy list order (depth first), which is what skin bone indices and `ItemDef.attach_node` use.
- **Skin plugin** (non-native): `{u8 bones, u8 used bones, u8 max weights (4), u8 0}`, `u8 used[used bones]`, then per vertex `u8 bone[4]` and `f32 weight[4]`, then per bone a 4x4 **inverse bind matrix** (RwMatrix layout: right, up, at, pos rows with flags/padding in the 4th column), then 3 u32 (bone limit, meshes, RLE count; all 0 seen). **Skin bone k = HAnim node index k** of the clump's own hierarchy, and **inverse bind matrix k × the frame's world matrix = identity** exactly (checked on DATA 2650, 6858 and CDATA 96): the clump's stored frames are the bind pose, and skinned vertices are stored in bind-pose model space.
- Skinned clothes (tops, pants) carry **their own partial skeleton** with the same bone tags (a top has 17 nodes, pants 9; the root is tag 29 again) and **exactly the body's bind pose** (world positions equal by tag, checked on Aaron's top 6858 and pants 6618). Remapping their bone indices to the body's by tag works (rendered animated, M2; `rwkit.skin_map`); whether the game matches by node id the same way is not traced.
- Rigid items are bound with weight 1 to their attach node (rendered animated). The eyes item (item 5, mesh 2723) has its own 3-node skeleton with tags that aren't body tags (maybe eye or eyelid bones); the remake treats it as rigid on the head.
- Joint names the remake uses (`skeleton.BONE_NAMES`): sides from the bind pose with the model facing +Z, so its right side is -X: nodes 2-4 right leg, 5-7 left leg, 11-15 right arm (hand 14), 16-20 left arm (hand 19). Not checked in-game.
- The HAnim key frame size 36 is RenderWare's standard keyframe; the stored animations use the compressed one (docs/ANIMATION.md).

## Street models (walking around)

CDATA.XAF entry **preset + 7** (read: `NpcSpawn_Step` `0x00178700`; checked on 96): 8 Image chunks, then the **body clump** (5 atomics: the skinned body + 4 markers) and the **hair clump** (4 frames, one geometry). The images take their names from `g_StreetTextures[preset]` `0x00430C90` in order (`Pack_Load`); for preset 89: `SKI_A01AAA, PAL_A01AAA, WEL_A01AAA, HAI_A03AAA` (the 4 placeholders, shared by every male street model) then `SKI_D06LOW, PAL_F34AAA, WEL_C32AAD, HAI_D03AAH` (this person's skin/face atlas, pants, top, hair). docs/PARTS.md's "Street pack" table had indices 3-7 as skin/face/pants/top/hair; index 3 is the hair placeholder and 4 the skin/face atlas.

The body's materials name the placeholders. When **`g_PresetFlagA[preset]` `0x00431B60` is 1** (it is for most presets), `NpcSpawn_Step` retextures (read):
- body clump: `RpClumpForAllAtomics(Street_RetextureAtomic 0x001755A0)` → `Street_RetextureMaterial` `0x001754B0`: a material whose texture is list[i] (i < 4) gets list[i + 4];
- hair clump: `Street_HairAtomic` `0x00175650` → `Street_HairMaterial` `0x001755E0`: every material gets list[7].

The hair clump's vertices are relative to its own frame; the remake hangs it on the body's head node (10), like an outfit item (rendered: sits right; how the game attaches it isn't traced).

## Fight models built from outfit slots

A fighter whose model is built from the outfit (persons 51/52, changed outfits; docs/PARTS.md) gets one clump per outfit slot (read: `Fighter_LoadModel` `0x002F53A0`, `Fighter_AttachPart` `0x002F4BF0`). The prebuilt per-preset fight models are ARCHIVE.XAF (not in this `ISO/`, so not used by the remake).

**ItemDef** (`g_ItemTable` `0x004F2400`, 52 bytes; corrected 2026-10-15, checked on the items below):

```
+0x00 u32 category        0 body, 1 head, 2 hair, 3 mouth, 4 eyes, 5/6 hands, 7/8 shoes, 18 top, 19 pants... (docs/PARTS.md)
+0x04 u32 attach_node     body skeleton node a rigid item hangs on: 10 head/hair/mouth/eyes, 19 and 14 hands, 7 and 4 feet
+0x08 u32 flags
+0x0C void *use_handler
+0x10 u16 mesh            DATA.XAF clump (item 7: 2650 body; 266: 2762 head)
+0x12 u16 anim            DATA.XAF animation (type 0x1B) for tops and pants (6619 next to mesh 6618; 6859 next to 6858), else 0
+0x14 s16 placeholders[]  DATA.XAF ids of the placeholder textures the mesh's materials name, ending -1
```

The game loads each item's model as a pack from **ARCHIVE.XAF entry item + 0x3A6** (read; the index dump names entry 941 = item 7 `BAC_A01AAA`), with a mesh when `+0x10` ≠ 0 and an animation when `+0x12` ≠ 0. The remake uses the DATA.XAF clump `+0x10` instead, which has the same placeholder materials (rendered); whether it's byte-identical to the ARCHIVE copy is unchecked.

**Assembly** (read, rendered on preset 78):
1. For each outfit slot `{item, parts[]}` load the item's clump.
2. **Textures**: a material whose texture name is `placeholders[i]`'s name gets `parts[i]` (same index; Aaron's body: 9 placeholders `LEG_A01AAA, LEG_A01BAA, ARM_A01AAA, HAN_A01AAA, ARM_A01BAA, HAN_A01BAA, BRE_A01AAA, ABD_A01AAA, BAC_A01AAA` ↔ his 9 parts).
3. **Category 0 (body)** is the skinned clump with the 22-node skeleton; it becomes the fighter's main clump.
4. **Skinned items** (tops, pants) are already in bind-pose model space.
5. **Rigid items** (head, hair, mouth, eyes, hands, shoes) are in their attach bone's space: `Fighter_AttachPart` stores `hierarchy->nodeInfo[ItemDef.attach_node].frame` in the part slot (`+0x5F0`). World = vertex × the item clump's frame (world) × that body node's world matrix.

## Other model entries

- **CDATA.XAF 196-384** (189 entries, one per preset?): a texture dictionary of PS2-native textures (`0x15`, platform "PS2", 4 textures in 196) then a clump with the 23-frame skeleton. Not decoded further; maybe the talk-scene or menu models (open question).
- **FSTAGE.XAF**: the area packs (texture dictionary, an RpWorld 0x0B with its sectors 0x09/0x0A, collision and door clumps, props): see docs/STAGES.md and `tools/stagekit.py`. Entries 57-127 (first words 0x1F-0x21) are a per-fighter format, not RenderWare.
- **FSCENE.XAF**: 162 texture dictionary + clump entries next to the cutscene scripts.
- PS2-native textures (`0x15`): see [above](#ps2-native-textures-0x15), `tools/ps2tex.py`.

## Text

Decoded 2026-10-15 for the remake (TODO "Game text"); **read** from `Text_Get` `0x00387980`, `Text_LoadBank` `0x00387780`, `Text_FindIndex` `0x00387D20` and the text encoder `Text_Encode` `0x001B2BE0`, **checked** on all banks in all six languages (`remake/tools/test_text.py`: every MOVE LIST of docs/movesets.md, names, area 5, the negotiation menu). Tools: `tools/textkit.py` (decoder, CLI), `remake/tools/conv_text.py` (JSON for the remake), `remake/godot/game/text/game_text.gd` (`GameText`).

**Banks.** CDATA.XAF entries 385-432 are 8 banks x 6 languages (entry order JP, EN, FR, DE, ES, IT). An entry is `{u32 size, u16 count, u16 language, count x {u16 id, u16 byte length, u32 offset}}`, then the strings (offsets from the end of the table), UTF-8, NUL-terminated, ids sorted (binary search). The header's language number is `g_SystemData.language`: 0 JP, 1 EN, 2 DE, 3 ES, 4 FR, 5 IT (so the FR entry says 4). `Text_Get` (id) picks the bank by id range, with 5 slots in `g_TextBanks` `0x0076DDB0`:

| Bank | Entries | Slot | Ids Text_Get sends there | Holds |
|---|---|---|---|---|
| ui | 385-390 | 0 (always loaded) | everything else | menus, HUD, names (11001 + person, Aaron = 11069), areas (18000-18161, 22000-), tutorials and help (30000-32999), street and battle lines (50000-51016: greetings, taunts, and what looks like each hero's negotiation lines, e.g. 50581 "Su dinero. All of it." / 50585 "Tell me everything you know. Now!" / 50587 "Wanna join me?..."; guess from the text, not traced), status screens (51500-), messages (52000-53999), menu help (60000-, 65500-) |
| items | 391-396 | 2 | 12000-17999 | item names and descriptions; also a copy of the negotiation menu (13004 ...) |
| moves | 397-402 | 1 | 40000-49999 | MOVE LIST inputs and names (`g_MoveLists`, docs/movesets.md) |
| missions | 403-408 | 3/4 | 35000-39498 | job titles and descriptions (`g_Jobs`) |
| partner | 409-414 | 3/4 | 61000-63999 | party member lines |
| rumours | 415-420 | 3/4 | 29000-29999 | town rumours and hints |
| system | 421-426 | 3/4 | 25000-26999 | memory card messages |
| credits | 427-432 | 3/4 | 5000-8999, 9100-9399 | staff credits |

The swappable banks share one slot (`g_TextSwapSlot` `0x00600320` says 3 = static buffer or 4 = heap) loaded on demand. A missing id falls back to text 10201. Every id each bank holds is in its own range (no unreachable entries). Mission and dialogue text is not in these banks: it is the string table of each SCRIPT.XAF script image (docs/SCRIPTS.md, "Script file format"), same encoding; SCRIPT.XAF 324 and 485-499 still hold Shift-JIS strings from development (unused, read as cp932).

**Encoding and control codes** (`Text_Encode`: UTF-8 in, 16-bit font codes plus a colour byte per character out, `g_TextCodes` `0x006620C0`). ASCII is stored full-width (U+FF01-FF5E, space U+3000); half-width characters are codes:

| In the string | Meaning | Remake markup (`textkit.to_markup`) |
|---|---|---|
| `\` `n` (two characters) or LF | new line | `\n` |
| `@`*d* or `$`*d* (half-width; *d* a digit) | colour *d* for what follows, 0 = default (English uses 6 and 8) | `{c`*d*`}` |
| `%s` | printf argument (a few UI strings) | kept |
| ∀ / ⑫ | person name (`Text_SetPerson` `0x001B7D80`; 0 = the player's hero via `Fighter_DisplayName`, else text 11001 + n) / a second person (setter not found) | `{person}` / `{person2}` |
| 〒 | area name (`Text_SetArea`: 1-54 `AreaDef.name_text`, 100-153 the short name of area n - 100) | `{area}` |
| ㈲ / ⑦ / ⑧ | item name (`Text_SetItem*`: text 11999 + n, from 108 on 17316 + n; ⑦ ⑧ give items 2, 5, 9, 10, 11, 23, 40 their own texts 0x39D1-0x39DB) | `{item}` `{item1}` `{item2}` |
| ㈱ | money: text 10202 "$" + `Str_FromInt` (German: number first) | `{money}` |
| ⑮ / ⑯ | numbers (`Text_SetNum1` / `Text_SetNum2`: KB needed, port or slot number) | `{num1}` / `{num2}` |
| ⑬ / ⑭ | any text id (`Text_SetText1/2`) | `{text1}` / `{text2}` |
| ⑪ / ⑩ | opening / closing double quote | “ / ” |
| 〆 ◎ ◇ ▽ | the button of action punch / kick / guard / special, from the player's controller layout (`Pad_ActionButton` `0x002EBD40`, `g_PadLayouts` `0x005CF7C0`; layout 0: □ △ × ○) | `{btn:punch}` `{btn:kick}` `{btn:guard}` `{btn:special}` |
| ≠ ⑳ ◆ ▼ | the same four, drawn filled (pressed) | `{btn:punch_on}` ... |
| ♯ ♭ ♪ | menu buttons: × △ □ (JP: ○ × △) | `{btn:ok}` `{btn:back}` `{btn:third}` |
| ○ △ □ × / ● ▲ ■ Ⅹ | fixed face-button glyphs, outline / filled | `{btn:circle}` ... `{btn:cross_on}` |
| ①-⑥, ⑰, ⑱, ∬, α, β, ㊤-㊨ | icon glyphs: ① + stick = RUN, ②/⑤ use the equipped items, ④ grab / pick up (move lists: "□□ ④"), ⑥ taunt, ∬ rapid press ("GRAB ∬□"), α opens a menu | `{icon:1}` ... `{icon:rapid}` `{icon:alpha}` |
| ⑲ | ® | ® |

Everything else (Latin-1 and Latin Extended-A letters, general punctuation, arrows ←↑→↓ which the MOVE LIST uses, kana, kanji) is a font glyph. Note that NFKC normalisation (what bdkit.py and scriptkit.py use for display) folds the circled placeholders into digits ("controller port ⑯" becomes "port 16"); use `textkit` when the codes matter. A real `{` or `}` would be written `{lb}` / `{rb}` (none occur).

**For the remake** (`conv_text.py`, run by `remake_assets.py` as `text`): `assets_ripped/text/<lang>.json` `{"text": {id: markup}}` (7,943 texts), `dialogue_<lang>.json` `{"scripts": {SCRIPT.XAF entry: [markup]}}` (1,088 scripts, 6,245 strings), `index.json` (banks, tokens, area id -> name texts, style -> move list text ids, id bases). `GameText.text(id)`, `render(id, vars, bbcode)`, `person_name(n)`, `item_name(n)`, `area_name(area)`, `move_list(style)`, `dialogue(entry)`; missing assets give `#id`.

## Tools

```
python tools/rwkit.py tree ISO/XAF/CDATA.XAF 96     # chunk tree of an entry (or a file)
python tools/rwkit.py info ISO/XAF/DATA.XAF 2650    # frames, bones, geometries, materials, skin
python tools/ps2tex.py list ISO/XAF/FSTAGE.XAF 5     # PS2-native textures of an area pack (png ... OUT writes them)
python remake/tools/remake_assets.py ISO remake/godot/assets_ripped   # glTF for the remake
python tools/textkit.py get ISO/XAF/CDATA.XAF 11069 18002   # text by id with the markup (banks, find, dialogue)
```

`rwkit.py` as a library: `read_clumps(blob)`, `images(blob)`, `world_matrices(frames)`, `skeleton_nodes(clump)`, `street_model(...)`, `outfit_model(...)` (returns the placed geometries with their DATA.XAF texture ids).

## Open questions

- Alpha on clothes and skin: a gloss mask for the `SPECULAR` environment pass (guess)? Find the material/pipeline setup that uses texture 0 `SPECULAR`.
- Skinned clothes: binding by tag works in the remake; not traced in the game. What the clothes' animation (`ItemDef +0x12`) does: cloth sway?
- What the one-triangle marker geometries are for.
- How `NpcSpawn_Step` attaches the street hair clump (head node 10 is assumed).
- CDATA.XAF 196-384: what uses them (their PS2-native textures now decode with `tools/ps2tex.py`).
- Pack chunk types 0x23 and 0x0C (`0x00259980`, `0x0022B9A0`).
- Left/right of the leg and arm chains; confirm by posing in M2.
- Is the DATA.XAF clump of an item identical to its ARCHIVE.XAF item + 0x3A6 copy?
- Text: the colour palette behind `@0`-`@9`; which physical buttons icons ①-⑥, ⑰, ⑱, α, β are (L1/R1/L2/R2/START/SELECT?); who sets the second person `⑫` (gp-0x771C); what Text_Encode's `box` (0x308-byte records at `0x006629E4`) holds (line count, wrap width); the font itself (glyph table and texture) for a faithful look. Not checked in the emulator.
