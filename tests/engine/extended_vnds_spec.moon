pprint = require "lib/pprint"
_G.love = {
	filesystem: {
		getDirectoryItems: => {"main.scr", "chapter2.scr"}
	}
}
script = require "script"

run_scr = (code, files = {}) ->
	files["main.scr"] = code
	fs = (path) ->
		for name, content in pairs files
			if path\sub(-#name) == name then return content
	i = script.load("", fs)
	instructions = {}
	while true
		i, ins = script.next_instruction(i)
		if ins then table.insert(instructions, ins)
		else break
	return i, instructions

describe "Extended VNDS - Phase 1.5", ->
	describe "call/return", ->
		it "returns to the instruction after call", ->
			i, ins = run_scr('
				call helper
				text after the call

				label helper
				text inside the helper
				return
			')
			assert.are.equal(ins[1].text, "inside the helper")
			assert.are.equal(ins[2].text, "after the call")

		it "supports nested calls", ->
			i, ins = run_scr('
				call outer
				text done
				goto the_end

				label outer
				text in outer
				call inner
				text back in outer
				return

				label inner
				text in inner
				return

				label the_end
			')
			texts = [instruction.text for instruction in *ins]
			assert.are.equal(#texts, 4)
			assert.are.equal(texts[1], "in outer")
			assert.are.equal(texts[2], "in inner")
			assert.are.equal(texts[3], "back in outer")
			assert.are.equal(texts[4], "done")

	describe "jump (extended: same-file label)", ->
		it "jumps to a same-file label without needing goto", ->
			i, ins = run_scr('
				jump elsewhere
				text not run

				label elsewhere
				text run
			')
			assert.are.equal(#ins, 1)
			assert.are.equal(ins[1].text, "run")

	describe "jump (extended: pipe-delimited choice branch)", ->
		it "selects the target matching the selected choice index", ->
			code = '
				choice A|B
				jump path_a|path_b

				label path_a
				text went a
				return

				label path_b
				text went b
				return
			'
			fs = -> code
			i = script.load("", fs)
			-- step to the choice instruction (mirrors main.moon: the engine
			-- pauses here for player input, it does not auto-continue)
			i, choice_ins = script.next_instruction(i)
			assert.are.equal(choice_ins.type, "choice")

			script.choose(i, 2) -- select option 2 ("B")
			i, next_ins = script.next_instruction(i)
			assert.are.equal(next_ins.text, "went b")

	describe "jump (legacy: cross-file, unchanged)", ->
		it "still loads another file by filename when no matching same-file label exists", ->
			i, ins = run_scr('
				jump chapter2.scr
				text not run
			', {["chapter2.scr"]: 'text from chapter 2'})
			assert.are.equal(#ins, 1)
			assert.are.equal(ins[1].text, "from chapter 2")

	describe "nameplate / clearimg / window", ->
		it "parses as recognized instruction types with their fields", ->
			i, ins = run_scr('
				nameplate Avery
				setimg avery.png 10 20
				clearimg avery.png
				window hide
				window show
			')
			assert.are.equal(ins[1].type, "nameplate")
			assert.are.equal(ins[1].name, "Avery")
			assert.are.equal(ins[2].type, "setimg")
			assert.are.equal(ins[3].type, "clearimg")
			assert.are.equal(ins[3].path, "foreground/avery.png")
			assert.are.equal(ins[4].type, "window")
			assert.are.equal(ins[4].state, "hide")
			assert.are.equal(ins[5].state, "show")

		it "parses clearslot as a bare slot reference", ->
			i, ins = run_scr('
				clearslot afd_l
			')
			assert.are.equal(ins[1].type, "clearslot")
			assert.are.equal(ins[1].slot, "afd_l")

		it "parses overlay_text with id/x/y/size/color/text and overlay_clear as a bare type", ->
			i, ins = run_scr('
				overlay_text day_title 200 66 80 fff Day
				overlay_clear
			')
			assert.are.equal(ins[1].type, "overlay_text")
			assert.are.equal(ins[1].id, "day_title")
			assert.are.equal(ins[1].x, 200)
			assert.are.equal(ins[1].y, 66)
			assert.are.equal(ins[1].size, 80)
			assert.are.equal(ins[1].color, "fff")
			assert.are.equal(ins[1].text, "Day")
			assert.are.equal(ins[2].type, "overlay_clear")

	describe "setimg (static ATL/transform props)", ->
		it "parses slot and trailing key=value props alongside the existing x/y", ->
			-- vnds_writer.py's _static_prop_tokens appends these after the
			-- slot token (position 5) -- a static ATL block/named
			-- transform's resolved yalign/yanchor/sx/sy/r/alpha, reusing the
			-- same parse_props helper "keyframe" already relies on.
			i, ins = run_scr('
				setimg eileen_happy.t3x 200 40 eileen yalign=0.5 yanchor=1.0 sx=1.4 sy=1.4 r=0.5 alpha=0.8
			')
			setimg = ins[1]
			assert.are.equal(setimg.type, "setimg")
			assert.are.equal(setimg.x, 200)
			assert.are.equal(setimg.y, 40)
			assert.are.equal(setimg.slot, "eileen")
			assert.are.equal(setimg.props.yalign, 0.5)
			assert.are.equal(setimg.props.yanchor, 1.0)
			assert.are.equal(setimg.props.sx, 1.4)
			assert.are.equal(setimg.props.sy, 1.4)
			assert.are.equal(setimg.props.r, 0.5)
			assert.are.equal(setimg.props.alpha, 0.8)

		it "leaves props an empty table for a plain setimg with no static ATL props", ->
			i, ins = run_scr('
				setimg avery.png 10 20 avery
			')
			assert.are.same(ins[1].props, {})

describe "save/load (Phase 2.7)", ->
	it "round-trips script position and variable state", ->
		fs = -> '
			gsetvar affection = 3
			text first
			text second
		'
		i = script.load("", fs)
		i, ins1 = script.next_instruction(i)
		assert.are.equal(ins1.text, "first")

		saved = script.save(i)
		assert.are.equal(saved.globals.affection, 3)

		i2 = script.load("", fs, saved)
		i2, ins2 = script.next_instruction(i2)
		-- save()'s n-1 rewind re-delivers the just-returned instruction on load
		assert.are.equal(ins2.text, "first")
		assert.are.equal(i2.globals.affection, 3)

	it "round-trips the call stack, so return still resumes at the call site after loading", ->
		-- real bug found while verifying 2.7: script.save() didn't include
		-- s.callstack at all, so saving/loading mid-call lost the return
		-- address entirely -- `return` would treat the stack as empty and
		-- end the script instead of resuming after the `call`.
		fs = -> '
			call helper
			text after the call
			return

			label helper
			text inside the helper
			return
		'
		i = script.load("", fs)
		i, ins1 = script.next_instruction(i)
		assert.are.equal(ins1.text, "inside the helper")

		saved = script.save(i)
		i2 = script.load("", fs, saved)
		i2, ins2 = script.next_instruction(i2) -- re-delivers "inside the helper" (n-1 rewind)
		i2, ins3 = script.next_instruction(i2) -- then "return" -- must resume at the call site
		assert.are.equal(ins2.text, "inside the helper")
		assert.are.equal(ins3.text, "after the call")

describe "sound / music / delay (Phase 2.6 verification: original VNDS commands)", ->
	it "parses sound with a repeat count and music without one", ->
		i, ins = run_scr('
			sound click.ogg 1
			music theme.ogg
		')
		assert.are.equal(ins[1].type, "sound")
		assert.are.equal(ins[1].path, "sound/click.ogg")
		assert.are.equal(ins[1].n, 1)
		assert.are.equal(ins[2].type, "music")
		assert.are.equal(ins[2].path, "sound/theme.ogg")
		assert.is_nil(ins[2].n)

	it "parses delay's frame count", ->
		i, ins = run_scr('
			delay 90
		')
		assert.are.equal(ins[1].type, "delay")
		assert.are.equal(ins[1].frames, 90)

describe "Animation commands (Phase 3.1/3.2, VN3DS-spec.md §9.1)", ->
	it "parses a preset anim command", ->
		i, ins = run_scr('
			anim eileen_happy enter_fade 0.3
		')
		assert.are.equal(ins[1].type, "anim")
		assert.are.equal(ins[1].target, "eileen_happy")
		assert.are.equal(ins[1].preset, "enter_fade")
		assert.are.equal(ins[1].duration, 0.3)

	it "parses an anim_wait command", ->
		i, ins = run_scr('
			anim_wait eileen_happy
		')
		assert.are.equal(ins[1].type, "anim_wait")
		assert.are.equal(ins[1].target, "eileen_happy")

	it "parses a keyframe block's begin/keyframe/end commands", ->
		i, ins = run_scr('
			anim_begin char_hero 0.6 ease_out
			keyframe 0.0 x=80 alpha=0 sx=0.8 sy=0.8
			keyframe 0.5 x=160 alpha=1 sx=1.05 sy=1.05
			keyframe 1.0 x=160 alpha=1 sx=1.0 sy=1.0
			anim_end
		')
		assert.are.equal(ins[1].type, "anim_begin")
		assert.are.equal(ins[1].target, "char_hero")
		assert.are.equal(ins[1].duration, 0.6)
		assert.are.equal(ins[1].ease, "ease_out")

		assert.are.equal(ins[2].type, "keyframe")
		assert.are.equal(ins[2].t, 0.0)
		assert.are.equal(ins[2].props.x, 80)
		assert.are.equal(ins[2].props.alpha, 0)
		assert.are.equal(ins[2].props.sx, 0.8)
		assert.are.equal(ins[2].props.sy, 0.8)

		assert.are.equal(ins[3].t, 0.5)
		assert.are.equal(ins[3].props.x, 160)

		assert.are.equal(ins[4].t, 1.0)
		assert.are.equal(ins[5].type, "anim_end")

	it "parses random's low/high bounds as numbers and assigns a value in range", ->
		-- regression test: parse()'s "random" branch used to write
		-- `low: num(c[3], high: num(c[4]))` -- the comma before `high:`
		-- made MoonScript build an implicit table and pass it as num()'s
		-- (tonumber's) second argument, crashing with "bad argument #2 to
		-- 'num' (number expected, got table)" the first time real content
		-- (Jisei, via renpy.random.randint) ever emitted a `random` line
		-- and hit this parse path on real 3DS hardware.
		i, ins = run_scr('
			random points 1 6
			text after
		')
		assert.are.equal(#ins, 1)
		assert.are.equal(ins[1].text, "after")
		assert.is_true(i.globals.points >= 1 and i.globals.points <= 6)

describe "Expression evaluator wiring (Phase 2.4)", ->
	it "gsetvar = evaluates a boolean literal correctly (previously fell through to a variable reference)", ->
		i, ins = run_scr('
			gsetvar book = True
			text after
		')
		assert.is_true(i.globals.book)

	it "gsetvar = evaluates a cross-variable arithmetic expression", ->
		i, ins = run_scr('
			gsetvar shield = 10
			gsetvar hp = shield + 5
			text after
		')
		assert.are.equal(i.globals.hp, 15)

	it "gsetvar = still supports a plain literal assignment", ->
		i, ins = run_scr('
			gsetvar affection = 0
			text after
		')
		assert.are.equal(i.globals.affection, 0)

	it "gsetvar + / - self-referential accumulation is unaffected by the new evaluator", ->
		i, ins = run_scr('
			gsetvar affection = 0
			gsetvar affection + 1
			gsetvar affection + 1
			gsetvar affection - 1
			text after
		')
		assert.are.equal(i.globals.affection, 1)

	it "falls back to the original literal-or-var parse if the evaluator can't handle it", ->
		-- an empty/malformed expression after "=" -- evaluator returns nil,
		-- so this must not crash and must fall back gracefully
		i, ins = run_scr('
			gsetvar flag =
			text after
		')
		assert.are.equal(#ins, 1) -- didn't crash; execution reached the text line

describe "ifvar (Phase 2.5)", ->
	it "jumps when the single-condition expression is true", ->
		i, ins = run_scr('
			gsetvar affection = 3
			ifvar affection >= 3 jump route_good
			text not run

			label route_good
			text reached the good route
		')
		assert.are.equal(#ins, 1)
		assert.are.equal(ins[1].text, "reached the good route")

	it "falls through to the next instruction when the expression is false", ->
		i, ins = run_scr('
			gsetvar affection = 1
			ifvar affection >= 3 jump route_good
			text fell through
			return

			label route_good
			text reached the good route
		')
		assert.are.equal(#ins, 1)
		assert.are.equal(ins[1].text, "fell through")

	it "evaluates a compound and/or condition in a single line", ->
		i, ins = run_scr('
			gsetvar affection = 1
			gsetvar book = True
			ifvar ((affection >= 3)) or (book) jump route_good
			text not run

			label route_good
			text reached via the or branch
		')
		assert.are.equal(#ins, 1)
		assert.are.equal(ins[1].text, "reached via the or branch")

	it "chains multiple ifvar checks like flattened if/elif/else", ->
		i, ins = run_scr('
			gsetvar affection = 1
			ifvar (affection >= 3) jump route_good
			ifvar (affection >= 1) jump route_ok
			jump route_bad

			label route_good
			text good
			return

			label route_ok
			text ok
			return

			label route_bad
			text bad
			return
		')
		assert.are.equal(#ins, 1)
		assert.are.equal(ins[1].text, "ok")

describe "Custom screen commands (Phase 5.1, VN3DS-spec.md's pulled-forward slice)", ->
	it "parses a real converter-emitted screen definition end-to-end", ->
		-- round-trip against the exact text vnds_writer.py emits (not a
		-- hand-simplified version of it) -- this is precisely the kind of
		-- gap that let the .t3x-extension and bare-voice-statement bugs
		-- ship unnoticed: the converter's own tests never exercised the
		-- real engine parser on its actual output.
		i, ins = run_scr('
			screen_begin main_menu2
			vbox_begin
			screen_text Welcome
			screen_button Start Game | jump start
			screen_button Quit | quit
			vbox_end
			screen_end
			text after
		')
		assert.are.equal(#ins, 8)
		assert.are.equal(ins[1].type, "screen_begin")
		assert.are.equal(ins[1].name, "main_menu2")
		assert.are.equal(ins[2].type, "vbox_begin")
		assert.are.equal(ins[3].type, "screen_text")
		assert.are.equal(ins[3].text, "Welcome")
		assert.are.equal(ins[4].type, "screen_button")
		assert.are.equal(ins[4].label, "Start Game")
		assert.are.equal(ins[4].action, "jump start")
		assert.are.equal(ins[5].type, "screen_button")
		assert.are.equal(ins[5].label, "Quit")
		assert.are.equal(ins[5].action, "quit")
		assert.are.equal(ins[6].type, "vbox_end")
		assert.are.equal(ins[7].type, "screen_end")
		assert.are.equal(ins[8].text, "after")

	it "parses screen_if/screen_elif/screen_else/screen_endif", ->
		i, ins = run_scr('
			screen_if (affection > 5)
			screen_text High
			screen_elif (affection > 0)
			screen_text Medium
			screen_else
			screen_text Low
			screen_endif
		')
		assert.are.equal(ins[1].type, "screen_if")
		assert.are.equal(ins[1].expr, "(affection > 5)")
		assert.are.equal(ins[3].type, "screen_elif")
		assert.are.equal(ins[3].expr, "(affection > 0)")
		assert.are.equal(ins[5].type, "screen_else")
		assert.are.equal(ins[7].type, "screen_endif")

	it "parses show_screen and hide_screen", ->
		i, ins = run_scr('
			show_screen main_menu2
			hide_screen
		')
		assert.are.equal(ins[1].type, "show_screen")
		assert.are.equal(ins[1].name, "main_menu2")
		assert.are.equal(ins[2].type, "hide_screen")
