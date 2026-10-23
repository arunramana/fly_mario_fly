"""Build a brain from the 636-neuron base plus chosen mechanisms, cache it, and run the rate model on it.

Rows are MaleCNS neurons. W[i, j] is the weight of j -> i: synapse count, divided by the row's in-network input
(so every row with inputs sums to 1), signed by the transmitter of the presynaptic neuron (Dale's law).

Base: the 636 neurons of the old W_steer -- escape (LC4, LPLC2, Giant Fiber, TTMn), walking (DNp09, LC10a) and
steering (DNa01/02), plus the 40 relays that carry the most synapses from LC10a to DNa. Edges among them keep
every synapse count (no threshold). A mechanism's extra neurons are appended below the base; an edge that touches
a new neuron needs >= 5 synapses. A mechanism that is not allowed to write into older rows drops its
new -> old edges, so everything built before it behaves exactly as without it.

Brains are cached by content hash under $FLY_MARIO_FLY_DATA/brains.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import scipy.sparse as sp

from fly_mario_fly import registry
from fly_mario_fly.fly import connectome as cn
from fly_mario_fly.fly.groups import group_types, masks_for
from fly_mario_fly.fly.spec import BrainSpec

BUILD_VERSION = 1
N_RELAYS = 40


def base_types() -> tuple:
    """Cell types of the base: those of the groups owned by the mechanisms that add no neurons (escape, walking).
    groups.yaml is the one table; the order is its order, which the brain's content hash depends on."""
    own = {g for m in registry.list_plugins("mechanisms").values() if m.extra is None for g in m.neuron_sets}
    return group_types(own)


def base_recipe() -> dict:
    return {
        "name": "steer636", "types": list(base_types()), "relays": N_RELAYS,
        "rule": "relays = top-40 bodies by min(synapses from LC10a, synapses to DNa01/02); edges among the cast keep every count",
    }


@dataclass(frozen=True)
class RateModel:
    """The leaky rate update. All four numbers are hand-set (invented), not read off the connectome."""
    g: float = 0.5        # global recurrent gain
    alpha: float = 0.3    # leak / mix rate per step
    clip: float = 50.0    # activity ceiling
    substeps: int = 10    # network steps per game frame


def step(h, W, g, I_t, alpha, clip):
    """One leaky rate update."""
    drive = g * (W @ h) + I_t
    return (1.0 - alpha) * h + alpha * np.clip(drive, 0.0, clip)


class Brain:
    def __init__(self, spec: BrainSpec, W, body_ids, types, sides, signs):
        self.spec, self.W = spec, W
        self._Ws = sp.csr_matrix(W)              # W is 4-7 % non-zero: advance() multiplies by the sparse copy
        self.body_ids = np.asarray(body_ids, dtype=np.int64)
        self.types, self.sides, self.signs = np.asarray(types, dtype="U40"), np.asarray(sides, dtype="U40"), np.asarray(signs, dtype=float)
        self.masks = masks_for(self.types, self.sides)
        self._row = {int(b): i for i, b in enumerate(self.body_ids)}

    @property
    def n(self) -> int:
        return len(self.body_ids)

    def counts(self) -> dict:
        return {k: int(m.sum()) for k, m in self.masks.items()}

    # ---- dynamics -----------------------------------------------------------------------------------
    def new_state(self) -> np.ndarray:
        return np.zeros(self.n)

    def drive(self, inputs: dict) -> np.ndarray:
        """Input vector from {group name: level}; a group this brain does not have is an error."""
        I = np.zeros(self.n)
        for name, level in inputs.items():
            I[self.masks[name]] = level
        return I

    def advance(self, h, I, model: RateModel = RateModel()) -> np.ndarray:
        """One game frame: `model.substeps` rate updates under the same input."""
        for _ in range(model.substeps):
            h = step(h, self._Ws, model.g, I, model.alpha, model.clip)
        return h

    def rates(self, h) -> dict:
        """Mean rate of every group in this brain."""
        return {k: float(h[m].mean()) for k, m in self.masks.items()}

    # ---- saved moments ------------------------------------------------------------------------------
    def get_state(self, h) -> dict:
        """Rates keyed by MaleCNS body id, so a moment saved from one brain loads into another."""
        return {int(b): float(v) for b, v in zip(self.body_ids, h)}

    def set_state(self, state: dict) -> np.ndarray:
        """Rate vector for this brain; neurons absent from `state` start at rest (0), ids not in this brain are ignored."""
        h = self.new_state()
        for b, v in state.items():
            i = self._row.get(int(b))
            if i is not None:
                h[i] = v
        return h

    # ---- cache --------------------------------------------------------------------------------------
    def save(self, path: Path, meta: dict) -> None:
        np.savez(path, W=self.W, body_ids=self.body_ids, types=self.types, sides=self.sides, signs=self.signs)
        path.with_suffix(".json").write_text(json.dumps(meta, indent=1), encoding="utf-8")

    @classmethod
    def load(cls, spec: BrainSpec, path: Path) -> "Brain":
        d = np.load(path)
        return cls(spec, d["W"], d["body_ids"], d["types"], d["sides"], d["signs"])


