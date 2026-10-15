// @section Debug: 128 MB RAM probe (sandbox only)
// @description Sandbox test helper, not a mod: every frame adds 1 to the word at 0x02000000 (above the PS2's 32 MB) and copies it to 0x000F0004. If 0x000F0004 keeps counting up, the game can use PCSX2's extended RAM (EmuCore ExtraMemory = true). Turn on with python tools/pcsx2.py cheats --c tools/debug/ram128_probe.c
// @org 0x000DF100
// @max 0x100
// @hook MissionMgr_Task Dbg_ProbeTask

#include "game.h"

void orig_MissionMgr_Task(void *task);

#define HIGH_WORD ((volatile u32 *)0x02000000)   /* first word past 32 MB */
#define REPORT ((volatile u32 *)0x000F0004)      /* debug scratch RAM, readable over PINE */

#define TICKS ((volatile u32 *)0x000F0008)       /* counts calls, before touching high RAM */

void Dbg_ProbeTask(void *task)
{
    *TICKS = *TICKS + 1;
    *HIGH_WORD = *HIGH_WORD + 1;
    *REPORT = *HIGH_WORD;
    orig_MissionMgr_Task(task);
}
