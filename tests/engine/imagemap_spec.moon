require "util"
event = require "event"
_G.dispatch = event.dispatch
_G.dispatch_often = event.dispatch_often
_G.on = event.on
_G.remove = event.remove
_G.register = event.register

next_ins_calls = 0
ground_w, ground_h = 400, 240 -- matches the mocked screen size 1:1 (scale=1, no centering offset)

_G.love = {
	graphics: {
		newImage: (path) -> {getDimensions: -> ground_w, ground_h}
		setColor: (...) ->
		draw: (...) ->
		getWidth: -> 400
		getHeight: -> 240
	}
	event: {
		quit: -> _G.__quit_called = true
	}
}
_G.lg = love.graphics
_G.sx, _G.sy = 1, 1 -- device-reference scale main.moon's love.resize would normally compute

_G.interpreter = {globals: {}, locals: {}, n: 5, labels: {start: 1, ending: 10}}

screen = require "screen"

on "next_ins", -> next_ins_calls += 1

-- Jisei's real main_menu shape: ground + several hotspots, one of them
-- intentionally inert (NullAction). Hotspot x/y/w/h are fractions
-- (0.0-1.0) of the game's own declared resolution -- the same
-- convention rpy_parser.py's _parse_screen_imagemap now emits (real-
-- hardware regression: raw pixel values, as this spec used before,
-- silently assumed the *loaded* ground image always matched whatever
-- resolution the hotspots were authored against, which broke the
-- instant the asset pipeline started resizing oversized backgrounds --
-- every hotspot landed far outside the visible image). With
-- ground_w/ground_h == 400x240 in the default mock, a fraction of
-- N/400 or N/240 reproduces the exact same effective pixel rect as the
-- old literal-pixel test data below (0,0,50,20 / 50,0,50,20 / 100,0,50,20).
build_main_menu = ->
	dispatch "screen_begin", {name: "main_menu"}
	dispatch "imagemap_begin", {path: "background/mainmenu.t3x"}
	dispatch "hotspot", {x: 0/400, y: 0/240, w: 50/400, h: 20/240, action: "jump start"}
	dispatch "hotspot", {x: 50/400, y: 0/240, w: 50/400, h: 20/240, action: "quit"}
	dispatch "hotspot", {x: 100/400, y: 0/240, w: 50/400, h: 20/240, action: nil}
	dispatch "imagemap_end"
	dispatch "screen_end"

