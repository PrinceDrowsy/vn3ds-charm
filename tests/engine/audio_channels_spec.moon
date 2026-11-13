require "util"
pprint = require "lib/pprint"
event = require "event"
_G.dispatch = event.dispatch
_G.dispatch_often = event.dispatch_often
_G.on = event.on
_G.remove = event.remove
_G.register = event.register

mock_source = ->
	obj = {playing: false, looping: false, volume: 1}
	obj.setLooping = (self, val) -> self.looping = val
	obj.setVolume = (self, val) -> self.volume = val
	obj.getVolume = (self) -> self.volume
	obj.play = (self) -> self.playing = true
	obj.stop = (self) -> self.playing = false
	obj.isPlaying = (self) -> self.playing
	return obj

_G.love = {
	audio: {
		newSource: (path, kind) -> mock_source!
	}
	filesystem: {
		getDirectoryItems: => {""}
	}
}
_G.lfs = love.filesystem

script = require "script"
audio = require "audio"

describe "Audio channels (Phase 1.7)", ->
	before_each ->
		dispatch "config", {audio: {music: 100, sound: 100}}
		dispatch "restore", {}

	it "voiceover starts a non-looping source on its own channel", ->
		dispatch "voiceover", {path: "sound/line1.ogg"}
		-- indirectly verify via save: the voice channel now has this path
		saved = {}
		dispatch "save", saved
		assert.are.equal(saved.voice.path, "sound/line1.ogg")

	it "starting a new voiceover does not stop music or sound", ->
		dispatch "music", {path: "sound/theme.ogg"}
		dispatch "sound", {path: "sound/click.ogg", n: 1}
		dispatch "voiceover", {path: "sound/line1.ogg"}
		saved = {}
		dispatch "save", saved
		assert.are.equal(saved.music.path, "sound/theme.ogg")
		assert.are.equal(saved.sound.path, "sound/click.ogg")
		assert.are.equal(saved.voice.path, "sound/line1.ogg")

	it "stopmusic clears only the music channel", ->
		dispatch "music", {path: "sound/theme.ogg"}
		dispatch "sound", {path: "sound/click.ogg", n: 1}
		dispatch "stopmusic"
		saved = {}
		dispatch "save", saved
		assert.is_nil(saved.music.path)
		assert.are.equal(saved.sound.path, "sound/click.ogg")

	it "stopsound clears only the sound channel", ->
		dispatch "music", {path: "sound/theme.ogg"}
		dispatch "sound", {path: "sound/click.ogg", n: 1}
		dispatch "stopsound"
		saved = {}
		dispatch "save", saved
		assert.are.equal(saved.music.path, "sound/theme.ogg")
		assert.is_nil(saved.sound.path)

	it "stopvoice clears only the voice channel", ->
		dispatch "music", {path: "sound/theme.ogg"}
		dispatch "voiceover", {path: "sound/line1.ogg"}
		dispatch "stopvoice"
		saved = {}
		dispatch "save", saved
		assert.are.equal(saved.music.path, "sound/theme.ogg")
		assert.is_nil(saved.voice.path)

	it "ambiance plays simultaneously with music, on its own independent channel", ->
		-- real content (Mice Tea's screens/music.rpy) registers "ambiance"
		-- as a genuinely separate Ren'Py channel via
		-- renpy.music.register_channel, distinct from and playable at the
		-- same time as "music" -- aliasing it onto the existing music
		-- channel would incorrectly cut one off when the other starts.
		dispatch "music", {path: "sound/theme.ogg"}
		dispatch "ambiance", {path: "sound/amb_city.ogg"}
		saved = {}
		dispatch "save", saved
		assert.are.equal(saved.music.path, "sound/theme.ogg")
		assert.are.equal(saved.ambiance.path, "sound/amb_city.ogg")

	it "stopambiance clears only the ambiance channel", ->
		dispatch "music", {path: "sound/theme.ogg"}
		dispatch "ambiance", {path: "sound/amb_city.ogg"}
		dispatch "stopambiance"
		saved = {}
		dispatch "save", saved
		assert.are.equal(saved.music.path, "sound/theme.ogg")
		assert.is_nil(saved.ambiance.path)

	it "ambiance survives save/restore independently of music", ->
		dispatch "music", {path: "sound/theme.ogg"}
		dispatch "ambiance", {path: "sound/amb_city.ogg"}
		saved = {}
		dispatch "save", saved
		dispatch "restore", saved
		saved2 = {}
		dispatch "save", saved2
		assert.are.equal(saved2.music.path, "sound/theme.ogg")
		assert.are.equal(saved2.ambiance.path, "sound/amb_city.ogg")

	it "music2 plays simultaneously with music, on its own independent channel", ->
		-- real content (Mice Tea) uses "music2" for a genuine layered-music
		-- crossfade -- a real, independent 5th channel, not cleanup-only.
		dispatch "music", {path: "sound/theme.ogg"}
		dispatch "music2", {path: "sound/theme2.ogg"}
		saved = {}
		dispatch "save", saved
		assert.are.equal(saved.music.path, "sound/theme.ogg")
		assert.are.equal(saved.music2.path, "sound/theme2.ogg")

	it "stopmusic2 clears only the music2 channel", ->
		dispatch "music", {path: "sound/theme.ogg"}
		dispatch "music2", {path: "sound/theme2.ogg"}
		dispatch "stopmusic2"
		saved = {}
		dispatch "save", saved
		assert.are.equal(saved.music.path, "sound/theme.ogg")
		assert.is_nil(saved.music2.path)

describe "Custom/generic audio channels", ->
	-- 13-corpus comparison finding: real content (ScarletHollow's
	-- secondary/tertiary/music4-6, Our Life's voice2) uses channel names
	-- outside the 5 curated ones above -- audio.moon's generic `channels`
	-- table + "channel_play"/"channel_stop" handlers exist for exactly
	-- this, proven here against a channel name ("secondary") that was
	-- never hardcoded. (Named "channel_play"/"channel_stop", not the raw
	-- "play"/"stop" wire keywords, because "play" already means something
	-- else globally -- see the real-hardware regression test below.)
	before_each ->
		dispatch "config", {audio: {music: 100, sound: 100}}
		dispatch "restore", {}

	it "play starts a custom channel and stop clears only that channel", ->
		dispatch "music", {path: "sound/theme.ogg"}
		dispatch "channel_play", {channel: "secondary", path: "sound/track.ogg", loop: true, mixer: "music"}
		saved = {}
		dispatch "save", saved
		assert.are.equal(saved.music.path, "sound/theme.ogg")
		assert.are.equal(saved.custom_channels.secondary.path, "sound/track.ogg")
		dispatch "channel_stop", {channel: "secondary"}
		saved2 = {}
		dispatch "save", saved2
		assert.are.equal(saved2.music.path, "sound/theme.ogg")
		assert.is_nil(saved2.custom_channels.secondary)

	it "a custom channel plays simultaneously with music without cutting it off", ->
		dispatch "music", {path: "sound/theme.ogg"}
		dispatch "channel_play", {channel: "secondary", path: "sound/track.ogg", loop: true, mixer: "music"}
		dispatch "channel_play", {channel: "tertiary", path: "sound/track2.ogg", loop: true, mixer: "music"}
		saved = {}
		dispatch "save", saved
		assert.are.equal(saved.music.path, "sound/theme.ogg")
		assert.are.equal(saved.custom_channels.secondary.path, "sound/track.ogg")
		assert.are.equal(saved.custom_channels.tertiary.path, "sound/track2.ogg")

	it "a custom channel survives save/restore with its path/loop/mixer intact", ->
		dispatch "channel_play", {channel: "voice2", path: "sound/line.ogg", loop: false, mixer: "sound"}
		saved = {}
		dispatch "save", saved
		dispatch "restore", saved
		saved2 = {}
		dispatch "save", saved2
		assert.are.equal(saved2.custom_channels.voice2.path, "sound/line.ogg")
		assert.are.equal(saved2.custom_channels.voice2.loop, false)
		assert.are.equal(saved2.custom_channels.voice2.mixer, "sound")

	it "setvolume/fade works on a custom channel via the generalized channel_table fallback", ->
		captured = {}
		love.audio.newSource = (path, kind) ->
			source = mock_source!
			captured[path] = source
			source
		dispatch "channel_play", {channel: "secondary", path: "sound/track.ogg", loop: true, mixer: "music"}
		dispatch "setvolume", {channel: "secondary", level: 0.0, delay: 2.0}
		dispatch "update", 1.0
		assert.are.near(captured["sound/track.ogg"].volume, 0.5, 0.001)
		dispatch "update", 1.0
		assert.are.near(captured["sound/track.ogg"].volume, 0.0, 0.001)

	it "the global unrelated \"play\"/\"stop\" pause-toggle events do not crash and do not touch custom-channel state", ->
		-- real-hardware regression: main.moon's generic instruction fallthrough used to dispatch the
		-- raw "play"/"stop" wire keywords directly, colliding with listbox.moon's pre-existing
		-- menu-close unpause signal (dispatched with no data payload) and crashing audio.moon with
		-- "attempt to index local 'self' (a nil value)" on every menu close.
		dispatch "channel_play", {channel: "secondary", path: "sound/track.ogg", loop: true, mixer: "music"}
		assert.has_no.errors(-> dispatch "play")
		assert.has_no.errors(-> dispatch "stop")
		saved = {}
		dispatch "save", saved
		assert.are.equal(saved.custom_channels.secondary.path, "sound/track.ogg")

describe "setvolume (renpy.music.set_volume)", ->
	captured = nil

	before_each ->
		dispatch "config", {audio: {music: 100, sound: 100}}
		dispatch "restore", {}
		-- audio.moon's channel tables are module-locals (not visible from
		-- here) -- capture the mock Source object `love.audio.newSource`
		-- returns for each channel so its .volume can be inspected
		-- directly, the same role `lg.draw` spies play in other specs.
		captured = {}
		love.audio.newSource = (path, kind) ->
			source = mock_source!
			captured[path] = source
			source

	it "sets a channel's volume immediately when no delay is given", ->
		dispatch "music", {path: "sound/theme.ogg"}
		dispatch "setvolume", {channel: "music", level: 0.3, delay: 0}
		assert.are.equal(captured["sound/theme.ogg"].volume, 0.3)

	it "fades a channel's volume linearly to the target over the given delay", ->
		dispatch "music2", {path: "sound/theme2.ogg"}
		dispatch "setvolume", {channel: "music2", level: 0.0, delay: 2.0}
		source = captured["sound/theme2.ogg"]
		-- starts at whatever the channel's current volume was (1.0 from
		-- "config"/music_volume), not yet at the target
		dispatch "update", 1.0 -- halfway through the 2-second fade
		assert.are.near(source.volume, 0.5, 0.001)
		dispatch "update", 1.0 -- fade complete
		assert.are.near(source.volume, 0.0, 0.001)

	it "does not affect a different channel's volume", ->
		dispatch "music", {path: "sound/theme.ogg"}
		dispatch "ambiance", {path: "sound/amb_city.ogg"}
		dispatch "setvolume", {channel: "ambiance", level: 0.0, delay: 1.0}
		dispatch "update", 1.0
		assert.are.near(captured["sound/theme.ogg"].volume, 1.0, 0.001)
		assert.are.near(captured["sound/amb_city.ogg"].volume, 0.0, 0.001)

	it "a fade stops advancing once its target channel has been cleared", ->
		dispatch "music2", {path: "sound/theme2.ogg"}
		dispatch "setvolume", {channel: "music2", level: 0.0, delay: 2.0}
		dispatch "stopmusic2"
		-- should not error even though the faded channel no longer has a source
		dispatch "update", 1.0
		dispatch "update", 1.0

