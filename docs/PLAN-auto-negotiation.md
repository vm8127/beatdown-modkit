# Mod plan: negotiation menu on knockout

Status: **idea, not built**. Written 2026-10-13 from README.md, docs/MECHANICS.md, docs/CODEMAP.md, docs/CUTCONTENT.md and a short look at the ELF. Addresses marked **probably** were found while writing this and are not traced fully.

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

1. **Does Pride still matter?**
   - **Default: a knockout counts as breaking Pride**, so the menu opens on every negotiable knockout. Simple and always works.
   - Strict: the menu opens only if Pride was already 0 when they went down; otherwise they just lose. Keeps the Pride mechanic, but the mod will trigger less often because Pride refills.
2. **Group fights.**
   - **Default: open on each negotiable knockout**, like threatening mid-fight does today. Needs a check in-game of what a success does to the enemies still standing.
   - Last enemy only: the menu opens only when the final enemy drops.
3. **Failed negotiation** ("TRY AGAIN?"). **Default: keep the vanilla retry**; answering NO (or cancelling) gives the normal knockout, same as CANCEL. Alternative: a fail goes straight to the normal knockout.

## How it would be built

A PCSX2 pnach section, same style as the Chester model mod (a hook into a code cave):

1. Hook the point where an enemy's HP reaches 0 from a hit (after `Fighter_ApplyDamage` `0x002FB880`, before the knockout state is set).
2. In the cave: if the fighter is an enemy, not already in negotiation, and the game's negotiation check passes, then set HP to 1, set Pride (`+0x4420`) to 0, and start negotiation on that fighter the same way the threaten button does.
3. Otherwise run the original code, so the knockout happens normally.
4. When the menu is cancelled (CANCEL `0x2713`, or backing out) for a fighter the mod held at 1 HP, finish the knockout: set HP to 0 and let the normal KO path run. BEATDOWN and the other choices are left to the game.

Code areas to trace first:

| What | Where | Status |
|---|---|---|
| Threaten button → negotiation start, and its availability check | not found yet; pad bits: Circle `0x200` (CUTCONTENT.md) | **next step** |
| Battle menu state machine (NEGOTIATION/ESCAPE/CHANGE/CANCEL) | `0x00300390`, menu context pointer at `gp-19936`, buffer `0x0071F3F0` (1568 bytes) | **probably** |
| Negotiation screens (RECRUIT/ROB/INTERROGATE/BEATDOWN, "NEGOTIATION OK!") | `0x001C2000`-`0x001C8000`, e.g. `0x001C6010` (called from `0x00301410`), `0x001C29F0` | **probably** |
| Pride refill timer | `0x00313F90` | **probably** |
| Where a knockout is decided | after `0x0030DFD0` | not traced |
| Where CANCEL / back-out closes the menu | inside the battle menu code above | not traced |
| Free space for the hook | the Chester mod uses `0x003E0130`; needs a separate spot | to pick |

## Risks

- Bosses whose defeat starts a cutscene or ends a chapter: the mod must leave these alone, which it will if the game's own check refuses negotiation there.
- The knockout animation and the menu could fight over the fighter's state; clamping HP before the KO state is set should avoid that.
- Throws and finishers that do big damage in one go must also take the hook path.
- VS mode and the tournament must stay untouched.

## Steps

1. Trace the threaten button to the negotiation start and its availability check. Add names to `symbols/symbols.tsv` and CODEMAP.md.
2. Trace where the knockout is decided.
3. Build the hook as a test pnach section and try it in PCSX2: a street fight, a mission fight, a group fight, a boss.
4. Settle the three choices above, then add the section to `mods/` and the README mod list with test results.
