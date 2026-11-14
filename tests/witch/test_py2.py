"""Python 2 trees, in the JSON form harvest.rpy writes, to Python 3 source."""
import pytest

from witch.python.py2 import ConversionError, to_source

L = {"_": "Load"}
S = {"_": "Store"}


def name(id_, ctx=L):
    return {"_": "Name", "id": id_, "ctx": ctx}


def num(n):
    return {"_": "Num", "n": n}


def string(s):
    return {"_": "Str", "s": s}


def call(func, *args, starargs=None, kwargs=None, keywords=()):
    return {"_": "Call", "func": func, "args": list(args), "keywords": list(keywords), "starargs": starargs,
            "kwargs": kwargs}


def expr(e):
    return {"_": "Expr", "value": e}


def binop(left, op, right):
    return {"_": "BinOp", "left": left, "op": {"_": op}, "right": right}


def args(*names, vararg=None, kwarg=None, defaults=()):
    return {"args": list(names), "vararg": vararg, "kwarg": kwarg, "defaults": list(defaults)}


def run(source, **env):
    """Runs converted source with stand-ins for the shim's division helpers."""
    def div(a, b):
        return a // b if isinstance(a, int) and isinstance(b, int) else a / b

    def div_attr(obj, attr, b):
        setattr(obj, attr, div(getattr(obj, attr), b))

    def div_item(obj, key, b):
        obj[key] = div(obj[key], b)

    scope = {"__py2_div__": div, "__py2_div_attr__": div_attr, "__py2_div_item__": div_item, **env}
    exec(compile(source, "<test>", "exec"), scope)
    return scope


def test_integer_division_floors_unless_the_snippet_imports_division():
    stmt = {"_": "Assign", "targets": [name("x", S)], "value": binop(num(7), "Div", num(2))}
    assert run(to_source([stmt], "exec"))["x"] == 3
    future = {"_": "ImportFrom", "module": "__future__", "names": [{"name": "division", "asname": None}],
              "level": 0}
    assert run(to_source([future, stmt], "exec"))["x"] == 3.5
    assert to_source(binop(num(7.0), "Div", num(2)), "eval") == "__py2_div__(7.0, 2)"


def test_augmented_division_evaluates_its_target_once():
    tree = [
        {"_": "AugAssign", "target": name("n", S), "op": {"_": "Div"}, "value": num(2)},
        {"_": "AugAssign", "target": {"_": "Subscript", "value": call(name("pick")),
                                      "slice": {"_": "Index", "value": num(0)}, "ctx": S},
         "op": {"_": "Div"}, "value": num(2)},
        {"_": "AugAssign", "target": {"_": "Attribute", "value": name("o"), "attr": "v", "ctx": S},
         "op": {"_": "Div"}, "value": num(4)},
    ]
    picks = []
    box = [9]

    class O:
        v = 10

    def pick():
        picks.append(1)
        return box

    scope = run(to_source(tree, "exec"), n=7, pick=pick, o=O)
    assert (scope["n"], box, O.v, len(picks)) == (3, [4], 2, 1)


def test_print_and_exec_statements():
    tree = [
        {"_": "Print", "dest": None, "values": [string("a"), num(1)], "nl": True},
        {"_": "Print", "dest": name("out"), "values": [string("b")], "nl": False},
        {"_": "Exec", "body": string("y = 2"), "globals": None, "locals": None},
    ]
    src = to_source(tree, "exec")
    assert src.splitlines() == ["print('a', 1)", "print('b', file=out, end=' ')", "exec('y = 2')"]


def test_raise_and_except_forms():
    tree = [{"_": "TryFinally", "finalbody": [expr(call(name("done")))], "body": [{
        "_": "TryExcept", "orelse": [],
        "body": [{"_": "Raise", "type": name("ValueError"), "inst": {"_": "Tuple", "elts": [string("m"), num(3)],
                                                                     "ctx": L}, "tback": None}],
        "handlers": [{"_": "ExceptHandler", "type": name("ValueError"),
                      "name": {"_": "Tuple", "elts": [name("a", S), name("b", S)], "ctx": S},
                      "body": [{"_": "Pass"}]}],
    }]}]
    src = to_source(tree, "exec")
    assert "raise ValueError('m', 3)" in src and "finally:" in src
    done = []
    scope = run(src, done=lambda: done.append(1))
    assert done == [1] and (scope["a"], scope["b"]) == ("m", 3)


def test_tuple_parameters_are_unpacked_in_the_body():
    tree = [{"_": "FunctionDef", "name": "f", "decorator_list": [],
             "args": args(name("k", {"_": "Param"}), {"_": "Tuple", "elts": [name("x", S), name("y", S)],
                                                       "ctx": S}),
             "body": [{"_": "Return", "value": binop(name("x"), "Add", name("y"))}]}]
    assert run(to_source(tree, "exec"))["f"](0, (2, 3)) == 5


def test_literals_names_slices_and_calls():
    assert to_source(string({"bytes": "636166c3a9"}), "eval") == "'café'"
    assert to_source(num({"int": "123456789012345678901234567890"}), "eval") == "123456789012345678901234567890"
    assert to_source({"_": "Repr", "value": name("x")}, "eval") == "repr(x)"
    assert to_source(name("None"), "eval") == "None"
    ext = {"_": "Subscript", "value": name("a"), "ctx": L, "slice": {"_": "ExtSlice", "dims": [
        {"_": "Slice", "lower": num(1), "upper": None, "step": None}, {"_": "Index", "value": num(2)}]}}
    assert to_source(ext, "eval") == "a[1:, 2]"
    star = call(name("f"), num(1), starargs=name("rest"), kwargs=name("kw"),
                keywords=[{"arg": "k", "value": num(2)}])
    assert to_source(star, "eval") == "f(1, *rest, k=2, **kw)"


def test_unknown_node_is_reported():
    with pytest.raises(ConversionError, match="Backquote"):
        to_source({"_": "Backquote"}, "eval")
