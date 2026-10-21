"""The genome: the evolvable knobs of whatever is switched ON in a fly, as numbers in [0, 1].

Nothing here names a sense, an object or an action: the knobs come from the KnobSpecs of the plug-ins the
FlyConfig turns on. A log-scaled knob is searched on its log axis (as the old E1s genes were); a knob with a
`floor` never goes below it, so a selected drive stays strong enough to be usable.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace

from fly_mario import registry
from fly_mario.contracts import FlyConfig, KnobSpec
from fly_mario.runner import config as C


@dataclass(frozen=True)
class Gene:
    spec: KnobSpec
    lo: float              # effective lower bound: the spec's lo, raised to its floor
    hi: float
    start: float

    @property
    def key(self) -> str:
        return self.spec.key

    @property
    def log(self) -> bool:
        return self.spec.scale == "log" and self.lo > 0

    def value(self, u: float) -> float:
        u = min(1.0, max(0.0, float(u)))
        if self.log:
            return self.lo * (self.hi / self.lo) ** u
        return self.lo + u * (self.hi - self.lo)

    def unit(self, v: float) -> float:
        v = min(self.hi, max(self.lo, float(v)))
        if self.hi == self.lo:
            return 0.5
        if self.log:
            return math.log(v / self.lo) / math.log(self.hi / self.lo)
        return (v - self.lo) / (self.hi - self.lo)


def _shapes_on(fly: FlyConfig) -> list:
    """Loom shapes in use: the ones the fly names, plus the default shape of every object a sense is attached to."""
    shapes, objects = registry.list_plugins("shapes"), registry.list_plugins("objects")
    names = set(fly.loom_shapes.values())
    for types in fly.attachments.values():
        names |= {objects[t].default_loom_shape for t in types if t in objects}
    return [shapes[n] for n in sorted(names) if n in shapes]


def on_specs(fly: FlyConfig) -> list:
    """Every KnobSpec of the plug-ins that are ON in this fly (senses, actions, loom shapes), once per key."""
    specs, seen = [], set()
    for plugin in C.active_senses(fly) + C.active_actions(fly) + _shapes_on(fly):
        for k in plugin.knobs:
            if k.key not in seen:
                seen.add(k.key)
                specs.append(k)
    return specs


def build_genome(fly: FlyConfig) -> list:
    """The evolvable knobs of the fly, in a fixed order, each starting at the fly's value (or the default)."""
    current = C.resolve_knobs(fly)
    genes = []
    for k in on_specs(fly):
        if not k.evolvable:
            continue
        lo = max(k.lo, k.floor) if k.floor is not None else k.lo
        genes.append(Gene(k, lo, k.hi, min(k.hi, max(lo, current.get(k.key, k.default)))))
    return genes


def decode(genes: list, u) -> dict:
    return {g.key: g.value(x) for g, x in zip(genes, u)}


def encode(genes: list) -> list:
    return [g.unit(g.start) for g in genes]


def apply_knobs(fly: FlyConfig, values: dict) -> FlyConfig:
    """The same fly with the evolved knob values written over its own."""
    return replace(fly, knobs={**fly.knobs, **values})
