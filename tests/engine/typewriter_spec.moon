require "util"
pprint = require "lib/pprint"
event = require "event"
_G.dispatch = event.dispatch
_G.dispatch_often = event.dispatch_often
_G.on = event.on
_G.remove = event.remove
_G.register = event.register

print_calls = {}
rect_calls = {}
quad_calls = {}
frame_draw_calls = {}
mock_font = {
	getHeight: -> 20
	getWidth: (self, text) -> #text * 8
}
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
		getWidth: -> 400
		getHeight: -> 240
		setFont: (fontArg) ->
		getFont: -> mock_font
		setColor: (...) ->
		rectangle: (...) -> table.insert(rect_calls, {...})
		print: (text, x, y) -> table.insert(print_calls, {:text, :x, :y})
		newQuad: (x, y, w, h, sw, sh) ->
			q = {:x, :y, :w, :h, :sw, :sh}
			table.insert(quad_calls, q)
			q
		draw: (image, ...) -> table.insert(frame_draw_calls, {:image, ...})
		newImage: (path) -> mock_image(path)
	}
	filesystem: {
		getInfo: (path) -> nil
		read: (path) -> nil
	}
	_console_name: "Test"
}
_G.lg = love.graphics
_G.lfs = love.filesystem
_G.font = mock_font
_G.text_font = mock_font
_G.interpreter = nil

import ui from require "ui_assets"
require "text/text"

