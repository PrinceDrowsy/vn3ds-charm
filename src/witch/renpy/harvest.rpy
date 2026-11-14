# Witch's Ren'Py harvester (REWORK-PLAN §5). Copied into a scratch copy of a
# game and run by the game's own Ren'Py as `<game> . witch_harvest`, with the
# output path in WITCH_HARVEST_OUT. Runs on Ren'Py 6.17-8.x, so it must stay
# valid Python 2 and Python 3. It records what Ren'Py loaded, as plainly as
# possible; mapping onto the bundle format happens in Witch, where it's tested.

init 999 python:

    def _witch_harvest():
        import json
        import os

        renpy.arguments.takes_no_arguments("Witch's harvester")

        # In the store, list/dict/set are Ren'Py's revertable subclasses, so
        # the real built-ins have to be fetched for isinstance.
        try:
            import __builtin__ as builtins
            text_types = (builtins.str, builtins.unicode)
        except ImportError:
            import builtins
            text_types = (builtins.str,)
        sequence_types = (builtins.list, builtins.tuple)
        number_types = (builtins.bool, builtins.int, builtins.float)

        script = renpy.game.script
        nodes = list(script.all_stmts)
        index = dict((id(n), i) for i, n in enumerate(nodes))
        unknown_refs = []

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
                return {"parameters": enc(value.parameters, depth + 1),
                        "extrapos": getattr(value, "extrapos", None),
                        "extrakw": getattr(value, "extrakw", None)}
            if isinstance(value, renpy.ast.ArgumentInfo):
                return {"arguments": enc(value.arguments, depth + 1),
                        "extrapos": getattr(value, "extrapos", None),
                        "extrakw": getattr(value, "extrakw", None)}
            out = {"object": type(value).__name__}
            name = getattr(value, "name", None)
            if isinstance(name, text_types):
                out["name"] = name
            return out

        def slots(cls):
            names = []
            for klass in cls.__mro__:
                for name in getattr(klass, "__slots__", ()):
                    if name not in names and name not in ("name", "filename", "linenumber", "next"):
                        names.append(name)
            return names

        out_nodes = []
        for n in nodes:
            fields = {}
            for name in slots(type(n)):
                if hasattr(n, name):
                    fields[name] = enc(getattr(n, name))
            out_nodes.append({
                "class": type(n).__name__,
                "name": node_name(n.name),
                "file": n.filename,
                "line": n.linenumber,
                "next": index.get(id(n.next)) if n.next is not None else None,
                "fields": fields,
            })

        labels = {}
        for key, n in script.namemap.items():
            if isinstance(key, text_types):
                labels[key] = index.get(id(n))

        images = {}
        for name, d in renpy.display.image.images.items():
            filename = getattr(d, "filename", None)
            images[" ".join(name)] = {
                "class": type(d).__name__,
                "file": filename if isinstance(filename, text_types) else None,
            }

        named = set(id(n) for n in script.namemap.values())
        out = {
            "harvest_version": 1,
            "renpy_version": renpy.version(),
            "screen_size": [config.screen_width, config.screen_height],
            "nodes": out_nodes,
            "labels": labels,
            "images": images,
            "named_nodes": len(named),
            "named_outside_graph": len(named - set(index)),
            "unindexed_refs": unknown_refs,
        }
        # Written under a temporary name and renamed, so a finished file is
        # the signal that the harvest completed.
        path = os.environ["WITCH_HARVEST_OUT"]
        with open(path + ".part", "w") as f:
            json.dump(out, f)
        os.rename(path + ".part", path)
        return False

    renpy.arguments.register_command("witch_harvest", _witch_harvest)
