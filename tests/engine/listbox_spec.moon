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

rect_calls = {}
frame_draw_calls = {}
quad_calls = {}
mock_images = {}
mock_image = (path) ->
	unless mock_images[path]
		mock_images[path] = {
			path: path
			getDimensions: -> 64, 32
			setWrap: (u, v) =>
		}
	mock_images[path]

_G.love = {
	graphics: {
		newImage: (path) -> mock_image(path)
		setColor: (...) ->
		setFont: (...) ->
		print: (...) ->
		rectangle: (...) -> table.insert(rect_calls, {...})
		newQuad: (x, y, w, h, sw, sh) ->
			q = {:x, :y, :w, :h, :sw, :sh}
			table.insert(quad_calls, q)
			q
		draw: (image, ...) -> table.insert(frame_draw_calls, {:image, ...})
		getWidth: -> 400
		getHeight: -> 240
	}
	filesystem: {
		getInfo: (path) -> nil
		read: (path) -> nil
	}
}
_G.lg = love.graphics
_G.lfs = love.filesystem
_G.interpreter = nil
_G.center = (size, bound) -> (bound - size) / 2

import ui from require "ui_assets"
import create_listbox from require "listbox"

describe "Shared choice/menu widget (listbox.moon) button chrome (VN3DS-spec.md §6)", ->
	before_each ->
		rect_calls = {}
		frame_draw_calls = {}
		quad_calls = {}
		for key in pairs(ui) do ui[key] = nil

	make_choices = -> {
		{text: "First option", action: (chosen, close) -> false}
		{text: "Second option", action: (chosen, close) -> false}
	}

	it "draws one shared flat-color panel behind every row when no button chrome is declared", ->
		create_listbox {choices: make_choices!, selected: 1}
		dispatch "draw_choice"
		assert.is_true(#rect_calls > 0)
		assert.are.equal(#frame_draw_calls, 0)

	it "draws a real per-row background via draw_frame for each choice when button chrome is declared, skipping the shared panel", ->
		ui.choice_idle = {image: mock_image("choice_idle.t3x"), borders: {150, 22, 150, 8}, tile: false}
		ui.choice_hover = {image: mock_image("choice_hover.t3x"), borders: {150, 22, 150, 8}, tile: false}
		create_listbox {choices: make_choices!, selected: 1}
		dispatch "draw_choice"
		assert.are.equal(#rect_calls, 0)
		assert.is_true(#frame_draw_calls >= 2) -- one per row

	it "uses the hover image for the selected row and the idle image for the rest", ->
		-- a single draw_frame call can emit several sub-region draws
		-- (corners/edges/center, all sharing the same image), so this
		-- checks *presence*, not an exact per-row draw count.
		ui.choice_idle = {image: mock_image("choice_idle.t3x"), borders: {150, 22, 150, 8}, tile: false}
		ui.choice_hover = {image: mock_image("choice_hover.t3x"), borders: {150, 22, 150, 8}, tile: false}
		create_listbox {choices: make_choices!, selected: 2}
		dispatch "draw_choice"
		hover_draws = [c for c in *frame_draw_calls when c.image.path == "choice_hover.t3x"]
		idle_draws = [c for c in *frame_draw_calls when c.image.path == "choice_idle.t3x"]
		assert.is_true(#hover_draws > 0)
		assert.is_true(#idle_draws > 0)
