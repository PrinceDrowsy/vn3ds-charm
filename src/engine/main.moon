export *
import dispatch, dispatch_often, on, remove, register from require 'event'
import create_listbox from require 'listbox'
love.graphics.setDefaultFilter("linear", "linear")
script = require "script"
pprint = require "lib/pprint"
Timer = require 'lib/timer'
profile = require 'lib/profile'
profile.setclock(love.timer.getTime)
lfs = love.filesystem
lg = love.graphics
interpreter = nil
-- require "lovelog"
require "audio"
require "debugging"
require "images"
require "portrait"
require "overlay"
require "ui_assets"
require "text/text"
require "choose"
require "save"
require "input"
require "menu"
require "config"
require "screen"
os.setlocale("", "time") --Needed for the correct time
lfs.setIdentity("VNDS-LOVE")
sx, sy = 0,0
px, py = 0,0
original_width, original_height = lg.getWidth!,lg.getHeight!
-- on "input", =>
-- 	if @ == "y"
-- 		love.filesystem.write('profile.txt', profile.report(40))

font = nil
text_font = nil
love.resize = (w, h) ->
	sx, sy = w / original_width, h / original_height
	-- extended: sprite/background position and size coordinates (setimg
	-- x/y, ATL-derived xalign/yalign) are specified against the O3DS top
	-- screen's own native resolution (400x240), not the original DS's
	-- 256x192 -- this project targets 3DS hardware natively rather than
	-- treating it as "a bigger DS". On a real O3DS top screen this makes
	-- pscale exactly 1 (no up-conversion); it only differs from 1 on other
	-- window sizes (desktop LOVE, New 3DS's identical-resolution top
	-- screen, etc.), same as sx/sy's existing scale-to-fit behavior.
	px, py = w/400, h/240
	font_size = 32 -- fix the font scaling to work based on resolution
	if w < 600 then font_size = 20
	lg.setNewFont(font_size)
	font = lg.getFont!
	text_font = font
	dispatch "resize", {:sx, :sy, :px, :py}
path_exists = (path) ->
	-- lfs.getInfo is unreliable on LOVE Potion 2.0.0's 3DS filesystem backend
	-- (it can report false for files that getDirectoryItems clearly lists),
	-- so check via directory listing instead, same as script.moon's find_script.
	dir, filename = path\match("^(.*)/([^/]*)$")
	return false unless filename
	items = lfs.getDirectoryItems(dir) or {}
	for item in *items
		if item\lower! == filename\lower!
			return true
	return false