describe "imagemap/hotspot custom-screen widget", ->
	before_each ->
		next_ins_calls = 0
		_G.__quit_called = false
		ground_w, ground_h = 400, 240
		_G.sx, _G.sy = 1, 1
		_G.interpreter = {globals: {}, locals: {}, n: 5, labels: {start: 1, ending: 10}}
		dispatch "restore", {}

	it "builds a single flat imagemap node (not a vbox) into the definition", ->
		build_main_menu!
		def = screen.definitions["main_menu"]
		assert.are.equal(#def.children, 1)
		node = def.children[1]
		assert.are.equal(node.type, "imagemap")
		assert.are.equal(node.ground, "background/mainmenu.t3x")
		assert.are.equal(#node.hotspots, 3)
		assert.are.equal(node.hotspots[1].action, "jump start")
		assert.is_nil(node.hotspots[3].action)

	it "draws the ground image and does not build a listbox", ->
		build_main_menu!
		draw_calls = {}
		lg.draw = (...) -> table.insert(draw_calls, {...})
		screen.show_screen("main_menu")
		dispatch "draw_choice"
		assert.are.equal(#draw_calls, 1)

	it "tapping a hotspot with a jump action redirects the interpreter and resumes script flow", ->
		build_main_menu!
		screen.show_screen("main_menu")
		dispatch "draw_choice" -- computes bounds
		dispatch "touch", {x: 25, y: 10} -- inside the first hotspot (0,0,50,20)
		assert.are.equal(interpreter.n, 1) -- jumped to "start"
		assert.are.equal(next_ins_calls, 1)

	it "tapping a hotspot with a quit action calls love.event.quit", ->
		build_main_menu!
		screen.show_screen("main_menu")
		dispatch "draw_choice"
		dispatch "touch", {x: 75, y: 10} -- inside the second hotspot (50,0,50,20)
		assert.is_true(_G.__quit_called)

	it "tapping a NullAction hotspot does nothing and leaves the imagemap open", ->
		build_main_menu!
		screen.show_screen("main_menu")
		dispatch "draw_choice"
		dispatch "touch", {x: 125, y: 10} -- inside the third hotspot (100,0,50,20)
		assert.is_false(_G.__quit_called)
		assert.are.equal(next_ins_calls, 0)
		-- still open/responsive: a later tap on a real hotspot still works
		dispatch "touch", {x: 75, y: 10}
		assert.is_true(_G.__quit_called)

	it "tapping outside every hotspot is a no-op", ->
		build_main_menu!
		screen.show_screen("main_menu")
		dispatch "draw_choice"
		dispatch "touch", {x: 300, y: 200}
		assert.is_false(_G.__quit_called)
		assert.are.equal(next_ins_calls, 0)

	it "consumes directional input instead of leaking it to other global handlers", ->
		-- real-hardware regression: unlike listbox.moon (which always
		-- intercepts "input" while any other screen is shown), an
		-- imagemap has no keyboard/gamepad navigation model of its own --
		-- but it still has to swallow "input", or a global handler
		-- elsewhere (e.g. text.moon's dialogue-backlog scrollback, bound
		-- to plain "up") fires unprotected. Confirmed real crash: pressing
		-- "up" on the very first, pre-any-dialogue main menu reached
		-- text.moon's backlog handler with an empty backlog, crashing in
		-- listbox.moon's create_listbox on an empty choices list.
		build_main_menu!
		leaked = false
		-- registered *before* show_screen, so show_imagemap's own input_event
		-- (registered after, and therefore dispatched first -- event.lua's
		-- registry is LIFO) has to be the one that actually stops
		-- propagation here, not just an artifact of registration order.
		on "input", (input) -> leaked = true; false
		screen.show_screen("main_menu")
		assert.has_no.errors(-> dispatch "input", "up")
		assert.is_false(leaked)

	it "hotspot rects track a ground image resized smaller than the game's declared resolution", ->
		-- real-hardware regression: this is the actual bug found live --
		-- the asset pipeline resizes an oversized ground image down (e.g.
		-- Jisei's real 1024x768 main-menu art resized to fit 400x240), so
		-- the *loaded* image (200x120 here, exactly half the 400x240
		-- reference the hotspot fractions above are relative to) is
		-- smaller than the reference the hotspots were authored against.
		-- Every hotspot's rect must shrink right along with it, not stay
		-- anchored to the old (now-wrong) reference size.
		build_main_menu!
		ground_w, ground_h = 200, 120
		screen.show_screen("main_menu")
		dispatch "draw_choice"
		-- ground centered: ox = getWidth!/2 - (ground_w/2)*scale = 200 - 100 = 100
		--                  oy = getHeight!/2 - (ground_h/2)*scale = 120 - 60 = 60
		-- hotspot 1 (fraction x=0, w=50/400=0.125) -> screen rect
		-- x: 100 + 0*200 = 100, w: 0.125*200 = 25 -> spans x 100-125
		dispatch "touch", {x: 110, y: 65}
		assert.are.equal(interpreter.n, 1)
		assert.are.equal(next_ins_calls, 1)

	it "hotspot rects also scale with sx/sy same as images.moon's draw_background", ->
		-- separately from image-resize (above), a device-scale difference
		-- (e.g. a New 3DS wide top screen) must apply too.
		build_main_menu!
		_G.sx, _G.sy = 2, 2
		screen.show_screen("main_menu")
		dispatch "draw_choice"
		-- ground_w/h == 400x240 (unchanged), scale=2:
		-- ox = 200 - 200*2 = -200, oy = 120 - 120*2 = -120
		-- hotspot 1 (fraction x=0, w=0.125) -> x: -200 + 0*400*2 = -200, w: 0.125*400*2 = 100
		-- -> spans x -200 to -100
		dispatch "touch", {x: -150, y: -100}
		assert.are.equal(interpreter.n, 1)
		assert.are.equal(next_ins_calls, 1)
