// @section Aaron uses Ignacy's moveset and Chester's model (C version, one Aaron cheat at a time)
// @description The C rewrite of "Aaron uses Ignacy's moveset and Chester's model", built by tools/cmod.py. Aaron fights with Ignacy's style 0x0C and animation groups; fighter init loads Chester's outfit preset 23 whenever it builds Aaron (presets 78, 79, 153). Turn on only one Aaron cheat at a time, and restart the game after switching.
// @org 0x00216738
// @max 0x100
//
// Aaron's class row (row 33 of the class table): Ignacy's style and group list.
// @word 0x0050D8B4 0x0000000C
// @word 0x0050D8BC 0x0050D290
//
// Fighter init 0x0013B490 calls Preset_Get twice; both calls go through the mod.
// @jal 0x0013B54C Mod_PresetGet
// @jal 0x0013B55C Mod_PresetGet

#include "game.h"

#define PRESET_CHESTER 23

void *Mod_PresetGet(int preset, int part)
{
    if (preset == 78 || preset == 79 || preset == 153)  /* Aaron's three presets */
        preset = PRESET_CHESTER;
    return Preset_Get(preset, part);
}
