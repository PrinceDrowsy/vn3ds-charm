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

next_ins_calls = 0

_G.love = {
	graphics: {
		newImage: (path) -> {}
		setColor: (...) ->
		setFont: (...) ->
		print: (...) ->
		rectangle: (...) ->
		getWidth: -> 400
		getHeight: -> 240
	}
	event: {
		quit: -> _G.__quit_called = true
	}
}
_G.lg = love.graphics

_G.interpreter = {globals: {}, locals: {}, n: 5, labels: {start: 1, ending: 10}}

screen = require "screen"

-- "next_ins" is what real script instructions dispatch to advance the VN;
-- wire it to the same next_msg stub so screen.moon's dispatch "next_ins"
-- calls are observable the same way main.moon's real next_msg would be.
on "next_ins", -> next_ins_calls += 1

describe "Native main menu", ->
	it "registers a default main_menu screen with Start Game and Quit", ->
		-- checked before any other test's "main_menu" registration
		-- overwrites it -- Ren'Py's own default main_menu screen is a
		-- builtin with no .rpy source to convert, so this native
		-- fallback is the only way the engine ever shows one.
		def = screen.definitions["main_menu"]
		assert.is_not_nil(def)
		box = def.children[1].node
		assert.are.equal(box.children[1].label, "Start Game")
		assert.are.equal(box.children[1].action, "hide_screen")
		assert.are.equal(box.children[2].label, "Quit")
		assert.are.equal(box.children[2].action, "quit")

describe "Custom screen runtime (pulled-forward Phase 5.1)", ->
	before_each ->
		next_ins_calls = 0
		_G.__quit_called = false
		_G.interpreter = {globals: {}, locals: {}, n: 5, labels: {start: 1, ending: 10}}
		dispatch "restore", {}

	it "builds a flat vbox of text and buttons into a named definition", ->
		dispatch "screen_begin", {name: "main_menu"}
		dispatch "vbox_begin"
		dispatch "screen_text", {text: "Welcome"}
		dispatch "screen_button", {label: "Start", action: "jump start"}
		dispatch "screen_button", {label: "Quit", action: "quit"}
		dispatch "vbox_end"
		dispatch "screen_end"

		def = screen.definitions["main_menu"]
		assert.is_not_nil(def)
		assert.are.equal(#def.children, 1) -- the vbox itself
		box = def.children[1].node
		assert.are.equal(#box.children, 3)
		assert.are.equal(box.children[1].type, "text")
		assert.are.equal(box.children[2].label, "Start")
		assert.are.equal(box.children[3].label, "Quit")

	it "builds if/elif/else branches as separate branch nodes on one if-node", ->
		dispatch "screen_begin", {name: "conditional"}
		dispatch "screen_if", {expr: "affection > 5"}
		dispatch "screen_text", {text: "They like you"}
		dispatch "screen_elif", {expr: "affection > 0"}
		dispatch "screen_text", {text: "Neutral"}
		dispatch "screen_else"
		dispatch "screen_text", {text: "They dislike you"}
		dispatch "screen_endif"
		dispatch "screen_end"

		def = screen.definitions["conditional"]
		if_node = def.children[1].node
		assert.are.equal(#if_node.branches, 3)
		assert.are.equal(if_node.branches[1].cond, "affection > 5")
		assert.are.equal(if_node.branches[2].cond, "affection > 0")
		assert.is_nil(if_node.branches[3].cond)

	it "shows only the matching if/elif/else branch's text based on live variable state", ->
		dispatch "screen_begin", {name: "conditional"}
		dispatch "screen_if", {expr: "affection > 5"}
		dispatch "screen_text", {text: "They like you"}
		dispatch "screen_else"
		dispatch "screen_text", {text: "They dislike you"}
		dispatch "screen_endif"
		dispatch "screen_end"

		draw_calls = {}
		lg.print = (...) -> table.insert(draw_calls, {...})

		_G.interpreter.globals.affection = 10
		screen.show_screen("conditional")
		dispatch "draw_choice"
		assert.are.equal(draw_calls[1][1], "They like you")

		dispatch "input", "b" -- close (closable: true) so a fresh show_screen can render again
		draw_calls = {}
		_G.interpreter.globals.affection = 0
		screen.show_screen("conditional")
		dispatch "draw_choice"
		assert.are.equal(draw_calls[1][1], "They dislike you")

	it "a jump action redirects the interpreter and resumes script flow", ->
		dispatch "screen_begin", {name: "main_menu"}
		dispatch "screen_button", {label: "Start", action: "jump start"}
		dispatch "screen_end"

		screen.show_screen("main_menu")
		dispatch "input", "a" -- select the (only, first) button
		assert.are.equal(interpreter.n, 1) -- jumped to the "start" label's instruction index
		assert.are.equal(next_ins_calls, 1)

	it "a quit action calls love.event.quit", ->
		dispatch "screen_begin", {name: "main_menu"}
		dispatch "screen_button", {label: "Quit", action: "quit"}
		dispatch "screen_end"

		screen.show_screen("main_menu")
		dispatch "input", "a"
		assert.is_true(_G.__quit_called)

	it "closing a screen with no caller (top-level show_screen) resumes script flow", ->
		dispatch "screen_begin", {name: "main_menu"}
		dispatch "screen_button", {label: "Only Option", action: "hide_screen"}
		dispatch "screen_end"

		screen.show_screen("main_menu")
		dispatch "input", "a"
		assert.are.equal(next_ins_calls, 1)

	it "showing an unknown screen name doesn't hang script flow forever", ->
		screen.show_screen("does_not_exist")
		assert.are.equal(next_ins_calls, 1)
