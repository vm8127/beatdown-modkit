# Mod plan: negotiation menu on knockout

Status: **v1 tested 2026-10-13; test v2 (CANCEL = normal knockout) built and tested the same day**. The pnach section is now `Negotiation menu on knockout (test v2)` (v1 plus the CANCEL fix). (pnach section `Negotiation menu on knockout (test v1)`). Plan first Written 2026-10-13 from README.md, docs/MECHANICS.md, docs/CODEMAP.md, docs/CUTCONTENT.md and a short look at the ELF. Addresses marked **probably** were found while writing this and are not traced fully.

## What the mod would do

Today you open negotiation by hand: wear an enemy's Pride Gauge down to 0, press the threaten button near them, then pick from a menu. The fight stops while you do it, and Pride refills if you wait too long.

With the mod you just fight. When you knock out an enemy that the game would let you negotiate with, the knockout doesn't finish them. Instead the negotiation menu opens on them, the same menu the threaten button opens:

| Choice | Result (vanilla behaviour, unchanged) |
|---|---|
| RECRUIT | they join you as an ally |
| ROB | you get money ("YOU GOT MONEY") |
| INTERROGATE | you get info (missions and shop leads need this) |
| BEATDOWN | the game's own BEATDOWN outcome, unchanged |
| CANCEL (or backing out) | **a normal knockout**: the enemy goes down as if the mod weren't there |

Cancelling is the way to get a plain knockout. Enemies you can't negotiate with go down as normal. The threaten button keeps working, so you can still negotiate early by hand.

## How the game works today (from our notes)

- **Pride Gauge** (MECHANICS.md, "Pride Gauge and negotiation"): current Pride is a float at fighter `+0x4420`, max at `+0x4424`, from person `+0x3A6`. Every landed hit and every taunt takes Pride off (`Fighter_PrideDamage` `0x002FB8D0`, `Fighter_SubPride` `0x002FBAE0`).
- **Negotiation**: when the gauge is 0 you press the threaten button (tutorial text `0x7655`, "use ▽ to negotiate"; in-game this is Circle). A successful negotiation wins the fight.
- **Menu text** (CDATA.XAF entry 386, found for this plan): battle menu `0x2710` NEGOTIATION, `0x2711` ESCAPE, `0x2712` CHANGE, `0x2713` CANCEL; negotiation choices `0x2714` RECRUIT, `0x2715` ROB, `0x2716` INTERROGATE, `0x2717` BEATDOWN; banner `0x28CE` "NEGOTIATION OK!"; `0x28C9` "TRY AGAIN?", so a negotiation can fail.
- **Pride comes back** (**probably**, found for this plan): `0x00313F90` (uses `Fighter_GetPride` `0x002F8C00`) restarts a timer when Pride hits 0 and refills it from `Fighter_SetGuard` `0x002FB780` when the timer runs out. That is the "you waited too long" window.
- **Damage and KO**: `Combat_ResolveHit` `0x00305CC0` → `Combat_TakeHit` `0x0030DFD0` → `Fighter_ApplyDamage` `0x002FB880` (HP at fighter `+0x441C`). The knockout is decided somewhere after this; not traced yet.

## Who counts as "recruitable"

Max Pride is **not** the filter: 488 of the 602 person templates have 100 Pride and only one has 0 (dumps/persons.txt), so almost everyone has a gauge. Whether you may negotiate is decided by the fight (story bosses, scripted mission fights, VS mode, tournament), not the person. The mod must reuse the game's own "can I threaten this enemy now?" check, so it opens the menu exactly where the threaten button would work. Finding that check is the first job.

## Choices for Daniel

Defaults marked; each is a small switch in the patch.

1. **Does Pride still matter?** Settled: the default (Daniel, 2026-10-13).
   - **Default: a knockout counts as breaking Pride**, so the menu opens on every negotiable knockout. Simple and always works.
   - Strict: the menu opens only if Pride was already 0 when they went down; otherwise they just lose. Keeps the Pride mechanic, but the mod will trigger less often because Pride refills.
