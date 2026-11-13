-- Pulled-forward Phase 5.1 slice: a minimal custom-screen runtime for the
-- most common Ren'Py `screen:` patterns -- vbox/hbox layout containers,
-- static text, textbutton + a handful of actions, and if/elif/else
-- conditionals. Not a general screen-language interpreter: no `for`
-- loops (no list-typed VNDS variables to iterate), no composite
-- `[Action, Action]` lists, no arbitrary Python. Reuses listbox.moon's
-- existing navigable-list widget for rendering/input rather than
-- building a second one from scratch.
expr = require 'expr'
script = require 'script'
import create_listbox from require 'listbox'
local *

-- Screen *definitions* (the parsed vbox/text/button/if tree, one per
-- "screen_begin ... screen_end" block) vs. `screen_stack` (the runtime
-- stack of currently-shown screen names) are deliberately separate:
-- definitions are registered once (typically from the script's
-- always-executed top-level preamble) and can be shown many times.
definitions = {}
building = nil          -- {name, container_stack: [current nesting of children-lists]}
if_stack = nil          -- parallel stack of open "if" nodes, for screen_elif/screen_else
building_imagemap = nil -- the single in-progress imagemap (ground + hotspots so far), if any
screen_stack = {}

-- extended: screen *definitions* persist across a save/load (they're
-- registered once from the script's top-level preamble, re-run on every
-- load same as `default`/`define`), but any screen that happened to be
-- showing at the time -- and the runtime show/hide stack tracking it --
-- must not survive a restore, same as images.moon's sprite list.
on "restore", => screen_stack = {}