# ---- recipe, hash, paths ------------------------------------------------------------------------------
def _mechanisms(spec: BrainSpec) -> list:
    """The spec's mechanisms that bring extra neurons, in build order. Unknown names are an error."""
    known = registry.list_plugins("mechanisms")
    bad = [m for m in spec.mechanisms if m not in known]
    if bad:
        raise ValueError(f"unknown mechanism(s) {bad}; known: {sorted(known)}")
    return sorted((known[m] for m in set(spec.mechanisms) if known[m].extra is not None), key=lambda p: p.build_order)


def _data_signature(root: Path) -> dict:
    folder = root / "malecns_v1.0"
    return {k: (folder / v).stat().st_size if (folder / v).exists() else None for k, v in cn.FILES.items()}


def brain_name(spec: BrainSpec) -> str:
    return "+".join([spec.base] + [p.name for p in _mechanisms(spec)])


def recipe(spec: BrainSpec, root: Path) -> dict:
    return {"build_version": BUILD_VERSION, "base": base_recipe(), "data": _data_signature(root),
            "mechanisms": [{"name": p.name, "writes_into_base": p.extra.writes_into_base, **p.extra.recipe} for p in _mechanisms(spec)]}


def brain_hash(spec: BrainSpec, root: Path | None = None) -> str:
    return hashlib.sha256(json.dumps(recipe(spec, root or cn.data_dir()), sort_keys=True).encode()).hexdigest()


def brain_path(spec: BrainSpec, root: Path | None = None) -> Path:
    root = root or cn.data_dir()
    return root / "brains" / f"{brain_name(spec)}-{brain_hash(spec, root)[:12]}.npz"


# ---- building -----------------------------------------------------------------------------------------
@dataclass
class _Net:
    """A brain under construction: synapse counts (not yet normalised) with its per-row bookkeeping."""
    ids: np.ndarray
    types: np.ndarray
    sides: np.ndarray
    signs: np.ndarray
    counts: np.ndarray = field(repr=False)


