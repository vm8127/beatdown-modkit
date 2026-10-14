/* Beat Down (SLUS-21150) game interface for mods written in C (tools/cmod.py).
 *
 * Every name in symbols/symbols.tsv is available to the linker at its game address, so declaring it
 * here (or in your mod) with the right type is enough to call or read it. Add prototypes here as
 * functions get understood; the comment column in symbols.tsv and decomp/funcs/ say what they take.
 *
 * Calls: arguments 1-8 go in a0-a7 as in the game's own code. Stick to int and pointer arguments
 * when calling game functions; float arguments are assigned differently by this compiler (n32)
 * than by the game's compiler once ints and floats are mixed.
 */
#ifndef BEATDOWN_GAME_H
#define BEATDOWN_GAME_H

typedef signed char s8;
typedef unsigned char u8;
typedef short s16;
typedef unsigned short u16;
typedef int s32;
typedef unsigned int u32;

#define NULL ((void *)0)

/* Outfit presets (CDATA.XAF entry 0) */
#define PRESET_PART_SLOTS 1   /* -> outfit slots (+0) */
#define PRESET_PART_PARAMS 2  /* -> body params (+0x318) */
void *Preset_Get(int preset, int part);

/* Text and names */
const char *Text_Get(int text_id, int zero);
const char *Fighter_DisplayName(int person_id);
void *Person_Get(int person_id);

/* C library inside the game */
void *memcpy(void *dst, const void *src, u32 size);
void *memset(void *dst, int byte, u32 size);

#endif