-- helper: how many total characters were actually handed to lg.print this
-- frame. Each print call now carries one run's plain text string directly
-- (text.moon draws per-run, not LOVE's native flat color/text pair table),
-- so this is just each call's own text length -- no pair-unpacking needed.
rendered_char_count = ->
	total = 0
	for call in *print_calls
		total += #call.text
	return total

describe "Typewriter reveal", ->
	before_each ->
		print_calls = {}
		dispatch "restore", {} -- reset text.moon's module state between tests

	it "reveals nothing before the first update tick", ->
		dispatch "text", {text: "Hello there friend"}
		dispatch "draw_text"
		assert.are.equal(rendered_char_count!, 0)

	it "reveals more characters as time passes", ->
		dispatch "text", {text: "Hello there friend"}
		dispatch "update", 0.1 -- 40 chars/sec * 0.1s = 4 chars
		print_calls = {}
		dispatch "draw_text"
		first_count = rendered_char_count!
		assert.is_true(first_count > 0)

		dispatch "update", 0.5
		print_calls = {}
		dispatch "draw_text"
		second_count = rendered_char_count!
		assert.is_true(second_count > first_count)

	it "eventually reveals the full line and stops growing", ->
		dispatch "text", {text: "Short line"}
		for i = 1, 50 do dispatch "update", 0.1 -- way more than enough time
		print_calls = {}
		dispatch "draw_text"
		fully_revealed_count = rendered_char_count!
		assert.is_true(fully_revealed_count > 0)

		dispatch "update", 1 -- more time should not reveal anything further
		print_calls = {}
		dispatch "draw_text"
		assert.are.equal(rendered_char_count!, fully_revealed_count)

	it "pressing A while still revealing skips to the full line instead of advancing", ->
		next_ins_fired = false
		on "next_ins", -> next_ins_fired = true
		dispatch "text", {text: "A longer line of dialogue text"}
		dispatch "update", 0.01 -- barely started revealing
		print_calls = {}
		dispatch "draw_text"
		partial_count = rendered_char_count!

		dispatch "input", "a"
		assert.is_false(next_ins_fired)
		print_calls = {}
		dispatch "draw_text"
		assert.is_true(rendered_char_count! > partial_count)

	it "pressing A after fully revealed advances to the next instruction", ->
		next_ins_fired = false
		on "next_ins", -> next_ins_fired = true
		dispatch "text", {text: "Short"}
		for i = 1, 50 do dispatch "update", 0.1
		dispatch "input", "a"
		assert.is_true(next_ins_fired)

	it "a real line of dialogue re-shows the window even after a prior window hide with no window show", ->
		-- real hardware bug: Ren'Py's "window hide" is transient -- it
		-- only suppresses the dialogue box until the *next* real line of
		-- dialogue, which auto-shows it again; it is not a persistent
		-- toggle. Confirmed against Jisei's own source: `label
		-- cafeexamine:` opens with `window hide` and never calls `window
		-- show` before its own dialogue lines. This engine treated
		-- "window hide" as sticky, so selecting "Examine Room" showed no
		-- flavor text at all before returning to the café menu.
		dispatch "window", {state: "hide"}
		dispatch "text", {text: "This area is small, but comfortable."}
		for i = 1, 50 do dispatch "update", 0.1
		print_calls = {}
		dispatch "draw_text"
		assert.is_true(#print_calls > 0)

	it "a new dialogue line replaces the box instead of piling up alongside the previous one", ->
		-- real hardware bug: every ordinary `text` event only replaced the
		-- box once the accumulated buffer happened to already equal
		-- `lines` (a paging threshold meant for one long wrapped
		-- paragraph) -- in every other case it just concatenated onto
		-- whatever was already showing. On real Ren'Py-converted content,
		-- every say statement is its own separate `text` dispatch, so
		-- unrelated lines from different speakers piled up together in
		-- the box (confirmed on real hardware: several lines of dialogue
		-- from different characters all visible at once, looking like one
		-- continuous run-on line).
		dispatch "text", {text: "First speaker's line"}
		for i = 1, 50 do dispatch "update", 0.1
		dispatch "text", {text: "Second speaker's line"}
		for i = 1, 50 do dispatch "update", 0.1

		print_calls = {}
		dispatch "draw_text"
		rendered_text = ""
		for call in *print_calls
			rendered_text ..= call.text
		assert.is_nil(rendered_text\find("First"))
		assert.is_not_nil(rendered_text\find("Second"))

	it "wraps text so its right edge leaves a margin matching the left, instead of reaching the screen edge", ->
		-- real hardware bug: word_wrap's max_width didn't account for
		-- draw_text's own 2*pad text origin (the box's own left edge at
		-- x=pad, plus one more pad of inner margin) -- a line wrapped to
		-- text_box_width!-2*pad (measuring from 0) actually reached
		-- x = 2*pad + (text_box_width!-2*pad) = text_box_width!, the
		-- screen's absolute right edge, with no margin to match the left.
		-- Confirmed on real hardware: word-wrap consistently let lines run
		-- to (and get cut off at) the edge instead of an inset box.
		--
		-- mock_font here is 8px/char, text_box_width! is 400 (this mock's
		-- fixed lg.getWidth!()), pad is 10. Two 23-char words plus a space
		-- (47 chars = 376px) fit on one line under the old, buggy max_width
		-- (400-2*pad = 380) but must wrap under the fixed one
		-- (400-4*pad = 360).
		word = string.rep("a", 23)
		dispatch "text", {text: word .. " " .. word}
		for i = 1, 50 do dispatch "update", 0.1
		print_calls = {}
		dispatch "draw_text"
		assert.are.equal(#print_calls, 2)

	it "sizes the dialogue box (and nameplate above it) to the actual visible line count, not the full paging capacity", ->
		-- real hardware bug: the box's height (and therefore its y
		-- position, and the nameplate drawn above that) was computed from
		-- the fixed `lines` capacity (7 on 3DS) every frame regardless of
		-- how much text was actually showing. Once a normal line replaces
		-- the box outright (usually just 1 wrapped line), that reserved
		-- height pushed the box -- and the nameplate above it -- up past
		-- the top of the screen. Confirmed on real hardware: the nameplate
		-- was positioned too high, partially cut off at the screen's top.
		dispatch "nameplate", {name: "Eileen"}
		dispatch "text", {text: "Short"}
		for i = 1, 50 do dispatch "update", 0.1

		rect_calls = {}
		lg.rectangle = (mode, x, y, w, h) -> table.insert(rect_calls, {:x, :y, :w, :h})
		dispatch "draw_text"

		-- box is the second rectangle (nameplate plate is drawn first)
		box = rect_calls[2]
		-- font height 20, pad 10, 1 visible line -> h = 10 + (20+10)*1 = 40
		assert.are.equal(box.h, 40)
		-- box must stay fully on screen: y >= 0 (screen height 240 in this mock)
		assert.is_true(box.y >= 0)
		-- nameplate plate sits directly above the box and must also stay
		-- on screen
		plate = rect_calls[1]
		assert.is_true(plate.y >= 0)

describe "Styled text runs ({b}/{i}/{color}/{w}/{p} tags, translated by the converter into escape codes)", ->
	before_each ->
		print_calls = {}
		dispatch "restore", {}

	it "a bold run double-draws offset by 1px (no second font weight available)", ->
		dispatch "text", {text: "x1b[1mbold"}
		for i = 1, 50 do dispatch "update", 0.1
		print_calls = {}
		dispatch "draw_text"
		bold_calls = [c for c in *print_calls when c.text == "bold"]
		assert.are.equal(#bold_calls, 2)
		xs = [c.x for c in *bold_calls]
		table.sort(xs)
		assert.are.equal(xs[2] - xs[1], 1)

	it "an italic run draws once, sheared via love.graphics.print's kx parameter", ->
		orig_print = lg.print
		print_args = {}
		lg.print = (...) -> table.insert(print_args, {...})
		dispatch "text", {text: "x1b[3mitalic"}
		for i = 1, 50 do dispatch "update", 0.1
		print_args = {}
		dispatch "draw_text"
		italic_calls = [a for a in *print_args when a[1] == "italic"]
		assert.are.equal(#italic_calls, 1)
		assert.is_true(italic_calls[1][9] < 0) -- kx (9th positional arg) is non-zero/negative
		lg.print = orig_print

	it "a plain (non-bold, non-italic) run draws exactly once", ->
		dispatch "text", {text: "plain"}
		for i = 1, 50 do dispatch "update", 0.1
		print_calls = {}
		dispatch "draw_text"
		plain_calls = [c for c in *print_calls when c.text == "plain"]
		assert.are.equal(#plain_calls, 1)

	it "a pause run consumes reveal budget as phantom characters, with no visible text of its own", ->
		-- a "P1.0" pause is modeled as typewriter_speed (40 chars/sec) * 1.0
		-- = 40 phantom characters of budget -- advancing 39 real chars'
		-- worth of time must not yet reach the text *after* the pause.
		dispatch "text", {text: "hix1b[P1.0mthere"}
		dispatch "update", 39 / 40 -- just under the pause's phantom-char budget
		print_calls = {}
		dispatch "draw_text"
		rendered = ""
		for c in *print_calls do rendered ..= c.text
		assert.are.equal(rendered, "hi")

		dispatch "update", 2 -- comfortably past the pause now
		print_calls = {}
		dispatch "draw_text"
		rendered = ""
		for c in *print_calls do rendered ..= c.text
		assert.are.equal(rendered, "hithere")

	it "a color escape changes the run's draw color, defaulting back to colorify's reset", ->
		color_calls = {}
		lg.setColor = (...) -> table.insert(color_calls, {...})
		dispatch "text", {text: "x1b[#3a7bffmblue"}
		for i = 1, 50 do dispatch "update", 0.1
		color_calls = {}
		dispatch "draw_text"
		-- the run's own setColor call (not the box background/reset calls)
		found = false
		for call in *color_calls
			if type(call[1]) == "table" and math.abs(call[1][1] - (0x3a/255)) < 0.01
				found = true
		assert.is_true(found)

describe "Nameplate color (Character(color=...), VN3DS-spec.md §6)", ->
	before_each ->
		dispatch "restore", {}

	it "renders the nameplate in the character's own color when given", ->
		color_calls = {}
		lg.setColor = (...) -> table.insert(color_calls, {...})
		dispatch "nameplate", {name: "Eileen", color: "ff0000"}
		dispatch "text", {text: "Hi"}
		for i = 1, 50 do dispatch "update", 0.1
		color_calls = {}
		dispatch "draw_text"
		found = false
		for call in *color_calls
			if type(call[1]) == "table" and call[1][1] > 0.9 and call[1][2] < 0.1
				found = true
		assert.is_true(found)

	it "falls back to plain white when the character has no explicit color", ->
		dispatch "nameplate", {name: "Eileen"}
		dispatch "text", {text: "Hi"}
		for i = 1, 50 do dispatch "update", 0.1
		print_calls = {}
		dispatch "draw_text"
		name_calls = [c for c in *print_calls when c.text == "Eileen"]
		assert.are.equal(#name_calls, 1)

describe "Custom UI-asset-import chrome (VN3DS-spec.md §6, textbox/namebox)", ->
	before_each ->
		dispatch "restore", {}
		rect_calls = {}
		quad_calls = {}
		frame_draw_calls = {}
		for key in pairs(ui) do ui[key] = nil

	it "draws the real textbox image via draw_frame instead of a flat rectangle when ui.textbox is set", ->
		ui.textbox = {image: mock_image("textbox.t3x")}
		dispatch "text", {text: "Hi"}
		for i = 1, 50 do dispatch "update", 0.1
		rect_calls, frame_draw_calls = {}, {}
		dispatch "draw_text"
		assert.is_true(#frame_draw_calls > 0)
		assert.are.equal(frame_draw_calls[1].image.path, "textbox.t3x")
		-- the textbox's own flat-color rectangle must not have drawn too
		box_rects = [c for c in *rect_calls when c[4] != nil and c[4] > 100] -- w > 100 -> the box, not the nameplate
		assert.are.equal(#box_rects, 0)

	it "falls back to the flat-color rectangle when ui.textbox is not set", ->
		dispatch "text", {text: "Hi"}
		for i = 1, 50 do dispatch "update", 0.1
		rect_calls, frame_draw_calls = {}, {}
		dispatch "draw_text"
		assert.are.equal(#frame_draw_calls, 0)
		assert.is_true(#rect_calls > 0)

	it "draws the real namebox image via draw_frame when ui.namebox is set", ->
		ui.namebox = {image: mock_image("namebox.t3x"), borders: {5, 5, 5, 5}, tile: true}
		dispatch "nameplate", {name: "Eileen"}
		dispatch "text", {text: "Hi"}
		for i = 1, 50 do dispatch "update", 0.1
		frame_draw_calls = {}
		dispatch "draw_text"
		namebox_draws = [c for c in *frame_draw_calls when c.image.path == "namebox.t3x"]
		assert.is_true(#namebox_draws > 0)

	it "uses a character's own namebox override image, keyed by display name, while keeping the shared border/tile metrics", ->
		ui.namebox = {image: mock_image("namebox.t3x"), borders: {5, 5, 5, 5}, tile: true}
		ui.character_namebox = {"Margaret": {image: mock_image("nameboxM.t3x")}}
		dispatch "nameplate", {name: "Margaret"}
		dispatch "text", {text: "Hi"}
		for i = 1, 50 do dispatch "update", 0.1
		frame_draw_calls = {}
		dispatch "draw_text"
		override_draws = [c for c in *frame_draw_calls when c.image.path == "nameboxM.t3x"]
		assert.is_true(#override_draws > 0)
		default_draws = [c for c in *frame_draw_calls when c.image.path == "namebox.t3x"]
		assert.are.equal(#default_draws, 0)

describe "Custom game font (update_font)", ->
	after_each ->
		_G.interpreter = nil
		_G.path_exists = nil
		dispatch "restore", {}

	it "loads the game's own default.ttf via path_exists, not the unreliable lfs.getInfo", ->
		-- real hardware bug: lfs.getInfo is unreliable on LÖVE Potion
		-- 2.0.0's 3DS filesystem backend (it can report false for a file
		-- getDirectoryItems clearly lists) -- main.moon's path_exists was
		-- already written to work around exactly this elsewhere, but
		-- update_font still used a fresh lfs.getInfo call of its own.
		-- Found while wiring Jisei's real font ("gui/HanSrf.ttf") through
		-- for the first time -- this whole path was previously dead code.
		_G.interpreter = {base_dir: "novels/test/"}
		checked_paths = {}
		_G.path_exists = (path) ->
			table.insert(checked_paths, path)
			path == "novels/test/default.ttf"
		newFont_calls = {}
		lg.newFont = (path, size) ->
			table.insert(newFont_calls, {:path, :size})
			mock_font

		dispatch "config", {font: {override_font: false}}

		-- update_typewriter_speed's own text_cps.txt check also fires on
		-- "config" now, so default.ttf's check is no longer the only path
		-- checked -- still first, though (update_font runs before it).
		assert.are.equal(checked_paths[1], "novels/test/default.ttf")
		assert.are.equal(#newFont_calls, 1)
		assert.are.equal(newFont_calls[1].path, "novels/test/default.ttf")

	it "sizes the custom font the same way main.moon sizes the default one (20 on a narrow screen, not a hardcoded 32)", ->
		-- real hardware bug: the custom font always loaded at a hardcoded
		-- size 32, ignoring the same screen-width-based sizing main.moon's
		-- own love.resize already uses for the default font -- on the
		-- O3DS's narrow physical bottom screen this rendered larger than
		-- intended, worsening rather than fixing overflow.
		_G.interpreter = {base_dir: "novels/test/"}
		_G.path_exists = -> true
		newFont_calls = {}
		lg.newFont = (path, size) ->
			table.insert(newFont_calls, {:path, :size})
			mock_font

		dispatch "config", {font: {override_font: false}}

		-- this mock's lg.getWidth!() is 400 (< 600) -> narrow-screen sizing
		assert.are.equal(newFont_calls[1].size, 20)

	it "falls back to the built-in font when no default.ttf is declared", ->
		_G.interpreter = {base_dir: "novels/test/"}
		_G.path_exists = -> false

		dispatch "config", {font: {override_font: false}}

		assert.are.equal(text_font, font)

describe "Custom game typewriter speed (config.default_text_cps/text_cps)", ->
	after_each ->
		_G.interpreter = nil
		_G.path_exists = nil
		lfs.read = nil
		dispatch "restore", {}

	it "uses the game's own text_cps.txt value instead of the hardcoded 40 cps default", ->
		_G.interpreter = {base_dir: "novels/test/"}
		_G.path_exists = (path) -> path == "novels/test/text_cps.txt"
		lfs.read = (path) -> "80" -- double the hardcoded default

		dispatch "config", {font: {override_font: false}}
		dispatch "restore", {}
		dispatch "text", {text: "0123456789"} -- 10 chars
		dispatch "update", 0.1 -- at 80 cps -> 8 chars revealed
		print_calls = {}
		dispatch "draw_text"
		rendered = ""
		for c in *print_calls do rendered ..= c.text
		assert.are.equal(rendered, "01234567")

	it "falls back to the hardcoded 40 cps default when no text_cps.txt is declared", ->
		_G.interpreter = {base_dir: "novels/test/"}
		_G.path_exists = -> false

		dispatch "config", {font: {override_font: false}}
		dispatch "restore", {}
		dispatch "text", {text: "0123456789"}
		dispatch "update", 0.1 -- at the default 40 cps -> 4 chars revealed
		print_calls = {}
		dispatch "draw_text"
		rendered = ""
		for c in *print_calls do rendered ..= c.text
		assert.are.equal(rendered, "0123")

describe "Player-set text-speed override (config.moon settings screen, Phase 3.8)", ->
	after_each ->
		_G.interpreter = nil
		_G.path_exists = nil
		lfs.read = nil
		dispatch "restore", {}

	it "a player override wins over the game's own text_cps.txt default", ->
		_G.interpreter = {base_dir: "novels/test/"}
		_G.path_exists = (path) -> path == "novels/test/text_cps.txt"
		lfs.read = (path) -> "80" -- the game's own authored default

		dispatch "config", {font: {override_font: false}, text: {speed_cps: 20}}
		dispatch "restore", {}
		dispatch "text", {text: "0123456789"}
		dispatch "update", 0.1 -- at the player's 20 cps -> 2 chars revealed
		print_calls = {}
		dispatch "draw_text"
		rendered = ""
		for c in *print_calls do rendered ..= c.text
		assert.are.equal(rendered, "01")

	it "a player override wins over the hardcoded 40 cps fallback when no text_cps.txt exists", ->
		_G.interpreter = {base_dir: "novels/test/"}
		_G.path_exists = -> false

		dispatch "config", {font: {override_font: false}, text: {speed_cps: 100}}
		dispatch "restore", {}
		dispatch "text", {text: "0123456789"}
		dispatch "update", 0.1 -- at the player's 100 cps -> all 10 chars revealed
		print_calls = {}
		dispatch "draw_text"
		rendered = ""
		for c in *print_calls do rendered ..= c.text
		assert.are.equal(rendered, "0123456789")

	it "a config dispatch with no text section at all (backward-compat) does not crash and keeps the prior override in effect", ->
		_G.interpreter = {base_dir: "novels/test/"}
		_G.path_exists = -> false

		dispatch "config", {font: {override_font: false}, text: {speed_cps: 100}}
		dispatch "config", {font: {override_font: false}} -- e.g. an older/partial payload
		dispatch "restore", {}
		dispatch "text", {text: "0123456789"}
		dispatch "update", 0.1
		print_calls = {}
		dispatch "draw_text"
		rendered = ""
		for c in *print_calls do rendered ..= c.text
		-- the second dispatch's missing @text clears the override back to
		-- nil (speed_override = @text and @text.speed_cps), so this falls
		-- back to the hardcoded 40 cps default -- 4 chars in 0.1s -- not a
		-- stale 100 cps read.
		assert.are.equal(rendered, "0123")
