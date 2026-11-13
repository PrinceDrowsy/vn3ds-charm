-- extended: a real, small "positioned text overlay" engine feature (not an
-- approximation) -- VNDS's existing dialogue box is fixed position/size/
-- one font, and the custom-screen runtime (screen.moon) is purpose-built
-- for interactive menus (listbox-based), neither of which can reproduce a
-- Ren'Py title-card/chapter-heading beat (freeform positioned/sized/
-- colored static text over a plain background). Confirmed real need: Mice
-- Tea's custom `day`/`subchapter`/`the_end` statements (statements.rpy)
-- all show exactly this shape. Drawn in its own pass (main.moon's
-- "draw_overlay", between background/foreground and the dialogue box) so
-- it layers correctly regardless of which screen mode is active.
local *
entries = {}
font_cache = {}

get_font = (size) ->
	unless font_cache[size]
		font_cache[size] = lg.newFont(size)
	font_cache[size]

-- Converts a bare hex color ("fff" or "ffffff", no "#") to 0.0-1.0 RGB --
-- vnds_writer.py already strips the "#" Ren'Py's own color strings use,
-- since VNDS commands are plain whitespace-delimited tokens.
hex_to_rgb = (hex) ->
	if #hex == 3
		hex = hex\gsub("(.)", "%1%1")
	r = (tonumber(hex\sub(1, 2), 16) or 255) / 255
	g = (tonumber(hex\sub(3, 4), 16) or 255) / 255
	b = (tonumber(hex\sub(5, 6), 16) or 255) / 255
	r, g, b

on "overlay_text", =>
	-- x/y are the text's on-screen *center* point, matching the same
	-- horizontal-center-anchor convention images.moon's sprites already
	-- use -- real content (Mice Tea's day/subchapter/the_end text) is
	-- always xalign-centered.
	entries[@id] = {x: @x, y: @y, size: @size, color: @color, text: @text}

on "overlay_clear", -> entries = {}

on "save", =>
	@overlay = [{:id, x: e.x, y: e.y, size: e.size, color: e.color, text: e.text} for id, e in pairs(entries)]

on "restore", =>
	entries = {}
	if @overlay
		for e in *@overlay
			entries[e.id] = {x: e.x, y: e.y, size: e.size, color: e.color, text: e.text}

on "draw_overlay", ->
	return unless next(entries)
	pscale = math.min(px, py)
	for _id, e in pairs(entries)
		font = get_font(math.max(1, math.floor(e.size * pscale)))
		lg.setFont(font)
		r, g, b = hex_to_rgb(e.color)
		lg.setColor(r, g, b, 1)
		w = font\getWidth(e.text)
		lg.print(e.text, e.x * pscale - w / 2, e.y * pscale)
	lg.setColor(1, 1, 1, 1)
