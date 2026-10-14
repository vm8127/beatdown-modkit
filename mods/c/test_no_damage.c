// @section C mod test: the player takes no damage (hook, mod area, globals)
// @description Test for tools/cmod.py's @hook, the mod area 0x000A0000 and @bss globals. Hits on the player (fighter slot 0) do no damage; how many hits and how much damage were blocked are added up at 0x000E0000 and 0x000E0004 (read them with tools/pcsx2.py r32 0x000E0000 2). Can be on with any other cheat.
// @org 0x000A0000
// @max 0x100
// @bss 0x000E0000 0x10
// @hook Fighter_ApplyDamage My_ApplyDamage

#include "game.h"

void orig_Fighter_ApplyDamage(Fighter *fighter, int damage);

static int hits_blocked;    /* 0x000E0000 */
static int damage_blocked;  /* 0x000E0004 */

void My_ApplyDamage(Fighter *fighter, int damage)
{
    damage = (s16)damage;  /* the game uses the low 16 bits */
    if (fighter == &g_Fighters[FIGHTER_PLAYER] && damage > 0) {
        hits_blocked++;
        damage_blocked += damage;
        damage = 0;
    }
    orig_Fighter_ApplyDamage(fighter, damage);
}
