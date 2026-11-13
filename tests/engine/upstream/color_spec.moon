pprint = require "lib/pprint"
import colorify, hex_to_rgb from require "text/text_color"

describe "Basic Colors", ->
	it "Single Color", ->
		-- colorify now returns a list of run tables ({color:, text:,
		-- bold:, italic:}, plus an optional pause: field) instead of a
		-- flat {color, text, color, text, ...} pair list, so bold/italic/
		-- pause markers (VN3DS's own extension for Ren'Py's {b}{i}{w}{p}
		-- tags) can ride alongside color runs without changing shape.
		assert.are.equal("demon", colorify("x1b[32;1mdemon")[1].text)
	it "No Color", ->
		assert.are.equal("hello", colorify("hello")[1].text)

describe "Extended escape codes (Ren'Py {color}/{b}/{i}/{w}/{p} tags)", ->
	it "decodes an arbitrary hex color, not just the fixed 8-color palette", ->
		runs = colorify("x1b[#3a7bffmHello")
		assert.are.equal(runs[1].text, "Hello")
		assert.are.same(runs[1].color, hex_to_rgb("3a7bff"))

	it "a reset (x1b[0m) clears both color and bold/italic state", ->
		runs = colorify("x1b[1mx1b[#ff0000mBoldRedx1b[0mPlain")
		assert.is_true(runs[1].bold)
		assert.are.same(runs[1].color, hex_to_rgb("ff0000"))
		assert.is_false(runs[2].bold)

	it "bold (1m/22m) and italic (3m/23m) toggle independently of color", ->
		runs = colorify("x1b[1mboldx1b[22mx1b[3mitalicx1b[23m")
		assert.are.equal(runs[1].text, "bold")
		assert.is_true(runs[1].bold)
		assert.is_false(runs[1].italic)
		assert.are.equal(runs[2].text, "italic")
		assert.is_false(runs[2].bold)
		assert.is_true(runs[2].italic)

	it "a color change preserves whatever bold/italic state is already active", ->
		runs = colorify("x1b[1mx1b[#00ff00mstill bold")
		assert.is_true(runs[1].bold)
		assert.are.same(runs[1].color, hex_to_rgb("00ff00"))

	it "a pause marker (Pn.n) is a zero-width run carrying no color/style side effect", ->
		runs = colorify("beforex1b[P1.5mafter")
		assert.are.equal(runs[1].text, "before")
		assert.are.equal(runs[2].text, "")
		assert.are.equal(runs[2].pause, 1.5)
		assert.are.equal(runs[3].text, "after")
		-- state (color/bold/italic) carries through the pause unchanged
		assert.is_false(runs[3].bold)
