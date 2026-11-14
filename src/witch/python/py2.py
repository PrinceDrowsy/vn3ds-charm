"""Python 2 syntax trees, as harvest.rpy writes them, to Python 3 source.

Python 2's own parser (inside the game's Ren'Py) did the parsing, so every
Python 2 form is already understood exactly; this maps its tree onto Python
3's and keeps Python 2's meaning where the two languages differ:

- `/` on two ints floors in Python 2 (no game Ren'Py compiles with the
  `division` future), so it becomes __py2_div__(a, b); augmented forms go
  through helpers that evaluate the target once, as Python does.
- Byte-string literals (no `unicode_literals`) become text, as games use them.
- print/exec statements, `raise E, msg`, `except E, e`, tuple parameters and
  backticks become their Python 3 spellings.

The __py2_*__ helpers are part of the shim's contract (REWORK-PLAN §6).
"""
from __future__ import annotations

import ast

PY2_DIV = "__py2_div__"  # a / b
PY2_DIV_ATTR = "__py2_div_attr__"  # obj.name /= b  ->  helper(obj, "name", b)
PY2_DIV_ITEM = "__py2_div_item__"  # obj[key] /= b  ->  helper(obj, key, b)
PY2_METHOD = "__py2_method__"  # obj.iteritems()  ->  helper(obj, "iteritems")

_PY2_DICT_METHODS = {"iteritems", "iterkeys", "itervalues", "has_key"}

_SIMPLE = {
    # Operators and contexts carry no fields and keep their names, except
    # Python 2's augmented/parameter contexts.
    "Load": ast.Load, "Store": ast.Store, "Del": ast.Del, "AugLoad": ast.Load, "AugStore": ast.Store,
    "Param": ast.Load,
    "Add": ast.Add, "Sub": ast.Sub, "Mult": ast.Mult, "Div": ast.Div, "Mod": ast.Mod, "Pow": ast.Pow,
    "LShift": ast.LShift, "RShift": ast.RShift, "BitOr": ast.BitOr, "BitXor": ast.BitXor,
    "BitAnd": ast.BitAnd, "FloorDiv": ast.FloorDiv, "And": ast.And, "Or": ast.Or, "Invert": ast.Invert,
    "Not": ast.Not, "UAdd": ast.UAdd, "USub": ast.USub, "Eq": ast.Eq, "NotEq": ast.NotEq, "Lt": ast.Lt,
    "LtE": ast.LtE, "Gt": ast.Gt, "GtE": ast.GtE, "Is": ast.Is, "IsNot": ast.IsNot, "In": ast.In,
    "NotIn": ast.NotIn,
}


# Standard modules Python 3 renamed (as 2to3's `imports` fixer does).
_RENAMED_MODULES = {
    "__builtin__": "builtins", "cPickle": "pickle", "cStringIO": "io", "StringIO": "io", "Queue": "queue",
    "ConfigParser": "configparser", "urlparse": "urllib.parse", "urllib2": "urllib.request", "copy_reg": "copyreg",
    "repr": "reprlib", "httplib": "http.client", "HTMLParser": "html.parser", "htmlentitydefs": "html.entities",
    "thread": "_thread", "SocketServer": "socketserver",
}


class ConversionError(Exception):
    pass


def to_source(tree, mode: str) -> str:
    """Python 3 source for a harvested Python 2 tree: a list of statements
    for "exec"/"hide", an expression for "eval"."""
    converter = _Converter(tree, mode)
    if mode == "eval":
        return ast.unparse(ast.fix_missing_locations(ast.Expression(converter.expr(tree))))
    module = ast.Module(body=converter.block(tree), type_ignores=[])
    return ast.unparse(ast.fix_missing_locations(module))


def _name(id_: str) -> ast.Name:
    return ast.Name(id=id_, ctx=ast.Load())


def _call(func: str, *args: ast.expr) -> ast.Call:
    return ast.Call(func=_name(func), args=list(args), keywords=[])


def _text(value) -> str:
    if isinstance(value, dict) and "bytes" in value:
        raw = bytes.fromhex(value["bytes"])
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("latin-1")
    return value


def _number(value):
    if isinstance(value, dict):
        if "int" in value:
            return int(value["int"])
        if "float" in value:
            return float(value["float"])
        if "complex" in value:
            return complex(value["complex"])
    return value


