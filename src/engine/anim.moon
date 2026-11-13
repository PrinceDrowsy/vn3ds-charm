-- VN3DS-spec.md §9.1 animation system: flux-driven tween presets + custom
-- keyframe animations. Pure tween logic only -- no knowledge of sprites,
-- events, or the VNDS script format; images.moon owns sprite state and
-- calls into this module directly (a plain require, not the event bus),
-- since only images.moon has the sprite list these animations target.
flux = require 'lib/flux'
local *

-- Each preset receives the target's mutable animation state table (x, y,
-- r, sx, sy, alpha -- see images.moon's per-sprite `anim` field, seeded
-- from setimg's x/y so it already holds the sprite's resting position)
-- and the requested duration; it sets any needed "from" values immediately
-- and returns the flux tween (or tween chain) driving it, or nil for an
-- instant effect with no tween to wait on. Slide presets capture the
-- state's *current* x/y as the resting position to animate back to/from,
-- matching VN3DS-spec.md §9.1's own sprite state table (a flat x/y, not a
-- base-position-plus-offset split).
presets =
	enter_fade: (state, dur) ->
		state.alpha = 0
		flux.to(state, dur, alpha: 1)
	exit_fade: (state, dur) -> flux.to(state, dur, alpha: 0)
	enter_left: (state, dur) ->
		rest_x = state.x
		state.x, state.alpha = rest_x - 150, 0
		flux.to(state, dur, x: rest_x, alpha: 1)
	enter_right: (state, dur) ->
		rest_x = state.x
		state.x, state.alpha = rest_x + 150, 0
		flux.to(state, dur, x: rest_x, alpha: 1)
	exit_left: (state, dur) -> flux.to(state, dur, x: state.x - 150, alpha: 0)
	exit_right: (state, dur) -> flux.to(state, dur, x: state.x + 150, alpha: 0)
	enter_bottom: (state, dur) ->
		rest_y = state.y
		state.y, state.alpha = rest_y + 100, 0
		flux.to(state, dur, y: rest_y, alpha: 1)
	pulse_zoom: (state, dur) ->
		flux.to(state, dur/2, sx: 1.08, sy: 1.08)\after(state, dur/2, sx: 1.0, sy: 1.0)
	shake: (state, dur) ->
		rest_x = state.x
		cycles = 6
		seg = dur / (cycles + 1)
		t = flux.to(state, seg/2, x: rest_x + 8)
		for i = 1, cycles
			t = t\after(state, seg, x: rest_x + (i % 2 == 0 and 8 or -8))
		t\after(state, seg/2, x: rest_x)
	bounce_in: (state, dur) ->
		state.sx, state.sy = 0.01, 0.01 -- flux can't tween to/from exactly 0 usefully with some eases; close enough to invisible
		flux.to(state, dur*0.6, sx: 1.1, sy: 1.1)\ease("quadout")\after(state, dur*0.4, sx: 1.0, sy: 1.0)\ease("quadout")
	fade_out_black: (state, dur) -> flux.to(state, dur, alpha: 1)
	fade_in_black: (state, dur) -> flux.to(state, dur, alpha: 0)
	flip_h: (state, dur) ->
		state.sx = -state.sx
		nil

-- Builds a flux tween chain from a custom keyframe list (VN3DS-spec.md
-- §9.1's `anim_begin`/`keyframe`/`anim_end` form): snaps the state to the
-- first keyframe's values immediately (avoiding a visible jump if the
-- state doesn't already match), then chains a tween across each
-- consecutive pair, each running for its share of the total duration
-- (proportional to the gap between their normalised times). Returns the
-- final tween in the chain (whose oncomplete fires when the whole
-- animation finishes), or nil if there's nothing to animate.
play_keyframes = (state, keyframes, duration, ease) ->
	return nil if #keyframes == 0
	first = keyframes[1]
	for k, v in pairs(first.props) do state[k] = v
	return nil if #keyframes == 1
	tween = nil
	for i = 2, #keyframes
		prev, cur = keyframes[i - 1], keyframes[i]
		seg_dur = (cur.t - prev.t) * duration
		tween = if tween == nil then flux.to(state, seg_dur, cur.props) else tween\after(state, seg_dur, cur.props)
		tween\ease(ease) if ease
	tween

return {:presets, :play_keyframes}