2. **Group fights.** Settled: Daniel says you can't threaten in group fights (up to 3 enemies). Because the mod reuses the game's own threaten check, group-fight knockouts stay normal knockouts. Confirm this when the check is traced.
3. **Failed negotiation** ("TRY AGAIN?"). **Default: keep the vanilla retry**; answering NO (or cancelling) gives the normal knockout, same as CANCEL. Alternative: a fail goes straight to the normal knockout.

## What the code does (traced 2026-10-13)

Read from the ELF; not run yet. `g_Battle` is the battle context pointer at `gp-20356` (`0x005FFC6C`).

- **Battle state machine** `Battle_Update` `0x002DD500`: state at `g_Battle +0x10`. State 0 is the fight. When a side goes down, `Battle_OnFighterDown` `0x002E2F60` records it (`+0xB8`) and the fight moves to state 2 with the winner at `+0x60` and the loser at `+0x64`.
- **After a knockout** (state 2): if the player lost with Pride at 0 the game starts the beg scene. Otherwise, if `Battle_CanTalkAfterKO` `0x002E38D0` passes (story mode, the loser is not a boss and not one of 8 ally people), it calls `Battle_StartTalk(1)` at `0x002DE478`: a short after-KO talk that ends the fight.
- **The threaten button** goes through `Battle_RequestTalk` `0x002DE540` (called from the fighter input code at `0x0032482C`): it works when your target is DOWN or GUARDING, or during a threaten grab, and ends in `Battle_StartTalk(0)`.
- **The talk scene** `Talk_Update` `0x002DE850` runs both. Kind 0 opens the menu (`Talk_OpenMenu` `0x002E0150`, menu descriptor at `0x005990F0`) and branches on the choice (measured in PCSX2): RECRUIT 0 and ROB 1 -> step 1000, INTERROGATE 2 -> 1150, BEATDOWN 3 -> 1200, CANCEL 4 -> 1250. INTERROGATE and BEATDOWN check `Fighter_HasPride` `0x002FB120` on the target (1300/1350 and 1500/1550). CANCEL (step 1250) returns outcome 5, which resumes the fight (`g_Battle +0x9C` bit 0); with a knocked-out enemy that just reopens the menu. Kind 1 skips the menu and goes 1600, 1601, 800.
- **Pride bar shown** `Battle_PrideHudShown` `0x002E3A20`: not VS mode, game flag `0x0076EA90` bit 9 clear, the target's person record `+0x388` bit 31 clear, and battle type `0x0076EAA0` not 3 (probably group fights; Daniel says you can't threaten there).

## Test v1 (built)

The cheat changes the after-KO call at `0x002DE478` so that, when the Pride bar is shown, the after-KO talk is the threaten talk (kind 0) instead of kind 1. The loser's Pride is set to 0 first, so ROB and INTERROGATE take the empty-Pride branch.

```
0x002DE478  sw    zero,0x4420(s2)     loser's Pride = 0
0x002DE47C  jal   0x003E0168
0x002DE480  nop
0x002DE484  b     0x002DE48C          (the original "li v0,5; b; sh" tail)
0x003E0168  move  s1,ra               s1 is reloaded right after, so it's free here
0x003E016C  jal   Battle_PrideHudShown
0x003E0174  move  ra,s1
0x003E0178  j     Battle_StartTalk
0x003E017C  sltiu a0,v0,1             kind = 0 if the Pride bar is shown, else 1
```

What to check in PCSX2 (story mode, a 1-on-1 street fight with a Pride bar):

1. Knock the enemy out. Does the RECRUIT/ROB/INTERROGATE/BEATDOWN menu open?
2. Try each choice on a different enemy. Does RECRUIT add an ally, ROB give money, INTERROGATE give info?
3. BEATDOWN: what happens? The code resumes the fight in "beat down" mode, but this enemy is already at 0 HP.
4. Is there a way to back out of the menu (Triangle or X)? I didn't find a cancel in the code yet.
5. A boss and a group fight: these should end as normal knockouts with no menu.

## Test v1 results (PCSX2, 2026-10-13)

Story mode, 1-on-1 street fight with Miles (Pride bar shown), from Daniel's save state. The knockout was forced by setting Miles to 1 HP and refilling Aaron's HP in memory.

