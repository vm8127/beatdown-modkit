# Labels and comments for Beat Down (SLUS-21150). Run from Ghidra's Script Manager.
# @category BeatDown
from ghidra.program.model.symbol import SourceType
SYMS = [
    (0x00100008, 'func', '_start', 'ELF entry point'),
    (0x001107C8, 'func', 'scePrintf', 'Sony kernel debug print (also called kprintf; libc printf is 0x12CDF8)'),
    (0x0012BA38, 'func', 'memcpy', '(dst, src, size)'),
    (0x0012BBF0, 'func', 'memset', '(dst, byte, size)'),
    (0x00138D20, 'func', 'Graph_FindName', 'name -> GRAPH.XAF entry via g_GraphNames'),
    (0x00138DF0, 'func', 'Flags_SaveTo', 'copy 1024-byte event flag block to buffer'),
    (0x00138E00, 'func', 'Flags_LoadFrom', 'copy buffer to event flag block'),
    (0x00138E20, 'func', 'Flag_Get', '(n) bit n of g_EventFlags'),
    (0x00138E70, 'func', 'Flag_Set', '(n)'),
    (0x00138EC0, 'func', 'Flag_Clear', '(n)'),
    (0x0013A950, 'func', 'SaveData_Pack', '(buf) copy game state into the 0x36A74-byte save image'),
    (0x0013AAB0, 'func', 'SaveData_Unpack', '(buf) copy a save image back into game state'),
    (0x0013B490, 'func', 'Person_Init', '(slot, personDefId, temp) build a person record from g_PersonDefs'),
    (0x0013C5C0, 'func', 'Team_GetMember', '(side, i) -> person id from the team lists 0x76EAC8 (side 0) / 0x76EAD0 (side 1), s16 ending -1'),
    (0x0013C960, 'func', 'Person_Get', '(personId) -> person record; ids 0-199 direct, 200-209 looked up by +62'),
    (0x0013CA80, 'func', 'Fighter_DisplayName', 'hero presets get the hero name (found by the model-swap work)'),
    (0x0013CC70, 'func', 'Person_SetMoney', '(personId, value) clamps 0..99,999,999; player also updates g_TotalMoneyEarned'),
    (0x0013CDC0, 'func', 'Person_AddMoney', '(personId, delta) clamps 0..99,999,999'),
    (0x0013D000, 'func', 'Inventory_InitForHero', "clears g_Inventory and fills it from the hero's start list"),
    (0x0013DE00, 'func', 'Item_CodeToIndex', '(item code, qty) used by Inventory_InitForHero; code = category*100 + n'),
    (0x0013DF00, 'func', 'Criminal_AddLeadership', '(n) adds to the Leadership bonus 0x60D34C'),
    (0x0013DF20, 'func', 'Criminal_AddCash', '(n) adds to the Cash Flow bonus 0x60D34E'),
    (0x0013DF40, 'func', 'Criminal_AddCharisma', '(n) adds to the Charisma bonus 0x60D350'),
    (0x0013DF60, 'func', 'Criminal_AddCashScore', '(amount) 0x60D1A8 += amount / 1000 x {0,1,2,3}[difficulty]'),
    (0x0013DFE0, 'func', 'Criminal_Recalc', 'rebuilds Leadership, Cash Flow and Charisma (0-255) from counters and difficulty weights'),
    (0x00172BD0, 'func', 'StoryVar_Add', '(index, delta) adds to g_StoryVars[index], refusing to pass 99 or a total budget of 200'),
    (0x00176130, 'func', 'Fighter_FindNpcSlot', '(personId) -> slot 2..12 or -1'),
    (0x0019F370, 'func', 'Debug_HeadStart', 'story setup: only with debug switch 18, adds to about 70 g_StoryVars'),
    (0x001C5BA0, 'func', 'MoveList_Count', '(?, style) -> number of MOVE LIST lines (move list table 0x5CAB40)'),
    (0x001C5BF0, 'func', 'MoveList_NameText', '(?, style, line) -> move name text'),
    (0x001C5C00, 'func', 'MoveList_GetName', '(style, move index) -> text, via g_MoveListTable'),
    (0x001C5C30, 'func', 'MoveList_InputText', '(?, style, line) -> move input text'),
    (0x001C5C70, 'func', 'MoveList_Color', '(style, line) -> 1 for the second text colour'),
    (0x001C89A0, 'func', 'ScenePlayer_Main', 'cutscene player (SELECT SCENE/PLAYER/LANGUAGE, PLAY, EXIT); reached from the DEBUG menu and from MOVIE VIEWER'),
    (0x001D02B0, 'func', 'Pad_RemapButtons', 'raw pad bits -> game bits (Up 4, Down 8, Left 1, Right 2, Start 0x10, Select 0x20, Tri 0x40, X 0x80, Sq 0x100, O 0x200, L1 0x400, L2 0x800, R1 0x1000, R2 0x2000, L3 0x4000, R3 0x8000)'),
    (0x001D1810, 'func', 'Boot_LoadModules', 'loads cdrom0:\\MODULES\\MODULE.BIN'),
    (0x001D8CA0, 'func', 'MemCard_Step', 'memory card state machine, jump table 0x5CB2F0'),
    (0x001DA020, 'func', 'MemCard_SetupFiles', 'registers save dir BASLUS-21150XXX: system file 584 bytes, game file 0x36A74 bytes, icons'),
    (0x001DB720, 'func', 'Save_BuildGameFile', 'calls SaveData_Pack before the memory card write'),
    (0x001DD1F0, 'func', 'Load_ApplyGameFile', 'calls SaveData_Unpack after a memory card read'),
    (0x001DD370, 'func', 'MemCard_PrintVersion', '"CAPCOM RD3 Memory Card System Ver.1.11"'),
    (0x00216538, 'func', 'Unused_DmaGsUpload', 'library DMA/GS upload code nothing calls or points to; code cave for bdkit roster hooks'),
    (0x0029BA10, 'func', 'Xaf_OpenAll', 'opens all ten XAF archives'),
    (0x0029BC40, 'func', 'Xaf_QueueLoad', '(archive, entry, mode)'),
    (0x0029CD10, 'func', 'Xaf_LoadAnimation', 'chunk type 0x1B'),
    (0x0029ED70, 'func', 'Xaf_LoadAnimPack', 'STAGE.XAF pack plus ID list'),
    (0x002A5B80, 'func', 'Fighter_PickWeaponMove', 'uses the style and held weapon'),
    (0x002A63A0, 'func', 'Cmd_CheckCondition', "(fighter, command condition) -> 1 if the fighter's stat levels meet it"),
    (0x002A6720, 'func', 'Cmd_MatchSequence', '(fighter, input history, style cmd list) -> action ID or 0'),
    (0x002A68B0, 'func', 'Cmd_MatchSingle', '(fighter, input code, style cmd list, out) -> action ID or 0'),
    (0x002A85B0, 'func', 'Person_CheckOutfit', 'checks outfit slots against tables 0x5016D0/0x501860'),
    (0x002A8720, 'func', 'Preset_Get', '(preset, part) part 1 = outfit slots (+0), 2 = body params (+792); CDATA.XAF entry 0'),
    (0x002A89D0, 'func', 'Fighter_AssignPerson', '(slot, personId) sets class row, copies the 22 outfit slots, picks body'),
    (0x002AF450, 'func', 'Criminal_GetTitle', '-> title 0..27: 7 x (dominant score, 3 = balanced) + tier (thresholds 21/61/101/141/191/241)'),
    (0x002AF640, 'func', 'Criminal_GetTitleCategory', 'title -> 0..4 at gp-21540, probably the ending'),
    (0x002AFD60, 'func', 'Person_RecalcMaxHP', '(personId) max HP from base HP, level and bonuses, capped at 9999'),
    (0x002AFEE0, 'func', 'Battle_CalcExp', 'EXP for a fight: per enemy (lvl diff + 1)^2 + 30 (10 if weaker), plus bonus, cap 100'),
    (0x002B00F0, 'func', 'Battle_GiveExp', "adds the fight's EXP to the player and party; 100 EXP = 1 level, cap 50"),
    (0x002B2660, 'func', 'Battle_AddBonusExp', '(n) adds to the EXP bonus pool at gp-21468, cap 100'),
    (0x002DC1E0, 'func', 'Anim_ResetAll', 'frees every animation slot not marked resident, clears the group counts'),
    (0x002DC280, 'func', 'Anim_SetSlot', '(slot, data) stores a loaded animation; slot = anim id + 1'),
    (0x002DC2E0, 'func', 'Anim_IsLoaded', '(slot) -> g_AnimSlots[slot] != 0'),
    (0x002DC300, 'func', 'Anim_GetSlot', '(slot) -> animation data (+0xC float length)'),
    (0x002DC360, 'func', 'Anim_LoadGroup', 'one animation group'),
    (0x002DC550, 'func', 'Anim_LoadGroupList', '9999-terminated list'),
    (0x002DC680, 'func', 'Anim_LoadClassGroups', 'uses the class table group list'),
    (0x002DC790, 'func', 'Anim_UnloadGroup', '(group) drops one reference, frees animations nobody else holds'),
    (0x002DC880, 'func', 'Anim_UnloadGroupList', '(9999-terminated group list)'),
    (0x002DC990, 'func', 'Anim_UnloadClassGroups', "(class row) unloads the row's group list"),
    (0x002DD500, 'func', 'Battle_Update', 'battle state machine, state at g_Battle +0x10 (12 states, jump table 0x5CF240): 0 fight, 2 after a KO, 3-5 talk scene, 6 resume fight, 10 end'),
    (0x002DE540, 'func', 'Battle_RequestTalk', '(fighter, kind) threaten button: allowed when the target is DOWN or GUARD, or during threaten grabs; sets g_Battle +0x144 bit 4, +0x60 = fighter, +0x5C = kind'),
    (0x002DE6E0, 'func', 'Battle_StartTalk', '(kind) starts the talk scene: 0 = threaten (RECRUIT/ROB/INTERROGATE/BEATDOWN menu), 1 = after knocking out a non-boss, 3 = beg for your life'),
    (0x002DE850, 'func', 'Talk_Update', 'talk scene steps at g_Battle +0x12; returns an outcome code that Battle_Update turns into a result (table 0x5CF210)'),
    (0x002E0150, 'func', 'Talk_OpenMenu', 'builds the negotiation menu from 0x5A90F0 (kind 3 uses 0x5A9160)'),
    (0x002E0310, 'func', 'Talk_PollMenu', 'waits for a menu choice; the choice goes to g_Battle +0x94'),
    (0x002E2F60, 'func', 'Battle_OnFighterDown', '(fighter, flag) records the downed fighter at g_Battle +0xB8 and sets +0x144 bit 8'),
    (0x002E37E0, 'func', 'Battle_IsStoryTalkBattle', 'story mode, not VS, g_Battle +0x144 bit 1; the empty-Pride x1.2 damage condition'),
    (0x002E38D0, 'func', 'Battle_CanTalkAfterKO', '(winner, loser) story battle, loser not a boss and not one of 8 ally person ids'),
    (0x002E3A20, 'func', 'Battle_PrideHudShown', "Pride bars shown: not VS, not flag 0x200, target's person +0x388 bit 31 clear, battle type (0x76EAA0) not 3"),
    (0x002E9590, 'func', 'Options_SetMode', '(0 = title screen, 1 = pause menu) -> gp-20216, picks byte +26 or +27 of each option record'),
    (0x002F0900, 'func', 'Fighter_PlayMotion', '(fighter, anim id, start frame, end frame or -1, blend frames); motion id at +0x3FA4'),
    (0x002F8990, 'func', 'Fighter_IsAlive', 'HP > 0'),
    (0x002F8A30, 'func', 'Fighter_RemapAction', '(fighter, action) via class row +8 per-body remap table'),
    (0x002F8A60, 'func', 'Fighter_RemapActionNeg', 'negative IDs go through the remap table'),
    (0x002F8AB0, 'func', 'Player_GetAbilityLevel', '(fighter, 0..2) Stamina/Attack/Technique level for the player, 0 for others'),
    (0x002F8BA0, 'func', 'Fighter_GetHP', ''),
    (0x002F8BB0, 'func', 'Fighter_GetMaxHP', ''),
    (0x002F8BC0, 'func', 'Fighter_GetHPRatio', ''),
    (0x002F8C00, 'func', 'Fighter_GetPride', '(fighter) -> float fighter +0x4420'),
    (0x002F8C20, 'func', 'Fighter_GetPrideRatio', 'Pride / max Pride'),
    (0x002F8C80, 'func', 'Fighter_GetPos', 'copies xyz at +0x2AC'),
    (0x002F8DC0, 'func', 'Person_GetBody', 'body size from the class row'),
    (0x002F8E00, 'func', 'Fighter_GetStyle', 'class row +4'),
    (0x002F8E20, 'func', 'Fighter_GetWeaponMoveList', 'weapon type x style -> weapon move list'),
    (0x002F9250, 'func', 'Fighter_GetPerson', 'Person_Get(fighter+8)'),
    (0x002F9260, 'func', 'Fighter_GetPersonDef', '-> g_PersonDefs entry'),
    (0x002F9930, 'func', 'Person_GetHeroDefId', "maps a hero preset to the hero's PersonDef (68 Aaron, 107 Raven, 108 Gina, 53 Jason G, 22 Lola)"),
    (0x002F9BE0, 'func', 'Fighter_IsPartyMember', "true when the fighter's person is in g_Party"),
    (0x002F9F30, 'func', 'Person_IsBoss', '(fighter) template +0x0D == 5; bosses take weapon power / 3'),
    (0x002FA150, 'func', 'Fighter_IsAttacking', '(fighter) state +0x4378 == 2 (ATTACK)'),
    (0x002FA170, 'func', 'Fighter_IsReeling', '(fighter) state +0x4378 & 0x1E0 (damage states)'),
    (0x002FA180, 'func', 'Fighter_IsHolding', '(fighter) state +0x4378 == 4 (HOLD)'),
    (0x002FB120, 'func', 'Fighter_HasPride', '1 when Pride is not 0'),
    (0x002FB780, 'func', 'Fighter_SetGuard', '(fighter, max, value)'),
    (0x002FB880, 'func', 'Fighter_ApplyDamage', '(fighter, dmg) HP -= dmg, floor 0; skipped while +0x471C bit 13 is set'),
    (0x002FB8D0, 'func', 'Fighter_PrideDamage', '(defender, base, attacker) Pride loss per hit: base + 30..39, x style %, + 10 - 20 x HP%, x (1 + 0.2 Technique)'),
    (0x002FBAE0, 'func', 'Fighter_SubPride', '(fighter, amount) fighter +0x4420 -= amount, floor 0'),
    (0x002FD300, 'func', 'Fighter_FindByPerson', '(personId) -> fighter or 0, slots 0..12'),
    (0x00301CD0, 'func', 'Action_LoadMtd', 'loads "%s/%04d.mtd" and registers it with Action_Register'),
    (0x00301D80, 'func', 'Action_Register', 'fills g_ActionScripts/Hits/Events for one action from a loaded record (ref count 0x7228E0)'),
    (0x003020E0, 'func', 'Debug_PrintAt', 'debug text helper'),
    (0x00302260, 'func', 'Debug_FighterInfo', 'debug overlay: HP, DAMAGE, TIRED, REV, LENGTH, motion category'),
    (0x00304B60, 'func', 'Fighter_Spawn', '(slot, target, team) HP from person, attack multiplier, difficulty scaling'),
    (0x00305CC0, 'func', 'Combat_ResolveHit', '(attacker, defender, ...) computes damage into defender +0x44B0'),
    (0x00307E40, 'func', 'Fighter_StartAction', "(fighter, action); negative ids go through the class row's remap table"),
    (0x0030DFD0, 'func', 'Combat_TakeHit', 'applies pending damage, knockdown meter, calls Fighter_ApplyDamage'),
    (0x00313F90, 'func', 'Fighter_PrideRegen', 'refills Pride from a timer after it hits 0'),
    (0x00314D30, 'func', 'Combat_SituationFactor', '(defender, attacker, &factor, &flag) low HP x0.8/x0.5, counter x1.5, combo scaling, hold x1.5'),
    (0x00317BC0, 'func', 'Style_GetCommandList', '(style) -> g_StyleCommands[style]'),
    (0x00317BE0, 'func', 'Style_GetWeaponCommandList', '(weapon kind 0..27) -> command list'),
    (0x00317E50, 'func', 'MoveList_IsLearned', "(fighter, style, line) -> 0 if a command gated on this line isn't learned yet"),
    (0x0031B210, 'func', 'HpBar_Build', "(side) builds one side's HP bar, one name line per team member; called from 0x3184D4; jal Fighter_DisplayName at 0x31B3E4 (hooked by bdkit roster)"),
    (0x0031F120, 'func', 'Fighter_SetAction', '(fighter, action, ?) starts an action from g_ActionScripts'),
    (0x0031F650, 'func', 'Action_Next', '(fighter, action) chain to the next action; -3 and other negatives are special cases'),
    (0x0031FAE0, 'func', 'Action_Step', "runs the fighter's motion script (+0x3FD4) until it plays a motion or ends"),
    (0x003340D0, 'func', 'Debug_ShopSelect', '"[SELECT SHOP]" debug shop picker'),
    (0x0033D7A0, 'func', 'Title_Main', 'title screen state machine (27 states, jump table 0x5D78B0)'),
    (0x0033E980, 'func', 'Title_DrawMenu', 'draws the 5 title menu items'),
    (0x00340020, 'func', 'DebugMenu_Draw', 'draws the DEBUG menu'),
    (0x00340220, 'func', 'DebugMenu_Main', 'cut DEBUG menu: SCENE PLAYER, LANGUAGE, EXIT (records 0x5899E0)'),
    (0x003404B0, 'func', 'VsMode_CharacterSelect', '"CHARACTER SELECT"'),
    (0x003409C0, 'func', 'VsMode_StageSelect', '"STAGE SELECT"'),
    (0x00340C60, 'func', 'VsMode_Main', 'VS MODE screen (title items VS MODE NORMAL/CUSTOM); calls VsMode_CharacterSelect/StageSelect and SaveData_Unpack. Was named SaveLoadScreen'),
    (0x00348020, 'func', 'Weapon_RollLoss', 'chance % = 0x5D7D90[class] + template +0x28 - 10 x Technique; probably weapon break'),
    (0x0034BE50, 'func', 'ZenFS_OpenXafIndex', ''),
    (0x0034C0A0, 'func', 'ZenFS_OpenArchive', ''),
    (0x0034C330, 'func', 'ZenFS_Open', ''),
    (0x0034C510, 'func', 'ZenFS_GetXAFStatus', ''),
    (0x0034C5E0, 'func', 'ZenFS_GetStatus', ''),
    (0x0034C640, 'func', 'ZenFS_GetSize', ''),
    (0x0034C760, 'func', 'ZenFS_GetNumRead', ''),
    (0x0034C7C0, 'func', 'ZenFS_Close', ''),
    (0x0034D2D0, 'func', 'ZenAudio_GetSoundStatus', ''),
    (0x0034EA50, 'func', 'zenGetIOPReply', ''),
    (0x00387760, 'func', 'Text_LoadLanguage', 'localized text from CDATA entries 385-432'),
    (0x00387980, 'func', 'Text_Get', '(text id) -> string'),
    (0x0039BA00, 'func', 'Debug_GetSwitch', '(n) -> g_DebugSwitches[n] != 0'),
    (0x003A4F40, 'func', 'Script_LoadEventList', 'loads SCRIPT.XAF entry 1000+n into 0x76F100'),
    (0x003B7400, 'func', 'DebugLanguage_Main', 'debug LANGUAGE screen: sets g_SystemData+0x10, cursor limited to 2 of 6 languages'),
    (0x003C0D50, 'func', 'Ability_ApplyAttack', 'sets player attack rank (person +0x51) from the Attack ability level'),
    (0x003E0130, 'data', 'CodeCave_SwapModel', '20 unused zero words before the VU microcode; used by bdkit swap-model'),
    (0x00411ACC, 'data', 'g_ScriptOpcodes', '118 x 20 bytes {char* name, id, argc, ?, char* argtypes}: EXF_* script commands'),
    (0x00413130, 'data', 'g_PersonDefs', '602 x 72-byte person templates (heroes, enemies, NPCs)'),
    (0x004F2400, 'data', 'g_ItemTable', '488 x 52 bytes: {u32 category, u32 ?, u32 flags, u32 use handler, u16 icon?, s16 parts[...] -1}'),
    (0x004FB4C0, 'data', 'g_AnimGroups', '317 x 8 bytes: {s16 STAGE.XAF entry, s16 0, s16* anim IDs}'),
    (0x00509A20, 'data', 'g_MinHpByDifficulty', 'float[4] {0, 0.5, 0.2, 0.2}, fraction of max HP, probably what allies keep after a fight'),
    (0x00509D90, 'data', 'g_OptionPages', 'option menu pages of 16 x 32-byte records, 0x200 apart; +20 default, +26 shown from the title screen, +27 shown from the pause menu'),
    (0x0050B990, 'data', 'g_ActionRemap_M', 's16 per action ID, medium body (class row +8)'),
    (0x0050BDE0, 'data', 'g_ActionRemap_L', 's16 per action ID, large body'),
    (0x0050C230, 'data', 'g_ActionRemap_S', 's16 per action ID, small body'),
    (0x0050D6A0, 'data', 'g_ClassTable', '51 x 16 bytes: {body, style, action remap ptr, group list ptr}, row = type - 1'),
    (0x00515C10, 'data', 'g_StyleCommands', 'one pointer per style 0x01-0x24: list of {cond ptr, sequence ptr}, sequence ptr 0 ends'),
    (0x00580A40, 'data', 'g_ActionHits', '2004 pointers: per action, 16-byte hit records (+8 u16 base damage, +14 u16 flags)'),
    (0x00582990, 'data', 'g_ActionEvents', '2004 pointers: per action, 16-byte event records starting with a handler address'),
    (0x005848E0, 'data', 'g_ActionScripts', '2001 x {u32 motion script, u32 second stream}; Fighter_SetAction copies them to fighter +0x3FD4/+0x3FD8 (docs/ANIMATION.md)'),
    (0x00589680, 'data', 'g_TitleMenuItems', '5 x {s16 element, s16 enabled, s16 action, s16 0}, then -1; action indexes g_TitleMenuJump'),
    (0x00589710, 'data', 'g_TitleMenuDebugStrings', 'ASCII fallback labels (PRESS START BUTTON ... OPTIONS, DEBUG) used when a text id is 0'),
    (0x00589740, 'data', 'g_TitleMenuTextIds', 'u16 text id per label index; index 7 (DEBUG) is 0'),
    (0x00589760, 'data', 'g_TitleMenuElements', '8 x 20 bytes {float x, float y, float scale, u16 label index, u16 0, u32 colour ptr}; element 7 = DEBUG at y 403'),
    (0x005899E0, 'data', 'g_DebugMenuItems', '3 x 24 bytes {u32 scene func, float x, float y, float scale, u16 text id, u16 0, u32 colour ptr}'),
    (0x00589A30, 'data', 'g_VsStages', '7 stage ids ending -999'),
    (0x00589A40, 'data', 'g_VsRoster', '84 fighter IDs ending -999 (heroes, bosses, enemies)'),
    (0x00589AF0, 'data', 'g_CharTypeNames', '52 string pointers (UNKNOWN, BOXER_S, ...)'),
    (0x00599000, 'data', 'g_DebugSwitches', '48 x u32 compile-time switches, nothing writes them; 5 = developer debug mode'),
    (0x005AB0D0, 'data', 'g_GraphNames', '602 x {u32 0, char* name}: names of GRAPH.XAF entries'),
    (0x005AC3A0, 'data', 'g_LanguageNames', '6 x {u16 text id 0x294D-0x2952, u16 0}: JAPANESE, ENGLISH, FRANCE, GERMANY, SPAIN, ITALY'),
    (0x005CAB40, 'data', 'g_MoveListTable', '47 x {u16 first input text, u16 last, u16 first name text, u16 last}'),
    (0x005D04D0, 'data', 'g_AttackRankMul', 'float[7] {0.5, 1.0, 1.3, 1.6, 1.8, 1.9, 2.0}, indexed by person +81'),
    (0x005D04F0, 'data', 'g_EnemyDamageByDifficulty', 'float[4] {1.0, 0.8, 1.0, 1.5}, indexed by g_SystemData +4'),
    (0x005D0650, 'data', 'g_HitSituation', '6 rows x 3 floats: base, HP<1000, HP<300, counter, combo (start, step, min), hold'),
    (0x005D4250, 'data', 'g_StylePrideMul', 'byte per style: Pride damage percent (Boxer 120, Negotiator 150, Carlo 200...), see MECHANICS.md'),
    (0x005D7890, 'data', 'g_TitleMenuJump', '6 handlers: NEW GAME, LOAD GAME, VS NORMAL, VS CUSTOM, OPTIONS (state 17), DEBUG (0x33DE38 -> DebugMenu_Main)'),
    (0x005D7D90, 'data', 'g_WeaponLossChance', 'two byte[4] tables {0,25,50,100}, {0,20,50,80} by weapon class (item +126)'),
    (0x005FB170, 'data', 'g_AbilityPointsPerLevel', 'byte per player level: 3 points for levels 2-50'),
    (0x005FB1A8, 'data', 'g_AbilityThresholds', '{6,12,17,23,25} points spent for ability level 1-5'),
    (0x005FEA70, 'data', 'g_AttackLevelToRank', '{1,2,3,4,5,6}: Attack ability level -> attack rank'),
    (0x005FEBD0, 'data', 'g_Party', 's16 person IDs of the party (saved, 8 bytes)'),
    (0x005FFC6C, 'data', 'g_Battle', "pointer to the battle context (gp-20356): +4/+8 the two sides' fighters, +0x10 state, +0x12 talk step, +0x60 winner/talker, +0x64 loser, +0x6C talk kind, +0x144 flags"),
    (0x005FFDD8, 'data', 'g_PresetData', 'pointer to CDATA.XAF entry 0 in RAM: 189 presets x 1176 bytes'),
    (0x005FFE30, 'data', 'g_DebugOverlayOn', 'u8, switch 5 fighter overlay shown (toggled by L2+R2)'),
    (0x005FFE44, 'data', 'g_DebugOverlayPage', 'u8, switch 5 overlay page 0-9 (L2+L3)'),
    (0x0060A680, 'data', 'g_EventFlags', '1024 bytes = 8192 story/event flags (saved)'),
    (0x0060B6E0, 'data', 'g_SaveBlock_365AC', '1024 bytes (saved)'),
    (0x0060BAE0, 'data', 'g_SaveBlock_369AC', '200 bytes (saved)'),
    (0x0060BE10, 'data', 'g_SaveBlock_357B0', '56 bytes (saved)'),
    (0x0060BE50, 'data', 'g_SaveBlock_35FF4', '156 bytes (saved)'),
    (0x0060BEF0, 'data', 'g_Inventory', '2052 bytes: u32 count, u32 items[512] (bits 0-11 item, 12-15 qty) (saved)'),
    (0x0060C700, 'data', 'g_SystemData', '584 bytes: the system save file (options, unlocks); +4 difficulty, +0x10 language'),
    (0x0060C704, 'data', 'g_Difficulty', 'byte in g_SystemData, indexes g_EnemyDamageByDifficulty'),
    (0x0060C710, 'data', 'g_Language', 'byte in g_SystemData, passed to the move list text lookups'),
    (0x0060C990, 'data', 'g_StoryVars', '128 x s16 script variables, 0-99, saved (save block 0x36090); read by the script VM at 0x39D2B0'),
    (0x0060CA90, 'data', 'g_SaveBlock_34EE0', '2256 bytes (saved)'),
    (0x0060D16C, 'data', 'g_Records', 's32 counters shown on the RECORDS screen (1 on 1 wins, group wins, murders, fled...), see MECHANICS.md'),
    (0x0060D19C, 'data', 'g_TotalMoneyEarned', 's32, grows when the player gains money'),
    (0x0060D346, 'data', 'g_CrimLeadership', 's16 0-255'),
    (0x0060D348, 'data', 'g_CrimCashFlow', 's16 0-255'),
    (0x0060D34A, 'data', 'g_CrimCharisma', 's16 0-255'),
    (0x0060D352, 'data', 'g_AbilityPointsSpent', '3 bytes: Stamina, Attack, Technique points spent (0-25)'),
    (0x0060D355, 'data', 'g_AbilityLevel', '3 bytes: Stamina, Attack, Technique level (0-5)'),
    (0x0060D360, 'data', 'g_Persons', '210 x 1084-byte person records; 0 = the player; 0-199 are saved'),
    (0x0060D3A0, 'data', 'g_PlayerMoney', 's32 = g_Persons[0] +0x40'),
    (0x00685450, 'data', 'g_Pad1', 'pad 1 state: +4 held, +8 newly pressed (game bits); pad 2 at 0x6854D0'),
    (0x006C55F0, 'data', 'g_AnimSlots', 'u32[0x6D1]: loaded animation per slot (anim id + 1)'),
    (0x006C7140, 'data', 'g_AnimSlotRefs', 'u8 per slot: how many loaded groups hold it'),
    (0x006C7860, 'data', 'g_AnimGroupRefs', 'u8[317]: how many times each animation group is loaded'),
    (0x006C79A0, 'data', 'g_AnimSlotResident', 'u8 per slot: loaded while the resident flag was on; Anim_ResetAll keeps it'),
    (0x006C8080, 'data', 'g_ClassGroupBuf', 'copy of the group list Anim_LoadClassGroups is loading'),
    (0x006CFB70, 'data', 'g_Fighters', 'fighters, 0x4730 bytes each; 0 = player, 2..12 = NPC slots'),
    (0x006D3F8C, 'data', 'g_Player_HP', 's16 = g_Fighters[0] +0x441C'),
    (0x006D3F8E, 'data', 'g_Player_MaxHP', 's16 = g_Fighters[0] +0x441E'),
    (0x0076F100, 'data', 'g_EventList', 'SCRIPT.XAF event list buffer'),
]
STRUCTS = [
    ('OutfitSlot', 36, 'one outfit slot: an item and the model parts it adds', [(0, 'u32', 'item', 'index into g_ItemTable'), (4, 's16[16]', 'parts', 'ARCHIVE.XAF part ids, ending -1')]),
    ('PresetParams', 384, "body parameters after a preset's 22 outfit slots", [(0, 's32', 'p0', 'copied to person +5'), (4, 's32', 'p1', 'copied to person +6'), (8, 's32', 'p2', 'copied to person +4'), (12, 's32', 'number', "the preset's own number"), (24, 's32', 'boss', '1 for boss presets; sets fighter flag 8')]),
    ('Preset', 1176, 'outfit preset (CDATA.XAF entry 0, 189 records), read through Preset_Get', [(0, 'OutfitSlot[22]', 'slots', 'copied to person +0x68 and fighter +0x3FF8'), (792, 'PresetParams', 'params', '')]),
    ('PersonDef', 72, 'person template, g_PersonDefs (602 records); Person_Init copies it into a person', [(4, 's16', 'preset', 'outfit preset: the model'), (6, 'u16', 'class_row', 'row in g_ClassTable: body, style, animation groups'), (8, 'u8', 'unk08', 'copied to the person record'), (13, 'u8', 'kind', '5 = story boss (Person_IsBoss); 2 is also tested'), (14, 's16', 'level', ''), (16, 's16', 'max_hp', ''), (18, 's16', 'pride', 'Pride Gauge max ("guard" in dumps/persons.txt)'), (21, 's8', 'attack_rank', 'index into g_AttackRankMul'), (24, 's32', 'money', ''), (40, 's32', 'weapon_break_mod', 'added to the weapon loss chance (heroes -20 to 0)'), (52, 'u8[16]', 'start_entries', 'two entries applied at spawn, probably weapons (copied to person +0x390)')]),
    ('Person', 1084, 'person record, g_Persons (210 records; 0 = the player; 0-199 are saved); Person_Get', [(0, 'u32', 'flags', ''), (58, 'u8', 'status', 'bit 1 = in hospital; 1 = probably in jail'), (62, 's16', 'id', 'person id (ids 200-209 are looked up by this)'), (64, 's32', 'money', '0-99,999,999'), (68, 's16', 'preset', 'outfit preset: the model'), (72, 's32', 'exp', '0-99; 100 = next level'), (76, 's16', 'level', '1-50'), (78, 's16', 'max_hp', 'cap 9999'), (81, 's8', 'attack_rank', 'index into g_AttackRankMul'), (82, 'u16', 'class_row', 'row in g_ClassTable (moveset)'), (84, 's16', 'hp', 'cap 9999'), (104, 'OutfitSlot[22]', 'outfit', 'copied from the preset'), (896, 's16', 'attack_percent', 'normally 100'), (898, 's16', 'bonus_max_hp', ''), (904, 'u32', 'flags388', 'bit 31 hides the Pride bar'), (912, 'u8[16]', 'start_entries', 'two entries applied at spawn (0x2FBC50), probably weapons'), (934, 's16', 'pride_max', 'Pride Gauge max'), (936, 'u8', 'ally_flags', 'bit 0 = ally (party or recruited)'), (948, 's16', 'bonus_max_hp2', 'added by Person_RecalcMaxHP')]),
    ('Fighter', 18224, 'fighter in a fight, g_Fighters (0 = player, 2-12 = NPC slots)', [(0, 'u32', 'flags', 'bit 0 active; bit 1 motion playing, bit 2 action running, bit 3 ready for the next motion'), (24, 'void*', 'unk18', 'CODEMAP said "in use"; holds a heap pointer (0x01694A20) in a fight'), (684, 'f32[3]', 'pos', 'position x, y, z'), (16292, 's16', 'motion', "current animation slot (anim id + 1; the overlay's MOT + 1)"), (16294, 's16', 'prev_motion', ''), (16296, 'f32', 'blend', 'blend time (seconds)'), (16340, 'u8*', 'motion_script', "current action's motion script (docs/ANIMATION.md)"), (16344, 'u8*', 'second_stream', "current action's second stream"), (16348, 'u8*', 'loop_start', 'motion script loop start'), (16352, 'f32', 'motion_start', 'motion start time (seconds)'), (16356, 'f32', 'motion_end', 'motion end time (seconds)'), (16360, 'f32', 'speed', 'playback speed (1.0)'), (16364, 's32', 'loop_count', 'motion script loop counter'), (16376, 'OutfitSlot[22]', 'outfit', "copy of the person's outfit"), (17196, 's16', 'weapon', 'held weapon item, -1 = none'), (17222, 's16', 'action', "current action id (the overlay's TASK)"), (17224, 's16', 'hit_action', 'attack action used for the hit lookup'), (17272, 'u32', 'state', '2 = ATTACK, 4 = HOLD, 0x1E0 = damage states'), (17288, 'u32', 'flags4388', '0x4000 = holding a weapon'), (17296, 'u8', 'flags4390', 'bit 2: armour or special state (no counter/combo scaling)'), (17428, 'f32', 'attack_mul', 'attack multiplier'), (17432, 'f32', 'defense_mul', 'defense multiplier, normally 1.0'), (17436, 's16', 'hp', ''), (17438, 's16', 'max_hp', ''), (17440, 'f32', 'pride', 'Pride Gauge'), (17444, 's16', 'pride_max', ''), (17446, 's16', 'stagger', 'damage/stagger meter, capped at max HP'), (17448, 's16', 'stagger_max', '500'), (17450, 's16', 'tired', 'tired meter'), (17452, 's16', 'tired_max', '1.5 x max HP'), (17460, 's16[6]', 'limb_pool', 'per-limb attack pool'), (17472, 's16[6]', 'limb_pool_max', ''), (17584, 's16', 'pending_damage', ''), (17592, 'f32', 'limb_fatigue', 'per-limb float lowered by 0.1 every 30 points used (array; length not known)'), (17646, 's16', 'hit_count', ''), (17678, 's16', 'combo_hits', 'combo count used for damage scaling'), (17692, 's16', 'rev', 'REV meter'), (17694, 's16', 'rev_max', ''), (17776, 'u8', 'hit_index', 'current hit within the action'), (18051, 'u8', 'target', 'target fighter slot'), (18112, 's32', 'class_row', 'class row (type id - 1); picks the remap table'), (18120, 's32', 'body', 'body size 0 S, 1 M, 2 L'), (18204, 'u32', 'flags471C', 'bit 13 = takes no damage')]),
    ('ClassRow', 16, 'g_ClassTable row (row = type id - 1): what a fighter class fights with', [(0, 'u32', 'body', '0 small, 1 medium, 2 large'), (4, 'u32', 'style', 'fighting style: picks g_StyleCommands[style]'), (8, 's16*', 'action_remap', 'g_ActionRemap_S/M/L'), (12, 's16*', 'groups', 'animation group ids ending 9999')]),
    ('CmdInput', 8, 'one input of a command sequence', [(0, 'u32', 'code', 'input code (0xFFFFFFFF ends the sequence)'), (4, 's16', 'action', 'action id; set on the last input only')]),
    ('Command', 8, "one command of a style's command list", [(0, 'u8*', 'condition', '16-byte unlock condition {u16 move list line, stat levels...}, 0 = always'), (4, 'CmdInput*', 'sequence', '0 ends the list')]),
    ('HitRecord', 16, 'one hit of an action (g_ActionHits)', [(0, 'u32', 'kind', ''), (4, 'u32', 'unk4', ''), (8, 'u16', 'damage', 'base damage'), (10, 'u16', 'unkA', ''), (12, 'u16', 'unkC', ''), (14, 'u16', 'flags', '')]),
    ('ActionScript', 8, 'g_ActionScripts entry; Fighter_SetAction copies it to fighter +0x3FD4', [(0, 'u8*', 'motion_script', ''), (4, 'u8*', 'second_stream', '')]),
    ('AnimGroup', 8, 'g_AnimGroups entry', [(0, 's16', 'stage_entry', 'STAGE.XAF entry'), (4, 's16*', 'anims', 'animation ids')]),
    ('ItemDef', 52, 'g_ItemTable entry (more fields further on: weapon class at +126 and +145 belong to another record)', [(0, 'u32', 'category', ''), (8, 'u32', 'flags', ''), (12, 'void*', 'use_handler', ''), (18, 's16[17]', 'parts', 'ARCHIVE.XAF part ids ending -1')]),
    ('Inventory', 2052, 'g_Inventory (saved)', [(0, 'u32', 'count', ''), (4, 'u32[512]', 'items', 'bits 0-11 item, 12-15 quantity')]),
    ('SystemData', 584, 'g_SystemData, the system save file (options, unlocks)', [(4, 'u8', 'difficulty', 'indexes g_EnemyDamageByDifficulty'), (16, 'u8', 'language', '0 JP, 1 EN, 2 FR, 3 DE, 4 ES, 5 IT')]),
    ('ScriptOpcode', 20, 'g_ScriptOpcodes entry: an EXF_* script command', [(0, 'char*', 'name', ''), (16, 'char*', 'arg_types', '')]),
    ('TitleMenuElement', 20, 'g_TitleMenuElements entry', [(0, 'f32', 'x', ''), (4, 'f32', 'y', ''), (8, 'f32', 'scale', ''), (12, 'u16', 'label', 'label index'), (16, 'u32*', 'colour', '')]),
    ('Battle', None, 'battle context, *g_Battle (docs/PLAN-auto-negotiation.md)', [(16, 's32', 'state', '0 = fighting, 2 = a side went down'), (88, 's32', 'unk58', 'cleared when the after-KO talk starts'), (96, 's32', 'winner', ''), (100, 's32', 'loser', ''), (108, 's32', 'talk_kind', '0 threaten menu, 1 after a knockout, 3 beg for your life'), (156, 'u32', 'flags9C', 'bit 0 = resume the fight'), (184, 's32', 'down', 'records a knockout (Battle_OnFighterDown)')]),
]
TYPES = [
    (0x001107C8, 'func', 'scePrintf', 'int (const char *fmt, ...)'),
    (0x0012BA38, 'func', 'memcpy', 'void *(void *dst, const void *src, u32 size)'),
    (0x0012BBF0, 'func', 'memset', 'void *(void *dst, int byte, u32 size)'),
    (0x00138D20, 'func', 'Graph_FindName', 'int (const char *name)'),
    (0x00138E20, 'func', 'Flag_Get', 'int (int n)'),
    (0x00138E70, 'func', 'Flag_Set', 'void (int n)'),
    (0x00138EC0, 'func', 'Flag_Clear', 'void (int n)'),
    (0x0013A950, 'func', 'SaveData_Pack', 'void (void *buf)'),
    (0x0013AAB0, 'func', 'SaveData_Unpack', 'void (void *buf)'),
    (0x0013B490, 'func', 'Person_Init', 'void (int slot, int person_def, int temp)'),
    (0x0013C5C0, 'func', 'Team_GetMember', 'int (int side, int i)'),
    (0x0013C960, 'func', 'Person_Get', 'Person *(int person_id)'),
    (0x0013CA80, 'func', 'Fighter_DisplayName', 'const char *(int person_id)'),
    (0x0013CC70, 'func', 'Person_SetMoney', 'void (int person_id, int value)'),
    (0x0013CDC0, 'func', 'Person_AddMoney', 'void (int person_id, int delta)'),
    (0x0013D000, 'func', 'Inventory_InitForHero', 'void (void)'),
    (0x0013DF00, 'func', 'Criminal_AddLeadership', 'void (int n)'),
    (0x0013DF20, 'func', 'Criminal_AddCash', 'void (int n)'),
    (0x0013DF40, 'func', 'Criminal_AddCharisma', 'void (int n)'),
    (0x0013DF60, 'func', 'Criminal_AddCashScore', 'void (int amount)'),
    (0x00172BD0, 'func', 'StoryVar_Add', 'int (int index, int delta)'),
    (0x00176130, 'func', 'Fighter_FindNpcSlot', 'int (int person_id)'),
    (0x001C5BA0, 'func', 'MoveList_Count', 's16 (int unused, int style)'),
    (0x001C5BF0, 'func', 'MoveList_NameText', 'const char *(int unused, int style, int line)'),
    (0x001C5C30, 'func', 'MoveList_InputText', 'const char *(int unused, int style, int line)'),
    (0x001C5C70, 'func', 'MoveList_Color', 'int (int style, int line)'),
    (0x0029BC40, 'func', 'Xaf_QueueLoad', 'int (int archive, int entry, int mode)'),
    (0x002A63A0, 'func', 'Cmd_CheckCondition', 'int (Fighter *fighter, u8 *condition)'),
    (0x002A6720, 'func', 'Cmd_MatchSequence', 's16 (Fighter *fighter, int *history, Command *list)'),
    (0x002A68B0, 'func', 'Cmd_MatchSingle', 's16 (Fighter *fighter, int code, Command *list, int *out)'),
    (0x002A8720, 'func', 'Preset_Get', 'void *(int preset, int part)'),
    (0x002A89D0, 'func', 'Fighter_AssignPerson', 'void (int slot, int person_id)'),
    (0x002AFD60, 'func', 'Person_RecalcMaxHP', 'void (int person_id)'),
    (0x002B2660, 'func', 'Battle_AddBonusExp', 'void (int n)'),
    (0x002DC2E0, 'func', 'Anim_IsLoaded', 'int (int slot)'),
    (0x002DC300, 'func', 'Anim_GetSlot', 'void *(int slot)'),
    (0x002DC790, 'func', 'Anim_UnloadGroup', 'int (int group)'),
    (0x002DC880, 'func', 'Anim_UnloadGroupList', 'void (int *groups)'),
    (0x002DE6E0, 'func', 'Battle_StartTalk', 'void (int kind)'),
    (0x002E2F60, 'func', 'Battle_OnFighterDown', 'void (Fighter *fighter, int flag)'),
    (0x002F0900, 'func', 'Fighter_PlayMotion', 'void (Fighter *fighter, int anim, int start_frame, int end_frame, int blend_frames)'),
    (0x002F8A30, 'func', 'Fighter_RemapAction', 's16 (Fighter *fighter, int action)'),
    (0x002F8A60, 'func', 'Fighter_RemapActionNeg', 's16 (Fighter *fighter, int action)'),
    (0x002F8AB0, 'func', 'Player_GetAbilityLevel', 'int (Fighter *fighter, int ability)'),
    (0x002F8BA0, 'func', 'Fighter_GetHP', 's16 (Fighter *fighter)'),
    (0x002F8BB0, 'func', 'Fighter_GetMaxHP', 's16 (Fighter *fighter)'),
    (0x002F8BC0, 'func', 'Fighter_GetHPRatio', 'f32 (Fighter *fighter)'),
    (0x002F8C00, 'func', 'Fighter_GetPride', 'f32 (Fighter *fighter)'),
    (0x002F8C20, 'func', 'Fighter_GetPrideRatio', 'f32 (Fighter *fighter)'),
    (0x002F8C80, 'func', 'Fighter_GetPos', 'void (Fighter *fighter, f32 *xyz)'),
    (0x002F8E00, 'func', 'Fighter_GetStyle', 'int (Fighter *fighter)'),
    (0x002F9250, 'func', 'Fighter_GetPerson', 'Person *(Fighter *fighter)'),
    (0x002F9260, 'func', 'Fighter_GetPersonDef', 'PersonDef *(Fighter *fighter)'),
    (0x002F9F30, 'func', 'Person_IsBoss', 'int (Fighter *fighter)'),
    (0x002FA150, 'func', 'Fighter_IsAttacking', 'int (Fighter *fighter)'),
    (0x002FA170, 'func', 'Fighter_IsReeling', 'int (Fighter *fighter)'),
    (0x002FA180, 'func', 'Fighter_IsHolding', 'int (Fighter *fighter)'),
    (0x002FB120, 'func', 'Fighter_HasPride', 'int (Fighter *fighter)'),
    (0x002FB780, 'func', 'Fighter_SetGuard', 'void (Fighter *fighter, int max, f32 value)'),
    (0x002FB880, 'func', 'Fighter_ApplyDamage', 'void (Fighter *fighter, int damage)'),
    (0x002FBAE0, 'func', 'Fighter_SubPride', 'void (Fighter *fighter, int amount)'),
    (0x002FD300, 'func', 'Fighter_FindByPerson', 'Fighter *(int person_id)'),
    (0x00304B60, 'func', 'Fighter_Spawn', 'void (int slot, int target, int team)'),
    (0x00307E40, 'func', 'Fighter_StartAction', 'void (Fighter *fighter, int action)'),
    (0x0030DFD0, 'func', 'Combat_TakeHit', 'void (Fighter *fighter)'),
    (0x00317BC0, 'func', 'Style_GetCommandList', 'Command *(int style)'),
    (0x00317BE0, 'func', 'Style_GetWeaponCommandList', 'Command *(int weapon_kind)'),
    (0x00317E50, 'func', 'MoveList_IsLearned', 'int (Fighter *fighter, int style, int line)'),
    (0x0031B210, 'func', 'HpBar_Build', 'void (int side)'),
    (0x0031F120, 'func', 'Fighter_SetAction', 'void (Fighter *fighter, int action)'),
    (0x0031F650, 'func', 'Action_Next', 'int (Fighter *fighter, int action)'),
    (0x0031FAE0, 'func', 'Action_Step', 'void (Fighter *fighter)'),
    (0x00387980, 'func', 'Text_Get', 'const char *(int text_id, int zero)'),
    (0x0039BA00, 'func', 'Debug_GetSwitch', 'int (int n)'),
    (0x00411ACC, 'data', 'g_ScriptOpcodes', 'ScriptOpcode[118]'),
    (0x00413130, 'data', 'g_PersonDefs', 'PersonDef[602]'),
    (0x004F2400, 'data', 'g_ItemTable', 'ItemDef[488]'),
    (0x004FB4C0, 'data', 'g_AnimGroups', 'AnimGroup[317]'),
    (0x0050D6A0, 'data', 'g_ClassTable', 'ClassRow[51]'),
    (0x00515C10, 'data', 'g_StyleCommands', 'Command *[37]'),
    (0x00580A40, 'data', 'g_ActionHits', 'HitRecord *[2004]'),
    (0x005848E0, 'data', 'g_ActionScripts', 'ActionScript[2001]'),
    (0x00589760, 'data', 'g_TitleMenuElements', 'TitleMenuElement[8]'),
    (0x005D04D0, 'data', 'g_AttackRankMul', 'f32[7]'),
    (0x005D04F0, 'data', 'g_EnemyDamageByDifficulty', 'f32[4]'),
    (0x005FEBD0, 'data', 'g_Party', 's16[4]'),
    (0x005FFC6C, 'data', 'g_Battle', 'Battle *'),
    (0x005FFDD8, 'data', 'g_PresetData', 'Preset *'),
    (0x0060A680, 'data', 'g_EventFlags', 'u8[1024]'),
    (0x0060BEF0, 'data', 'g_Inventory', 'Inventory'),
    (0x0060C700, 'data', 'g_SystemData', 'SystemData'),
    (0x0060C990, 'data', 'g_StoryVars', 's16[128]'),
    (0x0060D19C, 'data', 'g_TotalMoneyEarned', 's32'),
    (0x0060D360, 'data', 'g_Persons', 'Person[210]'),
    (0x0060D3A0, 'data', 'g_PlayerMoney', 's32'),
    (0x006CFB70, 'data', 'g_Fighters', 'Fighter[13]'),
    (0x006D3F8C, 'data', 'g_Player_HP', 's16'),
    (0x006D3F8E, 'data', 'g_Player_MaxHP', 's16'),
]
for addr, kind, name, com in SYMS:
    a = toAddr(addr)
    if kind == 'func' and getFunctionAt(a) is None:
        disassemble(a)
        createFunction(a, name)
    createLabel(a, name, True, SourceType.USER_DEFINED)
    if com:
        setPlateComment(a, com)
