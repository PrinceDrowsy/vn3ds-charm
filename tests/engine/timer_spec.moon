-- main.moon's "delay" instruction handler (Phase 2.6's `pause`) is:
--   when "delay" then Timer.after(ins.frames/60, -> next_msg!)
-- main.moon itself is heavy to require directly in a spec (love.load side
-- effects, many submodule requires), so this verifies the actual timing
-- primitive it depends on in isolation: Timer.after doesn't fire until
-- enough time has been fed to Timer.update, confirming `delay`/`pause`
-- genuinely pauses script advancement rather than continuing immediately
-- (unlike every other instruction type, which main.moon dispatches and
-- advances past in the same frame).
Timer = require "lib/timer"

describe "Timer.after (Phase 2.6: pause/delay timing)", ->
	before_each -> Timer.clear!

	it "does not fire before the delay has elapsed", ->
		fired = false
		Timer.after(90 / 60, -> fired = true) -- delay 90 frames at 60fps = 1.5s
		Timer.update(1.0)
		assert.is_false(fired)

	it "fires once enough time has elapsed, matching frames/60 seconds", ->
		fired = false
		Timer.after(90 / 60, -> fired = true)
		Timer.update(1.0)
		Timer.update(0.6)
		assert.is_true(fired)

	it "accumulates across multiple update calls rather than needing one large step", ->
		calls = 0
		Timer.after(0.3, -> calls += 1)
		for i = 1, 10
			Timer.update(0.05) -- 10 * 0.05 = 0.5s total, well past the 0.3s delay
		assert.are.equal(calls, 1)
