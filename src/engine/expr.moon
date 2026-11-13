-- A tiny, safe expression evaluator (VN3DS-spec.md §6.1): int/bool/string
-- literals, `+ - * /`, `== != < <= > >=`, `and or not`, parenthesised
-- grouping, and bare variable lookups against a caller-provided scope
-- table. Deliberately not a general-purpose language: no function calls,
-- no attribute/subscript access. Any unrecognized syntax (or a type error,
-- e.g. `"a" + 1`) makes `evaluate` return nil rather than raise, so callers
-- can fail safely (matching the rest of the engine's graceful-degradation
-- philosophy) instead of crashing on malformed input.
local *

_tokenize = (text) ->
	tokens = {}
	pos = 1
	len = #text
	while pos <= len
		c = text\sub(pos, pos)
		if c\match("%s")
			pos += 1
			continue
		two = text\sub(pos, pos + 1)
		if two == "==" or two == "!=" or two == ">=" or two == "<="
			table.insert(tokens, two)
			pos += 2
			continue
		if c == '"'
			e = text\find('"', pos + 1, true)
			if e == nil then return nil
			table.insert(tokens, text\sub(pos, e))
			pos = e + 1
			continue
		if c\match("[%(%)%+%-%*/<>]")
			table.insert(tokens, c)
			pos += 1
			continue
		s = pos
		while pos <= len and text\sub(pos, pos)\match("[%w_%.]")
			pos += 1
		if pos == s then return nil -- unrecognized character
		table.insert(tokens, text\sub(s, pos - 1))
	return tokens

-- Recursive-descent, precedence climbing from lowest to highest:
--   or_expr -> and_expr -> not_expr -> compare_expr -> add_expr -> mul_expr -> atom
evaluate = (text, scope = {}) ->
	tokens = _tokenize(text)
	return nil if tokens == nil or #tokens == 0
	pos = 1
	peek = -> tokens[pos]
	advance = ->
		v = tokens[pos]
		pos += 1
		v

	atom, mul_expr, add_expr, compare_expr, not_expr, and_expr, or_expr = nil, nil, nil, nil, nil, nil, nil

	atom = ->
		tok = peek!
		return nil if tok == nil
		if tok == "("
			advance!
			v = or_expr!
			return nil if v == nil or peek! != ")"
			advance!
			return v
		if tok == "-"
			advance!
			v = atom!
			return nil if type(v) != "number"
			return -v
		advance!
		if tok\sub(1, 1) == '"'
			return tok\sub(2, -2)
		return true if tok == "True"
		return false if tok == "False"
		n = tonumber(tok)
		return n if n != nil
		return scope[tok] -- bare variable reference; nil if undefined

	mul_expr = ->
		v = atom!
		return nil if v == nil
		while peek! == "*" or peek! == "/"
			op = advance!
			rhs = atom!
			return nil if type(v) != "number" or type(rhs) != "number"
			v = if op == "*" then v * rhs else v / rhs
		return v

	add_expr = ->
		v = mul_expr!
		return nil if v == nil
		while peek! == "+" or peek! == "-"
			op = advance!
			rhs = mul_expr!
			return nil if rhs == nil
			if op == "+"
				if type(v) == "string" or type(rhs) == "string"
					v = tostring(v)..tostring(rhs)
				else
					return nil if type(v) != "number" or type(rhs) != "number"
					v += rhs
			else
				return nil if type(v) != "number" or type(rhs) != "number"
				v -= rhs
		return v

	compare_expr = ->
		v = add_expr!
		return nil if v == nil
		op = peek!
		if op == "==" or op == "!=" or op == ">=" or op == "<=" or op == "<" or op == ">"
			advance!
			rhs = add_expr!
			return nil if rhs == nil
			ok, result = pcall(-> switch op
				when "==" then v == rhs
				when "!=" then v != rhs
				when ">=" then v >= rhs
				when "<=" then v <= rhs
				when "<" then v < rhs
				when ">" then v > rhs)
			return nil if not ok
			return result
		return v

	not_expr = ->
		if peek! == "not"
			advance!
			v = not_expr!
			return nil if v == nil
			return not v
		return compare_expr!

	and_expr = ->
		v = not_expr!
		return nil if v == nil
		while peek! == "and"
			advance!
			rhs = not_expr!
			return nil if rhs == nil
			v = v and rhs
		return v

	or_expr = ->
		v = and_expr!
		return nil if v == nil
		while peek! == "or"
			advance!
			rhs = and_expr!
			return nil if rhs == nil
			v = v or rhs
		return v

	result = or_expr!
	return nil if pos <= #tokens -- leftover tokens: malformed expression
	return result

{:evaluate}
