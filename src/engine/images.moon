Timer = require 'lib/timer'
flux = require 'lib/flux'
anim = require 'anim'
background = {}
images = {}
alpha = value: 1
-- extended: VN3DS-spec.md §9.1 animation system state. `active_animations`
-- tracks which target names currently have an in-flight tween (so
-- "anim_wait" knows whether to block); `building_anim` accumulates
-- "anim_begin"/"keyframe" instructions until "anim_end" fires (the plain
-- VNDS script format has no nested blocks -- this mirrors how "if"/"fi"
-- already work via forward-scanning rather than real nesting);
-- `overlay_alpha` backs the `fade_out_black`/`fade_in_black` presets,
-- which animate a screen-wide overlay rather than any one sprite.
active_animations = {}
building_anim = nil
overlay_alpha = alpha: 0

on "save", =>
	@background = {path: background.path}
	@images = _.map(images, => {path: @path, x: @x, y: @y, slot: @slot})

on "restore", =>
	background = {}
	images = {}
	alpha = value: 1
	active_animations = {}
	building_anim = nil
	overlay_alpha = alpha: 0
	if get(@, "background", "path") then dispatch "bgload", @background
	if @images then for image in *@images do dispatch "setimg", image

on "bgload", =>
	-- real-hardware regression, found and removed here: this handler used
	-- to compare the *background image's own* pixel dimensions against
	-- `original_width`/`original_height` (the device/window reference
	-- resolution main.moon's love.resize maintains for sx/sy scaling) and,
	-- on any mismatch, overwrite that reference with the image's own
	-- dimensions and re-run love.resize -- confusing "what size is this
	-- piece of art" with "what size is the actual screen". Since real
	-- background art is essentially never exactly the device's native
	-- resolution, this fired on almost every bgload, corrupting sx/sy/px/py
	-- (making every subsequent sprite's setimg scale wrong -- "character
	-- sprites now appear way too big") and, via love.resize's own
	-- `text_font = font` side effect, silently reverting any per-novel
	-- custom font back to the generic default mid-story. draw_background
	-- below already scales an arbitrarily-sized image to fit the screen via
	-- `scale = math.min(sx, sy)` -- nothing here ever needed to touch the
	-- device reference resolution at all.
	background = {}
	if @path\sub(-1) == "~" then return
	if @frames ~= nil
		alpha.value = 0
		Timer.tween(@frames/60, {[alpha]: value: 1})
	background = {path: @path, img: lg.newImage(@path)}
	images = {}

on "setimg", =>
	-- extended: replace whatever sprite is currently showing for this
	-- *slot* (Ren'Py's own character/tag identity -- the image tag's
	-- first word, e.g. "chance" -- see vnds_writer.py's Show emission),
	-- not just an exact path match. Ren'Py's `show <tag> <attrs>` for an
	-- already-shown tag swaps in a new expression for that character --
	-- but each expression converts to a *different* composited file (see
	-- assets/pipeline.py's resolve_composite_images), so the old
	-- path-only match never found the previous sprite to remove (real
	-- hardware symptom: successive `show chance ...` calls all remained
	-- visible simultaneously, stacked).
	--
	-- Position alone isn't a safe stand-in for identity: there are only 3
	-- canonical slots (left/center/right), so a scene with 3+ simultaneous
	-- characters can legitimately put a new character at the same
	-- position an earlier, still-visible *different* character occupies --
	-- matching by position alone incorrectly removed that earlier sprite
	-- too (also confirmed on real hardware). `slot` is only present for
	-- converted content (vnds_writer.py always emits it); hand-authored
	-- VNDS content with no 4th token falls back to the original
	-- position-based match.
	images = _.reject(images, (img) ->
		return true if img.path == @path
		if @slot != nil and img.slot != nil
			return img.slot == @slot
		img.x == @x and img.y == @y
	)
	img = lg.newImage(@path)
	props = @props or {}
	-- extended: a static ATL block/named transform's `yalign` (ypos
	-- fraction) and `sx`/`sy`/`r`/`alpha` (vnds_writer.py's
	-- _static_prop_tokens) resolve against this sprite's *real* loaded
	-- height right here, the same generalized formula `resolve_yalign`
	-- below uses for animations -- previously only the animated path was
	-- height-aware; a static yalign position was baked to a flat
	-- `yalign*240` pixel value at convert time (see script.moon/
	-- vnds_writer.py's `_resolve_show_xy`), which put any yalign-positioned
	-- sprite at the wrong height whenever its real image was taller than
	-- the screen (foreground art is deliberately never height-capped).
	anim_y = @y
	if props.yalign
		_w, sprite_height = img\getDimensions!
		yanchor = props.yanchor or props.yalign
		anim_y = props.yalign * 240 - yanchor * sprite_height
	table.insert(images, {
		path: @path, :img, x: @x, y: @y, slot: @slot
		-- extended: VN3DS-spec.md §9.1's animation state table is a flat
		-- x/y (not a base-position-plus-offset split) -- seed it from
		-- setimg's own (possibly height-resolved) position and any static
		-- sx/sy/r/alpha so presets/keyframes can read the sprite's current
		-- resting state directly.
		-- extended: a per-sprite color tint (VN3DS-spec.md §6) -- the
		-- custom UI-asset-import system's CharacterImage counterpart:
		-- the original characterimage.rpy applies a fixed blue-ish
		-- `im.matrix.tint(.75, 0.85, 1.0)` to every layer whenever a
		-- show's "lighting_night" attribute is present (vnds_writer.py's
		-- `_NIGHT_TINT`/`_emit_character_image_show`) -- defaults to
		-- {1,1,1} (no tint) so every other sprite's color is unaffected.
		anim: {
			x: @x, y: anim_y, r: props.r or 0, sx: props.sx or 1, sy: props.sy or 1, alpha: props.alpha or 1
			tint_r: props.tint_r or 1, tint_g: props.tint_g or 1, tint_b: props.tint_b or 1
		}
	})

on "clearimg", =>
	images = _.reject(images, (img) -> img.path == @path)

-- extended: CharacterImage's real-time multi-layer sprite system
-- (VN3DS-spec.md, converter/parser/character_image.py) -- a single
-- `show <tag> <attrs>` resolves to *several* layer sprites (base/eyes/
-- mouth/...), each with its own distinct "<tag>:<layer index>" slot (e.g.
-- "afd_l:0", "afd_l:1") so they don't dedup-remove *each other* the way
-- "setimg"'s existing exact-match-by-slot logic above would if they all
-- shared one bare slot. `clearslot <tag>` removes every sprite whose slot
-- is either exactly `tag` (an ordinary, non-layered show) *or* prefixed
-- "tag:" (any of that character's layers) -- emitted once before the N
-- `setimg`s for a new attribute combination, so the character's entire
-- previous layer set is atomically replaced.
on "clearslot", =>
	prefix = @slot..":"
	images = _.reject(images, (img) ->
		return true if img.slot == @slot
		img.slot != nil and img.slot\sub(1, #prefix) == prefix
	)

on "update", (dt) -> flux.update(dt)

-- extended: a sprite's "target" name (for "anim"/"anim_wait") is its
-- basename with no folder or extension -- matching how the converter
-- already names foreground assets after the Ren'Py image tag
-- (vnds_writer.py's _resolve_image_path), so `anim eileen_happy ...` finds
-- whatever sprite is currently on screen at "foreground/eileen_happy.t3x".
sprite_target_name = (path) -> path\match("([^/\\]+)%.%w+$")
find_sprite = (target) -> _.detect(images, (img) -> sprite_target_name(img.path) == target)

finish_animation = (target) ->
	active_animations[target] = nil
	dispatch "anim_complete", {:target}

on "anim", =>
	if @preset == "fade_out_black" or @preset == "fade_in_black"
		active_animations[@target] = true
		tween = anim.presets[@preset](overlay_alpha, @duration)
		if tween then tween\oncomplete(-> finish_animation(@target))
		else finish_animation(@target)
		return
	sprite = find_sprite(@target)
	unless sprite then return finish_animation(@target)
	preset_fn = anim.presets[@preset]
	unless preset_fn then return finish_animation(@target)
	active_animations[@target] = true
	tween = preset_fn(sprite.anim, @duration)
	if tween then tween\oncomplete(-> finish_animation(@target))
	else finish_animation(@target)

on "anim_begin", =>
	building_anim = {target: @target, duration: @duration, ease: @ease, keyframes: {}}

on "keyframe", =>
	if building_anim then table.insert(building_anim.keyframes, {t: @t, props: @props})

-- Converts a keyframe's raw `yalign` fraction (0.0-1.0, Ren'Py's own
-- alignment convention -- see rpy_parser.py's `_atl_prop_to_engine`) into
-- a pixel `y` against the given sprite's *actual* loaded image height,
-- not the screen's own 240px height: a full-bleed pan image (spec's
-- vertical-pan idiom, e.g. Jisei's intro) is deliberately taller than the
-- screen so the animation has somewhere to pan *to* -- baking `yalign *
-- 240` at convert time (the previous approach) assumed the sprite was
-- always screen-height, so the pan covered only the screen's own 240px
-- instead of the image's real height, starting the image already
-- off-screen and never revealing most of it.
--
-- Generalized to an independent (position, anchor) pair -- `yalign` is the
-- *position* fraction, `yanchor` the *anchor* fraction, defaulting to
-- `yalign`'s own value when absent (every keyframe emitted today always
-- takes that default -- rpy_parser.py's animated path never emits a
-- separate yanchor -- so this is an exact no-op generalization for any
-- existing animation; only "on setimg"'s static path above ever passes a
-- distinct one). Reduces to the original formula exactly when
-- yanchor == yalign: `yalign*240 - yalign*height == yalign*(240-height)`.
resolve_yalign = (props, sprite_height) ->
	return props unless props.yalign
	resolved = {k, v for k, v in pairs(props) when k != "yalign" and k != "yanchor"}
	yanchor = props.yanchor or props.yalign
	resolved.y = props.yalign * 240 - yanchor * sprite_height
	resolved

on "anim_end", =>
	return unless building_anim
	def = building_anim
	building_anim = nil
	sprite = find_sprite(def.target)
	unless sprite then return finish_animation(def.target)
	_w, sprite_height = sprite.img\getDimensions!
	keyframes = [{t: k.t, props: resolve_yalign(k.props, sprite_height)} for k in *def.keyframes]
	active_animations[def.target] = true
	tween = anim.play_keyframes(sprite.anim, keyframes, def.duration, def.ease)
	if tween then tween\oncomplete(-> finish_animation(def.target))
	else finish_animation(def.target)

on "anim_wait", =>
	target = @target
	if not active_animations[target]
		next_msg!
	else
		handler = nil
		handler = on "anim_complete", (data) ->
			if data.target == target
				handler\remove!
				next_msg!

on "draw_background", ->
	lg.setColor(1, 1, 1, alpha.value)
	scale = math.min(sx, sy)
	if next(background)
		lg.draw(background.img,lg.getWidth!/2, lg.getHeight!/2,0, scale, scale, background.img\getWidth!/2, background.img\getHeight!/2)

on "draw_foreground", ->
	pscale = math.min(px, py)
	_.each(images, =>
		-- extended: sprites are drawn at pscale (the fixed 400x240 O3DS
		-- top-screen-baseline scale, already used for position above), not `scale` (the
		-- background's own scale, tied to whatever image happens to be
		-- loaded). The original code reused `scale` for the sprite's drawn
		-- size too, which meant a sprite's on-screen size silently changed
		-- whenever a differently-sized background loaded -- harmless for
		-- original VNDS content where every asset shared one native
		-- resolution, but wrong for converted content where backgrounds and
		-- sprites come from independently-sized source art (confirmed on
		-- real hardware: a sprite rendered correctly-positioned but
		-- comically oversized/off-screen because `scale` was 1 while the
		-- source art was full Ren'Py resolution).
		--
		-- extended: `x` is the sprite's horizontal CENTER, not its left
		-- edge (the `ox` origin argument below). The original top-left
		-- anchor only ever looked right for original VNDS content, where
		-- every "position" constant was tuned by hand against one known
		-- sprite width; Ren'Py's own `xalign`/`align` semantics anchor a
		-- sprite by its *center* at that screen fraction (real hardware
		-- symptom: a converted sprite was positioned and sized correctly,
		-- but its left edge -- not its center -- sat at the intended
		-- point, so anything wider than expected ran off the right side
		-- instead of being centered on it). Vertical anchoring stays
		-- top-edge for now -- true yalign-based vertical anchoring would
		-- need the alignment fraction itself threaded through setimg, not
		-- just a resolved pixel position; a known, documented limitation.
		--
		-- extended: VN3DS-spec.md §9.1 -- position/scale/rotation/alpha are
		-- driven by the sprite's own animation state table (x/y/r/sx/sy/
		-- alpha, seeded from setimg's position -- see "setimg" above),
		-- not the sprite's original x/y directly, so presets/keyframes can
		-- freely animate position in place. Alpha is applied per-sprite
		-- via setColor (previously foreground draws didn't set color at
		-- all, silently inheriting whatever draw_background last set).
		--
		-- extended: no offsetX/offsetY here (there used to be one, tied to
		-- the *background's* own fit scale/size) -- a sprite's x/y are
		-- already absolute positions in the fixed 400x240 virtual space
		-- (same space setimg's own x/y and pscale live in), so correcting
		-- them by "wherever the background happens to be letterboxed to"
		-- only made sense back when background and sprites always shared
		-- one native resolution (original VNDS content). For converted
		-- content, the background and every sprite are independently
		-- sized, so that offset just shifted every sprite off its
		-- intended screen position by however much the current background
		-- happened to be letterboxed (real hardware symptom: a sprite
		-- landed at the wrong, off-center spot, by an amount that changed
		-- depending on which background was loaded).
		w, _h = @img\getDimensions!
		a = @anim
		lg.setColor(a.tint_r or 1, a.tint_g or 1, a.tint_b or 1, a.alpha)
		lg.draw(@img, a.x*pscale, a.y*pscale, a.r, pscale*a.sx, pscale*a.sy, w/2, 0)
	)
	lg.setColor(1, 1, 1, 1)

on "draw_ui", ->
	if overlay_alpha.alpha > 0
		lg.setColor(0, 0, 0, overlay_alpha.alpha)
		lg.rectangle("fill", 0, 0, lg.getWidth!, lg.getHeight!)
		lg.setColor(1, 1, 1, 1)
