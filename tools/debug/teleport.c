// @section Debug: teleport (sandbox only)
// @description Sandbox test helper, not a mod: write an area id + 1 to 0x000F0000 (python tools/pcsx2.py w32 0x000F0000 18 for area 17) and the next frame the player is sent there, the way EXF_MOVE_STAGE does. Ids are in docs/UNLOCKS.md, "Location ids". Turn on with python tools/pcsx2.py cheats --c tools/debug/teleport.c
// @org 0x000DF000
// @max 0x100
// @hook MissionMgr_Task Dbg_MissionMgrTask

#include "game.h"

void orig_MissionMgr_Task(void *task);

#define TELEPORT_REQUEST ((volatile int *)0x000F0000)   /* debug scratch RAM (docs/mods/MEMORY-MAP.md) */

void Dbg_MissionMgrTask(void *task)
{
    int to = *TELEPORT_REQUEST;
    if (to > 0) {
        *TELEPORT_REQUEST = 0;
        Area_ChangeTo(Area_Current(), to - 1);
    }
    orig_MissionMgr_Task(task);
}