def _base_net(conn: cn.Connectome) -> _Net:
    h = hashlib.sha256(json.dumps([BUILD_VERSION, base_recipe(), _data_signature(conn.root)], sort_keys=True).encode()).hexdigest()[:12]
    cache = conn.derived / f"base_{h}.npz"
    if cache.exists():
        d = np.load(cache)
        return _Net(d["ids"], d["types"], d["sides"], d["signs"], d["counts"])
    core = conn.body_ids(types=base_types())
    lc10a, dna = conn.body_ids(types=["LC10a"]), conn.body_ids(types=["DNa01", "DNa02"])
    # Relays: bodies that both receive from LC10a and send to DNa; keep the 40 with the most synapses on the weaker side.
    from_ids, from_w, to_ids, to_w = conn.through_scores(lc10a, dna)
    both, i, j = np.intersect1d(from_ids, to_ids, return_indices=True)
    score = np.minimum(from_w[i], to_w[j])
    relays = both[np.lexsort((both, -score))][:N_RELAYS]
    ids = np.union1d(core, relays)
    row = conn.index(ids)
    types, sides = conn.type[row], conn.soma_side[row]
    # Row order: cell type, soma side (bodies without a side last), body id.
    last = lambda a: np.where(a == "", "\U0010ffff", a)
    order = np.lexsort((ids, last(sides), last(types)))
    ids, types, sides = ids[order], types[order], sides[order]
    pre, post, w = conn.edges_among(ids)
    by_id = np.argsort(ids)
    pos = by_id[np.searchsorted(ids, np.stack([pre, post]), sorter=by_id)]       # brain row of each end
    counts = np.zeros((len(ids), len(ids)))
    np.add.at(counts, (pos[1], pos[0]), w)
    net = _Net(ids, types, sides, conn.signs(ids), counts)
    np.savez(cache, ids=net.ids, types=net.types, sides=net.sides, signs=net.signs, counts=net.counts)
    return net


def _add_mechanism(conn: cn.Connectome, net: _Net, plugin) -> _Net:
    old = len(net.ids)
    new_ids = [i for i in plugin.extra.ids(conn) if i not in set(net.ids.tolist())]
    assert len(set(new_ids)) == len(new_ids), f"{plugin.name}: duplicate neurons"
    ids = np.concatenate([net.ids, np.array(new_ids, dtype=np.int64)])
    k = len(ids)
    row = conn.index(ids)
    loc = np.full(len(conn.ids), -1)                      # annotation row -> brain row
    loc[row] = np.arange(k)
    pre, post, w = conn.edge_table()
    a, b = loc[pre], loc[post]                            # brain rows of the two ends (-1 = not in the brain)
    keep = (a >= 0) & (b >= 0) & ((a >= old) | (b >= old))   # both ends in the brain, at least one of them new
    if not plugin.extra.writes_into_base:
        keep &= ~((a >= old) & (b < old))                 # drop new -> old
    counts = np.zeros((k, k))
    counts[:old, :old] = net.counts
    np.add.at(counts, (b[keep], a[keep]), w[keep].astype(np.float64))
    new_row = row[old:]
    return _Net(ids, np.concatenate([net.types, conn.type[new_row]]), np.concatenate([net.sides, conn.side[new_row]]),
                np.concatenate([net.signs, conn.signs(ids[old:])]), counts)


def _finish(spec: BrainSpec, net: _Net) -> Brain:
    row_sum = net.counts.sum(axis=1, keepdims=True)
    W = np.divide(net.counts, row_sum, out=np.zeros_like(net.counts), where=row_sum > 0) * net.signs[np.newaxis, :]
    return Brain(spec, W, net.ids, net.types, net.sides, net.signs)


def build_brain(spec: BrainSpec, conn: cn.Connectome | None = None, force: bool = False) -> Brain:
    """Load the brain from the cache, or build it (and cache it) from the MaleCNS data."""
    root = conn.root if conn else cn.data_dir()
    path = brain_path(spec, root)
    if path.exists() and not force:
        return Brain.load(spec, path)
    conn = conn or cn.Connectome(root)
    net = _base_net(conn)
    for plugin in _mechanisms(spec):
        net = _add_mechanism(conn, net, plugin)
    brain = _finish(spec, net)
    path.parent.mkdir(parents=True, exist_ok=True)
    brain.save(path, {"name": brain_name(spec), "n": brain.n, "recipe": recipe(spec, root), "group_counts": brain.counts()})
    return brain


def all_specs() -> list:
    """Every brain worth having: the base plus each subset of the mechanisms that add neurons."""
    extras = sorted((p for p in registry.list_plugins("mechanisms").values() if p.extra is not None), key=lambda p: p.build_order)
    return [BrainSpec(mechanisms=tuple(p.name for k, p in enumerate(extras) if mask >> k & 1)) for mask in range(1 << len(extras))]
