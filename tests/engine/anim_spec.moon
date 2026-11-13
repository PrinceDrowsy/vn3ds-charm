require "util"
event = require "event"
_G.dispatch = event.dispatch
_G.dispatch_often = event.dispatch_often
_G.on = event.on
_G.remove = event.remove
_G.register = event.register

_G.original_width, _G.original_height = 400, 240
_G.sx, _G.sy, _G.px, _G.py = 1, 1, 1, 1
_G.love = {
	graphics: {
		newImage: (path) -> {getDimensions: -> 100, 100}
		setColor: (...) ->
		draw: (...) ->
		rectangle: (...) ->
		getWidth: -> 400
		getHeight: -> 240
	}
	resize: (w, h) ->
}
_G.lg = love.graphics

next_ins_calls = 0
_G.next_msg = -> next_ins_calls += 1

require "images"

describe "Animation system (Phase 3.1/3.2, VN3DS-spec.md §9.1)", ->
	before_each ->
		dispatch "restore", {}
		next_ins_calls = 0

	it "fires a named preset animation on the matching sprite by target name", ->
		-- target names match the sprite's basename with no folder/extension
		-- (the same basename the converter already names foreground assets
		-- after the Ren'Py image tag), so a sprite loaded via a real
		-- setimg path resolves correctly.
		dispatch "setimg", {path: "novels/x/foreground/eileen_happy.t3x", x: 200, y: 40}
		dispatch "anim", {target: "eileen_happy", preset: "enter_fade", duration: 0.3}

		-- enter_fade sets alpha to 0 immediately, then tweens to 1
		draw_calls = {}
		lg.setColor = (...) -> table.insert(draw_calls, {...})
		dispatch "draw_foreground"
		-- the sprite's own setColor call (not the final full-opacity reset)
		assert.are.equal(draw_calls[1][4], 0)

		dispatch "update", 0.3 -- full duration elapsed
		draw_calls = {}
		dispatch "draw_foreground"
		assert.is_true(draw_calls[1][4] > 0.9)

	it "advances a tween at real wall-clock speed, not 2x (only one 'update' handler drives flux)", ->
		-- regression test: images.moon used to register `on "update", ->
		-- flux.update(dt)` twice, so a single dispatched frame advanced
		-- every tween by 2*dt -- invisible to the tests above, since they
		-- all dispatch "update" once with the *full* duration and only
		-- check for completion (which a doubled update still reaches).
		-- Dispatching exactly half the duration must leave the tween
		-- mid-flight, not already complete.
		dispatch "setimg", {path: "novels/x/foreground/eileen_happy.t3x", x: 200, y: 40}
		dispatch "anim", {target: "eileen_happy", preset: "enter_fade", duration: 0.4}

		dispatch "update", 0.2 -- half the duration
		draw_calls = {}
		lg.setColor = (...) -> table.insert(draw_calls, {...})
		dispatch "draw_foreground"
		assert.is_true(draw_calls[1][4] < 0.9) -- must still be mid-fade, not already ~1

	it "dispatches anim_complete and unblocks anim_wait once a preset finishes", ->
		dispatch "setimg", {path: "novels/x/foreground/eileen_happy.t3x", x: 200, y: 40}
		dispatch "anim", {target: "eileen_happy", preset: "enter_fade", duration: 0.2}

		dispatch "anim_wait", {target: "eileen_happy"}
		assert.are.equal(next_ins_calls, 0) -- still animating, must not have continued yet

		dispatch "update", 0.2 -- completes the tween
		assert.are.equal(next_ins_calls, 1) -- anim_complete unblocked it

	it "anim_wait continues immediately when the target has no in-flight animation", ->
		dispatch "setimg", {path: "novels/x/foreground/eileen_happy.t3x", x: 200, y: 40}
		dispatch "anim_wait", {target: "eileen_happy"}
		assert.are.equal(next_ins_calls, 1)

	it "an unknown/missing target's anim_wait doesn't hang forever", ->
		dispatch "anim_wait", {target: "nobody_on_screen"}
		assert.are.equal(next_ins_calls, 1)

	it "plays a custom keyframe animation across anim_begin/keyframe/anim_end", ->
		dispatch "setimg", {path: "novels/x/foreground/char_hero.t3x", x: 160, y: 40}
		dispatch "anim_begin", {target: "char_hero", duration: 1.0, ease: nil}
		dispatch "keyframe", {t: 0.0, props: {x: 80, alpha: 0}}
		dispatch "keyframe", {t: 0.5, props: {x: 160, alpha: 1}}
		dispatch "keyframe", {t: 1.0, props: {x: 160, alpha: 1}}
		dispatch "anim_end"

		draw_calls = {}
		lg.draw = (...) -> table.insert(draw_calls, {...})
		dispatch "draw_foreground"
		-- snapped to the first keyframe's x=80 immediately
		call = draw_calls[1]
		assert.are.equal(call[2], 80) -- anim.x*pscale, pscale=1 in this mock

		dispatch "update", 1.0 -- full animation duration elapsed
		draw_calls = {}
		dispatch "draw_foreground"
		assert.are.equal(draw_calls[1][2], 160)

	it "resolves a yalign keyframe against the sprite's real loaded height, not the screen's", ->
		-- real hardware bug: `yalign` used to be pre-baked to a pixel `y`
		-- at *parse* time assuming the sprite was exactly screen-height
		-- (240px) -- correct for an ordinary sprite, but wrong for a
		-- full-bleed pan image (spec's vertical-pan idiom) deliberately
		-- taller than the screen, which panned across only 240px instead
		-- of its own real height and started already off-screen. `yalign`
		-- is now resolved at animation time against whatever image is
		-- actually loaded.
		lg.newImage = (path) -> {getDimensions: -> 400, 625} -- a tall pan image, screen is 240 high
		dispatch "setimg", {path: "novels/x/foreground/01.t3x", x: 200, y: 0}
		dispatch "anim_begin", {target: "01", duration: 23, ease: nil}
		dispatch "keyframe", {t: 0.0, props: {yalign: 1.0}}
		dispatch "keyframe", {t: 1.0, props: {yalign: 0.0}}
		dispatch "anim_end"

		draw_calls = {}
		lg.draw = (...) -> table.insert(draw_calls, {...})
		dispatch "draw_foreground"
		-- yalign=1.0 -> y = 1.0 * (240 - 625) = -385 (image's bottom edge
		-- flush with the screen's bottom, showing the image's own bottom)
		assert.are.equal(draw_calls[1][3], -385)

		dispatch "update", 23
		draw_calls = {}
		dispatch "draw_foreground"
		-- yalign=0.0 -> y = 0 (image's top edge flush with the screen's top)
		assert.are.equal(draw_calls[1][3], 0)

	it "resolves a keyframe's yalign against an independently-set yanchor (generalized resolve_yalign)", ->
		-- resolve_yalign now takes an independent (position, anchor) pair
		-- rather than a single collapsed fraction -- this confirms the
		-- generalization (added to support named transforms overriding just
		-- `ypos` after a `yalign`/`yanchor` shorthand) still resolves a
		-- keyframe correctly when yanchor is given explicitly, not just
		-- defaulted from yalign (the case the test above already covers).
		lg.newImage = (path) -> {getDimensions: -> 400, 625}
		dispatch "setimg", {path: "novels/x/foreground/01.t3x", x: 200, y: 0}
		dispatch "anim_begin", {target: "01", duration: 1.0, ease: nil}
		dispatch "keyframe", {t: 0.0, props: {yalign: 1.2, yanchor: 1.0}}
		dispatch "anim_end"

		draw_calls = {}
		lg.draw = (...) -> table.insert(draw_calls, {...})
		dispatch "draw_foreground"
		-- 1.2*240 - 1.0*625 == 288-625 == -337
		assert.are.equal(draw_calls[1][3], -337)

	it "fade_out_black/fade_in_black animate a screen-wide overlay, not a sprite", ->
		dispatch "anim", {target: "screen", preset: "fade_out_black", duration: 0.2}
		rect_calls = {}
		lg.rectangle = (...) -> table.insert(rect_calls, {...})
		dispatch "update", 0.2
		dispatch "draw_ui"
		assert.are.equal(#rect_calls, 1)
