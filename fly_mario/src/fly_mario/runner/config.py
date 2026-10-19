"""A fly is a config file: which senses attach to which objects, which actions are on, and the knob values.

    name: champion_e1s
    attachments:            # per_object senses: sense name -> object types it looks at
      looming: [goomba, koopa, pipe, pit]
    loom_shapes: {}         # object type -> loom shape, only where it differs from the type's own default
    whole_fly: [home]       # whole_fly senses that are on
    actions: [walk, jump]   # actions that are on
    knobs: {home.drive: 0.46}
    provenance: {...}       # free text: where the numbers came from
"""
from __future__ import annotations

from pathlib import Path

import yaml

from fly_mario import registry
from fly_mario.contracts import FlyConfig
from fly_mario.fly.spec import BrainSpec

FLIES = Path(__file__).resolve().parents[3] / "configs" / "flies"      # fly_mario/configs/flies


def _plugins() -> dict:
    return {k: registry.list_plugins(k) for k in ("senses", "actions", "objects", "shapes", "mechanisms")}


def fly_from_dict(d: dict) -> FlyConfig:
    return FlyConfig(
        name=str(d["name"]),
        attachments={s: frozenset(t) for s, t in (d.get("attachments") or {}).items()},
        loom_shapes=dict(d.get("loom_shapes") or {}),
        whole_fly=frozenset(d.get("whole_fly") or ()),
        actions=frozenset(d.get("actions") or ()),
        knobs={k: float(v) for k, v in (d.get("knobs") or {}).items()},
        provenance=dict(d.get("provenance") or {}))


def fly_to_dict(fly: FlyConfig) -> dict:
    return {"name": fly.name,
            "attachments": {s: sorted(t) for s, t in sorted(fly.attachments.items())},
            "loom_shapes": dict(sorted(fly.loom_shapes.items())),
            "whole_fly": sorted(fly.whole_fly),
            "actions": sorted(fly.actions),
            "knobs": {k: float(v) for k, v in sorted(fly.knobs.items())},
            "provenance": dict(fly.provenance)}


def load_fly(path_or_name) -> FlyConfig:
    """A fly from a yaml path, or from the name of a file in configs/flies/. Validated."""
    p = Path(path_or_name)
    if not p.exists():
        p = FLIES / f"{path_or_name}.yaml"
    fly = fly_from_dict(yaml.safe_load(p.read_text(encoding="utf-8")))
    validate(fly)
    return fly


def dump_fly(fly: FlyConfig) -> str:
    return yaml.safe_dump(fly_to_dict(fly), sort_keys=False, allow_unicode=True)


def active_senses(fly: FlyConfig) -> list:
    """The sense plug-ins that are on (attached to something, or whole_fly and on), in run order."""
    senses = registry.list_plugins("senses")
    names = {s for s, types in fly.attachments.items() if types} | set(fly.whole_fly)
    return sorted((senses[n] for n in names), key=lambda s: (getattr(s, "order", 50), s.name))


def active_actions(fly: FlyConfig) -> list:
    actions = registry.list_plugins("actions")
    return sorted((actions[n] for n in fly.actions), key=lambda a: (a.priority, a.name))


def knob_specs(fly: FlyConfig) -> list:
    """Every KnobSpec the fly can be given: its senses', its actions', and every loom shape's."""
    specs = [k for c in active_senses(fly) + active_actions(fly) for k in c.knobs]
    specs += [k for s in registry.list_plugins("shapes").values() for k in s.knobs]
    return specs


def resolve_knobs(fly: FlyConfig) -> dict:
    """key -> value: the specs' defaults, overridden by the fly's own."""
    out = {k.key: k.default for k in knob_specs(fly)}
    out.update(fly.knobs)
    return out


def mechanisms_for(fly: FlyConfig) -> tuple:
    """The brain this fly needs: what its senses feed plus what its actions read."""
    mechs = registry.list_plugins("mechanisms")
    need = {m for s in active_senses(fly) for m in s.feeds}
    for a in active_actions(fly):
        need |= {m.name for m in mechs.values() if set(a.source_groups) & set(m.neuron_sets)}
    return tuple(sorted(need))


def brain_spec(fly: FlyConfig) -> BrainSpec:
    return BrainSpec(mechanisms=mechanisms_for(fly))


def validate(fly: FlyConfig, strict_range: bool = True) -> None:
    """Raise ValueError naming the first thing that does not exist or is out of range."""
    p = _plugins()
    for sense, types in fly.attachments.items():
        if sense not in p["senses"]:
            raise ValueError(f"{fly.name}: unknown sense {sense!r}; known: {sorted(p['senses'])}")
        if p["senses"][sense].scope != "per_object":
            raise ValueError(f"{fly.name}: {sense!r} is a whole_fly sense; list it under whole_fly, not attachments")
        bad = set(types) - set(p["objects"])
        if bad:
            raise ValueError(f"{fly.name}: {sense!r} attached to unknown object type(s) {sorted(bad)}")
    for sense in fly.whole_fly:
        if sense not in p["senses"] or p["senses"][sense].scope != "whole_fly":
            raise ValueError(f"{fly.name}: {sense!r} is not a whole_fly sense")
    for action in fly.actions:
        if action not in p["actions"]:
            raise ValueError(f"{fly.name}: unknown action {action!r}; known: {sorted(p['actions'])}")
    for obj, shape in fly.loom_shapes.items():
        if obj not in p["objects"] or shape not in p["shapes"]:
            raise ValueError(f"{fly.name}: loom_shapes {obj!r}: {shape!r} names something that does not exist")
    specs = {k.key: k for c in p["senses"].values() for k in c.knobs}
    specs.update({k.key: k for c in p["actions"].values() for k in c.knobs})
    specs.update({k.key: k for c in p["shapes"].values() for k in c.knobs})
    for key, value in fly.knobs.items():
        if key not in specs:
            raise ValueError(f"{fly.name}: unknown knob {key!r}; known: {sorted(specs)}")
        s = specs[key]
        if strict_range and not (s.lo <= value <= s.hi):
            raise ValueError(f"{fly.name}: knob {key} = {value} is outside its range [{s.lo}, {s.hi}]")