class _Converter:
    def __init__(self, tree, mode: str):
        self.true_division = mode != "eval" and _imports_division(tree)
        self.temps = 0

    def temp(self) -> str:
        self.temps += 1
        return f"__py2_tmp{self.temps}__"

    def block(self, nodes) -> list[ast.stmt]:
        out = []
        for node in nodes or []:
            converted = self.stmt(node)
            out.extend(converted if isinstance(converted, list) else [converted])
        return out or [ast.Pass()]

    def stmt(self, n):
        kind = n["_"]
        method = getattr(self, "stmt_" + kind, None)
        if method is None:
            raise ConversionError(f"no conversion for statement {kind}")
        return method(n)

    def expr(self, n):
        if n is None:
            return None
        kind = n["_"]
        method = getattr(self, "expr_" + kind, None)
        if method is None:
            raise ConversionError(f"no conversion for expression {kind}")
        return method(n)

    def exprs(self, nodes) -> list[ast.expr]:
        return [self.expr(n) for n in nodes or []]

    def simple(self, n):
        return _SIMPLE[n["_"]]()

    # Statements.

    def stmt_FunctionDef(self, n):
        args, unpack = self.arguments(n["args"])
        return ast.FunctionDef(name=n["name"], args=args, body=unpack + self.block(n["body"]),
                               decorator_list=self.exprs(n["decorator_list"]), returns=None, type_params=[])

    def stmt_ClassDef(self, n):
        return ast.ClassDef(name=n["name"], bases=self.exprs(n["bases"]), keywords=[], body=self.block(n["body"]),
                            decorator_list=self.exprs(n.get("decorator_list")), type_params=[])

    def stmt_Return(self, n):
        return ast.Return(value=self.expr(n["value"]))

    def stmt_Delete(self, n):
        return ast.Delete(targets=self.exprs(n["targets"]))

    def stmt_Assign(self, n):
        return ast.Assign(targets=self.exprs(n["targets"]), value=self.expr(n["value"]))

    def stmt_AugAssign(self, n):
        if n["op"]["_"] != "Div" or self.true_division:
            return ast.AugAssign(target=self.expr(n["target"]), op=self.simple(n["op"]), value=self.expr(n["value"]))
        target, value = n["target"], self.expr(n["value"])
        if target["_"] == "Name":
            return ast.Assign(targets=[self.expr(target)],
                              value=_call(PY2_DIV, ast.Name(id=target["id"], ctx=ast.Load()), value))
        if target["_"] == "Attribute":
            return ast.Expr(_call(PY2_DIV_ATTR, self.expr(target["value"]), ast.Constant(target["attr"]), value))
        if target["_"] == "Subscript":
            return ast.Expr(_call(PY2_DIV_ITEM, self.expr(target["value"]), self.slice(target["slice"]), value))
        raise ConversionError(f"/= on a {target['_']}")

    def stmt_Print(self, n):
        keywords = []
        if n["dest"] is not None:
            keywords.append(ast.keyword(arg="file", value=self.expr(n["dest"])))
        if not n["nl"]:
            keywords.append(ast.keyword(arg="end", value=ast.Constant(" ")))
        return ast.Expr(ast.Call(func=_name("print"), args=self.exprs(n["values"]), keywords=keywords))

    def stmt_For(self, n):
        return ast.For(target=self.expr(n["target"]), iter=self.expr(n["iter"]), body=self.block(n["body"]),
                       orelse=self.block(n["orelse"]) if n["orelse"] else [])

    def stmt_While(self, n):
        return ast.While(test=self.expr(n["test"]), body=self.block(n["body"]),
                         orelse=self.block(n["orelse"]) if n["orelse"] else [])

    def stmt_If(self, n):
        return ast.If(test=self.expr(n["test"]), body=self.block(n["body"]),
                      orelse=self.block(n["orelse"]) if n["orelse"] else [])

    def stmt_With(self, n):
        item = ast.withitem(context_expr=self.expr(n["context_expr"]), optional_vars=self.expr(n["optional_vars"]))
        return ast.With(items=[item], body=self.block(n["body"]))

    def stmt_Raise(self, n):
        exc = self.expr(n["type"])
        if n["inst"] is not None:
            inst = n["inst"]
            # `raise E, (a, b)` passes the tuple's items as the arguments.
            args = self.exprs(inst["elts"]) if inst["_"] == "Tuple" else [self.expr(inst)]
            exc = ast.Call(func=exc, args=args, keywords=[])
        return ast.Raise(exc=exc, cause=None)

    def stmt_TryExcept(self, n):
        return ast.Try(body=self.block(n["body"]), handlers=[self.handler(h) for h in n["handlers"]],
                       orelse=self.block(n["orelse"]) if n["orelse"] else [], finalbody=[])

    def stmt_TryFinally(self, n):
        body = n["body"]
        if len(body) == 1 and body[0]["_"] == "TryExcept":
            inner = self.stmt_TryExcept(body[0])
            inner.finalbody = self.block(n["finalbody"])
            return inner
        return ast.Try(body=self.block(body), handlers=[], orelse=[], finalbody=self.block(n["finalbody"]))

    def handler(self, h):
        body = self.block(h["body"])
        name = None
        if h["name"] is not None:
            if h["name"]["_"] == "Name":
                name = h["name"]["id"]
            else:
                # `except E, (a, b):` unpacks the exception, which in Python 2
                # is a sequence of its args.
                name = self.temp()
                args = ast.Attribute(value=_name(name), attr="args", ctx=ast.Load())
                body.insert(0, ast.Assign(targets=[self.expr(h["name"])], value=args))
        return ast.ExceptHandler(type=self.expr(h["type"]), name=name, body=body)

    def stmt_Assert(self, n):
        return ast.Assert(test=self.expr(n["test"]), msg=self.expr(n["msg"]))

    def stmt_Import(self, n):
        names = []
        for a in n["names"]:
            new = _RENAMED_MODULES.get(a["name"])
            # Keep the Python 2 name bound, so the code that uses it still works.
            names.append(ast.alias(name=new, asname=a["asname"] or a["name"]) if new
                         else ast.alias(name=a["name"], asname=a["asname"]))
        return ast.Import(names=names)

    def stmt_ImportFrom(self, n):
        if n["module"] == "__future__":
            return []  # already applied by the conversion
        module = _RENAMED_MODULES.get(n["module"], n["module"])
        return ast.ImportFrom(module=module, names=[ast.alias(name=a["name"], asname=a["asname"])
                                                    for a in n["names"]], level=n["level"] or 0)

    def stmt_Exec(self, n):
        args = [self.expr(n["body"])]
        if n["globals"] is not None:
            args.append(self.expr(n["globals"]))
            if n["locals"] is not None:
                args.append(self.expr(n["locals"]))
        return ast.Expr(ast.Call(func=_name("exec"), args=args, keywords=[]))

    def stmt_Global(self, n):
        return ast.Global(names=list(n["names"]))

    def stmt_Expr(self, n):
        return ast.Expr(value=self.expr(n["value"]))

    def stmt_Pass(self, n):
        return ast.Pass()

    def stmt_Break(self, n):
        return ast.Break()

    def stmt_Continue(self, n):
        return ast.Continue()

    # Function parameters. Python 2 allows tuple parameters, `def f((a, b))`,
    # which Python 3 doesn't: they become a plain parameter unpacked first.

    def arguments(self, a) -> tuple[ast.arguments, list[ast.stmt]]:
        unpack = []
        args = []
        for target in a["args"]:
            if target["_"] == "Name":
                args.append(ast.arg(arg=target["id"]))
            else:
                name = self.temp()
                args.append(ast.arg(arg=name))
                unpack.append(ast.Assign(targets=[self.expr(target)], value=_name(name)))
        arguments = ast.arguments(
            posonlyargs=[], args=args, kwonlyargs=[], kw_defaults=[], defaults=self.exprs(a["defaults"]),
            vararg=ast.arg(arg=a["vararg"]) if a["vararg"] else None,
            kwarg=ast.arg(arg=a["kwarg"]) if a["kwarg"] else None)
        return arguments, unpack

    # Expressions.

    def expr_BoolOp(self, n):
        return ast.BoolOp(op=self.simple(n["op"]), values=self.exprs(n["values"]))

    def expr_BinOp(self, n):
        left, right = self.expr(n["left"]), self.expr(n["right"])
        if n["op"]["_"] == "Div" and not self.true_division:
            return _call(PY2_DIV, left, right)
        return ast.BinOp(left=left, op=self.simple(n["op"]), right=right)

    def expr_UnaryOp(self, n):
        return ast.UnaryOp(op=self.simple(n["op"]), operand=self.expr(n["operand"]))

    def expr_Lambda(self, n):
        args, unpack = self.arguments(n["args"])
        if unpack:
            raise ConversionError("a lambda with a tuple parameter")
        return ast.Lambda(args=args, body=self.expr(n["body"]))

    def expr_IfExp(self, n):
        return ast.IfExp(test=self.expr(n["test"]), body=self.expr(n["body"]), orelse=self.expr(n["orelse"]))

    def expr_Dict(self, n):
        return ast.Dict(keys=self.exprs(n["keys"]), values=self.exprs(n["values"]))

    def expr_Set(self, n):
        return ast.Set(elts=self.exprs(n["elts"]))

    def comprehensions(self, gens):
        return [ast.comprehension(target=self.expr(g["target"]), iter=self.expr(g["iter"]), ifs=self.exprs(g["ifs"]),
                                  is_async=0) for g in gens]

    def expr_ListComp(self, n):
        return ast.ListComp(elt=self.expr(n["elt"]), generators=self.comprehensions(n["generators"]))

    def expr_SetComp(self, n):
        return ast.SetComp(elt=self.expr(n["elt"]), generators=self.comprehensions(n["generators"]))

    def expr_DictComp(self, n):
        return ast.DictComp(key=self.expr(n["key"]), value=self.expr(n["value"]),
                            generators=self.comprehensions(n["generators"]))

    def expr_GeneratorExp(self, n):
        return ast.GeneratorExp(elt=self.expr(n["elt"]), generators=self.comprehensions(n["generators"]))

    def expr_Yield(self, n):
        return ast.Yield(value=self.expr(n["value"]))

    def expr_Compare(self, n):
        return ast.Compare(left=self.expr(n["left"]), ops=[self.simple(o) for o in n["ops"]],
                           comparators=self.exprs(n["comparators"]))

    def expr_Call(self, n):
        func = n["func"]
        if func["_"] == "Attribute" and func["attr"] in _PY2_DICT_METHODS:
            # The object's own method if it has one, else Python 2's dict
            # behaviour: Ren'Py's own modules call these on plain dicts.
            return _call(PY2_METHOD, self.expr(func["value"]), ast.Constant(func["attr"]), *self.exprs(n["args"]))
        if (func["_"] == "Attribute" and func["attr"] == "__new__" and func["value"].get("_") == "Name"
                and func["value"]["id"] == "object" and len(n["args"]) > 1):
            # Python 2's object.__new__ ignores extra arguments when the class
            # has its own __init__; Python 3's refuses them.
            return ast.Call(func=self.expr(func), args=[self.expr(n["args"][0])], keywords=[])
        args = self.exprs(n["args"])
        keywords = [ast.keyword(arg=k["arg"], value=self.expr(k["value"])) for k in n["keywords"]]
        if n.get("starargs") is not None:
            args.append(ast.Starred(value=self.expr(n["starargs"]), ctx=ast.Load()))
        if n.get("kwargs") is not None:
            keywords.append(ast.keyword(arg=None, value=self.expr(n["kwargs"])))
        return ast.Call(func=self.expr(n["func"]), args=args, keywords=keywords)

    def expr_Repr(self, n):
        return _call("repr", self.expr(n["value"]))

    def expr_Num(self, n):
        return ast.Constant(value=_number(n["n"]))

    def expr_Str(self, n):
        return ast.Constant(value=_text(n["s"]))

    def expr_Attribute(self, n):
        return ast.Attribute(value=self.expr(n["value"]), attr=n["attr"], ctx=self.simple(n["ctx"]))

    def expr_Subscript(self, n):
        return ast.Subscript(value=self.expr(n["value"]), slice=self.slice(n["slice"]), ctx=self.simple(n["ctx"]))

    def expr_Name(self, n):
        if n["id"] in ("True", "False", "None"):
            return ast.Constant(value={"True": True, "False": False, "None": None}[n["id"]])
        return ast.Name(id=n["id"], ctx=self.simple(n["ctx"]))

    def expr_List(self, n):
        return ast.List(elts=self.exprs(n["elts"]), ctx=self.simple(n["ctx"]))

    def expr_Tuple(self, n):
        return ast.Tuple(elts=self.exprs(n["elts"]), ctx=self.simple(n["ctx"]))

    def slice(self, s):
        kind = s["_"]
        if kind == "Index":
            return self.expr(s["value"])
        if kind == "Slice":
            return ast.Slice(lower=self.expr(s["lower"]), upper=self.expr(s["upper"]), step=self.expr(s["step"]))
        if kind == "ExtSlice":
            return ast.Tuple(elts=[self.slice(d) for d in s["dims"]], ctx=ast.Load())
        if kind == "Ellipsis":
            return ast.Constant(value=Ellipsis)
        raise ConversionError(f"no conversion for slice {kind}")


def _imports_division(tree) -> bool:
    """Whether a statement list starts with `from __future__ import division`."""
    for n in tree or []:
        if n.get("_") == "ImportFrom" and n.get("module") == "__future__":
            if any(a["name"] == "division" for a in n["names"]):
                return True
        elif not (n.get("_") == "Expr" and n["value"].get("_") == "Str"):  # a docstring may come first
            break
    return False
