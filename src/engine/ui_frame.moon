-- Real 9-patch/Frame() rendering (VN3DS-spec.md §6, the custom UI-asset-
-- import system): fixed-size corners, edges/center either stretched or
-- tiled to fit an arbitrary destination size, matching Ren'Py's own
-- Frame(image, borders, tile=...) behavior exactly -- confirmed real
-- content: Mice Tea's namebox genuinely tiles its border, not stretches
-- (`gui.namebox_tile = True`), while its choice buttons stretch
-- (`gui.choice_button_tile = False`). Degenerates to a single plain scaled
-- draw when `borders` is all zero (used for the dialogue textbox, which
-- has no Frame() at all in either target game -- one code path for both
-- "richly bordered" and "plain image" chrome).
local *

-- Draws one source region (sx, sy, sw, sh) into one destination region
-- (dx, dy, dw, dh): stretched (tile=false, a Quad scaled to fit) or tiled
-- (tile=true) -- LÖVE's own wrap-mode technique, a single draw call either
-- way: the image's wrap mode is set to "repeat" and the Quad's viewport is
-- sized to the *destination* rather than the source, so out-of-bounds
-- sampling wraps around and repeats the source tile automatically instead
-- of stretching it.
draw_region = (image, sx, sy, sw, sh, dx, dy, dw, dh, tile) ->
	return if dw <= 0 or dh <= 0 or sw <= 0 or sh <= 0
	iw, ih = image\getDimensions!
	if tile
		image\setWrap("repeat", "repeat")
		quad = lg.newQuad(sx, sy, dw, dh, iw, ih)
		lg.draw(image, quad, dx, dy)
	else
		quad = lg.newQuad(sx, sy, sw, sh, iw, ih)
		lg.draw(image, quad, dx, dy, 0, dw / sw, dh / sh)

-- image: a real love.graphics.Image (already loaded). borders: a 4-tuple
-- {left, top, right, bottom} in the image's *own* source pixels. tile:
-- true/false, applied to the 4 edges + center only (corners are always 1:1,
-- per real Frame() semantics -- tiling/stretching a corner would distort
-- the one part of a 9-patch that's specifically meant to stay pixel-exact).
-- (x, y, w, h): the destination rectangle to fill, in screen pixels.
draw_frame = (image, borders, tile, x, y, w, h) ->
	iw, ih = image\getDimensions!
	l, t, r, b = borders[1], borders[2], borders[3], borders[4]
	-- Clamp so a destination smaller than the combined border widths
	-- (a degenerate/misconfigured case) never draws negative-sized or
	-- overlapping regions -- shrinks each border proportionally rather
	-- than crashing.
	cw = math.min(l + r, w)
	ch = math.min(t + b, h)
	l = math.min(l, cw)
	r = cw - l
	t = math.min(t, ch)
	b = ch - t

	-- 4 corners: always 1:1, never scaled or tiled.
	if l > 0 and t > 0
		draw_region(image, 0, 0, l, t, x, y, l, t, false)
	if r > 0 and t > 0
		draw_region(image, iw - r, 0, r, t, x + w - r, y, r, t, false)
	if l > 0 and b > 0
		draw_region(image, 0, ih - b, l, b, x, y + h - b, l, b, false)
	if r > 0 and b > 0
		draw_region(image, iw - r, ih - b, r, b, x + w - r, y + h - b, r, b, false)

	-- 4 edges + center: stretched or tiled per `tile`.
	mid_w, mid_h = w - l - r, h - t - b
	src_mid_w, src_mid_h = iw - l - r, ih - t - b
	if t > 0 and mid_w > 0 and src_mid_w > 0
		draw_region(image, l, 0, src_mid_w, t, x + l, y, mid_w, t, tile)
	if b > 0 and mid_w > 0 and src_mid_w > 0
		draw_region(image, l, ih - b, src_mid_w, b, x + l, y + h - b, mid_w, b, tile)
	if l > 0 and mid_h > 0 and src_mid_h > 0
		draw_region(image, 0, t, l, src_mid_h, x, y + t, l, mid_h, tile)
	if r > 0 and mid_h > 0 and src_mid_h > 0
		draw_region(image, iw - r, t, r, src_mid_h, x + w - r, y + t, r, mid_h, tile)
	if mid_w > 0 and mid_h > 0 and src_mid_w > 0 and src_mid_h > 0
		draw_region(image, l, t, src_mid_w, src_mid_h, x + l, y + t, mid_w, mid_h, tile)

{:draw_frame}
