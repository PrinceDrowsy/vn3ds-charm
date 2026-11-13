import colorify, hex_to_rgb from require "text/text_color"
import draw_frame from require "ui_frame"
import ui from require "ui_assets"
local *
buffer = {}
backlog = {}
lines = 3
if love._console_name == "3DS" then lines = 7
pad = 10
-- extended: the text box always renders on the bottom screen (main.moon's
-- love.draw only dispatches "draw_text"/"draw_choice" when @screen ==
-- "bottom"), but `lg.getWidth!` with no argument returns whichever screen
-- LÖVE Potion's boot.lua last called love.graphics.setActiveScreen for --
-- which, per its own per-frame draw loop (left/right/bottom/top, in that
-- order), is "top" (400px) once the frame's draw calls finish, not
-- "bottom" (320px). Any width lookup made outside an actual draw call
-- (e.g. this module's "text" event, fired from game-logic dispatch, not
-- from love.draw) therefore silently measured against the wrong, wider
-- screen -- real hardware symptom: dialogue text word-wrapped assuming a
-- 400px-wide box, then rendered into an actual 320px-wide box, running
-- off the right edge. love.graphics.getWidth(screen) takes an explicit
-- screen name to sidestep the ambient active-screen state entirely; only
-- 3DS has more than one screen; getHeight() has no such parameter at all
-- (both screens are the same height), so it needs no equivalent fix.
text_box_width = -> if love._console_name == "3DS" then lg.getWidth("bottom") else lg.getWidth!
override_font = nil
speed_override = nil
update_font = ->
	-- extended, two compounding bugs fixed here:
	-- (1) previously `if interpreter and not override_font ... else
	-- text_font = font` -- the `else` bound to the *inner* single-line
	-- `if lfs.getInfo(...) then ...`, not the outer condition, so the
	-- fallback assignment only ran when `interpreter` was truthy (and
	-- was skipped entirely -- not even reset to the default `font` --
	-- if the custom font file didn't exist). Restructured with an
	-- explicit early return so the fallback always runs whenever the
	-- custom-font path doesn't apply.
	-- (2) `text_font = ...` (a bare assignment) never actually updated
	-- the `text_font` that `draw_text`/`word_wrap` read: this file's
	-- `local *` only hoists a name to a shared file-level local when
	-- compiling from a scope where it's already known -- since this was
	-- the assignment's *first* appearance in the file, MoonScript scoped
	-- it as a throwaway local to update_font's own function body only
	-- (confirmed by inspecting the compiled Lua: `local text_font = ...`
	-- appeared *inside* update_font, while every other reference in this
	-- file compiled as a bare global read). `draw_text`/`word_wrap`
	-- therefore always read `main.moon`'s own separate `text_font`
	-- global (set once, in `love.resize`) instead -- meaning a
	-- per-novel custom "default.ttf" override has never actually taken
	-- effect, silently, since this function was written. Assigning to
	-- `_G.text_font` explicitly makes the intent (a real shared global,
	-- matching main.moon's own declaration) unambiguous.
	-- (3) `lfs.getInfo(font_path)` is the same LÖVE Potion 2.0.0
	-- 3DS-filesystem-backend quirk `main.moon`'s `path_exists` was
	-- already written to work around elsewhere (it can report false for
	-- a file `getDirectoryItems` clearly lists) -- reusing that function
	-- (exported globally by `main.moon`'s `export *`) instead of a fresh
	-- `lfs.getInfo` call keeps this check reliable on real hardware too.
	-- Found while wiring a real game font (Jisei's own "gui/HanSrf.ttf")
	-- through for the first time -- this whole path was previously dead
	-- code, since no converter run had ever produced a "default.ttf".
	-- (4) the custom font always loaded at a hardcoded size 32, ignoring
	-- the same screen-width-based sizing `main.moon`'s own `love.resize`
	-- already uses for the *default* font (32 normally, 20 on a narrow/
	-- 3DS-bottom-screen-width display) -- on the O3DS's physical bottom
	-- screen this would have rendered the custom font larger than
	-- intended, worsening rather than fixing overflow.
	if interpreter and not override_font
		font_path = interpreter.base_dir.."default.ttf"
		if path_exists(font_path)
			font_size = if text_box_width! < 600 then 20 else 32
			_G.text_font = lg.newFont(font_path, font_size)
			return
	_G.text_font = font
on "config", =>
	override_font = @font.override_font
	speed_override = @text and @text.speed_cps
	update_font!
	update_typewriter_speed!
nameplate_text = nil
window_visible = true
on "restore", ->
	update_font!
	update_typewriter_speed!
	buffer = {} --clear text state when restoring
	backlog = {}
	nameplate_text = nil
	nameplate_color = nil
	window_visible = true
	if fast_forward
		fast_forward\remove!
		fast_forward = nil
nameplate_color = nil
on "nameplate", =>
	nameplate_text = if @name == "~" then nil else @name
	-- extended: Character(color=...)'s per-character nameplate tint
	-- (VN3DS-spec.md §6) -- previously parsed by the converter and then
	-- discarded, so every character's name rendered in the same hardcoded
	-- white regardless. `@color` is an optional trailing hex token (e.g.
	-- "c2989c"); falls back to nil (colorify's own default run color)
	-- when a character has no explicit color=.
	nameplate_color = if @color then hex_to_rgb(@color) else nil
on "window", =>
	window_visible = @state != "hide"

-- typewriter reveal: `revealed` counts characters against the currently
-- visible window (_.first(buffer, lines)), not the whole backlog, so
-- scrolling to a new page always restarts the reveal for that page.
revealed = 0
typewriter_speed = 40 -- characters per second
-- extended: the game's own typewriter speed (`config.default_text_cps`/
-- `config.text_cps`, VN3DS-spec.md §6), if the converter found one --
-- rpy_parser.py's `_scan_default_text_cps` writes it to a plain
-- "text_cps.txt" at the bundle root (same lightweight, manifest.json-free
-- convention `update_font`'s "default.ttf" check already uses, since the
-- engine doesn't read manifest.json at all). Falls back to the hardcoded
-- default above when the source game never set one. A player-set
-- preference (config.moon's settings screen, persisted to config.ini)
-- takes precedence over both -- `speed_override` mirrors `override_font`'s
-- own persistent-local pattern above, since this function (unlike
-- `on "config"`) is also called from `on "restore"`, which carries no
-- config payload to read from directly.
update_typewriter_speed = ->
	typewriter_speed = 40 -- reset first so this stays idempotent across restores/reloads
	if interpreter
		cps_path = interpreter.base_dir.."text_cps.txt"
		if path_exists(cps_path)
			parsed = tonumber(lfs.read(cps_path))
			if parsed then typewriter_speed = parsed
	if speed_override then typewriter_speed = speed_override
-- Ren'Py's {w}/{p} tags (VN3DS-spec.md §6) become a zero-width "pause" run
-- (rpy_parser.py encodes them as a "Pn.n" escape -- see text_color.moon's
-- colorify) -- modeled as `pause * typewriter_speed` phantom characters of
-- reveal budget rather than as a real wall-clock stall in `on "update"`
-- below: revealing that many *extra* characters takes exactly `pause`
-- seconds at the current typewriter speed, with no separate pause-state
-- machinery needed anywhere else (total_chars/truncate_colored_lines
-- already just consume budget, whether from real text or a pause run).
pause_chars = (run) -> if run.pause then math.ceil(run.pause * typewriter_speed) else 0
total_chars = (lines_) ->
	count = 0
	for line in *lines_
		for run in *line
			count += #run.text + pause_chars(run)
	return count
truncate_colored_lines = (lines_, budget) ->
	result, remaining = {}, budget
	for line in *lines_
		break if remaining <= 0
		new_line = {}
		for run in *line
			break if remaining <= 0
			cost = pause_chars(run)
			if cost > 0
				if cost <= remaining
					table.insert(new_line, run)
					remaining -= cost
				else
					remaining = 0
			else
				text = run.text
				if #text <= remaining
					table.insert(new_line, run)
					remaining -= #text
				else
					table.insert(new_line, {color: run.color, text: text\sub(1, remaining), bold: run.bold, italic: run.italic})
					remaining = 0
		table.insert(result, new_line)
	return result
is_fully_revealed = -> revealed >= total_chars(_.first(buffer, lines))
reveal_instantly = -> revealed = total_chars(_.first(buffer, lines))

done = () ->
	buffer = _.rest(buffer, lines + 1)
	revealed = 0
on "text", =>
	-- extended: every ordinary `text` event (a separate Ren'Py say
	-- statement, not a `@`-prefixed continuation) now replaces the box
	-- outright (`buffer = add`) instead of only doing so once `#buffer`
	-- happened to already equal `lines` exactly. The old condition meant
	-- a *fresh* dialogue line was appended onto whatever was already
	-- showing in every other case -- harmless for original VNDS content
	-- (where "lines" governs paging through one long wrapped paragraph,
	-- and successive text() calls are rare/short), but on real
	-- Ren'Py-converted content every say statement is its own separate
	-- `text` dispatch: confirmed on real hardware, unrelated dialogue
	-- lines from different speakers piled up together in the box (up to
	-- `lines` == 7 of them on 3DS) looking like one continuous run-on
	-- line, and corrupting word-wrap's rendered width in the process
	-- (measuring/drawing several statements' worth of stale text
	-- together). `no_input` (the `@` continuation marker) still appends,
	-- preserving that behavior, and a single statement that itself wraps
	-- past `lines` still pages via "done!" (`on "input"`'s `#buffer >
	-- lines` check), unaffected by this change.
	no_input = false
	if @text\sub(1, 1) == "@"
		@text = @text\sub(2, -1)
		no_input = true
	if @text == '' or @text == '!' then return
	-- extended: Ren'Py's `window hide` is transient -- it only suppresses
	-- the dialogue box until the *next* real line of dialogue, which
	-- auto-shows it again; it's not a persistent toggle that stays off
	-- until an explicit `window show` (confirmed against Jisei's own
	-- source: `label cafeexamine:` opens with `window hide` and never
	-- shows it again before its own dialogue lines). This engine treated
	-- "window hide" as sticky (`window_visible` only flips back via an
	-- explicit "window" dispatch), so any text right after a "window
	-- hide" with no following "window show" silently never rendered at
	-- all -- confirmed on real hardware: selecting "Examine Room" showed
	-- no flavor text whatsoever before returning to the café menu. A real
	-- line of dialogue always makes the window visible again, matching
	-- Ren'Py's actual behavior.
	window_visible = true
	-- extended: `draw_text` draws each line at x=2*pad (the box's own left
	-- edge at x=pad, plus one more `pad` of inner margin), not x=0 -- so a
	-- line wrapped to fit `text_box_width! - 2*pad` (measured from 0) actually
	-- reaches x = 2*pad + (text_box_width! - 2*pad) = text_box_width!, i.e.
	-- the screen's absolute right edge, with *no* margin on the right to
	-- match the 2*pad margin already reserved on the left. Confirmed on real
	-- hardware: word-wrap consistently let lines run right up to (and
	-- occasionally past) the edge instead of the intended inset box.
	-- Subtracting the text's own 2*pad origin keeps its right edge at
	-- `text_box_width! - 2*pad`, symmetric with the left.
	add = word_wrap(@text, text_box_width! - 4*pad)
	for line in *add do table.insert(backlog, line)
	if no_input
		buffer = concat(buffer, add)
		dispatch "next_ins"
	else
		buffer = add
	revealed = 0
on "sfx", => table.insert(backlog, @)
fast_forward = nil
on "input", =>
	if @ == "a"
		if not is_fully_revealed!
			reveal_instantly!
		elseif #buffer > lines then done!
		else dispatch "next_ins"
	else if @ == "y"
		if fast_forward then
			fast_forward\remove!
			fast_forward = nil
		else
			fast_forward = Timer.every(0.2, ->
				if #buffer > lines then done!
				else dispatch "next_ins"
			)
	else if @ == "x"
		last_ins = {}
		images = {}
		file, line = interpreter.file, interpreter.n
		cancelled = deepcopy(interpreter)
		while true
			interpreter, ins = script.next_instruction(interpreter)
			export interpreter = interpreter
			if interpreter.file == file and interpreter.n == line
				export interpreter = cancelled
				break
			switch ins.type
				when "setimg"
					table.insert(images, ins)
				when "text", "sound", "music", "bgload"
					last_ins[ins.type] = ins
					if ins.type == "bgload" then images = {}
			if ins.type == "choice"
				export interpreter = interpreter
				buffer = {} --clear text state when skipping
				for img in *images do dispatch "next_ins", img
				for key, value in *last_ins
					dispatch "next_ins", value
				dispatch "next_ins", ins
				break
	else if @ == "up"
		choices = {}
		-- choices = [text: t, action: -> for t in *backlog]
		for line in *backlog
			if line.file
				table.insert(choices, {
					text: "[SFX]"
					action: ->
						line.file\play!
						return false
				})
			else
				table.insert(choices, {text: line, action: ->})
		create_listbox(:choices, closable: true, selected: #choices)
	return false
on "touch", ->
	if not is_fully_revealed!
		reveal_instantly!
	elseif #buffer > lines then done!
	else dispatch "next_ins"
	return false
on "update", (dt) ->
	return if is_fully_revealed!
	if fast_forward
		reveal_instantly!
	else
		revealed = math.min(revealed + typewriter_speed * dt, total_chars(_.first(buffer, lines)))
-- Draws one styled run at (x, y): a bold run double-draws offset by 1px
-- (no second font weight available -- see A2's audit note), an italic run
-- shears via love.graphics.print's own kx parameter (no second font style
-- available either); both compose by shearing *both* draws. Cheap: at
-- most 2 extra draw calls per run, same cost class as the rest of the
-- already-per-frame dialogue box.
draw_run_text = (run, x, y) ->
	kx = if run.italic then -0.2 else 0
	lg.print(run.text, x, y, 0, 1, 1, 0, 0, kx, 0)
	if run.bold
		lg.print(run.text, x + 1, y, 0, 1, 1, 0, 0, kx, 0)
on "draw_text", ->
	if #buffer > 0 and window_visible
		lg.setFont(text_font)
		-- extended: box height (and therefore the nameplate drawn above it)
		-- used to unconditionally reserve room for the full `lines` capacity
		-- (7 on 3DS) every frame, regardless of how much text is actually
		-- showing -- harmless back when separate say statements piled up
		-- together and often filled most of that space anyway, but once a
		-- normal line replaces the box outright (usually just 1-2 wrapped
		-- lines), that reserved height pushed the box's top -- and the
		-- nameplate above it -- up past the top of the (240px-tall) bottom
		-- screen entirely. Confirmed on real hardware: the nameplate was
		-- positioned too high and partially cut off at the screen's top
		-- edge. Sized to the buffer's actual visible line count instead
		-- (still capped at `lines`, so an over-long single statement that
		-- pages through "done!" keeps using the full box height it needs).
		visible_lines = math.max(1, math.min(#buffer, lines))
		w, h = text_box_width! - 2*pad, pad + (text_font\getHeight! + pad) * visible_lines
		x, y = pad, lg.getHeight! - h - pad
		if nameplate_text
			-- extended: a character's display name can itself carry text
			-- tags (real content: `Character("{i}(Margaret){/i}{alt}
			-- Thinking{/alt}", ...)`), so it needs the same colorify/
			-- per-run treatment as body text, not a plain lg.print --
			-- `nameplate_color` (Character(color=...), VN3DS-spec.md §6)
			-- seeds the *default* run color when the name has no explicit
			-- {color} tag of its own.
			plate_h = text_font\getHeight! + pad
			name_runs = colorify(nameplate_text, 1, nameplate_color or {1, 1, 1, 1})
			plate_w = 0
			for run in *name_runs do plate_w += text_font\getWidth(run.text)
			-- extended: the custom UI-asset-import system (VN3DS-spec.md
			-- §6) -- draws the game's own real namebox image (9-patch,
			-- possibly tiled -- confirmed real content: Mice Tea's
			-- namebox genuinely tiles) instead of a flat rectangle when
			-- one was converted. A per-character override
			-- (`Character(namebox_background=...)`) swaps just the
			-- *image*; its borders/tile always come from the game-wide
			-- default namebox Frame (a character override has no
			-- border/tile of its own -- see ui_assets.moon's
			-- resolve_entry). Falls back to exactly today's flat color
			-- when no namebox was declared/resolved at all.
			namebox_entry = (ui.character_namebox and ui.character_namebox[nameplate_text]) or ui.namebox
			if namebox_entry and ui.namebox
				lg.setColor(1, 1, 1)
				draw_frame(namebox_entry.image, ui.namebox.borders, ui.namebox.tile, x, y - plate_h, plate_w + 2*pad, plate_h)
			else
				lg.setColor(.506, .631, .757, .9)
				lg.rectangle("fill", x, y - plate_h, plate_w + 2*pad, plate_h)
			name_x = x + pad
			for run in *name_runs
				lg.setColor(run.color)
				draw_run_text(run, name_x, y - plate_h + pad/2)
				name_x += text_font\getWidth(run.text)
		-- extended: the game's own real dialogue textbox image (VN3DS-
		-- spec.md §6) -- always a plain image in both target games (no
		-- Frame()/border-scaling), so borders are all-zero (draw_frame's
		-- degenerate "one plain scaled draw" case). Falls back to exactly
		-- today's flat color when none was declared/resolved.
		if ui.textbox
			lg.setColor(1, 1, 1)
			draw_frame(ui.textbox.image, {0, 0, 0, 0}, false, x, y, w, h)
		else
			lg.setColor(.18,.204,.251, .8)
			lg.rectangle("fill", x, y, w, h)
		lg.setColor(1, 1, 1)
		y_pos = y + pad
		draw_buffer = truncate_colored_lines(_.first(buffer, lines), revealed)
		for line in *draw_buffer
			x_pos = 2*pad
			for run in *line
				lg.setColor(run.color)
				draw_run_text(run, x_pos, y_pos)
				x_pos += text_font\getWidth(run.text)
			y_pos += text_font\getHeight! + pad
		lg.setColor(1, 1, 1)
		lg.setFont(font)
word_wrap = (text, max_width) ->
	-- Come up with a way to handle a single word that is longer than the width
	-- This code is complex
	colored = colorify(text)
	list = {{}}
	l = 1
	line = ""
	for run in *colored
		if run.pause
			-- a pause run carries no visible text -- pass it straight
			-- through as its own zero-width entry (still consumed by
			-- total_chars/truncate_colored_lines' reveal budget), never
			-- affecting word-wrap width math.
			table.insert(list[l], run)
		else
			words = split(run.text, " ")
			if #words > 0
				line = line..words[1]
				for j=2, #words
					tmp = line.." "..words[j]
					if text_font\getWidth(tmp) > max_width
						table.insert(list[l], {color: run.color, text: line, bold: run.bold, italic: run.italic})
						l += 1
						table.insert(list, {})
						line = words[j]
					else line = tmp
				if #words > 1 then line = line.." "
			table.insert(list[l], {color: run.color, text: line, bold: run.bold, italic: run.italic})
			line = ""
	return list

concat = (t1,t2) ->
	for i=1,#t2 do t1[#t1+1] = t2[i]
	return t1