describe "script.moon parsing (Phase 1.7)", ->
	it "parses voiceover with a sound/ prefixed path", ->
		i = script.load("", -> "voiceover line1.ogg")
		i, ins = script.next_instruction(i)
		assert.are.equal(ins.type, "voiceover")
		assert.are.equal(ins.path, "sound/line1.ogg")

	it "parses stopmusic/stopsound/stopvoice as bare instruction types", ->
		i = script.load("", ->
			"stopmusic\nstopsound\nstopvoice"
		)
		i, a = script.next_instruction(i)
		i, b = script.next_instruction(i)
		i, c = script.next_instruction(i)
		assert.are.equal(a.type, "stopmusic")
		assert.are.equal(b.type, "stopsound")
		assert.are.equal(c.type, "stopvoice")

	it "parses ambiance/stopambiance the same shape as music/stopmusic", ->
		i = script.load("", -> "ambiance amb_city.ogg\nstopambiance")
		i, a = script.next_instruction(i)
		i, b = script.next_instruction(i)
		assert.are.equal(a.type, "ambiance")
		assert.are.equal(a.path, "sound/amb_city.ogg")
		assert.are.equal(b.type, "stopambiance")

	it "parses music2/stopmusic2 the same shape as music/stopmusic", ->
		i = script.load("", -> "music2 theme2.ogg\nstopmusic2")
		i, a = script.next_instruction(i)
		i, b = script.next_instruction(i)
		assert.are.equal(a.type, "music2")
		assert.are.equal(a.path, "sound/theme2.ogg")
		assert.are.equal(b.type, "stopmusic2")

	it "parses setvolume with channel/level/delay", ->
		i = script.load("", -> "setvolume music2 0.5 2.0")
		i, ins = script.next_instruction(i)
		assert.are.equal(ins.type, "setvolume")
		assert.are.equal(ins.channel, "music2")
		assert.are.equal(ins.level, 0.5)
		assert.are.equal(ins.delay, 2.0)

	it "parses setvolume with a defaulted (omitted) delay as 0", ->
		i = script.load("", -> "setvolume music 1.0")
		i, ins = script.next_instruction(i)
		assert.are.equal(ins.delay, 0)

	it "parses the generic play/stop instructions for a custom channel", ->
		i = script.load("", -> "play secondary track.ogg 1 music\nstop secondary")
		i, a = script.next_instruction(i)
		i, b = script.next_instruction(i)
		assert.are.equal(a.type, "play")
		assert.are.equal(a.channel, "secondary")
		assert.are.equal(a.path, "sound/track.ogg")
		assert.are.equal(a.loop, true)
		assert.are.equal(a.mixer, "music")
		assert.are.equal(b.type, "stop")
		assert.are.equal(b.channel, "secondary")

	it "parses the generic play instruction's loop flag as false for '0'", ->
		i = script.load("", -> "play voice2 line.ogg 0 sound")
		i, ins = script.next_instruction(i)
		assert.are.equal(ins.loop, false)
		assert.are.equal(ins.mixer, "sound")