1. Knockout opens the NEGOTIATION menu: **yes**. Items are RECRUIT / ROB / INTERROGATE / BEATDOWN / CANCEL, with Miles lying KO'd.
2. RECRUIT: normal recruit scene, then "Add Miles to the party / Keep on call"; Miles joined the party. ROB: "Hand over your money!", haul only $3 (maybe the empty-Pride branch, maybe Miles is poor). INTERROGATE: an info note (the wharf crane). These three end with the normal BATTLE RESULT screen (EXP 12).
3. BEATDOWN: the finisher cutscene, then straight back to the street with Miles gone, no BATTLE RESULT; the star meter rose 21% to 79%. The fight did **not** resume with a 0-HP enemy, so that risk didn't happen.
4. Backing out: **doesn't work**. CANCEL reopens the same menu with the cursor on RECRUIT; Triangle, Circle, Start and Select do nothing.
5. Boss and group fights: not tested (no save state for one).

## Probe results (PCSX2, 2026-10-13)

- The menu descriptor is at `0x005990F0` (the widget at `B+0xEC` points to it from `B+0xFC`), not `0x005A90F0`. `+0xC` is the item Triangle jumps to; it is `0xFFFF` (none), which is why Triangle does nothing. Items are text ids 0x17, 0x18, 0x19, 0x1A, 0x1D.
- Cursor values: RECRUIT 0, ROB 1, INTERROGATE 2, BEATDOWN 3, CANCEL 4.
- CANCEL: step 1 -> 2 (choice 4) -> 1250 -> 0 -> 1 and the menu opens again on RECRUIT. ROB: step 1 -> 2 -> 1000 -> 1001 -> 1002.

## Test v2 (built)

```
0x002DEF70  j     0x00218F00          (the choice-4 branch of step 2)
0x00218F00  jal   Fighter_IsAlive     a0 = s1, the target
0x00218F08  beqz  v0,ko
            (alive: the vanilla CANCEL code, then step 1250)
ko:         sw    1, g_Battle+0x6C    talk kind 1 (after-KO talk)
            sb    zero,-18196(gp)     clear the stored choice
            sw    zero,g_Battle+0x58
            step = 1600               the normal after-KO ending
0x005990FC  word 4                    Triangle jumps to CANCEL
```

So CANCEL on a knocked-out enemy (only the mod opens the menu on one) ends the fight like a normal knockout, and a manual threaten's CANCEL stays vanilla. The cave `0x00218F00`-`0x00218F40` is at the end of the unused library function whose start the roster uses.

What to check: CANCEL and Triangle after a knockout end the fight with the normal BATTLE RESULT; the other four choices still work; a manual threaten's CANCEL still resumes the fight.

## Test v2 results (PCSX2, 2026-10-13)

1. CANCEL after a knockout: steps 1 -> 2 -> (kind 1) -> 801 -> 803 -> 804 -> 805; the normal after-KO talk, BATTLE RESULT (EXP 12), back on the street. No loop, no freeze.
2. Triangle after a knockout: cursor jumps to CANCEL, then the same ending.
3. ROB ("Please! That's all I got, man.", BATTLE RESULT) and BEATDOWN (finisher scene) still work. RECRUIT and INTERROGATE not rechecked; v2 doesn't touch them.
4. Manual threaten (Miles alive, 3152 HP, Pride 0): CANCEL goes to step 1250 and the fight resumes, as in vanilla. Triangle now does the same (in vanilla it did nothing).

## What's left after the test

- **BEATDOWN** already keeps its vanilla meaning (tested); no change needed.
- Check why ROB paid only $3 (compare with a manual threaten on the same enemy).
- Add a `bdkit.py` command if the hook needs parameters (it doesn't yet).

## Risks

- A choice that resumes the fight (BEATDOWN) with the enemy already at 0 HP is the main unknown.
- Bosses and scripted fights are excluded by `Battle_CanTalkAfterKO`, and group fights by `Battle_PrideHudShown`.
- The cave uses the last 6 free words at `0x003E0168`; the Chester `swap-model` hook uses the 14 words before it, so both can be on. The new roster system uses `0x00216538` and doesn't touch these addresses.
