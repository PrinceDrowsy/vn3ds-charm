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
        import json
        import os

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
                return {"code": source if isinstance(source, text_types) else repr(source),
                        "mode": value.mode}
            if isinstance(value, renpy.ast.PyExpr):
                return {"expr": value + ""}
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

        # Nodes are written one at a time: a large game held whole in memory
        # doesn't fit in a 32-bit Ren'Py 6. The file is written under a
        # temporary name and renamed, so a finished file means a finished harvest.
        with open(path + ".part", "w") as f:
            f.write('{"harvest_version": 2, "renpy_version": %s, "screen_size": %s, "nodes": ['
                    % (json.dumps(renpy.version()), json.dumps([config.screen_width, config.screen_height])))
            for i, n in enumerate(nodes):
                if i:
                    f.write(",\n")
                json.dump(node_entry(n), f)
            f.write('],\n"labels": %s,\n"images": %s,\n"named_nodes": %d,\n"named_outside_graph": %d,\n'
                    '"unindexed_refs": %s}' % (json.dumps(labels), json.dumps(images), len(named),
                                               len(named - builtins.set(index)), json.dumps(unknown_refs)))
        os.rename(path + ".part", path)

    import os as _witch_os
    if "WITCH_HARVEST_OUT" in _witch_os.environ:
        _witch_harvest()
