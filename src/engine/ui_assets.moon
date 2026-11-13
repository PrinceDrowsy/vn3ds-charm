-- Reads manifest.json's "ui" section (the custom UI-asset-import system,
-- VN3DS-spec.md §6) into a shared `ui` table that text.moon/listbox.moon
-- read directly -- the engine's first real consumer of manifest.json
-- (nothing read it at all before this). Falls back to every field simply
-- being absent (text.moon/listbox.moon's existing flat-color rendering
-- already handles a missing `ui.textbox`/etc. gracefully) when the game
-- never declared any UI chrome, or the bundle predates this feature.
json = require "lib/json"
local *

-- Mutated in place (never reassigned) so a reference another module
-- captured via `import ui from require "ui_assets"` at file-load time
-- stays live across a later `update_ui_assets!` -- reassigning `ui = {}`
-- here would silently strand any such reference on the old, now-stale
-- table instead.
ui = {}
loaded_images = {}

get_image = (path) ->
	unless loaded_images[path]
		loaded_images[path] = lg.newImage(path)
	loaded_images[path]

-- Resolves one manifest "ui" entry -- either a bare basename (textbox) or
-- a {image:, borders:, tile:} table (namebox/choice_idle/choice_hover,
-- also reused for a per-character namebox override) -- into a table
-- carrying a *loaded* image plus (for Frame entries) its borders/tile, or
-- nil if the entry itself was nil (undeclared/unresolved) or the file
-- doesn't actually exist in this bundle.
resolve_entry = (base_dir, entry) ->
	return nil unless entry
	path = if type(entry) == "table" then entry.image else entry
	full_path = base_dir.."ui/"..path
	return nil unless path_exists(full_path)
	image = get_image(full_path)
	if type(entry) == "table"
		{:image, borders: entry.borders, tile: entry.tile}
	else
		{:image}

update_ui_assets = ->
	for key in pairs(ui)
		ui[key] = nil
	loaded_images = {}
	return unless interpreter and interpreter.base_dir
	manifest_path = interpreter.base_dir.."manifest.json"
	return unless path_exists(manifest_path)
	ok, manifest = pcall(json.decode, lfs.read(manifest_path))
	return unless ok and manifest and manifest.ui
	base_dir = interpreter.base_dir
	ui.textbox = resolve_entry(base_dir, manifest.ui.textbox)
	ui.namebox = resolve_entry(base_dir, manifest.ui.namebox)
	ui.choice_idle = resolve_entry(base_dir, manifest.ui.choice_idle)
	ui.choice_hover = resolve_entry(base_dir, manifest.ui.choice_hover)
	-- Keyed by *display name*, not the character's script varname -- by
	-- the time a line reaches text.moon's "nameplate" command, only the
	-- resolved display name survives (vnds_writer.py's Say emission), so
	-- that's the only identity available to look this up by at draw time.
	character_namebox = {}
	if manifest.characters
		for _varname, cdef in pairs(manifest.characters)
			if cdef.namebox and cdef.name
				character_namebox[cdef.name] = resolve_entry(base_dir, cdef.namebox)
	ui.character_namebox = character_namebox

on "config", -> update_ui_assets!
on "restore", -> update_ui_assets!

{:ui}
