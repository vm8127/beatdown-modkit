extends SceneTree
## Headless check of the converted game text through GameText (game/text/game_text.gd).
## Run by remake/tools/test_text.py, which writes the expected values from the Python decoders:
##   godot --headless --path remake/godot --script res://dev/text_check.gd -- --expect=<file.json>
## Prints a sample and one line per mismatch; exit code 0 = all match.

var _fails: Array[String] = []
var _checked := 0


func _initialize() -> void:
	var path := ""
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--expect="):
			path = a.substr(9)
	var want = JSON.parse_string(FileAccess.get_file_as_string(path)) if path else null
	if not GameText.available():
		print("no converted text (run remake/tools/remake_assets.py first); fallback: %s" % GameText.text(11069))
		quit(2)
		return
	print("sample:")
	print("  person 68:      %s" % GameText.person_name(68))
	print("  area 5:         %s" % GameText.area_name(5))
	print("  style 0x13 #0:  %s  %s" % GameText.move_list(0x13)[0])
	print("  negotiation:    %s / %s / %s / %s" % [GameText.text(10004), GameText.text(10005),
			GameText.text(10006), GameText.text(10007)])
	print("  recruit line:   %s" % GameText.text(50587).replace("\n", " / "))
	print("  tutorial:       %s" % GameText.render(30232))
	print("  party:          %s" % GameText.render(30747, {"person": "Gina"}))
	print("  money:          %s" % GameText.render(30812, {"money": 500}).replace("%s", "500"))
	print("  dialogue 1:     %s" % GameText.dialogue(1)[0].replace("\n", " / "))
	if want == null:
		quit(0)
		return
	for k in want["texts"]:
		_eq("text %s" % k, GameText.render(int(k)), want["texts"][k])
	_eq("person 68", GameText.person_name(68), want["person_68"])
	_eq("area 5", GameText.area_name(5), want["area_5"])
	for style in want["move_lists"]:
		var got := GameText.move_list(int(style))
		var exp: Array = want["move_lists"][style]
		_eq("style %s lines" % style, got.size(), exp.size())
		for i in mini(got.size(), exp.size()):
			_eq("style %s #%d name" % [style, i], got[i][0], exp[i][0])
			_eq("style %s #%d input" % [style, i], got[i][1], exp[i][1])
	_eq("dialogue 1 count", GameText.dialogue(1).size(), int(want["dialogue_1_count"]))
	for f in _fails.slice(0, 40):
		print("FAIL " + f)
	print("%s: %d checks, %d failed" % ["PASS" if _fails.is_empty() else "FAIL", _checked, _fails.size()])
	quit(0 if _fails.is_empty() else 1)


func _eq(what: String, got, exp) -> void:
	_checked += 1
	if str(got) != str(exp):
		_fails.append("%s: got %s, expected %s" % [what, var_to_str(got), var_to_str(exp)])
