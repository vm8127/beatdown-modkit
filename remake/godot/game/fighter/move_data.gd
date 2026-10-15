class_name MoveData
extends Resource
## One move. Each move is a .tres file in game/moves/, editable in the Inspector.
## Placeholders for now; from M4 on, remake_assets.py generates them from the game's
## real tables (actions, frame data, hit records: docs/ANIMATION.md, docs/MECHANICS.md).
##
## Times are in frames (60 per second). Distances in metres, speeds in m/s.

@export var move_name := "Move"
@export_enum("arm", "leg") var limb := "arm"
@export_range(0, 1) var side := 0   ## which arm: 0 right, 1 left

@export_group("Timing")
@export var frames := 30            ## total length; back to stance after it
@export var active_start := 8       ## first frame the hitbox is out (before it: startup)
@export var active_end := 10        ## last frame the hitbox is out (after it: recovery)
@export var cancel_start := -1      ## combo window: a buffered press in [start, end]
@export var cancel_end := -1        ## starts the move in `next` (-1: no combo)
@export var next: Dictionary = {}   ## button ("P", "K") -> MoveData

@export_group("Hit")
@export var damage := 10
@export var hitstop := 6            ## frames both fighters freeze on contact
@export var hitstun := 18           ## frames the victim can't act
@export var knockback := 2.0        ## push speed
@export var knockdown := false
@export var launch := 5.0           ## upward speed of a knockdown

@export_group("Hitbox")
@export var reach := 0.9            ## sphere centre: this far in front of the fighter
@export var height := 1.35          ## and this high
@export var radius := 0.4
@export var lunge := 1.0            ## forward speed during startup


func is_active(f: int) -> bool:
	return f >= active_start and f <= active_end


func cancel_open(f: int) -> bool:
	return cancel_start >= 0 and f >= cancel_start and f <= cancel_end
