json = require "lib/json"
local *
media = 0
on "resize", -> media = font\getHeight! * 3
on "save_slot", ->
	base_dir = interpreter.base_dir
	write_slot = =>
		save_table = {interpreter: script.save(interpreter)}
		dispatch_often "save", save_table
		with love.filesystem.newFile(@data.fn, "w")
			\write(json.encode(save_table))
			\flush!
			\close!
		choice = preview_slot(@data.i, @data.fn, save_table, lfs.getInfo(@data.fn))
		@text = choice.text
		@action = write_slot
		@media = choice.media
		return false
	slot_ui(base_dir, write_slot, write_slot)
on "load_slot", (base_dir, closable = true) ->
	slot_ui(base_dir,
		=>
			export interpreter = script.load(base_dir, lfs.read, @data.save.interpreter)
			dispatch "restore", @data.save
			dispatch "next_ins"
			return true
		=>
			export interpreter = script.load(base_dir, lfs.read)
			dispatch "restore", {}
			-- extended, real-hardware regression: a real converted
			-- main_menu is registered by ordinary screen_begin/.../
			-- screen_end instructions in the script's own top-level
			-- preamble (before "@start") -- but at this exact point
			-- the interpreter hasn't advanced past instruction 1 yet,
			-- so that registration has never actually run. Walk it
			-- forward through the preamble first (see run_preamble's
			-- own docstring) so screen.moon's real main_menu (if the
			-- game has one) is what actually gets shown, not the
			-- hardcoded placeholder.
			export interpreter = script.run_preamble(interpreter)
			-- extended: show the native main menu before a fresh
			-- playthrough begins, rather than jumping straight into the
			-- story -- screen.moon's main_menu "Start Game" button
			-- dispatches "next_ins" itself once closed.
			dispatch "show_screen", {name: "main_menu"}
			return true
		closable
	)
preview_slot = (i, fn, save, info) ->
	bg_path = save.background.path
	preview = ->
	if save.background and save.background.path
		img = lg.newImage(save.background.path)
		s = math.min(media/img\getWidth!, media/img\getHeight!)
		preview = (x, y) -> lg.draw(img, x, y, 0, s, s)
	return {
		text: "Save #{i}\n#{os.date("%x %H:%M", info.modtime)}"
		media: preview
		data: {:save, :fn, :i}
	}
slot_ui = (base_dir, existing_slot, new_slot, closable = true) ->
	choices = {}
	for i = 1, 10
		fn = base_dir.."/save#{i}.json"
		info = lfs.getInfo(fn)
		if info
			save = json.decode(lfs.read(fn))
			choice = preview_slot(i, fn, save, info)
			choice.action = existing_slot
			table.insert(choices, choice)
		else
			table.insert(choices, {
				text: "Save #{i} --"
				action: new_slot
				data: {:fn, :i}
			})
	create_listbox({:choices, :closable, :media})
