"""The check of REWORK-PLAN §6.3: the records the shim's init produced
against the records the game's own Ren'Py lowered to (harvest.rpy), by the
same vocabulary (bundle/descriptions.py).

Records are plain data. Two are the same when their kinds, attributes and
values agree, where:
- an int and a float never agree (a position of 1 is a pixel, 1.0 the far
  edge), nor a bool and a number;
- floats agree within a few units in the last place (maths libraries
  differ between the PC that harvested and the device);
- dicts and sets are unordered, and so is each dict of a style's
  properties.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field


def _key(value) -> str:
    return json.dumps(value, sort_keys=True)


def normalize(value):
    """A record with its unordered parts in one order."""
    if isinstance(value, list):
        return [normalize(v) for v in value]
    if not isinstance(value, dict):
        return value
    if set(value) == {"dict"}:
        return {"dict": sorted(([normalize(k), normalize(v)] for k, v in value["dict"]), key=lambda p: _key(p[0]))}
    if set(value) == {"set"}:
        return {"set": sorted((normalize(v) for v in value["set"]), key=_key)}
    out = dict((k, normalize(v)) for k, v in value.items())
    if "style" in value and "properties" in value and "kind" not in value:
        out["properties"] = [sorted(d, key=lambda p: p[0]) for d in out["properties"]]
    return out


def differences(oracle, ours, path: str = "") -> list[tuple[str, object, object]]:
    """Where two normalized records disagree, as (path, oracle's, ours)."""
    if isinstance(oracle, bool) or isinstance(ours, bool) or oracle is None or ours is None:
        return [] if oracle is ours else [(path, oracle, ours)]
    if isinstance(oracle, float) and isinstance(ours, float):
        return [] if math.isclose(oracle, ours, rel_tol=1e-12, abs_tol=1e-15) else [(path, oracle, ours)]
    if type(oracle) is not type(ours):
        return [(path, oracle, ours)]
    if isinstance(oracle, list):
        if len(oracle) != len(ours):
            return [(path, oracle, ours)]
        return [d for i, (a, b) in enumerate(zip(oracle, ours)) for d in differences(a, b, f"{path}[{i}]")]
    if isinstance(oracle, dict):
        out = []
        for k in sorted(set(oracle) | set(ours)):
            if k not in oracle or k not in ours:
                out.append((f"{path}.{k}", oracle.get(k, "<absent>"), ours.get(k, "<absent>")))
            else:
                out += differences(oracle[k], ours[k], f"{path}.{k}")
        return out
    return [] if oracle == ours else [(path, oracle, ours)]


@dataclass
class Comparison:
    """One registry compared: entries by name."""
    same: int = 0
    different: dict = field(default_factory=dict)  # name -> [(path, oracle's, ours)]
    only_oracle: list = field(default_factory=list)
    only_ours: list = field(default_factory=list)

    @property
    def matches(self) -> bool:
        return not (self.different or self.only_oracle or self.only_ours)


def compare(oracle: list, ours: list) -> Comparison:
    """`oracle` and `ours` are [[name, record], ...], as harvest.rpy's
    "records" and the init result's "registries" hold them."""
    a = dict((_key(name), record) for name, record in oracle)
    b = dict((_key(name), record) for name, record in ours)
    result = Comparison(only_oracle=sorted(json.loads(k) for k in set(a) - set(b)),
                        only_ours=sorted(json.loads(k) for k in set(b) - set(a)))
    for key in sorted(set(a) & set(b)):
        found = differences(normalize(a[key]), normalize(b[key]))
        if found:
            result.different[key] = found
        else:
            result.same += 1
    return result


def check(harvest: dict, result: dict) -> dict[str, Comparison]:
    """Every registry init filled, the shim's (`result`, from run_init)
    against Ren'Py's (`harvest`)."""
    return dict((name, compare(harvest["records"][name], result["registries"][name]))
                for name in sorted(harvest["records"]))
