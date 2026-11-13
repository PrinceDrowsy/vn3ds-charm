LIP = require "lib/LIP"
local *
config = {
	audio: {music: 100, sound: 100}
	font: {override_font: false}
	text: {speed_cps: nil}
}
DEFAULT_TEXT_SPEED = 40
on "config_menu", ->
	copy = deepcopy(config)
	create_listbox({
		choices: {
			range(copy, "audio", "music", => "Music Volume #{@audio.music}%")
			range(copy, "audio", "sound", => "Sound Volume #{@audio.sound}%")
			text_speed_row(copy)
			toggle(copy, "font", "override_font", "Using System Font", "Using Novel Font")
			{
				text: "Save Settings",
				action: (choice, close) ->
					close!
					dispatch "save_config", copy
			}
		},
		closable: true
		onclose: -> dispatch "config", config
	})
on "load", ->
	new_config = LIP.load("config.ini")
	for key, value in pairs new_config --override defaults with config
		_.extend(config[key], new_config[key])
	dispatch "config", config

on "save_config", (new_config) ->
	config = new_config
	LIP.save('config.ini', config)
range = (copy, section, key, text) ->
	return {
		text: text(copy)
		action: ->
		right: =>
			copy[section][key] = math.min(copy[section][key] + 10, 100)
			@text = text(copy)
			dispatch "config", copy
		left: =>
			copy[section][key] = math.max(copy[section][key] - 10, 0)
			@text = text(copy)
			dispatch "config", copy
	}
toggle = (copy, section, key, true_text, false_text) ->
	text = -> if copy[section][key] then true_text else false_text
	return {
		text: text!
		action: =>
			copy[section][key] = not copy[section][key]
			@text = text!
			dispatch "config", copy
	}
-- text speed has no fixed 0-100 range like the volume rows, and `nil`
-- (never overridden by the player -- text.moon falls back to the game's
-- own authored default, or 40, VN3DS-spec.md §6) is a real, distinct
-- state from "40 cps", so it gets its own row instead of reusing range().
text_speed_row = (copy) ->
	text = -> if copy.text.speed_cps then "Text Speed #{copy.text.speed_cps} cps" else "Text Speed Default"
	return {
		text: text!
		action: ->
		right: =>
			copy.text.speed_cps = math.min((copy.text.speed_cps or DEFAULT_TEXT_SPEED) + 5, 200)
			@text = text!
			dispatch "config", copy
		left: =>
			copy.text.speed_cps = math.max((copy.text.speed_cps or DEFAULT_TEXT_SPEED) - 5, 10)
			@text = text!
			dispatch "config", copy
	}
