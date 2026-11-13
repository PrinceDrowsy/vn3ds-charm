expr = require "expr"

describe "Expression evaluator (Phase 2.4)", ->
	it "evaluates int/bool/string literals", ->
		assert.are.equal(expr.evaluate("5"), 5)
		assert.is_true(expr.evaluate("True"))
		assert.is_false(expr.evaluate("False"))
		assert.are.equal(expr.evaluate('"hello"'), "hello")

	it "looks up bare variables from the scope", ->
		assert.are.equal(expr.evaluate("affection", {affection: 3}), 3)

	it "evaluates arithmetic, including across two different variables", ->
		assert.are.equal(expr.evaluate("affection + 1", {affection: 3}), 4)
		assert.are.equal(expr.evaluate("shield + 5", {shield: 10}), 15)
		assert.are.equal(expr.evaluate("(1 + 2) * 3"), 9)
		assert.are.equal(expr.evaluate("10 / 2 - 1"), 4)

	it "concatenates strings with +", ->
		assert.are.equal(expr.evaluate('"a" + "b"'), "ab")

	it "evaluates comparisons", ->
		assert.is_true(expr.evaluate("affection >= 3", {affection: 3}))
		assert.is_false(expr.evaluate("affection >= 3", {affection: 2}))
		assert.is_true(expr.evaluate("book == True", {book: true}))

	it "evaluates and/or/not with correct precedence", ->
		assert.is_false(expr.evaluate("a and b", {a: true, b: false}))
		assert.is_true(expr.evaluate("a or b", {a: false, b: true}))
		assert.is_false(expr.evaluate("not book", {book: true}))
		assert.is_true(expr.evaluate("a == b and c", {a: 1, b: 1, c: true}))

	it "returns nil for undefined variables rather than erroring", ->
		assert.is_nil(expr.evaluate("undefined_var"))

	it "returns nil for malformed or unsupported syntax rather than erroring", ->
		assert.is_nil(expr.evaluate("1 +"))
		assert.is_nil(expr.evaluate("func_call()"))
		assert.is_nil(expr.evaluate("a.attr", {a: {}}))

	it "returns nil rather than erroring on a type-mismatched comparison", ->
		assert.is_nil(expr.evaluate('"a" < 1'))
