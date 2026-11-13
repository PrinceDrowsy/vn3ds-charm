require "util"
pprint = require "lib/pprint"
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
		newImage: (path) -> {getDimensions: -> 400, 240}
		setColor: (...) ->
		draw: (...) ->
		getWidth: -> 400
		getHeight: -> 240
	}
	resize: (w, h) ->
}
_G.lg = love.graphics

require "images"

describe "Background/sprite save+restore (Phase 2.7)", ->
	it "round-trips background and sprite state through save/restore", ->
		dispatch "bgload", {path: "bg.png"}
		dispatch "setimg", {path: "sprite.png", x: 10, y: 20}

		saved = {}
		dispatch "save", saved
		assert.are.equal(saved.background.path, "bg.png")
		assert.are.equal(#saved.images, 1)
		assert.are.equal(saved.images[1].path, "sprite.png")
		assert.are.equal(saved.images[1].x, 10)
		assert.are.equal(saved.images[1].y, 20)

		-- simulate resuming a save: restore from the saved table, then
		-- re-save and confirm the same state comes back out
		dispatch "restore", saved
		saved2 = {}
		dispatch "save", saved2
		assert.are.equal(saved2.background.path, "bg.png")
		assert.are.equal(saved2.images[1].path, "sprite.png")

	it "restoring an empty save (fresh game) clears background and sprites", ->
		dispatch "bgload", {path: "bg.png"}
		dispatch "setimg", {path: "sprite.png", x: 0, y: 0}

		dispatch "restore", {}
		saved = {}
		dispatch "save", saved
		assert.is_nil(saved.background.path)
		assert.are.equal(#saved.images, 0)

	it "(no slot, hand-authored VNDS content) a new setimg at the same position replaces whatever sprite was already there", ->
		-- fallback path for content with no 4th setimg token (original,
		-- non-converted VNDS scripts) -- still matches by position alone.
		dispatch "restore", {}
		dispatch "setimg", {path: "chance_normal.t3x", x: 200, y: 40}
		dispatch "setimg", {path: "chance_grin.t3x", x: 200, y: 40}

		saved = {}
		dispatch "save", saved
		assert.are.equal(#saved.images, 1)
		assert.are.equal(saved.images[1].path, "chance_grin.t3x")

	it "(no slot) sprites at genuinely different positions coexist (two characters on screen)", ->
		dispatch "restore", {}
		dispatch "setimg", {path: "chance_normal.t3x", x: 100, y: 40}
		dispatch "setimg", {path: "kizaki_normal.t3x", x: 300, y: 40}

		saved = {}
		dispatch "save", saved
		assert.are.equal(#saved.images, 2)

	it "a new setimg for the same slot replaces the previous expression, even at a different filename and position", ->
		-- real hardware bug: each composite-resolved character expression
		-- (base+eyebrows+mouth+eyes, see assets/pipeline.py's
		-- resolve_composite_images) is its own distinct file, so the old
		-- exact-path-match dedup never found the previous expression to
		-- remove -- every new `show <character> <expression>` just piled
		-- another sprite on top of the last instead of replacing it.
		-- vnds_writer.py now emits the Ren'Py image tag's first word (e.g.
		-- "chance") as setimg's 4th token, so the engine can replace by
		-- *who* a sprite is, not just where it happens to sit.
		dispatch "restore", {}
		dispatch "setimg", {path: "chance_normal.t3x", x: 200, y: 40, slot: "chance"}
		dispatch "setimg", {path: "chance_grin.t3x", x: 200, y: 40, slot: "chance"}

		saved = {}
		dispatch "save", saved
		assert.are.equal(#saved.images, 1)
		assert.are.equal(saved.images[1].path, "chance_grin.t3x")

	it "a 3rd/4th character at a position an earlier different character occupies does not remove that earlier sprite", ->
		-- real hardware bug: there are only 3 canonical positions (left/
		-- center/right), so a scene with 3+ simultaneous characters can
		-- legitimately put a new character at the same position an
		-- earlier, still-visible *different* character occupies --
		-- matching by position alone incorrectly removed that earlier
		-- sprite too (confirmed on real hardware: stacking returned once a
		-- scene had 3+ characters on screen).
		dispatch "restore", {}
		dispatch "setimg", {path: "chance_normal.t3x", x: 100, y: 40, slot: "chance"}
		dispatch "setimg", {path: "kizaki_normal.t3x", x: 300, y: 40, slot: "kizaki"}
		dispatch "setimg", {path: "miko_normal.t3x", x: 100, y: 40, slot: "miko"} -- shares chance's slot position

		saved = {}
		dispatch "save", saved
		assert.are.equal(#saved.images, 3)
		paths = [img.path for img in *saved.images]
		assert.is_true(_.include(paths, "chance_normal.t3x"))
		assert.is_true(_.include(paths, "kizaki_normal.t3x"))
		assert.is_true(_.include(paths, "miko_normal.t3x"))

	it "clearslot removes every layer sharing a tag prefix, for CharacterImage's multi-layer replace", ->
		-- CharacterImage's real-time layer system (converter/parser/
		-- character_image.py) gives each layer its own distinct
		-- "<tag>:<index>" slot (so simultaneous layers don't dedup-remove
		-- *each other* via setimg's own exact-match-by-slot logic), and
		-- emits `clearslot <tag>` once before the N `setimg`s for a new
		-- attribute combination, so the character's entire previous layer
		-- set is atomically replaced rather than left stacked with stale
		-- layers.
		dispatch "restore", {}
		dispatch "setimg", {path: "afd_l_base.t3x", x: 200, y: 40, slot: "afd_l:0"}
		dispatch "setimg", {path: "afd_l_eyes.t3x", x: 200, y: 40, slot: "afd_l:1"}
		dispatch "setimg", {path: "afd_l_mouth.t3x", x: 200, y: 40, slot: "afd_l:2"}
		dispatch "setimg", {path: "kizaki_normal.t3x", x: 300, y: 40, slot: "kizaki"}

		dispatch "clearslot", {slot: "afd_l"}
		dispatch "setimg", {path: "afd_l_base2.t3x", x: 200, y: 40, slot: "afd_l:0"}
		dispatch "setimg", {path: "afd_l_eyes2.t3x", x: 200, y: 40, slot: "afd_l:1"}

		saved = {}
		dispatch "save", saved
		paths = [img.path for img in *saved.images]
		assert.are.equal(#saved.images, 3)
		assert.is_true(_.include(paths, "afd_l_base2.t3x"))
		assert.is_true(_.include(paths, "afd_l_eyes2.t3x"))
		assert.is_true(_.include(paths, "kizaki_normal.t3x")) -- a different tag, untouched
		assert.is_false(_.include(paths, "afd_l_base.t3x"))
		assert.is_false(_.include(paths, "afd_l_mouth.t3x")) -- had no replacement, must not linger

	it "clearslot does not remove an unrelated slot that merely starts with the same letters", ->
		dispatch "restore", {}
		dispatch "setimg", {path: "afd_l_base.t3x", x: 200, y: 40, slot: "afd_l:0"}
		dispatch "setimg", {path: "afd_larger_thing.t3x", x: 300, y: 40, slot: "afd_larger"}
		dispatch "clearslot", {slot: "afd_l"}
		saved = {}
		dispatch "save", saved
		paths = [img.path for img in *saved.images]
		assert.are.equal(#saved.images, 1)
		assert.is_true(_.include(paths, "afd_larger_thing.t3x"))

describe "draw_foreground sprite scale (regression)", ->
	before_each -> dispatch "restore", {} -- earlier describe blocks/tests must not leave sprites behind

	it "draws sprites at the fixed DS-baseline scale (pscale), not whatever scale the current background happens to use", ->
		-- real hardware bug: a sprite rendered at the correct position but
		-- wildly oversized/off-screen, because draw_foreground reused
		-- `scale` (derived from sx/sy, tied to whatever background image
		-- happens to be loaded) for the sprite's own drawn size, instead of
		-- `pscale` (the fixed 256x192 DS-baseline scale already used for
		-- position). A sprite's on-screen size must not depend on the
		-- unrelated background's dimensions.
		_G.px, _G.py = 1.5, 1.25 -- pscale = min(px, py) = 1.25
		_G.sx, _G.sy = 0.4, 0.4 -- scale = min(sx, sy) = 0.4 (an unrelated, much smaller background)
		_G.original_width, _G.original_height = 1000, 1000

		draw_calls = {}
		lg.draw = (...) -> table.insert(draw_calls, {...})

		dispatch "setimg", {path: "sprite.png", x: 10, y: 20}
		dispatch "draw_foreground"

		assert.are.equal(#draw_calls, 1)
		call = draw_calls[1]
		assert.are.equal(call[5], 1.25) -- sprite's own draw scale (sx)
		assert.are.equal(call[6], 1.25) -- sprite's own draw scale (sy)

	it "positions sprites independently of the background's own fit scale/size", ->
		-- real hardware bug: offsetX/offsetY shifted every sprite's
		-- position by however much the *background* happened to be
		-- letterboxed to fit the screen -- correct only when background
		-- and sprites shared one native resolution (original VNDS
		-- content), but wrong for converted content where a sprite's x/y
		-- are already absolute positions in the fixed 400x240 virtual
		-- space. A sprite at a given (x, y) must land in the same place
		-- on screen no matter what background is currently loaded.
		_G.px, _G.py = 1, 1
		_G.sx, _G.sy = 0.4, 0.4 -- an unrelated, heavily letterboxed background
		_G.original_width, _G.original_height = 1000, 1000

		draw_calls = {}
		lg.draw = (...) -> table.insert(draw_calls, {...})
		lg.newImage = (path) -> {getDimensions: -> 400, 240}

		dispatch "setimg", {path: "sprite.png", x: 200, y: 40}
		dispatch "draw_foreground"

		call = draw_calls[1]
		assert.are.equal(call[2], 200) -- x, unshifted by the background's own offset
		assert.are.equal(call[3], 40)  -- y, unshifted by the background's own offset

describe "Per-sprite color tint (VN3DS-spec.md §6, CharacterImage's lighting_night)", ->
	before_each -> dispatch "restore", {}

	it "applies the tint_r/tint_g/tint_b props from setimg to the sprite's draw color", ->
		-- vnds_writer.py's _NIGHT_TINT: `setimg ... tint_r=0.75 tint_g=0.85 tint_b=1`
		color_calls = {}
		lg.setColor = (...) -> table.insert(color_calls, {...})
		dispatch "setimg", {path: "sprite.png", x: 10, y: 20, props: {tint_r: 0.75, tint_g: 0.85, tint_b: 1}}
		dispatch "draw_foreground"
		found = false
		for call in *color_calls
			if call[1] == 0.75 and call[2] == 0.85 and call[3] == 1
				found = true
		assert.is_true(found)

	it "defaults to no tint (1,1,1) when no tint props are given", ->
		color_calls = {}
		lg.setColor = (...) -> table.insert(color_calls, {...})
		dispatch "setimg", {path: "sprite.png", x: 10, y: 20}
		dispatch "draw_foreground"
		found = false
		for call in *color_calls
			if call[1] == 1 and call[2] == 1 and call[3] == 1
				found = true
		assert.is_true(found)

	it "resolves a static yalign against the sprite's real loaded height, and applies static sx/sy/alpha", ->
		-- real (pre-transform-support) bug: a static (non-animated) yalign
		-- position was baked to a flat `yalign*240` pixel value at convert
		-- time (vnds_writer.py's `_resolve_show_xy`), ignoring the sprite's
		-- actual height entirely -- only the animated/keyframe path
		-- (resolve_yalign, exercised in anim_spec.moon) was height-aware.
		-- setimg's new trailing `yalign=`/`yanchor=`/`sx=`/`sy=`/`alpha=`
		-- tokens (vnds_writer.py's _static_prop_tokens) let a static block
		-- resolve correctly too, using the exact same formula, right here
		-- at setimg time rather than only at anim_end.
		_G.px, _G.py = 1, 1
		lg.newImage = (path) -> {getDimensions: -> 400, 625} -- a tall foreground sprite

		draw_calls = {}
		lg.draw = (...) -> table.insert(draw_calls, {...})

		dispatch "setimg", {path: "sprite.png", x: 200, y: 40, props: {yalign: 1.0, yanchor: 1.0, sx: 1.4, sy: 1.4, alpha: 0.5}}
		dispatch "draw_foreground"

		call = draw_calls[1]
		assert.are.equal(call[2], 200)  -- x untouched
		assert.are.equal(call[3], -385) -- yalign*240 - yanchor*625 == 240-625
		assert.are.equal(call[5], 1.4)  -- sx
		assert.are.equal(call[6], 1.4)  -- sy

	it "keeps yanchor independent of yalign when a transform overrides just the position", ->
		-- real content (Mice Tea transforms.rpy): `yalign 1.0 ypos 1.2` --
		-- the anchor stays 1.0, only the position fraction moves to 1.2.
		-- Collapsing both to a single fraction (the pre-transform-support
		-- model) can't represent this; the generalized (position, anchor)
		-- pair can.
		_G.px, _G.py = 1, 1
		lg.newImage = (path) -> {getDimensions: -> 400, 625}

		draw_calls = {}
		lg.draw = (...) -> table.insert(draw_calls, {...})

		dispatch "setimg", {path: "sprite.png", x: 200, y: 40, props: {yalign: 1.2, yanchor: 1.0}}
		dispatch "draw_foreground"

		call = draw_calls[1]
		assert.are.equal(call[3], -337) -- 1.2*240 - 1.0*625 == 288-625

	it "anchors sprites by horizontal center, not left edge", ->
		-- real hardware bug: a sprite rendered at the correct position and
		-- size, but its LEFT edge sat at the intended point instead of its
		-- center, so it ran off the right side of the screen instead of
		-- being centered on it. Ren'Py's own align/xalign semantics anchor
		-- by center, and images.moon's `x` values are meant to match that.
		_G.px, _G.py = 1, 1
		_G.sx, _G.sy = 1, 1
		_G.original_width, _G.original_height = 400, 240

		draw_calls = {}
		lg.draw = (...) -> table.insert(draw_calls, {...})
		lg.newImage = (path) -> {getDimensions: -> 300, 200} -- a wide sprite

		dispatch "setimg", {path: "sprite.png", x: 200, y: 0}
		dispatch "draw_foreground"

		call = draw_calls[1]
		assert.are.equal(call[7], 150) -- ox = sprite's own width/2
		assert.are.equal(call[8], 0)   -- oy = top edge (unchanged)