current_container = -> building.container_stack[#building.container_stack]

on "screen_begin", =>
	root = {children: {}}
	building = {name: @name, container_stack: {root}}
	if_stack = {}

on "screen_end", =>
	if building
		definitions[building.name] = building.container_stack[1]
		building = nil
		if_stack = nil

on "vbox_begin", =>
	if building
		node = {children: {}}
		table.insert(current_container!.children, {type: "box", node: node})
		table.insert(building.container_stack, node)
on "vbox_end", => if building then table.remove(building.container_stack)
on "hbox_begin", =>
	if building
		node = {children: {}}
		table.insert(current_container!.children, {type: "box", node: node})
		table.insert(building.container_stack, node)
on "hbox_end", => if building then table.remove(building.container_stack)

on "screen_text", =>
	if building then table.insert(current_container!.children, {type: "text", text: @text})

on "screen_button", =>
	if building then table.insert(current_container!.children, {type: "button", label: @label, action: @action})

on "screen_if", =>
	if building
		branch = {children: {}}
		node = {branches: {{cond: @expr, node: branch}}}
		table.insert(current_container!.children, {type: "if", node: node})
		table.insert(if_stack, node)
		table.insert(building.container_stack, branch)
on "screen_elif", =>
	if building and #if_stack > 0
		table.remove(building.container_stack)
		node = if_stack[#if_stack]
		branch = {children: {}}
		table.insert(node.branches, {cond: @expr, node: branch})
		table.insert(building.container_stack, branch)
on "screen_else", =>
	if building and #if_stack > 0
		table.remove(building.container_stack)
		node = if_stack[#if_stack]
		branch = {children: {}}
		table.insert(node.branches, {cond: nil, node: branch}) -- nil cond = always taken (else)
		table.insert(building.container_stack, branch)
on "screen_endif", =>
	if building
		table.remove(building.container_stack)
		table.remove(if_stack)

-- extended: imagemap/hotspot (a background image + touch-region
-- hotspots -- Ren'Py's `imagemap:` widget, most commonly a game's
-- customized main menu). Unlike vbox/hbox/if, a hotspot isn't a
-- recursively-nested child -- it's metadata belonging to the one
-- enclosing imagemap -- so this tracks a single in-progress imagemap
-- directly rather than pushing onto container_stack, and only
-- appends the finished node (as a flat leaf, same as "text"/"button")
-- to the current container once fully built.
on "imagemap_begin", =>
	if building
		building_imagemap = {ground: @path, hotspots: {}}
on "hotspot", =>
	if building_imagemap
		table.insert(building_imagemap.hotspots, {x: @x, y: @y, w: @w, h: @h, action: @action})
on "imagemap_end", =>
	if building and building_imagemap
		table.insert(current_container!.children, {type: "imagemap", ground: building_imagemap.ground, hotspots: building_imagemap.hotspots})
		building_imagemap = nil

-- Walks a definition tree, evaluating "if" branches against the current
-- variable scope (so a screen's visible content reflects live game state
-- each time it's shown), producing a flat list of {type: "text"/"button", ...}
-- -- listbox.moon has no concept of nested boxes, so vbox/hbox both
-- collapse to "items in order" for rendering (a real box-layout algorithm,
-- e.g. side-by-side hboxes, is future work; most real menus are single
-- vertical stacks anyway).
flatten = (node, scope, out) ->
	for child in *node.children
		switch child.type
			when "box" then flatten(child.node, scope, out)
			when "text" then table.insert(out, {type: "text", text: child.text})
			when "button" then table.insert(out, {type: "button", label: child.label, action: child.action})
			when "imagemap" then table.insert(out, {type: "imagemap", ground: child.ground, hotspots: child.hotspots})
			when "if"
				for branch in *child.node.branches
					if branch.cond == nil or expr.evaluate(branch.cond, scope)
						flatten(branch.node, scope, out)
						break
	out

run_action = (action_text) ->
	table.remove(screen_stack)
	tokens = {}
	for word in action_text\gmatch("%S+") do table.insert(tokens, word)
	switch tokens[1]
		when "jump"
			script.jump_to_label(interpreter, tokens[2])
			dispatch "next_ins"
		when "call"
			interpreter.callstack = interpreter.callstack or {}
			table.insert(interpreter.callstack, interpreter.n)
			script.jump_to_label(interpreter, tokens[2])
			dispatch "next_ins"
		when "quit" then love.event.quit!
		when "show_screen" then show_screen(tokens[2])
		when "hide_screen"
			if #screen_stack == 0 then dispatch "next_ins"
		when "setvar"
			var, op, value_expr = action_text\match("^setvar%s+(%S+)%s+(%S+)%s+(.+)$")
			if var and op == "="
				scope = _.extend({}, interpreter.globals, interpreter.locals)
				value = expr.evaluate(value_expr, scope)
				if value != nil then interpreter.globals[var] = value
			if #screen_stack == 0 then dispatch "next_ins"
		else
			if #screen_stack == 0 then dispatch "next_ins"

show_screen = (name) ->
	def = definitions[name]
	unless def
		dispatch "next_ins" if #screen_stack == 0
		return
	table.insert(screen_stack, name)
	scope = _.extend({}, interpreter.globals, interpreter.locals)
	flat = flatten(def, scope, {})
	if #flat == 1 and flat[1].type == "imagemap"
		show_imagemap(flat[1])
		return
	choices = {}
	for item in *flat
		if item.type == "button"
			button_action = (chosen, close) ->
				run_action(item.action)
				true
			table.insert(choices, {text: item.label, action: button_action})
		else
			table.insert(choices, {text: item.text, action: (chosen, close) -> false})
	create_listbox {
		:choices
		closable: true
		onclose: ->
			table.remove(screen_stack)
			dispatch "next_ins" if #screen_stack == 0
	}

-- extended: renders an imagemap-shaped screen (see flatten's "imagemap"
-- case) -- a background image plus pixel-rectangle touch hotspots,
-- fundamentally different from listbox.moon's auto-stacked-rows
-- layout, so this bypasses create_listbox entirely. The ground image
-- is drawn exactly like images.moon's "draw_background" (same
-- `scale = math.min(sx, sy)` centered-on-screen math -- sx/sy are a
-- sound, stable, once-at-boot device-reference scale, safe to reuse
-- here); each hotspot's rect (authored in the ground image's own
-- native pixel space, Ren'Py's convention) is scaled by that same
-- factor + centering offset into real screen/touch pixels. Touch-only
-- (no keyboard/gamepad focus model -- real Ren'Py imagemaps have none
-- either). A NullAction hotspot (action == nil) intentionally does
-- nothing and leaves the imagemap open; any other hotspot reuses the
-- exact same `run_action` real screen buttons already dispatch
-- through, then tears down its own listeners exactly like listbox's
-- own `close()` (no `onclose`/back-button handling -- real Ren'Py
-- imagemaps have no such affordance either).
show_imagemap = (node) ->
	local *
	dispatch "pause"
	image = lg.newImage(node.ground)
	img_w, img_h = image\getDimensions!
	bounds = {}
	close = ->
		input_event\remove!
		draw_event\remove!
		touch_event\remove!
		dispatch "play"
	-- real-hardware regression: every other screen (listbox.moon's
	-- own input_event) always intercepts/consumes input while shown,
	-- which is what protects global input handlers elsewhere (e.g.
	-- text.moon's dialogue-backlog scrollback, bound to plain "up")
	-- from ever firing during a menu. An imagemap has no keyboard/
	-- gamepad navigation model of its own (matching real Ren'Py), but
	-- it still has to swallow "input" the same way, or those global
	-- handlers fire unprotected -- confirmed real crash: pressing "up"
	-- on the very first, pre-any-dialogue main menu hit text.moon's
	-- backlog handler with an empty backlog, crashing in listbox.moon's
	-- create_listbox on an empty choices list.
	input_event = on "input", (input) -> false
	touch_event = on "touch", (t) ->
		for b in *bounds
			if t.x >= b.x and t.x <= b.x + b.w and t.y >= b.y and t.y <= b.y + b.h
				if b.action != nil
					run_action(b.action)
					close!
				break
		return false
	draw_event = on "draw_choice", ->
		scale = math.min(sx, sy)
		ox, oy = lg.getWidth!/2 - (img_w/2)*scale, lg.getHeight!/2 - (img_h/2)*scale
		lg.setColor(1, 1, 1)
		lg.draw(image, lg.getWidth!/2, lg.getHeight!/2, 0, scale, scale, img_w/2, img_h/2)
		-- h.x/h.y/h.w/h.h are fractions (0.0-1.0) of the game's own
		-- declared resolution, not pixels in the *actually loaded* ground
		-- image (which the asset pipeline may have resized) -- multiply
		-- by the real loaded image's own dimensions first (see
		-- ScreenHotspot's own docstring for the real-hardware regression
		-- this fixes: every hotspot landed far outside the visible image
		-- once the asset pipeline started resizing oversized backgrounds).
		bounds = [{x: ox + h.x*img_w*scale, y: oy + h.y*img_h*scale, w: h.w*img_w*scale, h: h.h*img_h*scale, action: h.action} for h in *node.hotspots]
		return false

on "show_screen", => show_screen(@name)
on "hide_screen", => run_action("hide_screen")

-- extended: a native main menu (Start Game / Quit), shown once per fresh
-- playthrough (save.moon's "new_slot" handler, right before it would
-- otherwise jump straight into the story). Games almost always customize
-- their real screen main_menu() (rpy_parser.py's _DEFAULT_SCREEN_NAMES no
-- longer skips it -- real-hardware finding), so a real script_begin
-- "main_menu" ... screen_end sequence overwrites this same
-- definitions["main_menu"] key at load time (see "screen_end" above) --
-- this hardcoded fallback is only ever actually shown for a game whose
-- main_menu didn't convert (parsing failed, or the source has none at
-- all), same as any other unconverted screen. Built directly rather
-- than via the screen_begin/vbox_begin/... event sequence real content
-- uses, since there's no script line driving it.
definitions["main_menu"] =
	children: {
		{
			type: "box"
			node: {
				children: {
					{type: "button", label: "Start Game", action: "hide_screen"}
					{type: "button", label: "Quit", action: "quit"}
				}
			}
		}
	}

return {:show_screen, :definitions}
