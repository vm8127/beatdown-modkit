class_name Moves
## Placeholder moves for M0. From M4 on they come from the real game's tables (style
## command lists, actions, hit records; docs/ANIMATION.md, docs/MECHANICS.md), extracted
## by remake_assets.py, never typed in here.
##
## Times are in frames (60 per second):
##   frames   total length; the fighter returns to stance after it
##   active   [first, last] frame the hitbox is out; before it is startup, after it recovery
##   cancel   [first, last] frame a buffered press can start a move from "next" (the combo)
##   hitstop  frames both fighters freeze on contact (the "impact" feel)
##   hitstun  frames the victim can't act; longer than the attacker's recovery = a true combo
## Distances in metres, speeds in m/s: reach/height place the hit sphere in front of the
## fighter, lunge is the forward speed during startup, launch the upward speed of a knockdown.

const ROOT := {"P": "jab1", "K": "kick1"}

const LIST := {
	"jab1": {"name": "Jab", "limb": "arm", "side": 0, "frames": 22, "active": [6, 8],
		"cancel": [9, 18], "next": {"P": "jab2", "K": "low_kick"},
		"damage": 10, "hitstop": 5, "hitstun": 18, "knockback": 1.5,
		"reach": 0.85, "height": 1.35, "radius": 0.35, "lunge": 1.5},
	"jab2": {"name": "Jab 2", "limb": "arm", "side": 1, "frames": 24, "active": [6, 8],
		"cancel": [9, 19], "next": {"P": "straight", "K": "low_kick"},
		"damage": 12, "hitstop": 6, "hitstun": 20, "knockback": 1.5,
		"reach": 0.85, "height": 1.35, "radius": 0.35, "lunge": 1.5},
	"straight": {"name": "Straight", "limb": "arm", "side": 0, "frames": 38, "active": [10, 13],
		"damage": 28, "hitstop": 11, "hitstun": 30, "knockback": 7.0,
		"knockdown": true, "launch": 4.5,
		"reach": 1.0, "height": 1.4, "radius": 0.45, "lunge": 3.0},
	"kick1": {"name": "Front Kick", "limb": "leg", "frames": 30, "active": [10, 13],
		"cancel": [14, 24], "next": {"K": "roundhouse"},
		"damage": 18, "hitstop": 8, "hitstun": 24, "knockback": 3.5,
		"reach": 1.0, "height": 0.9, "radius": 0.4, "lunge": 1.0},
	"low_kick": {"name": "Low Kick", "limb": "leg", "frames": 28, "active": [8, 10],
		"cancel": [11, 22], "next": {"P": "straight"},
		"damage": 14, "hitstop": 6, "hitstun": 22, "knockback": 2.0,
		"reach": 1.0, "height": 0.45, "radius": 0.4, "lunge": 1.0},
	"roundhouse": {"name": "Roundhouse", "limb": "leg", "frames": 44, "active": [14, 18],
		"damage": 30, "hitstop": 12, "hitstun": 30, "knockback": 8.0,
		"knockdown": true, "launch": 5.5,
		"reach": 1.05, "height": 1.4, "radius": 0.5, "lunge": 2.0},
}
