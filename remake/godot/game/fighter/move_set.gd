class_name MoveSet
extends Resource
## A fighting style: which move each button starts from stance. Combos continue
## through each MoveData's `next`. In the real game this is a style's command list
## (`g_StyleCommands`, docs/ANIMATION.md).

@export var style_name := "Style"
@export var root: Dictionary = {}   ## button ("P", "K") -> MoveData
