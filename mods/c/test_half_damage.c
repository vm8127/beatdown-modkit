// @section C mod test: the player takes half damage (hook, mod area, globals)
// @description Test for tools/cmod.py's @hook, the mod area 0x000A0000 and @bss globals. Every hit on the player (fighter slot 0) does half damage, at least 1; the damage it would have done and the damage it did are added up at 0x000E0000 and 0x000E0004 (read them with tools/pcsx2.py r32 0x000E0000 2). Can be on with any other cheat.
// @org 0x000A0000
// @max 0x100
// @bss 0x000E0000 0x10
// @hook Fighter_ApplyDamage My_ApplyDamage

#include "game.h"

void orig_Fighter_ApplyDamage(Fighter *fighter, int damage);

static int damage_in;   /* 0x000E0000: damage the player would have taken */
static int damage_out;  /* 0x000E0004: damage the player took */

void My_ApplyDamage(Fighter *fighter, int damage)
{
    damage = (s16)damage;  /* the game uses the low 16 bits */
    if (fighter == &g_Fighters[FIGHTER_PLAYER] && damage > 0) {
        damage_in += damage;
        damage = damage / 2 > 0 ? damage / 2 : 1;
        damage_out += damage;
    }
    orig_Fighter_ApplyDamage(fighter, damage);
}
