# Witch's Ren'Py harvester (REWORK-PLAN §5). Copied into a scratch copy of a
# game; when the game's own Ren'Py starts with WITCH_HARVEST_OUT set, it
# harvests at the end of init and exits. Runs on Ren'Py 6.15-8.x, so it must
# stay valid Python 2 and Python 3. It records what Ren'Py loaded, as plainly
# as possible; mapping onto the bundle format happens in Witch, where it's
# tested.
#
# It runs as init code rather than a registered command because how a
# game's launcher passes arguments differs between Ren'Py versions, and
# because some games stop on Steam or splash screens after init.

init 999999 python:

    def _witch_harvest():
        import os
        import traceback

        # A failure goes back to Witch as <output>.error: some Ren'Py versions
        # show an error screen and wait instead of writing traceback.txt.
        path = os.environ["WITCH_HARVEST_OUT"]
        try:
            _witch_harvest_to(path)
        except Exception:
            with open(path + ".error", "w") as f:
                f.write(traceback.format_exc())
        # Straight out, without starting the game or saving anything.
        os._exit(0)

    def _witch_harvest_to(path):
        import ast
        import json
        import os
        import sys

        py2 = sys.version_info[0] == 2

        # In the store, list/dict/set are Ren'Py's revertable subclasses, so
        # the real built-ins are fetched for isinstance, and for the big
        # tables, which don't need rollback's bookkeeping.
        try:
            import __builtin__ as builtins
            text_types = (builtins.str, builtins.unicode)
        except ImportError:
            import builtins
            text_types = (builtins.str,)
        sequence_types = (builtins.list, builtins.tuple)
        number_types = (builtins.bool, builtins.int, builtins.float)

        script = renpy.game.script
        nodes = builtins.list(script.all_stmts)
        index = builtins.dict((id(n), i) for i, n in enumerate(nodes))
        unknown_refs = []

        def text(value):
            return None if value is None else value + ""

        # Parameter kinds, as Python's inspect and Ren'Py 8 number them.
        POSITIONAL_OR_KEYWORD, VAR_POSITIONAL, VAR_KEYWORD = 1, 2, 4

        def signature(info):
            """A label/transform/screen signature as [name, kind, default
            source or None]: Ren'Py 8's Parameter objects, or Ren'Py 6/7's
            (name, default) pairs plus extrapos/extrakw."""
            params = info.parameters
            if hasattr(params, "values"):
                return {"signature": [[p.name, p.kind, text(p.default)] for p in params.values()]}
            out = [[name, POSITIONAL_OR_KEYWORD, text(default)] for name, default in params]
            if getattr(info, "extrapos", None):
                out.append([info.extrapos, VAR_POSITIONAL, None])
            if getattr(info, "extrakw", None):
                out.append([info.extrakw, VAR_KEYWORD, None])
            return {"signature": out}

        def call(info):
            """A call's arguments as [name or None, source], with the indexes
            of * and ** arguments: Ren'Py 8 keeps any number of them in
            place, Ren'Py 6/7 at most one of each, at the end."""
            args = [[name, text(expr)] for name, expr in info.arguments]
            starred = set(getattr(info, "starred_indexes", None) or ())
            doublestarred = set(getattr(info, "doublestarred_indexes", None) or ())
            if getattr(info, "extrapos", None):
                starred.add(len(args))
                args.append([None, text(info.extrapos)])
            if getattr(info, "extrakw", None):
                doublestarred.add(len(args))
                args.append([None, text(info.extrakw)])
            return {"call": args, "starred": sorted(starred), "doublestarred": sorted(doublestarred)}

        # Ren'Py 6.99-7.x compiles with print_function and unicode_literals
        # and retries without them if that fails; Ren'Py 6.15-6.18 has no
        # flags at all, a plain Python 2 parse.
        new_flags = getattr(renpy.python, "new_compile_flags", 0)
        old_flags = getattr(renpy.python, "old_compile_flags", 0)

        def needs_old_flags(source, mode):
            if not new_flags:
                return False
            escape = getattr(renpy.python, "escape_unicode", None)
            try:
                compile(escape(source) if escape else source, "<witch>", "exec" if mode == "hide" else mode,
                        ast.PyCF_ONLY_AST | new_flags, 1)
                return False
            except Exception:
                return True

        # Each snippet as Ren'Py itself would compile it: its own parser,
        # compile flags, Python 2 fixes (8.x), literal wrapping and `python
        # hide:` rewrite. On Python 3 that's written back as source; Python 2
        # has no ast.unparse, so the tree is written as JSON for Witch to
        # convert. Identical snippets share one entry.
        compiled = []
        compiled_keys = {}
        py_compile = renpy.python.py_compile
        has_ast_node = "ast_node" in py_compile.__code__.co_varnames

        def compiled_index(source, mode):
            key = (source + "", mode)
            if key not in compiled_keys:
                compiled_keys[key] = len(compiled)
                compiled.append(compile_entry(source, mode))
            return compiled_keys[key]

        def compile_entry(source, mode):
            try:
                if has_ast_node:
                    body = py_compile(source, mode, ast_node=True)
                else:
                    # Ren'Py 6.x: a plain Python 2 parse, then the wrap.
                    text = (source + "").replace("\r", "")
                    escape = getattr(renpy.python, "escape_unicode", None)
                    tree = ast.parse(escape(text) if escape else text, "<witch>", mode)
                    body = renpy.python.wrap_node.visit(tree).body
            except Exception as e:
                return {"error": "%s: %s" % (type(e).__name__, e)}
            if py2:
                return {"ast": dump_ast(body)}
            if isinstance(body, builtins.list):
                return {"source": ast.unparse(ast.Module(body=body, type_ignores=[]))}
            return {"source": ast.unparse(body)}

        def dump_ast(node):
            if isinstance(node, ast.AST):
                out = {"_": type(node).__name__}
                for field in node._fields:
                    value = getattr(node, field, None)
                    if type(node).__name__ == "Str" and field == "s" and isinstance(value, builtins.str):
                        out[field] = {"bytes": value.encode("hex")}  # a Python 2 str literal, not unicode
                    else:
                        out[field] = dump_ast(value)
                return out
            if isinstance(node, sequence_types):
                return [dump_ast(x) for x in node]
            if isinstance(node, builtins.str):
                return node.decode("ascii")  # identifiers and other names
            if isinstance(node, builtins.bool) or node is None:
                return node
            if isinstance(node, builtins.float):
                return node if node == node and abs(node) != float("inf") else {"float": repr(node)}
            if isinstance(node, builtins.complex):
                return {"complex": repr(node)}
            if isinstance(node, (builtins.int, getattr(builtins, "long", builtins.int))):
                return node if -2**53 < node < 2**53 else {"int": builtins.str(node)}
            return node

        def future_names(flags):
            import __future__
            return sorted(name for name in __future__.all_feature_names
                          if flags & getattr(__future__, name).compiler_flag)

        def node_name(name):
            if isinstance(name, tuple):
                return "|".join(str(part) for part in name)
            return name

        def enc(value, depth=0):
            if depth > 12:
                return {"too_deep": type(value).__name__}
            if value is None or isinstance(value, number_types):
                return value
            if isinstance(value, renpy.ast.Node):
                i = index.get(id(value))
                if i is None:
                    unknown_refs.append(type(value).__name__)
                return {"node": i}
            if isinstance(value, renpy.ast.PyCode):
                source = value.source
                out = {"code": source if isinstance(source, text_types) else repr(source), "mode": value.mode}
                if isinstance(source, text_types):  # Ren'Py 6.16 has code objects without source
                    if py2 and needs_old_flags(source, value.mode):
                        out["old_flags"] = True
                    out["c"] = compiled_index(source, value.mode)
                return out
            if isinstance(value, renpy.ast.PyExpr):
                return {"expr": value + "", "c": compiled_index(value, "eval")}
            if isinstance(value, text_types):
                return value
            if isinstance(value, sequence_types):
                if value and all(isinstance(v, renpy.ast.Node) for v in value):
                    return {"block": [index.get(id(v)) for v in value]}
                return [enc(v, depth + 1) for v in value]
            if isinstance(value, builtins.dict):
                return {"dict": [[enc(k, depth + 1), enc(v, depth + 1)] for k, v in value.items()]}
            if isinstance(value, renpy.ast.ParameterInfo):
                return signature(value)
            if isinstance(value, renpy.ast.ArgumentInfo):
                return call(value)
            out = {"object": type(value).__name__}
            name = getattr(value, "name", None)
            if isinstance(name, text_types):
                out["name"] = name
            return out

        def field_names(n):
            """A node's fields, wherever its Ren'Py declares them: __slots__
            (up to 8.4), class annotations with class-level defaults (8.5),
            or plain instance attributes."""
            names = []
            for klass in type(n).__mro__:
                names.extend(getattr(klass, "__slots__", ()))
                names.extend(getattr(klass, "__annotations__", {}))
            names.extend(getattr(n, "__dict__", {}))
            out = []
            for name in names:
                if (name not in out and not name.startswith("_")
                        and name not in ("name", "filename", "linenumber", "next")):
                    out.append(name)
            return out

        def node_entry(n):
            fields = {}
            for name in field_names(n):
                if hasattr(n, name):
                    fields[name] = enc(getattr(n, name))
            return {
                "class": type(n).__name__,
                "name": node_name(n.name),
                "file": n.filename,
                "line": n.linenumber,
                "next": index.get(id(n.next)) if n.next is not None else None,
                "fields": fields,
            }

        labels = {}
        # Labels are the nodes with string names. Ren'Py 8.5 keys the map by
        # the nodes themselves, so the name is read from the node.
        for n in script.namemap.values():
            if isinstance(n.name, text_types):
                labels[n.name] = index.get(id(n))

        images = {}
        for name, d in renpy.display.image.images.items():
            filename = getattr(d, "filename", None)
            images[" ".join(name)] = {
                "class": type(d).__name__,
                "file": filename if isinstance(filename, text_types) else None,
            }

        named = builtins.set(id(n) for n in script.namemap.values())

        # Init order exactly as Ren'Py runs it: (priority, first node).
        initcode = [[item[0], index.get(id(item[-1]))] for item in script.initcode]

        # Every module of Ren'Py's that was loaded, so the shim can stand in
        # for the ones it doesn't implement.
        renpy_modules = sorted(name for name, m in sys.modules.items()
                               if m is not None and (name == "renpy" or name.startswith("renpy.")))

        # Ren'Py's own pure-Python modules that the shim runs as they are,
        # in the order they're loaded: config defaults, the base object,
        # curry, preferences and persistent data, the names every store starts
        # with (minstore) and the main store's (defaultstore). As source on
        # Python 3, as a tree on Python 2. A list, not a dict: Python 2's
        # dicts have no order, and the load order matters.
        modules = []
        renpy_dir = os.path.dirname(renpy.__file__)
        for module in ("config", "object", "curry", "preferences", "persistent", "ui", "minstore", "defaultstore"):
            module_path = os.path.join(renpy_dir, module + ".py")
            if not os.path.exists(module_path):
                modules.append(["renpy." + module, {"error": "the game ships no source for it"}])
                continue
            with open(module_path, "rb") as source_file:
                module_source = source_file.read().decode("utf-8")
            if py2:
                modules.append(["renpy." + module, {"ast": dump_ast(ast.parse(module_source).body)}])
            else:
                modules.append(["renpy." + module, {"source": module_source}])

        # The store after init, the oracle for Witch's own init (REWORK-PLAN
        # §6.1). Containers and objects get an id when first written and are
        # a {"ref": id} after, so shared and cyclic values are kept; dicts
        # and sets are sorted so the output doesn't depend on hash order.
        seen = {}
        alive = []  # keeps encoded objects alive, so their ids can't be reused
        int_types = (builtins.int, getattr(builtins, "long", builtins.int))
        import types
        module_type = types.ModuleType
        function_types = (types.FunctionType, types.BuiltinFunctionType, types.MethodType)

        def qualified(obj):
            return "%s.%s" % (getattr(obj, "__module__", None) or "?", getattr(obj, "__name__", "?"))

        def sort_key(encoded):
            return json.dumps(encoded, sort_keys=True)

        def val(v, depth=0):
            if v is None or isinstance(v, builtins.bool):
                return v
            if isinstance(v, int_types):
                return v if -2**53 < v < 2**53 else {"int": builtins.str(v)}
            if isinstance(v, builtins.float):
                return v if v == v and v not in (float("inf"), float("-inf")) else {"float": repr(v)}
            if isinstance(v, text_types):
                if py2 and isinstance(v, builtins.str):
                    try:
                        return v.decode("ascii")
                    except UnicodeDecodeError:
                        return {"bytes": v.encode("hex")}
                return v
            if isinstance(v, module_type):
                return {"module": v.__name__}
            if isinstance(v, function_types):
                return {"function": qualified(getattr(v, "__func__", v))}
            if isinstance(v, type) or (py2 and type(v).__name__ == "classobj"):
                return {"class": qualified(v)}
            if depth > 40:
                return {"too_deep": type(v).__name__}
            key = id(v)
            if key in seen:
                return {"ref": seen[key]}
            seen[key] = len(seen)
            alive.append(v)
            out = {"id": seen[key]}
            if isinstance(v, builtins.list):
                out["list"] = [val(x, depth + 1) for x in v]
            elif isinstance(v, builtins.tuple):
                out["tuple"] = [val(x, depth + 1) for x in v]
            elif isinstance(v, builtins.dict):
                pairs = [[val(k, depth + 1), val(x, depth + 1)] for k, x in v.items()]
                out["dict"] = sorted(pairs, key=lambda p: sort_key(p[0]))
            elif isinstance(v, (builtins.set, builtins.frozenset)):
                out["set"] = sorted((val(x, depth + 1) for x in v), key=sort_key)
            else:
                out["object"] = qualified(type(v))
                attrs = {}
                for name in attribute_names(v):
                    try:
                        attrs[name] = val(getattr(v, name), depth + 1)
                    except AttributeError:
                        pass  # an empty slot
                out["attrs"] = attrs
            return out

        def attribute_names(v):
            """An object's own state: its slots and instance dict, not class
            attributes or properties."""
            names = builtins.set(getattr(v, "__dict__", {}))
            for klass in type(v).__mro__:
                slots = getattr(klass, "__slots__", ())
                names.update([slots] if isinstance(slots, text_types) else slots)
            return sorted(n for n in names if not n.startswith("__"))

        def own(name):
            return not name.startswith("__") and not name.startswith("_witch")

        # Nodes are written one at a time: a large game held whole in memory
        # doesn't fit in a 32-bit Ren'Py 6. The file is written under a
        # temporary name and renamed, so a finished file means a finished harvest.
        with open(path + ".part", "w") as f:
            f.write('{"harvest_version": 3, "renpy_version": %s, "screen_size": %s, "nodes": ['
                    % (json.dumps(renpy.version()), json.dumps([config.screen_width, config.screen_height])))
            for i, n in enumerate(nodes):
                if i:
                    f.write(",\n")
                json.dump(node_entry(n), f)
            f.write('],\n"compiled": [')
            for i, entry in enumerate(compiled):
                if i:
                    f.write(",\n")
                json.dump(entry, f)
            f.write('],\n"labels": %s,\n"images": %s,\n"named_nodes": %d,\n"named_outside_graph": %d,\n'
                    '"unindexed_refs": %s,\n' % (json.dumps(labels), json.dumps(images), len(named),
                                                 len(named - builtins.set(index)), json.dumps(unknown_refs)))
            python = {"version": list(sys.version_info[:3])}
            if py2:
                python["new_flags"] = future_names(new_flags)
                python["old_flags"] = future_names(old_flags)
            file_flags = getattr(renpy.python, "file_compiler_flags", {})
            python["file_flags"] = dict((k, future_names(v)) for k, v in file_flags.items() if v)
            f.write('"python": %s,\n"initcode": %s,\n"modules": %s,\n"renpy_modules": %s,\n"config": '
                    % (json.dumps(python), json.dumps(initcode), json.dumps(modules), json.dumps(renpy_modules)))
            json.dump(dict((k, val(v)) for k, v in sorted(vars(renpy.config).items()) if own(k)), f)
            f.write(',\n"store": {')
            for i, (store_name, store) in enumerate(sorted(renpy.python.store_dicts.items())):
                if i:
                    f.write(",\n")
                f.write("%s: " % json.dumps(store_name))
                json.dump(dict((k, val(v)) for k, v in sorted(store.items()) if own(k)), f)
            f.write("}}")
        os.rename(path + ".part", path)

    import os as _witch_os
    if "WITCH_HARVEST_OUT" in _witch_os.environ:
        _witch_harvest()
