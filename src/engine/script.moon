require "util"
pprint = require "lib/pprint"
expr = require "expr"
local *
load = (base_dir, fs, data = file: "main.scr") ->
	s = {:base_dir, :fs, locals: {}, globals: {}}
	s = _.extend(s, read_file(s, data.file))
	_.extend(s, data)
save = (s) -> {file: s.file, locals: s.locals, globals: s.globals, n: s.n-1, callstack: s.callstack}
mem = (s, key) -> s.locals if s.locals[key] ~= nil else s.globals
mem_type = (s, type) -> s.locals if type == "setvar" else s.globals
choose = (s, val) -> s.locals["selected"] = val
-- extended: lets screen.moon (a custom-screen action, e.g. a "jump start"
-- textbutton) redirect script flow the same way a real "jump" instruction
-- would, without needing its own copy of the label-lookup logic.
jump_to_label = (s, label) -> s.n = s.labels[label] or s.n
files = nil
find_script = (s, file) ->
	if files == nil
		files = love.filesystem.getDirectoryItems("#{s.base_dir}script/")
	for script_file in *files
		if script_file\lower! == file\lower!
			return script_file
escape_pattern = (text) ->
	return text\gsub("([^%w])", "%%%1")
read_file = (s, script_file) ->
	file = find_script(s, script_file)
	data = s.fs("#{s.base_dir}script/#{file}")
	if data == nil then error("Cannot read #{script_file}! Please check the scripts folder/zip")
	ins = {}
	for line in string.gmatch(data, "[^\n]+")
		if line != '' and line\sub(1,1) != "#"
			table.insert(ins, parse(line))
	labels = {ins.label, i for i, ins in ipairs ins when ins.type == "label" }
	{:file, :ins, :labels, n: 1}
interpolate = (s, text) ->
	for var in text\gmatch("$(%S*)")
		text = text\gsub("$"..escape_pattern(var), tostring(mem(s, var)[var]))
	return text
ops =
	"==": (a,b) -> a == b
	"!=": (a,b) -> a ~= b
	">=": (a,b) -> a >= b
	"<=": (a,b) -> a <= b
	"<": (a,b) -> a < b
	">": (a,b) -> a > b
	"+": (a,b) -> add(b, a)
	"-": (a,b) -> add(b, -a)
	"=": => @
	"~": => nil
	"if": 1, "fi": -1

