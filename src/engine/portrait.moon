-- Our Life: Beginnings & Always' bespoke ChangePortrait multi-layer live
-- portrait system (converter.parser.character_sprite) -- the real engine-
-- side runtime half of it: blink/lip-flap frame-cycling, a manual cross-
-- fade dissolve on layer change, and pulsing glow/magic opacity. None of
-- these exist anywhere else in the engine (confirmed via a dedicated
-- Explore pass before this module was written) -- they're built here from
-- the same primitives images.moon's ordinary sprites already use (a
-- "<name>:<slot>" setimg slot, the same per-sprite tint_r/g/b/alpha
-- `anim` state), so drawing needs no new pass at all: every portrait
-- layer is drawn by images.moon's existing draw_foreground loop, exactly
-- like any other foreground sprite.
--
-- Layer *compositing* itself (which files, what z-order) is already fully
-- resolved at convert time (see vnds_writer.py's _emit_portrait_update) --
-- this module only ever receives already-resolved paths/flags/order, it
-- never interprets any Ren'Py construct itself.
local *

-- name:slot -> {category, frames ({f0,f1,f2} for eyes/mouth, {f0} for
-- everything else), dissolve, order_index, tint_r/g/b, speaker (mouth
-- only), blink_timer/mouth_timer (eyes/mouth only), dissolve_t (0..1,
-- nil when not mid-dissolve), glow_t/glow_dir (glow/magic only)}
layers = {}
current_speaker = nil

slot_key = (name, slot) -> name..":"..slot

-- Matches character_sprite.rpy's real timing: each blink phase (opening/
-- closing) lasts 0.1s, with a randomized 2-5s gap between blinks (its own
-- `GetRandomBlinkValue`) -- reproduced directly rather than the original's
-- own render-call-cadence-dependent frame counting, which has no fixed
-- real-world duration to match against (Ren'Py's redraw cadence for a
-- DynamicDisplayable isn't a fixed framerate).
BLINK_PHASE = 0.1
BLINK_GAP_MIN, BLINK_GAP_MAX = 2, 5
-- character_sprite.rpy's own GetRandomLipflapValue range.
MOUTH_PHASE_MIN, MOUTH_PHASE_MAX = 0.05, 0.3
-- A short, snappy cross-fade -- the original's own frame-decrement timing
-- has no fixed real-world duration to match (see this file's header
-- comment); chosen to read as a deliberate transition, not an instant cut.
DISSOLVE_DURATION = 0.25
GLOW_RATE = 0.35 -- opacity units/second, ping-ponging between 0.05 and 0.95 (character_sprite.rpy's own bounds)

rand_range = (lo, hi) -> lo + math.random! * (hi - lo)

push_sprite = (name, slot, layer, path) ->
	dispatch "setimg", {
		:path, x: 200, y: 40, slot: slot_key(name, slot)
		props: {tint_r: layer.tint_r, tint_g: layer.tint_g, tint_b: layer.tint_b, alpha: layer.alpha or 1}
	}

start_layer = (data) ->
	name, slot = data.name, data.slot
	key = slot_key(name, slot)
	existed = layers[key] != nil
	layer = {
		category: data.category, frames: data.paths or {data.path}
		dissolve: data.dissolve, order_index: data.order_index
		tint_r: data.tint_r, tint_g: data.tint_g, tint_b: data.tint_b
		speaker: data.speaker
		alpha: 1
	}
	if data.category == "eyes"
		layer.blink = data.blink
		layer.blink_timer = rand_range(BLINK_GAP_MIN, BLINK_GAP_MAX)
		layer.blink_phase = 0 -- 0 = open (frame 0), 1/2 = mid-blink frames, matches redraw_eyes_img
	if data.category == "mouth"
		layer.mouth_timer = rand_range(MOUTH_PHASE_MIN, MOUTH_PHASE_MAX)
		layer.mouth_phase = 0
	if data.category == "glow" or data.category == "magic"
		layer.glow_t = 0
		layer.glow_dir = 1
	layers[key] = layer
	if existed and data.dissolve
		layer.dissolve_t = 0
		layer.alpha = 0 -- cross-fade in from transparent
	push_sprite(name, slot, layer, layer.frames[1])

on "portrait", (data) -> start_layer(data)
on "portrait_anim", (data) -> start_layer(data)

on "speaking", (data) -> current_speaker = data.name

on "save", =>
	saved = {}
	for key, layer in pairs(layers)
		saved[key] = {
			category: layer.category, frames: layer.frames, dissolve: layer.dissolve
			order_index: layer.order_index, tint_r: layer.tint_r, tint_g: layer.tint_g, tint_b: layer.tint_b
			speaker: layer.speaker, blink: layer.blink
		}
	@portrait_layers = saved

on "restore", =>
	layers = {}
	current_speaker = nil
	for key, data in pairs(@portrait_layers or {})
		name, slot = key\match("^(.-):(.*)$")
		start_layer {:name, :slot, category: data.category, paths: data.frames, dissolve: false,
			order_index: data.order_index, tint_r: data.tint_r, tint_g: data.tint_g, tint_b: data.tint_b,
			speaker: data.speaker, blink: data.blink}

on "update", (dt) ->
	for key, layer in pairs(layers)
		name, slot = key\match("^(.-):(.*)$")
		redraw = false

		if layer.category == "eyes" and layer.blink
			layer.blink_timer -= dt
			if layer.blink_phase == 0 and layer.blink_timer <= 0
				layer.blink_phase = 1
				layer.blink_timer = BLINK_PHASE
				redraw = true
			elseif layer.blink_phase > 0 and layer.blink_timer <= 0
				layer.blink_phase += 1
				layer.blink_timer = BLINK_PHASE
				if layer.blink_phase > 3
					layer.blink_phase = 0
					layer.blink_timer = rand_range(BLINK_GAP_MIN, BLINK_GAP_MAX)
				redraw = true
			if redraw
				-- character_sprite.rpy's own cycle: closed(frame1) -> half(frame2)
				-- -> closed(frame1) -> open(frame0), each phase BLINK_PHASE long.
				frame_for_phase = {[1]: 2, [2]: 3, [3]: 2}
				idx = frame_for_phase[layer.blink_phase] or 1
				push_sprite(name, slot, layer, layer.frames[idx])

		if layer.category == "mouth"
			speaking = current_speaker != nil and current_speaker == layer.speaker
			if speaking
				layer.mouth_timer -= dt
				if layer.mouth_timer <= 0
					layer.mouth_phase = (layer.mouth_phase + 1) % 4
					layer.mouth_timer = rand_range(MOUTH_PHASE_MIN, MOUTH_PHASE_MAX)
					frame_for_phase = {[0]: 1, [1]: 2, [2]: 1, [3]: 1}
					idx = frame_for_phase[layer.mouth_phase] or 1
					push_sprite(name, slot, layer, layer.frames[idx])
			elseif layer.mouth_phase != 0
				layer.mouth_phase = 0
				push_sprite(name, slot, layer, layer.frames[1])

		if layer.category == "glow" or layer.category == "magic"
			layer.glow_t += GLOW_RATE * dt * layer.glow_dir
			if layer.glow_t >= 0.95
				layer.glow_t, layer.glow_dir = 0.95, -1
			elseif layer.glow_t <= 0.05
				layer.glow_t, layer.glow_dir = 0.05, 1
			layer.alpha = layer.glow_t
			dispatch "setimg", {
				path: layer.frames[1], x: 200, y: 40, slot: key
				props: {tint_r: layer.tint_r, tint_g: layer.tint_g, tint_b: layer.tint_b, alpha: layer.alpha}
			}

		if layer.dissolve_t != nil
			layer.dissolve_t += dt / DISSOLVE_DURATION
			layer.alpha = math.min(layer.dissolve_t, 1)
			if layer.alpha >= 1
				layer.dissolve_t = nil
			current_frame = layer.frames[1]
			if layer.category == "eyes"
				frame_for_phase = {[0]: 1, [1]: 2, [2]: 3, [3]: 2}
				current_frame = layer.frames[frame_for_phase[layer.blink_phase] or 1]
			elseif layer.category == "mouth"
				frame_for_phase = {[0]: 1, [1]: 2, [2]: 1, [3]: 1}
				current_frame = layer.frames[frame_for_phase[layer.mouth_phase] or 1]
			dispatch "setimg", {
				path: current_frame, x: 200, y: 40, slot: key
				props: {tint_r: layer.tint_r, tint_g: layer.tint_g, tint_b: layer.tint_b, alpha: layer.alpha}
			}
