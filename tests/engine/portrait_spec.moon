require "util"
event = require "event"
_G.on = event.on
_G.remove = event.remove
_G.register = event.register

_G.love = {
	graphics: {
		newImage: (path) -> {getDimensions: -> 100, 100}
		setColor: (...) ->
		draw: (...) ->
	}
}
_G.lg = love.graphics

setimg_calls = {}
_G.dispatch = (name, data) ->
	table.insert(setimg_calls, {:name, :data}) if name == "setimg"
	event.dispatch(name, data)
_G.dispatch_often = event.dispatch_often

require "portrait"

-- character_sprite.rpy's own real 3-frame naming: frame 0 = closed/
-- neutral baseline, 1/2 = the two mid-blink/mid-flap frames.
frames = (base) -> {"#{base}0.png", "#{base}1.png", "#{base}2.png"}

describe "Portrait system (Our Life's ChangePortrait, converter.parser.character_sprite)", ->
	before_each ->
		setimg_calls = {}
		dispatch "restore", {}

	it "portrait draws a static single-frame layer immediately", ->
		dispatch "portrait", {name: "Cove_8", slot: "base", path: "base.png", category: "plain", dissolve: false, order_index: 0, tint_r: 1, tint_g: 1, tint_b: 1}
		assert.are.equal(#setimg_calls, 1)
		assert.are.equal(setimg_calls[1].data.path, "base.png")
		assert.are.equal(setimg_calls[1].data.slot, "Cove_8:base")

	it "portrait_anim draws frame0 immediately regardless of blink", ->
		dispatch "portrait_anim", {name: "Cove_8", slot: "eyes", paths: frames("closed_eyes"), category: "eyes", blink: true, dissolve: false, order_index: 3, tint_r: 1, tint_g: 1, tint_b: 1, speaker: "cove"}
		assert.are.equal(setimg_calls[1].data.path, "closed_eyes0.png")

	it "eyes blink through frames 1/2 and back to 0 on the expected schedule when blink is enabled", ->
		dispatch "portrait_anim", {name: "Cove_8", slot: "eyes", paths: frames("n_eyes"), category: "eyes", blink: true, dissolve: false, order_index: 3, tint_r: 1, tint_g: 1, tint_b: 1, speaker: nil}
		setimg_calls = {}
		-- force the randomized blink gap to elapse (max real bound is 5s)
		dispatch "update", 5.1
		assert.are.equal(setimg_calls[#setimg_calls].data.path, "n_eyes1.png")
		setimg_calls = {}
		dispatch "update", 0.1 -- one blink phase (0.1s) elapses
		assert.are.equal(setimg_calls[#setimg_calls].data.path, "n_eyes2.png")
		setimg_calls = {}
		dispatch "update", 0.1
		assert.are.equal(setimg_calls[#setimg_calls].data.path, "n_eyes1.png")
		setimg_calls = {}
		dispatch "update", 0.1
		assert.are.equal(setimg_calls[#setimg_calls].data.path, "n_eyes0.png")

	it "eyes never blink when blink is disabled", ->
		dispatch "portrait_anim", {name: "Cove_8", slot: "eyes", paths: frames("n_eyes"), category: "eyes", blink: false, dissolve: false, order_index: 3, tint_r: 1, tint_g: 1, tint_b: 1, speaker: nil}
		setimg_calls = {}
		dispatch "update", 10 -- well past any real blink gap
		assert.are.equal(#setimg_calls, 0)

	it "mouth only animates while its baked-in speaker is the current speaker", ->
		dispatch "portrait_anim", {name: "Cove_8", slot: "mouth", paths: frames("n_mouth"), category: "mouth", blink: false, dissolve: false, order_index: 2, tint_r: 1, tint_g: 1, tint_b: 1, speaker: "cove"}
		setimg_calls = {}
		dispatch "update", 0.5 -- no "speaking" dispatched yet -- must not animate
		assert.are.equal(#setimg_calls, 0)

		dispatch "speaking", {name: "cove"}
		setimg_calls = {}
		dispatch "update", 0.35 -- past MOUTH_PHASE_MAX (0.3s)
		assert.are.equal(setimg_calls[#setimg_calls].data.path, "n_mouth1.png")

	it "mouth stops animating and resets to frame0 once a different character starts speaking", ->
		dispatch "portrait_anim", {name: "Cove_8", slot: "mouth", paths: frames("n_mouth"), category: "mouth", blink: false, dissolve: false, order_index: 2, tint_r: 1, tint_g: 1, tint_b: 1, speaker: "cove"}
		dispatch "speaking", {name: "cove"}
		dispatch "update", 0.35
		dispatch "speaking", {name: "someone_else"}
		setimg_calls = {}
		dispatch "update", 0.01
		assert.are.equal(setimg_calls[#setimg_calls].data.path, "n_mouth0.png")

	it "glow/magic layers pulse opacity continuously between the two bounds", ->
		dispatch "portrait", {name: "Cove_8", slot: "eye_glow", path: "glow.png", category: "glow", dissolve: false, order_index: 10, tint_r: 1, tint_g: 1, tint_b: 1}
		setimg_calls = {}
		dispatch "update", 1.0
		first_alpha = setimg_calls[#setimg_calls].data.props.alpha
		setimg_calls = {}
		dispatch "update", 1.0
		second_alpha = setimg_calls[#setimg_calls].data.props.alpha
		assert.is_true(first_alpha ~= second_alpha)
		assert.is_true(first_alpha >= 0.05 and first_alpha <= 0.95)

	it "a dissolve cross-fades a replaced layer's alpha from 0 to 1 over the fixed duration", ->
		dispatch "portrait", {name: "Cove_8", slot: "base", path: "a.png", category: "plain", dissolve: false, order_index: 0, tint_r: 1, tint_g: 1, tint_b: 1}
		dispatch "portrait", {name: "Cove_8", slot: "base", path: "b.png", category: "plain", dissolve: true, order_index: 0, tint_r: 1, tint_g: 1, tint_b: 1}
		assert.are.equal(setimg_calls[#setimg_calls].data.props.alpha, 0)
		setimg_calls = {}
		dispatch "update", 0.125 -- half of the 0.25s dissolve
		assert.are.near(setimg_calls[#setimg_calls].data.props.alpha, 0.5, 0.05)
		setimg_calls = {}
		dispatch "update", 0.2 -- past the full duration
		assert.are.equal(setimg_calls[#setimg_calls].data.props.alpha, 1)

	it "a non-dissolve replacement pops to full opacity immediately", ->
		dispatch "portrait", {name: "Cove_8", slot: "base", path: "a.png", category: "plain", dissolve: false, order_index: 0, tint_r: 1, tint_g: 1, tint_b: 1}
		dispatch "portrait", {name: "Cove_8", slot: "base", path: "b.png", category: "plain", dissolve: false, order_index: 0, tint_r: 1, tint_g: 1, tint_b: 1}
		assert.are.equal(setimg_calls[#setimg_calls].data.props.alpha, 1)

	it "portrait layers survive save/restore with their category/frames/flags intact", ->
		dispatch "portrait_anim", {name: "Cove_8", slot: "eyes", paths: frames("n_eyes"), category: "eyes", blink: true, dissolve: false, order_index: 3, tint_r: 1, tint_g: 1, tint_b: 1, speaker: "cove"}
		saved = {}
		dispatch "save", saved
		dispatch "restore", saved
		setimg_calls = {}
		dispatch "update", 5.1 -- should still blink after restore
		assert.are.equal(setimg_calls[#setimg_calls].data.path, "n_eyes1.png")