print('Imported %d Beat Down symbols' % len(SYMS))

from ghidra.program.model.data import (ArrayDataType, ByteDataType, CategoryPath, CharDataType,
    DataTypeConflictHandler, FloatDataType, FunctionDefinitionDataType, IntegerDataType, LongLongDataType,
    ParameterDefinitionImpl, PointerDataType, ShortDataType, SignedByteDataType, StructureDataType,
    UnsignedIntegerDataType, UnsignedLongLongDataType, UnsignedShortDataType, VoidDataType)
from ghidra.app.cmd.function import ApplyFunctionSignatureCmd
import re

dtm = currentProgram.getDataTypeManager()
CAT = CategoryPath("/BeatDown")

# The ELF's zero-initialized globals (0x005FEB00-0x00788180) get no memory block from the loader, so
# Ghidra can't type or follow them; map them as an uninitialized read/write block.
mem = currentProgram.getMemory()
pos, gaps = 0x005FEB00, []
for blk in sorted(mem.getBlocks(), key=lambda b: b.getStart().getOffset()):
    lo, hi = blk.getStart().getOffset(), blk.getEnd().getOffset() + 1
    if hi <= pos or lo >= 0x00788180:
        continue
    if lo > pos:
        gaps.append((pos, lo))
    pos = max(pos, hi)
