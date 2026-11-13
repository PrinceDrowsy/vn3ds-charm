import draw_frame from require "ui_frame"
import ui from require "ui_assets"
local *
pad = 10
-- can also provide "data" as a part of choices
remove_color = =>
	w = ""
	if type(@) == "string" then return @
	else
		for i = 2, #@, 2
			w ..= @[i]
	return w
create_listbox = =>
	@selected = @selected or 1
	if @choices[@selected].onchange
		@choices[@selected].onchange(@choices[@selected])
	@closable = @closable or false
	@allow_menu = @allow_menu or false
	@onclose = @onclose or ->
	@media = @media or -pad
	local *
	dispatch "pause"
	bounds = {}
	font_height = (text) ->
		_, count = string.gsub(remove_color(text), "\n", "\n")
		return math.max(text_font\getHeight! * (1 + count), @media)
	close = ->
		input_event\remove!
		draw_event\remove!
		touch_event\remove!
		dispatch "play"
	input_event = on "input", (input) ->
		@selected = switch input
			when "up" then (@selected-2) % #@choices + 1
			when "down" then @selected % #@choices + 1
		chosen = @choices[@selected]
		if input == "up" or input == "down"
			if chosen.onchange then chosen.onchange(chosen)
		if input == "a"
			outcome = chosen.action(chosen, close)
			if @closable and outcome then close!
			if not @closable then close!
		else if input == "start" and @allow_menu
			return true --passes it to the below layer
		else if input == "b" and @closable
			close!
			@onclose!
		else if input == "right"
			if chosen.right then chosen.right(chosen)
		else if input == "left"
			if chosen.left then chosen.left(chosen)
		return false
	touch_event = on "touch", (t) ->
		for i, b in ipairs bounds
			if t.x >= b.x and t.x <= b.x + b.w and t.y >= b.y and t.y <= b.y + b.h
				@selected = i
				chosen = @choices[@selected]
				outcome = chosen.action(chosen, close)
				if @closable and outcome then close!
				if not @closable then close!
				break
		return false
	draw_event = on "draw_choice", ->
		lg.setFont(text_font)
		w = 3 * pad + _.max([text_font\getWidth(remove_color(c.text)) for c in *@choices]) + @media
		h, y_selected = pad, 0
		for i, c in ipairs @choices
			h += font_height(c.text) + pad
			if i == @selected then y_selected += h
		x, y = center(w, lg.getWidth!), center(h, lg.getHeight!)
		y = lg.getHeight!/2 - y_selected
		-- extended: the custom UI-asset-import system (VN3DS-spec.md §6)
		-- -- when the game's own real choice-button images converted
		-- (this widget backs in-story choices, custom screens, save/load
		-- slots, and the main menu, so all of them benefit at once), each
		-- row draws its own idle/hover background instead of one shared
		-- panel rectangle behind every row (matching Ren'Py's own
		-- per-button chrome, not an enclosing menu frame). Falls back to
		-- exactly today's single flat-color panel + text-color-only
		-- selection when no button chrome was declared/resolved.
		has_button_chrome = ui.choice_idle or ui.choice_hover
		unless has_button_chrome
			lg.setColor(.18,.204,.251, .8)
			lg.rectangle("fill", x, y, w, h)
		text_y = y + pad
		bounds = {}
		for i, c in ipairs @choices
			row_h = font_height(c.text) + pad
			table.insert(bounds, {x: x, y: text_y - pad/2, w: w, h: row_h})
			if has_button_chrome
				entry = if i == @selected
					ui.choice_hover or ui.choice_idle
				else
					ui.choice_idle or ui.choice_hover
				lg.setColor(1, 1, 1)
				draw_frame(entry.image, entry.borders, entry.tile, x, text_y - pad/2, w, row_h)
			lg.setColor(1, 1, 1)
			if c.media then c.media(x+pad, text_y)
			if i == @selected then lg.setColor(.506, .631, .757)
			lg.print(c.text, x + 2*pad + @media, text_y)
			text_y += pad + font_height(c.text)
		lg.setFont(font)
		return false
return {:create_listbox}
