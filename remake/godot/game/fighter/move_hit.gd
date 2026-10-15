class_name MoveHit
extends Resource
## One hit window of a move: when the attack spheres are out, and what the hit does.
## Generated from the game's tables by remake/tools/conv_moves.py (timeline op 0x24 for the window,
## g_ActionHits for the numbers: docs/ANIMATION.md "Frame data", docs/MECHANICS.md "Damage").
## The placeholder moves (game/moves/*.tres) build one from their own fields instead.
##
## Frames are game frames (60 per second) counted from the start of the move.

@export_group("Window")
@export var start := 8                 ## first frame the spheres are out
@export var end := 10                  ## last frame
@export var anim_start := 8            ## the same in animation frames (as the game's timeline stores it)
@export var anim_end := 10
@export var parts := PackedInt32Array()   ## attack sphere ids (g_AttackSpheres: 0/1 hands, 2/3 feet, ...); for bone attachment later

@export_group("Hit record")
@export var record := 0                ## index in the action's hit records
@export var damage := 10               ## base damage (before the MECHANICS multipliers)
@export var pride := 0                 ## Pride damage base (random 30-39 is added)
@export var strength := 1              ## record byte +11 (1-4); meaning not traced, drives the placeholder reaction size
@export var level := 2                 ## hit level flags: 2 high, 4 mid, 8 low
@export var level_name := "high"
@export var reaction := 1              ## reaction bits (0x20 down, 0x10 / 0x100 / 0x200 / 0x400 big reactions, ...)
@export var reaction_detail := 0       ## record +0xC: picks the stagger variant (bits 4, 8, 0x10, 0x20)
@export var knockdown := false         ## the reaction knocks the victim down

@export_group("Remake placeholders")   ## not in the game's data: tune by feel
@export var radius := 0.35             ## sphere radius from g_AttackSpheres (x2, in metres)
@export var hitstop := -1              ## -1: from strength
@export var hitstun := -1              ## -1: from strength
@export var knockback := -1.0          ## -1: from strength
@export var launch := 5.0


func is_active(f: int) -> bool:
	return f >= start and f <= end


func get_hitstop() -> int:
	return hitstop if hitstop >= 0 else 4 + 2 * strength


func get_hitstun() -> int:
	return hitstun if hitstun >= 0 else 26 + 4 * strength


func get_knockback() -> float:
	return knockback if knockback >= 0.0 else 1.0 + 0.5 * strength


## Height of the hit sphere on the capsule, from the hit level (the game uses the bone's position).
func height() -> float:
	if level & 8:
		return 0.45
	if level & 4:
		return 1.05
	return 1.4
