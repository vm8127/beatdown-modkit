# Game mechanics: how the numbers work

What the game's stats and meters do, with the formulas as the code computes them. This builds on `CODEMAP.md` (where things live) and is about what they mean in play. All addresses are EE addresses as PCSX2 shows them; ELF offset = address - 0x100000 + 0x80.

**Status words**: **read** means the formula was taken straight from the code. **Probably** means the code was read but what it is for in play is a guess. Nothing here has been tested in-game yet.

`difficulty` below is the byte at `0x0060C704` (g_SystemData +4): 1 = EASY, 2 = NORMAL, 3 = HARD (labels at `0x509CF0`). DIFFICULTY is an option in the title-screen OPTIONS (seen in-game 2026-10-13), but not in the pause menu (see [Difficulty](#difficulty)); the default is NORMAL. Many tables are 4 entries long and indexed by it, so entry 0 is unused.

## Contents

1. [The stats you see](#the-stats-you-see)
2. [Level and EXP](#level-and-exp)
3. [Ability points: Stamina, Attack, Technique](#ability-points-stamina-attack-technique)
4. [Damage](#damage)
5. [Pride Gauge and negotiation](#pride-gauge-and-negotiation)
6. [Other fight meters](#other-fight-meters)
7. [Weapons](#weapons)
8. [Difficulty](#difficulty)
9. [Criminal Level and titles](#criminal-level-and-titles)
10. [Records](#records)
11. [Things only described in the game's text](#things-only-described-in-the-games-text)
12. [Mod cheat sheet](#mod-cheat-sheet)
13. [Corrections to CODEMAP.md](#corrections-to-codemapmd)
14. [Open leads](#open-leads)

## The stats you see

| On screen | What it is in memory | Section |
|---|---|---|
| LEVEL | person `+0x4C` (player `0x0060D3AC`), 1-50 | [Level and EXP](#level-and-exp) |
| EXP / NEXT LEVEL | person `+0x48` (player `0x0060D3A8`), 0-99; 100 = next level | [Level and EXP](#level-and-exp) |
| LIFE | fighter `+0x441C` / `+0x441E` in a fight, person `+0x54` / `+0x4E` outside | [Damage](#damage) |
| POINTS, STAMINA, ATTACK, TECHNIQUE | ability screen; levels at `0x0060D355-0x0060D357` | [Ability points](#ability-points-stamina-attack-technique) |
| Pride Gauge | fighter `+0x4420` (float) / max `+0x4424`; template "guard" | [Pride Gauge](#pride-gauge-and-negotiation) |
| Cash on hand | person `+0x40` (player `0x0060D3A0`) | CODEMAP: People |
| CRIMINAL LEVEL: LEADERSHIP/TEAMWORK, CASH FLOW/ITEMS, CHARISMA, TITLE | `0x0060D346`, `0x0060D348`, `0x0060D34A` | [Criminal Level](#criminal-level-and-titles) |

The column `guard` in `dumps/persons.txt` is the **Pride Gauge** maximum, not a block stat.

## Level and EXP

**Read.** `Battle_GiveExp` `0x002B00F0` runs after a fight and gives every party member the same EXP.

EXP for one defeated enemy (`Battle_CalcExp` `0x002AFEE0`, up to 3 enemies per fight):

```
if enemy level < player level:  base = 10
else:                           base = (enemy level - player level + 1)^2 + 30
exp  = (base + bonus/10) x enemy factor
```

- `bonus` is the u16 at gp-21460 (`0x005FF994`), reset after each fight; what fills it is not traced yet.
- `enemy factor` is 1.0 unless a script set one (`0x002B26A0` stores it in tenths at `0x005FD5B0 + slot`).
- The fight total also adds a bonus pool (gp-21468 `0x005FF98C`, filled by `Battle_AddBonusExp` `0x002B2660`, capped at 100), then is **capped at 100**. So one fight never gives more than one level.
- On difficulty 1 (EASY) the total is multiplied by 1.2. That is what the code says; it looks backwards, so treat it with care.

Levelling up: EXP is stored per person at `+0x48`. When it reaches 100, 100 is taken off, level `+0x4C` goes up by 1 and `Person_RecalcMaxHP` `0x002AFD60` runs. The cap is level 50. The player and the two party members in `g_Party` (`0x005FEBD2`, `0x005FEBD4`) all level this way.

Examples at equal level: an enemy 1 level below gives 10, same level 31, 2 above 39, 5 above 66, 8 or more above hits the 100 cap.

Max HP when levelling:

- **Player** (person 0): `max HP = template HP + Stamina bonus + (level - 1) x 30 + person +0x3B4`. So +30 max HP per level.
- **Everyone else**: `max HP = template HP + (level - template level) x 80 + person +0x3B4`. Allies gain +80 per level.
- Both are capped at 9999. Current HP rises by the same amount.

## Ability points: Stamina, Attack, Technique

**Read.** The ability screen (`0x003BE280` onwards) spends points on three abilities.

| Address | What |
|---|---|
| `0x0060D352`, `0x53`, `0x54` | points spent on Stamina, Attack, Technique (bytes, 0-25) |
| `0x0060D355`, `0x56`, `0x57` | Stamina, Attack, Technique **level** (bytes, 0-5) |
| `0x005FB170` | points gained per level: `table[level]` = 3 for levels 2-50 |
| `0x005FB1A8` | `{6, 12, 17, 23, 25}`: total points spent to reach ability level 1, 2, 3, 4, 5 |
| gp-21380 `0x005FF96C` | the last player level already turned into points |

You get **3 points per level-up** (levels 2-50, so 147 in total) and can hold at most 30 unspent. Each ability levels at 6, 12, 17, 23 and 25 points spent, so maxing all three costs 75 points, which you have by level 26.

What each level does:

| Level | Stamina: extra max HP | Attack: attack rank, damage | Technique: Pride damage, weapon break chance |
|---|---|---|---|
| 0 | +0 | rank 1, x1.0 | x1.0, +0 |
| 1 | +300 | rank 2, x1.3 | x1.2, -10 |
| 2 | +800 | rank 3, x1.6 | x1.4, -20 |
| 3 | +1500 | rank 4, x1.8 | x1.6, -30 |
| 4 | +2400 | rank 5, x1.9 | x1.8, -40 |
| 5 | +3500 | rank 6, x2.0 | x2.0, -50 |

- **Stamina** `n`: extra max HP = `n x (100n + 200)`, added in `Person_RecalcMaxHP`.
- **Attack** `n`: `0x003C0D50` writes `{1,2,3,4,5,6}[n]` (table at `0x005FEA70`) into the player's attack rank (person `+0x51`), which picks the damage multiplier from `g_AttackRankMul` `0x005D04D0`. So Attack only matters at spawn time, through the rank.
- **Technique** `n`: Pride damage you deal is multiplied by `1 + 0.2n` (`0x002FBA60`), and the chance of losing your weapon drops by `10n` percentage points (`0x00348020`, see [Weapons](#weapons)). Only the player gets this; `Player_GetAbilityLevel` `0x002F8AB0` returns 0 for anyone else.

## Damage

**Read.** `Combat_ResolveHit` `0x00305CC0` (attacker, defender). Every step truncates to a whole number; the `+ 0.01` keeps 1.0 multipliers exact.

```
dmg = hit base damage                                  hit record +8 (dumps/commands.txt)
    + weapon power                                     only while holding a weapon (item data +96)
dmg = trunc(dmg x attacker attack multiplier + 0.01)   fighter +0x4414
dmg = trunc(dmg x defender defense multiplier + 0.01)  fighter +0x4418, normally 1.0
dmg = trunc(dmg x situation factor + 0.01)             Combat_SituationFactor 0x00314D30
if defender's Pride is 0 and condition 0x2E37E0 holds: dmg = trunc(dmg x 1.2 + 0.01)
dmg = at least 1
```

Then `Combat_TakeHit` `0x0030DFD0` takes it off HP with `Fighter_ApplyDamage` `0x002FB880` (nothing happens while fighter `+0x471C` bit 13 is set), and also hits the Pride Gauge (next section).

**Attack multiplier** (set once in `Fighter_Spawn` `0x00304B60`):

```
attack multiplier = g_AttackRankMul[attack rank] x person +0x380 / 100 x (enemies only) g_EnemyDamageByDifficulty[difficulty]
g_AttackRankMul           0x005D04D0 = {0.5, 1.0, 1.3, 1.6, 1.8, 1.9, 2.0}   rank 0-6
g_EnemyDamageByDifficulty 0x005D04F0 = {-, 0.8, 1.0, 1.5}                    EASY, NORMAL, HARD
```

The player's rank comes from the Attack ability; everyone else's from their template (`+0x15`).

**Weapon power**: added to the base damage before any multiplier. Against a boss (template `+0x0D` = 5: the story versions of Gregolio, Zanetti, Fatima, Wendel, Eugene, Ignacy, Quincy, Warrez, Chester) weapon power is divided by 3 (`Person_IsBoss` `0x002F9F30`). A weapon with item byte `+145` set makes the whole hit do exactly 1 before the multipliers.

**Situation factor** (`0x00314D30`, table `g_HitSituation` `0x005D0650`, rows of 3 floats; only the first column is used). The factors multiply together, top to bottom:

| Condition (defender) | Factor | Probably |
|---|---|---|
| HP below 1000 | x0.8 | low-HP protection |
| HP below 300 (instead of the line above) | x0.5 | stronger low-HP protection |
| state is ATTACK (fighter `+0x4378` = 2) | x1.5 | counter hit: hit while attacking |
| state is one of the damage states (`+0x4378` & 0x1E0) | x max(0.8 - 0.1 x combo hits, 0.3) | combo scaling, combo count at fighter `+0x450E` |
| state is HOLD (`+0x4378` = 4) | x1.5 | hit while grabbing someone |
| fighter `+0x4390` bit 2 | reset to x1.0 | an armour or special state |

The low-HP rows mean a fighter under 300 HP takes half damage, which makes the last bit of a life bar last longer. The counter-hit and hold rows also set a flag the hit effects use.

State values, from the debug overlay's names: 1 NORMAL, 2 ATTACK, 4 HOLD, 8 PROVOCATION (taunt), 0x10 DOWN, 0x20 ATTACK DAMAGE, 0x40 HOLD DAMAGE, 0x100 OTHER DAMAGE, 0x200 GUARD, 0x400 DOWN DAMAGE.

Example: Aaron's Triple Snake Fang (250 base) at Attack level 0, on a full-HP enemy, no counter: 250. At Attack level 5: 500. As a counter hit at level 5: 750. With a combo count of 3 at level 5: 500 x 0.5 = 250.

**Hit records, field by field** (read from `Combat_ResolveHit` and `Combat_TakeHit` `0x0030DFD0`, 2026-10-15, for the remake; not tested in-game). `g_ActionHits[action]` is best read as an 8-byte header followed by 16-byte records that overlap the next slot of the old 16-byte view (`codemap.py hits` prints that view):

| Bytes | What |
|---|---|
| header +0 `u32` | attack kind bits (2 for every strike checked; bit 0x400 is tested by the command handler) |
| header +4 `u16` | **cost**: added to the TIRED meter when the action starts (`Fighter_StartAction` `0x00307E40`); +6 `u8` a grab-target mask (tested against the defender's `+0x4393` while holding) |
| record +0 `u16` | base damage (the `+8` above) |
| record +2 `u8` / `u8` | Pride damage base (`Fighter_PrideDamage`) / a strength 1-4 (byte +11; not traced) |
| record +4 `u16` | reaction detail: bits 0x10 / 0x20 / 8 / 4 pick the stagger variant for high hits and the direction of the low ones |
| record +6 `u16` | **hit level**: 2 high, 4 mid, 8 low. A defender with status bit 2 dodges high hits, status bit 4 dodges low hits (`flags & 8`) |
| record +8 `u32` | **reaction** (the `kind` of the next 16-byte slot): 0x20 knocks down (also on a KO), 0x10, 0x100, 0x200, 0x400, 0x800, 0x1000 pick the big reactions (reaction kinds 8, 0xE, 0xD, 0xF, 0x14, 0x15; they also make the victim drop a held weapon), 0x40 special reactions by level (0x3E3-0x3E6), anything else (1, 8) a normal stagger chosen by the level and the detail bits |

Hit records are indexed by the timeline's op 0x30 (`+0x4570`), so a multi-hit move like Aaron's Moonlight Combo (1820) uses record 0 (100, reaction 0x100) then record 1 (250, reaction 0x200). Aaron's own examples: Blade Cut 100 high, reaction 8 (stagger); Low Kick (↓K) 100 low; Triple Snake Fang 250 mid, reaction 0x10 (big); Heel Strike's second hit 700, reaction 0x20 (down).

**Aaron's counter**: in `Combat_ResolveHit`, a defender with style 0x13 whose current action is 0x24B-0x24D (Weaving / Sway Back, `→G ←G ↑G`) and who passes `Cmd_CheckCondition(0x005CFBA0)` turns a **mid** hit (level 4) into his counter (remapped action 0x1EA): the move list's "Breezethrough (COUNTER MID-LEVEL MOVE)". Style 0x10 has the same rule for actions 0x24C, 0x24D and 0x664.

The remake (`remake/godot/game/fighter/fighter.gd`, `damage_from`) uses this formula with placeholder stats (attack rank 1, 100 %, defense 1.0, 3000 HP) and treats "damage state" as hitstun or airborne after a knockdown, with the combo count = hits taken so far in the combo (0 for the first). Hitstun, hitstop and knockback aren't in these records (they come from the reaction animations): the remake derives placeholders from the strength byte.

## Pride Gauge and negotiation

**Read**, except where marked. What CODEMAP calls "guard" is the Pride Gauge from the tutorial text ("Diminish your foe's Pride Gauge to prepare for negotiation").

- Max Pride = person `+0x3A6`, from template `+0x12` (the heroes have 300; bosses 500-800). Current Pride is a float at fighter `+0x4420`, max at `+0x4424`.
- `Fighter_SubPride` `0x002FBAE0` takes Pride off, never below 0. Callers: every landed hit, taunts (`0x00311554`), and one more at `0x002DEE84`.

Pride damage per hit (`Fighter_PrideDamage` `0x002FB8D0`, defender, base, attacker):

```
p = hit record byte +10 + random(30..39)
p = trunc(p x g_StylePrideMul[attacker's style] / 100)            0x005D4250, percent per style
p = p + trunc(10 - 20 x defender HP / defender max HP)            +10 at 0 HP, -10 at full HP
p = max(p, 0)
p = p + trunc(p x 0.2 x Technique level)                         player only
```

`g_StylePrideMul` per style: Boxer 120, Grappler 120, Knuckle Master 100, Juggler 100, Kickboxer 100, Strider 90, Weapon Master 90, Negotiator 150, Raven 120, Gina 120, Carlo 200, Melvin 120, everyone else 100. So Negotiators, Carlo and the boxing styles break Pride fastest.

A taunt (PROVOCATION) takes `Pride max x a factor` (`0x003114E0`; the factor comes from the taunt's data and wasn't traced).

How negotiation runs in the code (traced and tested for the negotiation-on-knockout mod, docs/mods/PLAN-auto-negotiation.md):

- Pride bars, and so threatening, only exist when `Battle_PrideHudShown` `0x002E3A20` passes: not VS mode, game flag `0x0076EA90` bit 9 clear, the target's person `+0x388` bit 31 clear, and battle type `0x0076EAA0` not 3 (probably group fights; you can't threaten there).
- The threaten button (`Battle_RequestTalk` `0x002DE540`) works when your target is down, guarding, or held in a threaten grab, and starts talk kind 0 (`Battle_StartTalk` `0x002DE6E0`). After a normal story knockout of a non-boss, the game plays talk kind 1 instead (`Battle_CanTalkAfterKO` `0x002E38D0`); kind 3 is "beg for your life".
- The menu (descriptor `0x005990F0`) has RECRUIT 0, ROB 1, INTERROGATE 2, BEATDOWN 3, CANCEL 4. RECRUIT and ROB go to talk step 1000, INTERROGATE 1150, BEATDOWN 1200, CANCEL 1250 (resumes the fight). INTERROGATE and BEATDOWN check `Fighter_HasPride` `0x002FB120` on the target. BEATDOWN plays a finisher scene and skips BATTLE RESULT (seen in-game).
- How much ROB pays isn't traced: Miles (Wharf street enemy) paid $3.

What empty Pride does, from the game's text: when the gauge is 0 you can press the threaten button to NEGOTIATE; a successful negotiation wins the fight and can give money, info or a new ally (RECRUIT). If **you** lose with your Pride at 0, you get the "Beg for your life?" choice: you go back to the hospital or clinic but may get Trauma. **Probably**: the x1.2 damage on an empty-Pride defender in the damage formula is part of this.

## Other fight meters

These are shown by the unused debug overlay `Debug_FighterInfo` `0x00302260`.

| Meter | Fields | What the code does |
|---|---|---|
| DAMAGE | `+0x4426` / `+0x4428` (500) | **Read**: every hit adds its damage, capped at max HP. **Probably** the stagger meter: some reactions (`0x003119A0`) pick a heavier stagger once it passes half of `+0x4428`. It is not a knockdown threshold as CODEMAP said. |
| TIRED | `+0x442A` / `+0x442C` | **Read**: max = 1.5 x max HP. Each attack you start adds its cost (`0x003081C4`); it drains by 1 per frame down to a floor (`0x0030BBB8`). The tutorial says the Devastator tires you. What a full meter does wasn't traced. |
| REV | `+0x451C` / `+0x451E` | reversal meter; not traced |
| ATTACK (per limb) | `+0x4434[6]` / `+0x4440[6]` | **Read**: when your hit lands, the limb that hit loses a third of the damage from its pool, and every 30 points used lowers a per-limb float (`+0x44B8`) by 0.1, down to 0.5. **Probably** limb fatigue. |
| INJURY | `+0x46AA[]` / `+0x4692[]` | face L/R, body front/back, arms, legs; not traced |

## Weapons

**Read.** Holding a weapon sets fighter `+0x4388` bit `0x4000`, and the item is at `+0x432C`.

- Power: item data `+96` is added to each hit's base damage, divided by 3 against bosses (see [Damage](#damage)).
- Losing the weapon (`0x00348020` and `0x003486F0`, **probably** breaking or dropping it): each time it is checked, the chance in percent is

  ```
  chance = table[weapon class] + holder's template +0x28 - 10 x Technique level
  table  0x005D7D90 = {0, 25, 50, 100}   first check
         0x005D7D98 = {0, 20, 50, 80}    second check
  weapon class = item data +126
  ```

  The heroes' template `+0x28` is -20 (Aaron, Gina), -10 (Raven, Lola) or 0 (Jason G). With Technique 5 Aaron's chance drops by 70 points in total, so class 1 and 2 weapons never break.
- From the tutorial text: weapon attacks can't be blocked bare-handed, only with another weapon, or you can steal the attacker's weapon.

## Difficulty

`0x0060C704`, 1 = EASY, 2 = NORMAL, 3 = HARD. It is in the title-screen OPTIONS but not the pause menu. The options menu items are 32-byte records; the DIFFICULTY record at `0x509D90` (label `0x5CF550`, text id `0x232D`) has default value 2 (byte `+20`), but bytes `+24` and `+27` are 0 where the visible SUBTITLES and MAP records (`0x509DB0`, `0x509DD0`) have 1. Update (docs/CUTCONTENT.md): byte `+26` decides whether an item shows in the title-screen OPTIONS and `+27` in the pause-menu options (`Options_SetMode` `0x2E9590`). DIFFICULTY has `+26` = 1 and `+27` = 0: it is in the title-screen OPTIONS (seen in-game: left/right sets EASY, NORMAL, HARD) and only missing from the pause menu, which the cheat `Cut content: DIFFICULTY in the pause menu options` fixes (seen in-game). So the EASY and HARD values below are reachable in normal play. A pnach can also just set `0x0060C704`.

Everything indexed by it:

| What | EASY | NORMAL | HARD | Where |
|---|---|---|---|---|
| Enemy damage | x0.8 | x1.0 | x1.5 | `0x005D04F0` |
| EXP per fight | x1.2 | x1.0 | x1.0 | `0x002B0118` |
| A minimum HP (fraction of max) used after fights, **probably** what an ally is left with | 0.5 | 0.2 | 0.2 | `0x00509A20` |
| Criminal Level weights | see below | | | |

## Criminal Level and titles

**Read.** `Criminal_Recalc` `0x0013DFE0` rebuilds the three Criminal Level scores from counters, weights indexed by difficulty, and a bonus each that scripts can add to. Each score is clamped to 0-255. The game's text: "You are evaluated by 3 criteria and granted a Criminal Level... Your title will change depending upon fluctuations in your Criminal Level."

Weights below are EASY / NORMAL / HARD.

**LEADERSHIP/TEAMWORK** `0x0060D346`:

```
  allies (party plus recruited people, person +0x3A8 bit 0, you count)  x 1 / 2 / 3     0x0041DD40
+ average level of those allies                                          x 1 / 2 / 2     0x005FD070
- allies with person +0x3A = 1 (probably in jail)                        x 30 / 20 / 15  0x0041DD50
- counter at 0x0060D704 (probably abandoned members)                     x 20 / 15 / 10  0x0041DD60
+ bonus 0x0060D34C                                                       Criminal_AddLeadership 0x0013DF00
```

**CASH FLOW/ITEMS** `0x0060D348`:

```
  total money earned (0x0060D19C) / 1000                                 x 1 / 1 / 1     0x0041DD70
+ trunc(items owned (0x0013DD00) / 5                                     x 1.0 / 1.0 / 2.0)  0x0041DD80
+ running score 0x0060D1A8 (Criminal_AddCashScore 0x0013DF60 adds amount/1000 x 1 / 2 / 3)
- bail paid (0x0060D1A0) / 100                                           x 3 / 2 / 1     0x005FD030
- medical expenses (0x0060D1A4) / 100                                    x 3 / 2 / 1     0x005FD038
+ bonus 0x0060D34E                                                       Criminal_AddCash 0x0013DF20
```

`items owned` is how many of the item types listed at `0x00412F40` are in the inventory.

**CHARISMA** `0x0060D34A`:

```
  enemies defeated 1 on 1 (0x0060D16C)                                  x 1 / 2 / 3     0x005FD040
+ group enemies defeated (0x0060D170) / 5                               x 1 / 2 / 3     0x005FD048
+ opponents murdered (0x0060D174)                                       x 8 / 10 / 12   0x005FD050
- times fled (0x0060D178)                                               x 8 / 5 / 5     0x005FD058
- counter 0x0060D344 (bumped in the fight-result code at 0x002CB234)    x 20 / 15 / 10  0x005FD060
- counter 0x0060D342 (bumped at 0x002CBD58)                             x 8 / 5 / 3     0x005FD068
+ bonus 0x0060D350                                                      Criminal_AddCharisma 0x0013DF40
```

Charisma rewards winning, especially killing, on harder difficulties, and punishes running away. The two unnamed counters are **probably** begging for your life and losing.

**Title** (`Criminal_GetTitle` `0x002AF450`): each score is turned into a tier:

| Score | 0-20 | 21-60 | 61-100 | 101-140 | 141-190 | 191-240 | 241-255 |
|---|---|---|---|---|---|---|---|
| Tier | 0 | 1 | 2 | 3 | 4 | 5 | 6 |

If all three tiers are equal, title = 21 + tier (a balanced title). Otherwise the highest score wins (ties go to Leadership, then Cash Flow) and title = 7 x (0 Leadership, 1 Cash Flow, 2 Charisma) + that score's tier. So there are 28 titles, 7 per kind.

`0x002AF640` turns the title into one of 5 categories, stored at gp-21540 (`0x005FF7CC`; gp is `0x00604BF0`): tier 3-6 Leadership → 0, tier 3-6 Cash Flow → 1, tier 3-6 balanced → 2, tier 3-6 Charisma → 3 or 4 (depends on `0x00396B70`), anything at tier 0-2 → 4. **Probably** this picks the ending; it is called from `0x002AE82C` and `0x0038F3B4`.

## Records

The RECORDS screen (`0x003C6FCC` onwards) reads these counters in the same order as its labels, so the names are **probably** right:

| Address | Record |
|---|---|
| `0x0060D16C` | Defeated 1 on 1 enemies |
| `0x0060D170` | Defeated group enemies |
| `0x0060D174` | Murdered opponents |
| `0x0060D178` | Number of times fled |
| `0x0060D17C` | Biggest combo |
| `0x0060D184` | Number of calls made |
| `0x0060D188` | Ally called most |
| `0x0060D18C` | Abandoned members |
| `0x0060D19C` | Accumulated cash (g_TotalMoneyEarned) |
| `0x0060D1A0` | Bail paid |
| `0x0060D1A4` | Medical expenses |

Hospital and clinic bills come from the facility's menu data (`+418` of the menu record), not from a formula; paying adds to Medical expenses and clears the patient's person `+0x3A` bit 1 (in hospital).

## Things only described in the game's text

Found in the UI text (CDATA.XAF entry 386) but not traced in code yet:

- **Status effects**: BAD TRIP (from drinking or cheap or experimental medicine; wears off with time or movement) and TRAUMA (from begging for your life; wears off with time or activity, or at once by beating the person who caused it). People refuse to deal with you while Traumatized. HEAL STATUS at a hospital or clinic cures both, and "dizzy".
- **Being spotted**: a percentage chance of being recognised that disguises (clothes, haircuts, plastic surgery) lower; over 100% you are spotted for sure. Hats aren't included in the shown number. Police recognise wanted criminals.
- **Ally skills**: PICKPOCKET, LOCKPICK, sells dope, MARTIAL ARTIST, CAR THIEF (shown in the ally list; set by script command EXF_SET_SKILL): bits of person `+0x388` (`EXF_SET_SKILL person, bit, on`); `EXF_CHECK_ABILITY` tests bits 0, 1, 2, 7, 4, 5 and 31 across the party (docs/SCRIPTS.md). Which bit is which skill isn't matched yet; the skill names are text 14532-14535 (PICKPOCKET, MARTIAL ARTIST, Specialty:, CAR THIEF).
- **Criminal Level ranks**: `Criminal_Rank` `0x003937C0` (1 Leadership, 2 Cash Flow, 3 Charisma) turns a 0-255 score into a rank: 0-20 = 0, 21-60 = 1, 61-100 = 2, 101-140 = 3, 141-190 = 4, 191-240 = 5, 241-255 = 6. Meeting the other heroes needs rank 2 (docs/UNLOCKS.md).
- **Game clears**: `g_ClearCount` `0x0060BADC` counts finished playthroughs (the ending adds 1); job 45 and events 0x5B, 0x5C need 1, 2 and 3. The playthrough after the ending keeps your money and the jobs-ever-cleared bits.
- **Items** (CDATA.XAF entry 392): CHICKEN restores all Pride and 1000 health, TURKEY restores all Pride and health, a PRIDE +16 item, an "increase attack power by 16" item, HEATDOWN, and fake cash that raises negotiation skill.

## Mod cheat sheet

Untested. RAM values (`0x006...`, `0x0060D...`) are rewritten by the game, so a pnach line that writes them every frame acts as a freeze.

| Goal | Patch |
|---|---|
| Max all abilities | `0x0060D355`, `56`, `57` = 5 (bytes) and `0x0060D352`, `53`, `54` = 25. Both take effect when the ability screen is confirmed (`0x003BFD10` recalculates max HP, then `0x003C0D50` writes the attack rank). |
| More points per level | `0x005FB172` onwards: 49 bytes, 3 each |
| Player attack rank directly | person 0 `+0x51` = `0x0060D3B1` (byte, 0-6) |
| Stronger attack ranks | `g_AttackRankMul` `0x005D04D0`, float[7] |
| No low-HP damage reduction | `0x005D065C` and `0x005D0668` = `0x3F800000` (1.0) |
| No combo scaling | `0x005D0680` = 1.0 and `0x005D0684` = 0.0 |
| Pride breaks faster | `g_StylePrideMul` `0x005D4250` (bytes, percent per style; Aaron is `0x005D4263`) |
| Infinite Pride (player) | fighter 0 `+0x4420` = `0x006D3F90` (float) |
| Easier level-ups | change the 100 EXP cap: `slti at,s4,101` at `0x002B0068` and `li s4,100` at `0x002B0070` |
| Criminal Level scores | `0x0060D346`, `48`, `4A` (s16, 0-255); they are recalculated by `Criminal_Recalc`, so patch the bonuses at `0x0060D34C`, `4E`, `50` instead |
| Weapons never break | `0x005D7D90` and `0x005D7D98`, 8 zero bytes |

## Corrections to CODEMAP.md

- Fighter `+0x4420` / `+0x4424` and person `+0x3A6` are the **Pride Gauge**, not a guard value. "No damage at all when the defender's guard value is 0" was wrong: empty Pride can make damage x1.2 instead.
- Fighter `+0x4426` is a damage/stagger meter capped at max HP, not a knockdown meter that triggers at 500.
- `0x005D4250` (CODEMAP's g_StyleReactTable) is the per-style Pride damage percent.
- The situation factor is a float multiplier, not a percentage.

## Open leads

- What fills the EXP bonus (gp-21460) and the bonus pool (gp-21468): probably fight style (combos, taunts, no damage taken). The per-fighter score at `[gp-20356] +212` (`0x002E3CA0` adds `10 + (500 - damage) / 4` per hit, `0x002E3D30` +100, `0x002E3D70` +200 on a taunt) is a candidate.
- The condition at `0x002E37E0` for the x1.2 damage on empty Pride.
- What a full TIRED meter does, the REV meter, and the INJURY table.
- Code for status effects, disguise and spotting, item effects, and the negotiation outcomes.
- The two unnamed Charisma counters (`0x0060D342`, `0x0060D344`) and `0x0060D704`.
- Whether `0x002AF640` really chooses the ending.
