require "util"
event = require "event"
_G.dispatch = event.dispatch
_G.dispatch_often = event.dispatch_often
_G.on = event.on
_G.remove = event.remove
_G.register = event.register

mock_font = {
	getWidth: (self, text) -> #text * 8
	getHeight: (self) -> 20
}
_G.font = mock_font
_G.text_font = mock_font

_G.love = {
	filesystem: {
		getDirectoryItems: => {"main.scr"}
	}
	graphics: {
		newImage: (path) -> {}
		setColor: (...) ->
		setFont: (...) ->
		print: (...) ->
		rectangle: (...) ->
		getWidth: -> 400
		getHeight: -> 240
	}
}
_G.lg = love.graphics

script = require "script"
screen = require "screen"

run_scr = (code) ->
	fs = (path) -> code
	script.load("", fs)

describe "real main_menu registration timing (real-hardware regression)", ->
	before_each ->
		dispatch "restore", {}

	-- runs first, deliberately, before any other test in this file ever
	-- registers a real main_menu -- screen.definitions persists across
	-- tests (registered once, same as real gameplay across save/restore),
	-- so this is the only point at which the placeholder is still the
	-- only definition present.
	it "a game with no real main_menu in source still falls back to the native placeholder", ->
		interpreter = run_scr('
			@start
			text No main menu here.
		')
		interpreter = script.run_preamble(interpreter)
		def = screen.definitions["main_menu"]
		box = def.children[1].node
		assert.are.equal(box.children[1].label, "Start Game")

	it "run_preamble registers a real converted main_menu before show_screen ever fires", ->
		-- mirrors save.moon's actual new-game sequence: script.load, then
		-- (the fix) run_preamble, *then* show_screen -- without run_preamble,
		-- screen_begin/screen_button/screen_end here would never have run
		-- yet, and screen.definitions["main_menu"] would still be the
		-- hardcoded Start Game/Quit placeholder.
		interpreter = run_scr('
			screen_begin main_menu
			screen_button Real New Game | jump start
			screen_end

			@start
			text Real story begins here.
		')
		interpreter = script.run_preamble(interpreter)
		def = screen.definitions["main_menu"]
		box = def.children[1]
		assert.are.equal(box.label, "Real New Game")
		assert.are.equal(box.action, "jump start")

	it "leaves the interpreter positioned exactly at the first real instruction after the label", ->
		interpreter = run_scr('
			screen_begin main_menu
			screen_button Real New Game | jump start
			screen_end

			@start
			text Real story begins here.
		')
		interpreter = script.run_preamble(interpreter)
		-- exactly what main.moon's "next_ins" -> next_msg would do next;
		-- proves run_preamble didn't overshoot into (or stop short of)
		-- "@start"'s own first real instruction.
		interpreter, ins = script.next_instruction(interpreter)
		assert.are.equal(ins.type, "text")
		assert.are.equal(ins.text, "Real story begins here.")
