# Body and outfit parts reference

What a character's look is made of, and the part ids found so far, for building new characters (docs/mods/PLAN-new-characters.md, `mods/c/new_characters.c`). Started 2026-10-15 while building Eggusz; **add to it as parts get identified** (Daniel: no need to scan everything at once). Ids were found by viewing the textures with the tool below and by testing in the sandbox unless marked otherwise.

## Viewing parts

```
python tools/bdkit.py tex ISO/XAF/DATA.XAF out_dir 3419 1870 336
```

writes each DATA.XAF texture as `out_dir/<id>.png` (8-bit textures with a 256-colour palette, or 4-bit ones stored one pixel per byte). The PNGs are made from your disc, so keep them out of the repo.

## How a look is built

A person looks different in three places, and each has its own data:

| Where | Model | What decides it |
|---|---|---|
| **Fights**, most people | the prebuilt fight model ARCHIVE.XAF entry = **preset number** | the preset number only (`Fighter_LoadModel` `0x002F53A0`) |
| **Fights**, persons **51 and 52** (the cut character editor's slots), and anyone whose outfit no longer matches their preset | built from the person's **22 outfit slots**: meshes from `g_ItemTable`, textures from DATA.XAF | the outfit slots (person `+0x68`, copied from the preset by `Person_Init`) |
| **Walking around** (street people, party members) | the **street pack** CDATA.XAF entry **preset + 7**: 8 texture chunks + one low-poly mesh | the preset number; the 10 ids in `g_StreetTextures[preset]` (`0x00430C90`) are the cache keys of the pack's 8 textures |

So a new character with a new look should be **person 51 or 52** (fight look from slots) with an **unused preset number** (street look; 1, 19, 20, 87, 94, 97, 127, 129, 132, 141, 143 are unused by any template).

### Outfit slot (fight look)

`{u32 item, s16 parts[16] ending -1}`, 22 per preset (`Preset` / `OutfitSlot` in symbols/structs.tsv). `item` is a row of `g_ItemTable` `0x004F2400` (52 bytes: `+0` category, `+0x10` u16 **DATA.XAF mesh**, `+0x12` a default part list); `parts` are the **DATA.XAF texture ids** the mesh uses, in the mesh's order. Copy whole slots from an existing preset and change only textures of the same size and kind, or the fight load waits forever (seen: giving a mesh id where a texture was expected froze the "VS" intro). The list of slots ends at the first item < 1.

Item categories (`g_ItemTable +0`) seen in presets: 0 body, 1 head, 2 hair, 3 mouth, 4 eyes, 5/6 hands, 7/8 shoes (left/right), 14 mouth wear, 15 neckwear, 18 top, 19 pants.

### Street pack (walking-around look)

CDATA.XAF entry preset + 7 = 8 texture chunks (copies of DATA.XAF textures) then the mesh (type `0x10`). The chunks are in `g_StreetTextures` order: `3561, 4529, 4729` (shared by every male street model), **skin**, **face/body atlas**, **pants**, **top**, **hair**; then `-1, 0`. Textures are cached by name, and DATA.XAF and CDATA.XAF share the name table, so a DATA texture loaded beforehand under its own id replaces the pack's chunk when the id is put in the list (what `new_characters.c` does).

## Parts found

### Bodies (fight, slot 0)

| Item | Textures | From preset | Notes |
|---|---|---|---|
| 195 | 1479 1479 1304 1377 1304 1377 676 988 1250 | 56 | large build, light skin (Eggusz) |
| 195 | 1503 1503 1324 1381 1324 1381 748 1060 1258 | 89 | large build, darker skin |
| 192 | 1503 1503 1094 1464 1324 1463 749 858 1258 | 63 | Jason G |

Body build params (preset `+0x318` p0, p1): 56 = (1, 6), 89 = (3, 7), 63 = (3, 6).

### Heads (fight, category 1)

Five textures: eyes, nose, then mouth/chin twice. The 4th/5th decide facial hair.

| Item | Textures | From preset | Look |
|---|---|---|---|
| 84 | 24 24 120 336 336 | 56 | light skin, **black mustache** (Eggusz) |
| 80 | 30 30 118 359 359 | 55 | mustache |
| 17 | 63 63 138 481 481 | 89 | clean-shaven, darker |

Other mouth/chin textures with facial hair seen (not yet tried on a head): 231 (preset 49), 6530 (79), 378 (88), 335 (93).

### Hair (fight, category 2)

| Item | Texture | Look |
|---|---|---|
| 23 | 1650 | **bald** (scalp; preset 55) |
| 23 | 1669 | short blond (preset 89) |
| 23 | 1649 | short dark (preset 56) |

Bald scalps also: 1639, 1661. The editor's HAIRSTYLE:BALD is item 23.

### Tops (fight, category 18)

| Item | Texture | Look |
|---|---|---|
| 208 | 3419 | **red leather jacket** (preset 89; Eggusz) |
| 209 | 2493 | (preset 56) |
| 231 | 4205 | (preset 55) |
| 390 | 7489 | Jason G's vest |

Other top textures seen: 2493 black leather biker jacket (preset 56), 4205 brown vest, 2285 brown tweed, 5817 green, 5882 orange, 2062 white.

### Pants (fight, category 19)

| Item | Texture | Look |
|---|---|---|
| 227 | 5902 | **blue jeans** (preset 27; Eggusz) |
| 227 | 5898 | dark brown trousers (preset 89) |
| 222 | 4119, 5674 | green cargo, red trousers |
| 223 | 3539, 1832 | black jeans, brown |

### Shoes (fight, categories 7 and 8, one item per foot)

| Items | Texture | Look |
|---|---|---|
| 35 / 36 | 1870 | **black sneakers** (preset 89; Eggusz) |
| 35 / 36 | 1854 | black leather shoes |
| 155 / 156 | 5695, 5697 | black boots, brown boots |
| 35 / 36 | 5783 | red sneakers |
| 35 / 36 | 1871 | white sneakers |

### Street pack textures

| Kind | Id | Look |
|---|---|---|
| pack | 89 + 7 = 96 | large build, red jacket, blond short hair (Eggusz's base) |
| face/body atlas | 7567 | light skin, **black mustache** (preset 56) |
| face/body atlas | 7580, 7568, 7594, 6207, 3563 | others (7594 and 3563 with sunglasses) |
| pants | 4535 | **blue jeans** (64x128) |
| pants | 6462 | black jeans |
| top | 5236 | red leather jacket |
| top | 5190, 5185, 4585 | green leather, black leather, black jacket |
| hair | 1650, 1639, 1661 | bald |

A replacement must have the same size as the chunk it replaces (check with `bdkit.py tex`, which prints the size).