next_msg = (ins) ->
	if ins == nil
		interpreter, ins = script.next_instruction(interpreter)
	if ins == nil then return --novel has no more instructions
	if ins.path --verify path exists before trying to run an instruction
		if ins.path\sub(-1) ~= "~" and not path_exists(ins.path)
			return next_msg!
	switch ins.type
		when "text"
			if ins.text == "~" then next_msg!
			else dispatch "text", ins
		when "choice"
			dispatch "choice", ins
		when "delay"
			Timer.after(ins.frames/60, -> next_msg!)
		when "anim_wait"
			-- extended: VN3DS-spec.md §9.1 -- unlike other instruction
			-- types (which dispatch and immediately continue via the
			-- `else` branch below), anim_wait must block until the named
			-- target's animation finishes; images.moon owns the
			-- animation state and calls next_msg! itself once that
			-- happens (or immediately, if nothing is animating).
			dispatch "anim_wait", ins
		when "show_screen"
			-- extended: pulled-forward Phase 5.1 -- blocks the same way
			-- "choice" does; screen.moon calls next_msg! itself once the
			-- screen closes (an action navigates away, or the player
			-- backs out of a closable screen).
			dispatch "show_screen", ins
		when "play"
			-- extended: the VNDS wire keyword "play" (custom audio
			-- channel, VN3DS-spec.md's generic form) collides with the
			-- pre-existing global "play" event (listbox.moon's
			-- close-menu unpause signal, handled below at
			-- `on "play", -> paused -= 1`) if dispatched under the
			-- generic fallthrough's ins.type name -- audio.moon's
			-- handler would then fire with no data on every menu
			-- close, and conversely every custom-channel play would
			-- spuriously decrement `paused`. Route it to its own event
			-- name instead; the wire format/parsed ins.type is
			-- unchanged, so no already-converted bundle needs re-emitting.
			dispatch "channel_play", ins
			next_msg!
		when "stop"
			dispatch "channel_stop", ins --same reasoning, kept symmetric though "stop" has no actual pre-existing collision today
			next_msg!
		--when "cleartext"
		else
			dispatch ins.type, ins
			next_msg!
on "next_ins", next_msg
love.load = ->
	-- love.window.setMode(400, 240)
	love.resize(lg.getWidth!, lg.getHeight!)
	dispatch "load"
	lfs.createDirectory("/novels")
	novels = lfs.getDirectoryItems("/novels")
	opts = {}
	media = font\getHeight! * 3
	for i,novel in ipairs novels
		base_dir = "novels/"..novel.."/"
		if lfs.getInfo(base_dir, "file") then continue
		icons = {"icon-high.png", "icon-high.jpg", "icon.png", "icon.jpg"}
		thumbnails = {"thumbnail-high.png", "thumbnail-high.jpg", "thumbnail.png", "thumbnail.jpg"}
		preview = ->
		for icon in *icons
			if lfs.getInfo(base_dir..icon)
				img = lg.newImage(base_dir..icon)
				s = math.min(media/img\getWidth!, media/img\getHeight!)
				preview = (x, y) -> lg.draw(img, x, y, 0, s, s)
				break
		path = "~"
		for thumb in *thumbnails
			if lfs.getInfo(base_dir..thumb)
				path = base_dir..thumb
				break
		table.insert(opts, {
			text: novel,
			media: preview
			onchange: () -> dispatch "bgload", {:path}
			action: () ->
				files = lfs.getDirectoryItems(base_dir)
				with wrap _(files)
					\filter => @match("^.+(%..+)$") == ".zip"
					\map => @gsub(".zip", "")
					\reject => _.include(files, @)
					\each => lfs.mount(base_dir..@..".zip", base_dir)
				dispatch "load_slot", base_dir, false
		})
	if next(opts) == nil
		dispatch "text", {text: "No novels found in this directory: "}
		dispatch "text", {text: lfs.getSaveDirectory!.."/novels"}
		dispatch "text", {text: "Add one and restart the program"}
	else create_listbox(choices: opts, :media)
love.draw = ->
	dispatch_often "draw_background"
	dispatch_often "draw_foreground"
	dispatch_often "draw_overlay"
	dispatch_often "draw_text"
	dispatch_often "draw_choice"
	dispatch_often "draw_ui"
	dispatch_often "draw_debug"

if love._console_name == "3DS"
	love.draw = =>
		if @ ~= "bottom"
			dispatch_often "draw_background"
			dispatch_often "draw_foreground"
			dispatch_often "draw_overlay"
			dispatch_often "draw_ui"
			dispatch_often "draw_debug"
		else
			dispatch_often "draw_text"
			dispatch_often "draw_choice"
paused = 0
on "pause", -> paused += 1
on "play", -> paused -= 1
love.update = (dt) ->
	dispatch_often "update", dt
	if paused == 0 then Timer.update(dt)

is_fullscreen = false
love.keypressed = (key) ->
	dispatch_often "keyboard_input", key
	if key == "f11" then
		love.window.setFullscreen(is_fullscreen, "desktop")
		is_fullscreen = not is_fullscreen

love.gamepadpressed = (joy, button) -> dispatch_often "gamepad_input", button
love.touchpressed = (id, x, y) -> dispatch_often "touch", {:x, :y}
