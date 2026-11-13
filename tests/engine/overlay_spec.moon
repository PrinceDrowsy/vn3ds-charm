require "util"
pprint = require "lib/pprint"
event = require "event"
_G.dispatch = event.dispatch
_G.dispatch_often = event.dispatch_often
_G.on = event.on
_G.remove = event.remove
_G.register = event.register

_G.px, _G.py = 1, 1
_G.lg = {
	newFont: (size) -> {getWidth: (self, text) -> #text * size / 2}
	setFont: (...) ->
	setColor: (...) ->
	print: (...) ->
}

require "overlay"

describe "Text overlay (title-card/chapter-heading system)", ->
	before_each -> dispatch "overlay_clear"

	it "draws nothing when no overlay text has been set", ->
		draw_calls = {}
		lg.print = (...) -> table.insert(draw_calls, {...})
		dispatch "draw_overlay"
		assert.are.equal(#draw_calls, 0)

	it "draws a positioned/sized overlay text entry, centered horizontally at x", ->
		dispatch "overlay_text", {id: "day", x: 200, y: 40, size: 80, color: "fff", text: "Day"}
		draw_calls = {}
		lg.print = (...) -> table.insert(draw_calls, {...})
		dispatch "draw_overlay"
		assert.are.equal(#draw_calls, 1)
		call = draw_calls[1]
		assert.are.equal(call[1], "Day")
		-- centered: x*pscale - textwidth/2 == 200 - (3*80/2)/2 == 200 - 60 == 140
		assert.are.equal(call[2], 140)
		assert.are.equal(call[3], 40)

	it "keeps multiple overlay entries independent (day/subtitle stacked)", ->
		dispatch "overlay_text", {id: "day", x: 200, y: 40, size: 80, color: "fff", text: "Day"}
		dispatch "overlay_text", {id: "subtitle", x: 200, y: 210, size: 48, color: "fff", text: "Routines"}
		draw_calls = {}
		lg.print = (...) -> table.insert(draw_calls, {...})
		dispatch "draw_overlay"
		assert.are.equal(#draw_calls, 2)

	it "overlay_clear removes every entry", ->
		dispatch "overlay_text", {id: "day", x: 200, y: 40, size: 80, color: "fff", text: "Day"}
		dispatch "overlay_clear"
		draw_calls = {}
		lg.print = (...) -> table.insert(draw_calls, {...})
		dispatch "draw_overlay"
		assert.are.equal(#draw_calls, 0)

	it "a later overlay_text with the same id replaces the earlier one, not stacks", ->
		dispatch "overlay_text", {id: "day", x: 200, y: 40, size: 80, color: "fff", text: "Day"}
		dispatch "overlay_text", {id: "day", x: 200, y: 40, size: 80, color: "fff", text: "Day 2"}
		draw_calls = {}
		lg.print = (...) -> table.insert(draw_calls, {...})
		dispatch "draw_overlay"
		assert.are.equal(#draw_calls, 1)
		assert.are.equal(draw_calls[1][1], "Day 2")

	it "round-trips overlay state through save/restore", ->
		dispatch "overlay_text", {id: "day", x: 200, y: 40, size: 80, color: "fff", text: "Day"}
		saved = {}
		dispatch "save", saved
		dispatch "overlay_clear"
		dispatch "restore", saved
		draw_calls = {}
		lg.print = (...) -> table.insert(draw_calls, {...})
		dispatch "draw_overlay"
		assert.are.equal(#draw_calls, 1)
		assert.are.equal(draw_calls[1][1], "Day")

	it "restoring an empty save (fresh game) clears any overlay text", ->
		dispatch "overlay_text", {id: "day", x: 200, y: 40, size: 80, color: "fff", text: "Day"}
		dispatch "restore", {}
		draw_calls = {}
		lg.print = (...) -> table.insert(draw_calls, {...})
		dispatch "draw_overlay"
		assert.are.equal(#draw_calls, 0)