if pos < 0x00788180:
    gaps.append((pos, 0x00788180))
for i, (lo, hi) in enumerate(gaps):
    b = mem.createUninitializedBlock(".bss%s" % (i or ""), toAddr(lo), hi - lo, False)
    b.setRead(True)
    b.setWrite(True)
    print("mapped .bss %08X-%08X" % (lo, hi - 1))
PRIM = {"s8": SignedByteDataType.dataType, "u8": ByteDataType.dataType, "char": CharDataType.dataType,
        "s16": ShortDataType.dataType, "u16": UnsignedShortDataType.dataType, "s32": IntegerDataType.dataType,
        "u32": UnsignedIntegerDataType.dataType, "f32": FloatDataType.dataType, "s64": LongLongDataType.dataType,
        "u64": UnsignedLongLongDataType.dataType, "void": VoidDataType.dataType, "int": IntegerDataType.dataType}

def resolve(t):
    t = t.replace("const ", "").strip()
    m = re.match(r"^(\w+)\s*(\**)\s*(?:\[(\w+)\])?$", t)
    base, ptr, count = m.group(1), len(m.group(2)), m.group(3)
    dt = PRIM.get(base) or dtm.getDataType(CAT, base)
    for _ in range(ptr):
        dt = PointerDataType(dt, 4, dtm)
    if count:
        dt = ArrayDataType(dt, int(count, 0), dt.getLength())
    return dt

