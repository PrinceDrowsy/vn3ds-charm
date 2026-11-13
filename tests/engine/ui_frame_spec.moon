quad_calls = {}
draw_calls = {}
set_wrap_calls = {}

_G.lg = {
	newQuad: (x, y, w, h, sw, sh) ->
		q = {:x, :y, :w, :h, :sw, :sh}
		table.insert(quad_calls, q)
		q
	draw: (...) -> table.insert(draw_calls, {...})
}

mock_image = (w, h) ->
	{
		getDimensions: -> w, h
		setWrap: (u, v) => table.insert(set_wrap_calls, {:u, :v})
	}

ui_frame = require "ui_frame"
draw_frame = ui_frame.draw_frame

describe "9-patch Frame rendering (VN3DS-spec.md §6, custom UI-asset-import)", ->
	before_each ->
		quad_calls = {}
		draw_calls = {}
		set_wrap_calls = {}

	it "draws all 4 corners at their exact source size, never scaled or tiled", ->
		image = mock_image(20, 20)
		draw_frame(image, {5, 5, 5, 5}, false, 100, 100, 200, 200)
		-- every quad whose w/h == the border size (5) is a corner -- none
		-- of them should trigger setWrap (corners never tile)
		corner_quads = [q for q in *quad_calls when q.w == 5 and q.h == 5]
		assert.are.equal(#corner_quads, 4)
		assert.are.equal(#set_wrap_calls, 0)

	it "stretch mode (tile=false) scales edges/center via a quad + scale-factor draw call", ->
		image = mock_image(20, 20)
		draw_frame(image, {5, 5, 5, 5}, false, 0, 0, 40, 60)
		-- center source is 10x10 (20-5-5), destination is 30x50 (40-5-5, 60-5-5)
		center_draw = nil
		for call in *draw_calls
			-- call: {image, quad, dx, dy, r, sx, sy}
			if call[6] == 3.0 and call[7] == 5.0 -- 30/10, 50/10
				center_draw = call
		assert.is_not_nil(center_draw)
		assert.are.equal(#set_wrap_calls, 0)

	it "tile mode (tile=true) sets wrap to repeat and sizes the quad to the destination, not the source", ->
		image = mock_image(20, 20)
		draw_frame(image, {5, 5, 5, 5}, true, 0, 0, 40, 60)
		assert.is_true(#set_wrap_calls > 0)
		for call in *set_wrap_calls
			assert.are.equal(call.u, "repeat")
			assert.are.equal(call.v, "repeat")
		-- the center region's quad must be sized to the *destination*
		-- (30x50), not the source (10x10) -- confirming real tiling, not a
		-- disguised stretch
		center_quad = nil
		for q in *quad_calls
			if q.w == 30 and q.h == 50
				center_quad = q
		assert.is_not_nil(center_quad)

	it "degenerates to a single plain scaled draw when borders are all zero (textbox's shape)", ->
		image = mock_image(64, 32)
		draw_frame(image, {0, 0, 0, 0}, false, 10, 20, 128, 64)
		assert.are.equal(#quad_calls, 1)
		assert.are.equal(#draw_calls, 1)
		q = quad_calls[1]
		assert.are.equal(q.x, 0)
		assert.are.equal(q.y, 0)
		assert.are.equal(q.w, 64)
		assert.are.equal(q.h, 32)
		call = draw_calls[1]
		assert.are.equal(call[3], 10) -- dx
		assert.are.equal(call[4], 20) -- dy
		assert.are.equal(call[6], 2.0) -- 128/64
		assert.are.equal(call[7], 2.0) -- 64/32

	it "clamps borders when the destination is smaller than the combined border widths, without crashing or drawing negative sizes", ->
		image = mock_image(20, 20)
		draw_frame(image, {15, 15, 15, 15}, false, 0, 0, 10, 10)
		for q in *quad_calls
			assert.is_true(q.w >= 0)
			assert.is_true(q.h >= 0)

	it "an asymmetric border (choice buttons' real shape) positions edges/corners correctly", ->
		-- Mice Tea's real choice_button_borders: (150, 22, 150, 8)
		image = mock_image(400, 100)
		draw_frame(image, {150, 22, 150, 8}, false, 0, 0, 500, 100)
		-- right corner's source x should start at iw - r = 400 - 150 = 250
		right_corner = nil
		for q in *quad_calls
			if q.x == 250 and q.w == 150 and q.h == 22
				right_corner = q
		assert.is_not_nil(right_corner)
