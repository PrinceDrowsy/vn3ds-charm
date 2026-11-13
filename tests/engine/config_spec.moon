require "util"
event = require "event"
_G.dispatch = event.dispatch
_G.dispatch_often = event.dispatch_often
_G.on = event.on
_G.remove = event.remove
_G.register = event.register

-- in-memory love.filesystem, just enough for lib/LIP.lua's newFile/open/
-- write/close/lines/getInfo calls to round-trip a config.ini through.
files = {}
_G.love = {
	filesystem: {
		newFile: (fileName) ->
			{
				open: (self, mode) -> true
				write: (self, contents) -> files[fileName] = contents
				close: (self) -> true
			}
		getInfo: (fileName) -> if files[fileName] then {} else nil
		lines: (fileName) ->
			content = files[fileName] or ""
			all_lines = {}
			for line in content\gmatch("[^\r\n]+") do table.insert(all_lines, line)
			idx = 0
			->
				idx += 1
				all_lines[idx]
	}
}
_G.lfs = love.filesystem

last_listbox_opts = nil
_G.create_listbox = (opts) -> last_listbox_opts = opts

require "config"

-- config_menu's choices are, in order: music volume, sound volume,
-- text speed, font toggle, "Save Settings" -- see config.moon.
text_speed_row = -> last_listbox_opts.choices[3]

describe "Settings screen text-speed control (Phase 3.8)", ->
	before_each ->
		files = {}
		last_listbox_opts = nil
		-- config.moon's `config` is a module-level local that otherwise
		-- persists across every test in this file (only "save_config"/
		-- "load" ever mutate it) -- reset it via the same real event a
		-- fresh boot would use, rather than reaching into config.moon's
		-- private state.
		dispatch "save_config", {audio: {music: 100, sound: 100}, font: {override_font: false}, text: {speed_cps: nil}}
		dispatch "config_menu"

	it "starts unset, labeled as using the game/hardcoded default", ->
		assert.are.equal(text_speed_row!.text, "Text Speed Default")

	it "pressing right seeds from the 40cps baseline and steps up by 5", ->
		row = text_speed_row!
		row.right(row)
		assert.are.equal(row.text, "Text Speed 45 cps")

	it "pressing left seeds from the 40cps baseline and steps down by 5", ->
		row = text_speed_row!
		row.left(row)
		assert.are.equal(row.text, "Text Speed 35 cps")

	it "clamps at the upper bound instead of climbing forever", ->
		row = text_speed_row!
		for i = 1, 100 do row.right(row)
		assert.are.equal(row.text, "Text Speed 200 cps")

	it "clamps at the lower bound instead of dropping forever", ->
		row = text_speed_row!
		for i = 1, 100 do row.left(row)
		assert.are.equal(row.text, "Text Speed 10 cps")

	it "dispatches \"config\" live on every adjustment, carrying the new value", ->
		seen = nil
		on "config", (cfg) -> seen = cfg.text.speed_cps
		row = text_speed_row!
		row.right(row)
		assert.are.equal(seen, 45)

describe "config.ini persistence of the player's text-speed preference", ->
	before_each ->
		files = {}
		last_listbox_opts = nil
		-- config.moon's `config` is a module-level local that otherwise
		-- persists across every test in this file (only "save_config"/
		-- "load" ever mutate it) -- reset it via the same real event a
		-- fresh boot would use, rather than reaching into config.moon's
		-- private state.
		dispatch "save_config", {audio: {music: 100, sound: 100}, font: {override_font: false}, text: {speed_cps: nil}}

	it "round-trips a chosen speed through save_config -> LIP.save -> LIP.load -> on \"load\"", ->
		dispatch "config_menu"
		row = text_speed_row!
		row.right(row) -- 40 -> 45
		row.right(row) -- 45 -> 50
		save_action = last_listbox_opts.choices[5]
		assert.are.equal(save_action.text, "Save Settings")
		save_action.action(save_action, ->)

		assert.is_not_nil(files["config.ini"])
		assert.is_not_nil(files["config.ini"]\find("speed_cps=50"))

		-- a fresh "load" (e.g. next boot) must pick the persisted value back
		-- up and reflect it the next time the settings screen opens
		dispatch "load"
		dispatch "config_menu"
		assert.are.equal(text_speed_row!.text, "Text Speed 50 cps")

	it "never overridden: config.ini has no meaningful speed_cps entry, and the row still reads as Default", ->
		dispatch "config_menu"
		save_action = last_listbox_opts.choices[5]
		save_action.action(save_action, ->)

		dispatch "load"
		dispatch "config_menu"
		assert.are.equal(text_speed_row!.text, "Text Speed Default")