next_instruction = (s) ->
	ins = s.ins[s.n]
	return s, ins if ins == nil --means novel is finished
	s.n += 1
	if ins.path then ins.path = s.base_dir..ins.path
	if ins.paths then ins.paths = [s.base_dir..p for p in *ins.paths] -- portrait_anim's 3 frame paths (plural, not a single .path)
	MEM = mem(s, ins.var) if ins.var
	switch ins.type
		when "bgload", "setimg", "sound", "music", "ambiance", "music2", "setvolume", "delay", "cleartext", "text", "choice", "nameplate", "clearimg", "clearslot", "window", "voiceover", "stopmusic", "stopsound", "stopvoice", "stopambiance", "stopmusic2", "play", "stop", "portrait", "portrait_anim", "speaking", "overlay_text", "overlay_clear", "anim", "anim_begin", "keyframe", "anim_end", "anim_wait", "screen_begin", "screen_end", "vbox_begin", "vbox_end", "hbox_begin", "hbox_end", "screen_text", "screen_button", "screen_if", "screen_elif", "screen_else", "screen_endif", "show_screen", "hide_screen", "imagemap_begin", "hotspot", "imagemap_end"
			if ins.type == "text" then ins.text = interpolate(s, ins.text)
			if ins.type == "bgload" then ins.path = interpolate(s, ins.path)
			if ins.type == "setimg" then ins.path = interpolate(s, ins.path)
			if ins.type == "voiceover" then ins.path = interpolate(s, ins.path)
			if ins.type == "play" then ins.path = interpolate(s, ins.path)
			if ins.type == "imagemap_begin" then ins.path = interpolate(s, ins.path)
			ins.choices = _.map(ins.choices,=> interpolate(s,@)) if ins.type == "choice"
			return s, ins
		when "setvar", "gsetvar"
			MEM = mem_type(s, ins.type)
			if ins.modifier == "="
				-- extended: full expression evaluator (VN3DS-spec.md §6.1) --
				-- int/bool/string, +-*/, ==!=<<=>>=, and/or/not, and
				-- cross-variable references, not just the original
				-- self-referential literal-or-bare-var assignment. Falls
				-- back to the original narrow parse if the evaluator can't
				-- handle the expression (e.g. legacy content), so existing
				-- scripts keep working unchanged.
				scope = _.extend({}, s.globals, s.locals)
				evaluated = expr.evaluate(ins.expr, scope)
				ins.value.literal = ins.value.literal or MEM[ins.value.var] or 0
				MEM[ins.var] = if evaluated != nil then evaluated else ins.value.literal
			else
				ins.value.literal = ins.value.literal or MEM[ins.value.var] or 0
				MEM[ins.var] = ops[ins.modifier](ins.value.literal, MEM[ins.var])
			if ins.modifer ==  "~" then MEM = {}
		when "random" then MEM[ins.var] = math.random(ins.low, ins.high)
		when "if"
			lhs = MEM[ins.var] or 0 --default to 0
			rhs = ins.value.literal or MEM[ins.value.var] or 0
			if not ops[ins.modifier](lhs, rhs)
				count = 1
				while count > 0
					s.n += 1
					count += ops[s.ins[s.n].type] or 0
		when "ifvar"
			-- extended: single-line conditional jump (VN3DS-spec.md §5.1),
			-- backed by the Phase 2.4 expression evaluator -- unlike the
			-- original if/fi block (one var-op-value test), this can
			-- evaluate a full compound expression (and/or/not, arithmetic,
			-- cross-variable comparisons) in one line.
			scope = _.extend({}, s.globals, s.locals)
			if expr.evaluate(ins.expr, scope)
				ins.label = interpolate(s, ins.label)
				s.n = s.labels[ins.label] or s.n
		when "goto"
			ins.label = interpolate(s, ins.label)
			s.n = s.labels[ins.label]
		when "call"
			ins.label = interpolate(s, ins.label)
			s.callstack = s.callstack or {}
			table.insert(s.callstack, s.n)
			s.n = s.labels[ins.label] or s.n
		when "return"
			if s.callstack and #s.callstack > 0
				s.n = table.remove(s.callstack)
			else
				-- extended: a "return" with no caller ends the reachable flow
				-- (matches Ren'Py's "return" ending the game/session), rather
				-- than silently falling through into whatever label happens
				-- to follow positionally in the file.
				s.n = #s.ins + 1
		when "jump" --see if I can reuse load here
			ins.filename = interpolate(s, ins.filename)\gsub('{', '')\gsub('}', '')
			if ins.filename\find("|")
				-- extended: choice-driven branch. filename is a pipe-delimited
				-- list of same-file labels, one per choice option; pick the
				-- one matching whichever choice was selected.
				targets = split(ins.filename, "|")
				target = targets[s.locals["selected"] or 1]
				s.n = s.labels[target] or s.n
			elseif s.labels[ins.filename]
				-- extended: plain same-file label jump (Ren'Py `jump <label>`)
				s.n = s.labels[ins.filename]
			else
				-- original VNDS: cross-file jump, optionally to a label
				if ins.label != nil then ins.label = interpolate(s, ins.label)
				s = _.extend(s, read_file(s, ins.filename))
				s.n = s.labels[ins.label] or s.n
	return next_instruction(s)
rest = (chunks, i) -> _.join(_.rest(chunks, i), " ")
getvalue = (chunks, index) ->
	r = rest(chunks, index)
	if r\sub(1,1) == '"'
		return literal: r\sub(2, -2)
	else if num(r) != nil
		return literal: num(r)
	else return var: r
	-- return literal: if r\sub(1,1) == '"' then r\sub(2, -2) else num(r), var: r
add = (a, b) -> --adds two strings, two ints, or an int and a string
	if a == nil then b
	else if _.any({a,b}, => type(@) == "string") then a..b
	else a + b
-- extended: parses "key=value" tokens from a keyframe line (VN3DS-spec.md
-- §9.1's `keyframe <t> x=80 alpha=0 sx=0.8 sy=0.8` form) into a plain table.
-- Used below by parse()'s "anim"/"anim_begin"/"keyframe"/"anim_end"/
-- "anim_wait" cases (spec §9.1): "anim" fires a named preset; "anim_begin"/
-- "keyframe"/"anim_end" build a custom keyframe animation (keyframes are
-- collected by images.moon as they're dispatched, not grouped here -- this
-- format has no concept of nested blocks, matching how "if"/"fi" already
-- work via forward-scanning rather than real nesting); "anim_wait" blocks
-- script execution until the named target's animation completes. (NOTE:
-- comments placed *between* `when` clauses inside a `switch` fail to parse
-- with this toolchain's MoonScript version -- keep block comments like
-- this one outside the switch entirely.)
--
-- Also below: "setimg"'s trailing key=value tokens (yalign/yanchor/sx/sy/r/
-- alpha -- vnds_writer.py's _static_prop_tokens) carry a static ATL block/
-- named transform's real fractions/scale/rotation/alpha, resolved against
-- the sprite's *actual* loaded height at setimg time (images.moon's "on
-- setimg") rather than the flat, sprite-height-unaware x/y pixel fallback
-- also present on every setimg line. Reuses the same parse_props helper.
--
-- Also below: custom-screen commands (a pulled-forward Phase 5.1 slice).
-- "screen_begin <name>"/"screen_end" bracket a screen *definition*
-- (registered once by screen.moon, typically from the always-executed
-- top-level preamble -- see vnds_writer.py -- not shown until
-- "show_screen <name>" is later reached); "vbox_begin"/"vbox_end"/
-- "hbox_begin"/"hbox_end" are layout containers; "screen_text"/
-- "screen_button" are leaf elements; "screen_if"/"screen_elif"/
-- "screen_else"/"screen_endif" are conditional branches (screen.moon
-- evaluates the condition via the same expr.moon evaluator "ifvar"
-- uses). "screen_button"'s line format is `screen_button <label> |
-- <action>` (a literal pipe separates the two, since both can contain
-- spaces): e.g. `screen_button Start Game | jump start`.
--
-- "imagemap_begin <ground_path>"/"imagemap_end" bracket an imagemap
-- (a background image + touch-region hotspots -- Ren'Py's `imagemap:`
-- widget, most commonly a game's customized main menu); each
-- "hotspot <x> <y> <w> <h> | <action>" is one pixel-rectangle touch
-- region, in the ground image's own native pixel space, same pipe-
-- separated convention as "screen_button" (an empty action after the
-- pipe is a `NullAction()` -- a real, intentional no-op hotspot).
-- screen.moon renders this very differently from a vbox/button list
-- (see its own show_imagemap) but reuses the exact same action
-- vocabulary (run_action) once a hotspot is actually tapped.
parse_props = (tokens) ->
	props = {}
	for tok in *tokens
		k, v = tok\match("^(%a+)=(.+)$")
		if k then props[k] = num(v) or v
	props
parse = (line) ->
	c = {}
	for word in line\gmatch("%S+") do table.insert(c, word)
	-- c = split(line, " ") --each word is an element of c
	c[1] = ascii(c[1] or '') --strip non-ascii values from the instruction, since it is english
	if c[1]\sub(1, 1) == "@"
		-- extended: "@name" label declaration (VN3DS-spec.md worked example),
		-- an alias for the original "label name" two-token form.
		return type: "label", label: c[1]\sub(2)
	_.extend type: c[1], switch c[1]
		when "bgload" then path: "background/"..c[2], frames: num(c[3])
			when "setimg" then path: "foreground/"..c[2], x: num(c[3] or 0), y: num(c[4] or 0), slot: c[5], props: parse_props([c[i] for i=6, #c])
		when "sound","music","ambiance","music2" then path: "sound/"..c[2], n: num(c[3]) --if n doesn't exist, nil
		when "setvolume" then channel: c[2], level: num(c[3]), delay: num(c[4]) or 0
		when "play" then channel: c[2], path: "sound/"..c[3], loop: (c[4] == "1"), mixer: c[5] --generic form for a custom channel outside the 5 curated ones above
		when "stop" then channel: c[2] --generic form's counterpart
		when "portrait" then name: c[2], slot: c[3], path: "foreground/"..c[4], category: c[5], dissolve: (c[6] == "1"), order_index: num(c[7]), tint_r: num(c[8]), tint_g: num(c[9]), tint_b: num(c[10]) --Our Life's ChangePortrait system (converter.parser.character_sprite): a static single-image layer
		when "portrait_anim" then name: c[2], slot: c[3], paths: ["foreground/"..c[i] for i=4,6], category: c[7], blink: (c[8] == "1"), dissolve: (c[9] == "1"), order_index: num(c[10]), tint_r: num(c[11]), tint_g: num(c[12]), tint_b: num(c[13]), speaker: (c[14] == "~" and nil or c[14])
		when "speaking" then name: (c[2] == "~" and nil or c[2])
		when "text" then text: rest(c, 2)
		when "choice" then choices: split(rest(c, 2), "|")
		when "gsetvar", "setvar" then var: c[2], modifier: c[3], value: getvalue(c, 4), expr: rest(c, 4)
		when "if" then var: c[2], modifier: c[3], value: getvalue(c, 4)
		when "ifvar"
			expr_text, label_text = line\match("^%s*ifvar%s+(.-)%s+jump%s+(%S+)%s*$")
			expr: expr_text, label: label_text
		when "jump" then filename: c[2], label: c[3]
		when "delay" then frames: num(c[2])
		when "random" then var: c[2], low: num(c[3]), high: num(c[4])
		when "label", "goto", "call" then label: c[2]
		when "cleartext" then modifier: c[2]
		when "nameplate"
			-- extended: Character(color=...)'s per-character nameplate
			-- tint (VN3DS-spec.md §6) rides as an optional "#hexcolor"
			-- token right after "nameplate", before the (arbitrary-length,
			-- possibly-spaced) name -- distinguishable from an ordinary
			-- name because no real display name starts with a literal "#".
			if c[2] and c[2]\sub(1, 1) == "#"
				{color: c[2]\sub(2), name: rest(c, 3)}
			else
				{name: rest(c, 2)}
		when "clearimg" then path: "foreground/"..c[2]
		when "clearslot" then slot: c[2]
		when "overlay_text" then id: c[2], x: num(c[3]), y: num(c[4]), size: num(c[5]), color: c[6], text: rest(c, 7)
		when "overlay_clear" then {}
		when "window" then state: c[2]
		when "voiceover" then path: "sound/"..c[2]
		when "anim" then target: c[2], preset: c[3], duration: num(c[4])
		when "anim_begin" then target: c[2], duration: num(c[3]), ease: c[4]
		when "keyframe" then t: num(c[2]), props: parse_props([c[i] for i=3, #c])
		when "anim_end" then {}
		when "anim_wait" then target: c[2]
		when "screen_begin" then name: c[2]
		when "screen_end" then {}
		when "vbox_begin", "vbox_end", "hbox_begin", "hbox_end" then {}
		when "screen_text" then text: rest(c, 2)
		when "screen_button"
			label_text, action_text = line\match("^%s*screen_button%s+(.-)%s*|%s*(.-)%s*$")
			label: label_text, action: action_text
		when "screen_if", "screen_elif" then expr: rest(c, 2)
		when "screen_else", "screen_endif" then {}
		when "imagemap_begin" then path: "background/"..c[2]
		when "hotspot"
			x_text, y_text, w_text, h_text, action_text = line\match("^%s*hotspot%s+(%-?[%d.]+)%s+(%-?[%d.]+)%s+(%-?[%d.]+)%s+(%-?[%d.]+)%s*|%s*(.-)%s*$")
			x: num(x_text), y: num(y_text), w: num(w_text), h: num(h_text), action: (action_text != "" and action_text or nil)
		when "imagemap_end" then {}
		when "show_screen" then name: c[2]
		when "hide_screen" then {}
		else {}
-- extended: a fresh game's `dispatch "show_screen", {name: "main_menu"}`
-- (save.moon's new-game path) fires immediately after `load` -- before
-- the interpreter has ever advanced a single instruction. Screen
-- *definitions* (screen_begin/vbox_begin/imagemap_begin/hotspot/.../
-- screen_end) are ordinary instructions in the script's own top-level
-- preamble (vnds_writer.py emits them before the first @label,
-- relying on normal top-to-bottom execution to register them before
-- any show_screen can reference one) -- so without first walking
-- through that preamble, a real converted main_menu was never actually
-- registered yet, and screen.moon's hardcoded placeholder (registered
-- once at require-time) was all that ever existed to show. This walks
-- s forward from wherever it currently sits, dispatching every
-- instruction that reaches this function's own generic fallthrough
-- (mirroring main.moon's next_msg, but stopping dead at the first
-- @label marker instead of recursing into it) -- safe because the
-- preamble only ever contains screen-definition instructions and
-- top-level gsetvars (already fully consumed internally by
-- next_instruction itself, never reaching this loop at all), never
-- anything that blocks (text/choice/anim_wait/show_screen).
run_preamble = (s) ->
	-- "label" instructions are never actually handed back to the
	-- caller at all -- next_instruction has no switch case for them,
	-- so they fall through to its own tail-recursive next_instruction(s)
	-- call and get transparently skipped, internally, as an
	-- implementation detail. That means checking ins.type == "label"
	-- here would never trigger -- the only reliable stopping point is
	-- s.n itself, checked *before* each call: s.labels["start"] is the
	-- exact index of "@start" (always the first label, textually --
	-- vnds_writer.py moves it to the front), so stopping the instant
	-- s.n reaches it leaves that label instruction completely
	-- unconsumed, ready for normal execution once the menu is
	-- dismissed, exactly as if this function had never run at all.
	target = s.labels["start"] or (#s.ins + 1)
	while s.n < target
		s, ins = next_instruction(s)
		break if ins == nil
		dispatch ins.type, ins
	s
return {:load, :save, :next_instruction, :choose, :jump_to_label, :run_preamble}
