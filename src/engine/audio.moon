puremagic = require "lib/puremagic"
local *
sound = {}
music = {}
voice = {}
-- extended: a real, independent 4th channel -- Ren'Py's own
-- `renpy.music.register_channel("ambiance", "sfx", loop=True)` idiom
-- (registered on the "sfx" mixer group, not "music" -- see the
-- sound_volume use in "ambiance"'s handler below), confirmed used
-- frequently enough in real content (Mice Tea: 59 play+stop) and
-- legitimately simultaneous with music that aliasing it onto the
-- existing "music" channel would be wrong (starting one would cut off
-- the other) -- mirrors "music"'s own shape exactly (own table, looping,
-- save/restore).
ambiance = {}
-- extended: a real 5th channel -- Ren'Py's own
-- `renpy.music.register_channel("music2", "music", loop=True)` idiom,
-- registered on the "music" mixer group (unlike "ambiance"'s "sfx"
-- group). Real content (Mice Tea) uses this heavily for a genuine
-- layered-music crossfade: playing a secondary track on "music2"
-- simultaneously with "music", fading each channel's volume in/out via
-- `renpy.music.set_volume` (see "setvolume"/`volume_fades` below) rather
-- than a straight cut -- not just cleanup, real gameplay-relevant audio.
music2 = {}
-- extended: any channel name outside the 5 curated ones above (VN3DS-
-- spec.md §6) -- e.g. real content confirmed using "secondary"/"tertiary"/
-- "music4-6" (ScarletHollow) and a second voice channel "voice2" (Our
-- Life). Auto-vivified per name the first time that game's own converted
-- script references it (see "play" below) -- memory-bounded by
-- construction, since a compiled script can never reference more distinct
-- channel names than it contains. Each entry has the same {path, file}
-- shape as the 5 curated tables above, plus `loop`/`mixer` (which of the
-- two curated shapes -- looping/"music"-mixer like music2, or one-shot/
-- "sound"-mixer like voice -- this custom channel behaves like; decided
-- once at convert time by the emitter, never guessed here at runtime).
channels = {}
sound_volume, music_volume = nil, nil
-- extended: in-progress `renpy.music.set_volume(level, delay=N)` fades,
-- one per channel name -- a real linear fade to the target volume over
-- `delay` seconds (matching the PC version's own crossfade timing),
-- advanced every "update" tick below. Not routed through lib/timer's
-- Timer.tween (which mutates a plain table field directly, once per
-- frame) since a LÖVE audio Source's volume is a method
-- (:setVolume!/:getVolume!), not a field.
volume_fades = {}
filetype = {
	"audio/x-aiff": "file.aiff"
	"audio/x-flac": "file.flac"
	"audio/mp4": "file.m4a"
	"audio/x-matroska": "file.mka"
	"audio/mpeg": "file.mp3"
	"audio/vorbis": "file.ogg"
	"audio/ogg": "file.ogg"
	"audio/x-wav": "file.wav"
	"audio/webm": "file.webm"
	"audio/x-ms-wma": "file.wma"
}
load_source = =>
	success, source = pcall(love.audio.newSource, @, "stream")
	if success then return source
	mime = puremagic.via_path(@)
	if filetype[mime] == nil then return nil
	original = lfs.newFileData(@)
	actual = lfs.newFileData(original\getString(), filetype[mime])
	return love.audio.newSource(actual, "stream")

on "config", => -- scale volume to be float
	sound_volume = @audio.sound/100
	music_volume = @audio.music/100
	if next sound then sound.file\setVolume(sound_volume)
	if next music then music.file\setVolume(music_volume)
	if next voice then voice.file\setVolume(sound_volume)
	if next ambiance then ambiance.file\setVolume(sound_volume)
	if next music2 then music2.file\setVolume(music_volume)
	for name, chan in pairs(channels)
		if next(chan)
			chan.file\setVolume(chan.mixer == "music" and music_volume or sound_volume)
on "save", =>
	@music = {path: music.path}
	@sound = {path: sound.path, n: sound.n}
	@voice = {path: voice.path}
	@ambiance = {path: ambiance.path}
	@music2 = {path: music2.path}
	@custom_channels = {}
	for name, chan in pairs(channels)
		if next(chan)
			@custom_channels[name] = {path: chan.path, loop: chan.loop, mixer: chan.mixer}

on "restore", =>
	music = clear music
	sound = clear sound
	voice = clear voice
	ambiance = clear ambiance
	music2 = clear music2
	channels = {}
	volume_fades = {}
	if get(@, "music", "path") then dispatch "music", @music
	if get(@, "sound", "path") then dispatch "sound", @sound
	if get(@, "voice", "path") then dispatch "voiceover", @voice
	if get(@, "ambiance", "path") then dispatch "ambiance", @ambiance
	if get(@, "music2", "path") then dispatch "music2", @music2
	for name, data in pairs(@custom_channels or {})
		dispatch "channel_play", {channel: name, path: data.path, loop: data.loop, mixer: data.mixer}
clear = =>
	-- returns the cleared table; callers must reassign (e.g. `music = clear
	-- music`) since reassigning @ here only rebinds this local parameter,
	-- not the caller's variable
	if next(@)
		@file\stop!
		{}
	else @
exists = => @\sub(-1) != "~"
on "sound", =>
	sound = clear sound
	if exists(@path) and @n != 0
		file = load_source(@path)
		if file == nil then return
		file = with file
			\setLooping(@n == -1)
			\setVolume(sound_volume)
			\play!
		sound = {path: @path, :file, n: @n or 0}
		dispatch "sfx", sound
on "music", =>
	music = clear music
	if exists @path
		file = load_source(@path)
		if file == nil then return
		file = with file
			\setLooping(true)
			\setVolume(music_volume)
			\play!
		music = {path: @path, :file}
on "voiceover", =>
	voice = clear voice
	if exists @path
		file = load_source(@path)
		if file == nil then return
		file = with file
			\setLooping(false)
			\setVolume(sound_volume)
			\play!
		voice = {path: @path, :file}
on "ambiance", =>
	ambiance = clear ambiance
	if exists @path
		file = load_source(@path)
		if file == nil then return
		file = with file
			\setLooping(true)
			\setVolume(sound_volume) -- Ren'Py registers "ambiance" on the "sfx" mixer group, not "music"
			\play!
		ambiance = {path: @path, :file}
on "music2", =>
	music2 = clear music2
	if exists @path
		file = load_source(@path)
		if file == nil then return
		file = with file
			\setLooping(true)
			\setVolume(music_volume)
			\play!
		music2 = {path: @path, :file}
on "stopmusic", -> music = clear music
on "stopsound", -> sound = clear sound
on "stopvoice", -> voice = clear voice
on "stopambiance", -> ambiance = clear ambiance
on "stopmusic2", -> music2 = clear music2

-- extended: generic play/stop for any channel name outside the 5 curated
-- ones above -- `loop`/`mixer` arrive as explicit data from script.moon's
-- generic "play"/"stop" instructions (or from "restore" above), so this
-- never has to guess a custom channel's behavior from its name at
-- runtime. Listens on "channel_play"/"channel_stop" (main.moon routes
-- the raw "play"/"stop" wire keywords there) rather than the bare
-- "play"/"stop" event names, which already mean something else globally
-- (listbox.moon's menu-close unpause signal below this file's own
-- "sfx"/pause handling elsewhere in main.moon).
on "channel_play", =>
	channels[@channel] = clear(channels[@channel] or {})
	if exists @path
		file = load_source(@path)
		if file == nil then return
		file = with file
			\setLooping(@loop)
			\setVolume(@mixer == "music" and music_volume or sound_volume)
			\play!
		channels[@channel] = {path: @path, :file, loop: @loop, mixer: @mixer}
on "channel_stop", => channels[@channel] = clear(channels[@channel] or {})

-- Maps a `setvolume`/fade target channel name to its live {path, file}
-- table -- kept in one place so "setvolume" and the fade-advancing
-- "update" loop below agree on the same lookup.
channel_table = (name) ->
	switch name
		when "music" then music
		when "sound" then sound
		when "voice" then voice
		when "ambiance" then ambiance
		when "music2" then music2
		else channels[name]

on "setvolume", =>
	chan = channel_table(@channel)
	return unless chan and next(chan)
	if @delay and @delay > 0
		volume_fades[@channel] = {from: chan.file\getVolume!, to: @level, duration: @delay, elapsed: 0}
	else
		volume_fades[@channel] = nil
		chan.file\setVolume(@level)

on "update", (dt) ->
	if next(sound) and not sound.file\isPlaying! and sound.n > 1
		sound.file\play!
		sound.n -= 1
	for name, fade in pairs(volume_fades)
		chan = channel_table(name)
		if chan and next(chan)
			fade.elapsed += dt
			t = math.min(fade.elapsed / fade.duration, 1)
			chan.file\setVolume(fade.from + (fade.to - fade.from) * t)
			if t >= 1 then volume_fades[name] = nil
		else
			volume_fades[name] = nil