for name, size, com, fields in STRUCTS:
    end = size or max(o + 1 for o, _, _, _ in fields)
    s = StructureDataType(CAT, name, end, dtm)
    s.setDescription(com)
    dtm.addDataType(s, DataTypeConflictHandler.REPLACE_HANDLER)
for name, size, com, fields in STRUCTS:
    s = dtm.getDataType(CAT, name)
    for off, t, field, fcom in fields:
        dt = resolve(t)
        if size is None and off + dt.getLength() > s.getLength():
            s.growStructure(off + dt.getLength() - s.getLength())
        s.replaceAtOffset(off, dt, dt.getLength(), field, fcom or None)

def apply_func(addr, name, proto):
    i = proto.index("(")
    fd = FunctionDefinitionDataType(name)
    fd.setReturnType(resolve(proto[:i]))
    params = []
    for a in proto[i + 1:proto.rindex(")")].split(","):
        a = a.strip()
        if a in ("", "void"):
            continue
        if a == "...":
            fd.setVarArgs(True)
            continue
        m = re.match(r"^(.*?)(\w+)$", a)
        params.append(ParameterDefinitionImpl(m.group(2), resolve(m.group(1)), None))
    fd.setArguments(params)
    ApplyFunctionSignatureCmd(toAddr(addr), fd, SourceType.USER_DEFINED).applyTo(currentProgram)

typed = 0
for addr, kind, name, proto in TYPES:
    try:
        if kind == "func":
            apply_func(addr, name, proto)
        else:
            dt = resolve(proto)
            a = toAddr(addr)
            clearListing(a, a.add(dt.getLength() - 1))
            createData(a, dt)
        typed += 1
    except Exception as e:
        print("type for %s not applied: %s" % (name, e))
print("Applied %d structs and %d symbol types" % (len(STRUCTS), typed))
