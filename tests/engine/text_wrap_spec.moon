require "util"
event = require "event"
_G.dispatch = event.dispatch
_G.dispatch_often = event.dispatch_often
_G.on = event.on
_G.remove = event.remove
_G.register = event.register

-- deterministic, simple width model: 10px per character
mock_font = {
	getWidth: (self, text) -> #text * 10
	getHeight: (self) -> 20
}
_G.interpreter = nil
_G.lfs = {getInfo: (path) -> nil}

wrap_calls = {}
_G.love = {
	_console_name: "3DS"
	graphics: {
		newImage: (path) -> {}
		setColor: (...) ->
		setFont: (...) ->
		print: (...) ->
		rectangle: (...) ->
		getWidth: (screen) ->
			table.insert(wrap_calls, screen)
			if screen == "bottom" then 320 else 400
		getHeight: (...) -> 240
	}
}
_G.lg = love.graphics

require "text/text"

describe "text box width (regression)", ->
	it "measures word-wrap against the bottom screen's width, not whatever screen happens to be active", ->
		-- real hardware bug: dialogue text ran off the right edge of the
		-- screen. LOVE Potion's love.graphics.getWidth() with no argument
		-- returns whichever screen boot.lua last called setActiveScreen
		-- for -- which, per its own per-frame draw loop, is "top" (400px)
		-- once a frame's draw calls finish. The "text" event fires from
		-- game-logic dispatch, not from inside a love.draw call, so it
		-- must ask for the bottom screen's width (320px, where the text
		-- box actually renders) explicitly rather than trusting the
		-- ambient active-screen state.
		_G.font = mock_font
		_G.love._console_name = "3DS"
		dispatch "restore"

		wrap_calls = {}
		dispatch "text", {text: "a normal line of dialogue"}

		assert.is_true(#wrap_calls > 0)
		for screen in *wrap_calls
			assert.are.equal(screen, "bottom")
