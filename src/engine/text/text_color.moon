pprint = require "lib/pprint"
rgb = (r, g, b) -> {r/256, g/256, b/256, 1}
reset = rgb(236, 239, 244)
color_map = {
	"x1b[;1m": reset
	"x1b[0m": reset
	"x1b[30;1m": rgb(59, 66, 82)
	"x1b[31;1m": rgb(191, 97, 106)
	"x1b[32;1m": rgb(163, 190, 140)
	"x1b[33;1m": rgb(235, 203, 139)
	"x1b[34;1m": rgb(129, 162, 193)
	"x1b[35;1m": rgb(180, 142, 173)
	"x1b[36;1m": rgb(143, 188, 187)
	"x1b[37;1m": rgb(236, 239, 244)
}

-- "#RRGGBB" (no leading "#" here -- already stripped by the caller) -> a
-- LOVE color table. Backs Ren'Py's {color=#RRGGBB} tags (rpy_parser.py
-- translates them into the "#RRGGBB" escape form below), which use
-- arbitrary hex, not this file's original fixed 8-color ANSI palette.
hex_to_rgb = (hex) ->
	r = tonumber(hex\sub(1, 2), 16) / 255
	g = tonumber(hex\sub(3, 4), 16) / 255
	b = tonumber(hex\sub(5, 6), 16) / 255
	{r, g, b, 1}

-- Applies one matched escape code's bracket content (`key` is the full
-- "x1b[...]m" match text, matching color_map's existing key shape; `code`
-- is just what's between the brackets, e.g. "30;1", "0", "#3a7bff", "1",
-- "22", "3", "23") to the running (color, bold, italic) state -- codes 1/22
-- and 3/23 are real ANSI SGR "bold on/off" and "italic on/off", extending
-- this module's original color-only escape scheme (VNDS's own 8-color
-- convention) rather than replacing it. A color-only code preserves
-- whatever bold/italic state is already active (real ANSI semantics --
-- SGR attributes are independent); only a full reset ("0"/"") clears both,
-- same as it always cleared color.
apply_code = (key, code, color, bold, italic) ->
	if code == "0" or code == ""
		return reset, false, false
	if code\sub(1, 1) == "#" and #code == 7
		return hex_to_rgb(code\sub(2)), bold, italic
	if code == "1"
		return color, true, italic
	if code == "22"
		return color, false, italic
	if code == "3"
		return color, bold, true
	if code == "23"
		return color, bold, false
	mapped = color_map[key]
	return (mapped or color), bold, italic

-- Splits `str` into an ordered list of runs, `{color:, text:, bold:,
-- italic:}` (plus a `pause:` seconds field on a special zero-width pause
-- run, from Ren'Py's {w}/{p} tags -- rpy_parser.py encodes these as a
-- "Pn.n" escape so the typewriter reveal loop in text.moon can consume
-- them inline without any color/style side effect). Each run carries the
-- (color, bold, italic) state in effect for its own text, so `word_wrap`/
-- `draw_text` never need to re-parse escape codes themselves -- only this
-- function's recursive scan does.
colorify = (str, i=1, color=reset, bold=false, italic=false, result={}) ->
	s, e = str\find("\\*x1b%[[#%xP%.;]+m", i)
	if s == nil
		table.insert(result, {:color, text: str\sub(i, -1), :bold, :italic})
		return result
	offset = 0
	if str\sub(s, s) == "\\" --remove the backslash
		offset = 1
	key = str\sub(s + offset, e)
	code = key\match("%[(.-)m$")
	if i != s
		table.insert(result, {:color, text: str\sub(i, s - 1), :bold, :italic})
	if code\sub(1, 1) == "P"
		table.insert(result, {:color, text: "", :bold, :italic, pause: tonumber(code\sub(2))})
		return colorify(str, e + 1, color, bold, italic, result)
	new_color, new_bold, new_italic = apply_code(key, code, color, bold, italic)
	colorify(str, e + 1, new_color, new_bold, new_italic, result)
	return result

{:colorify, :hex_to_rgb}
