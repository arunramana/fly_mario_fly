"""What the renderer needs to draw the brain: where the neurons are, which group each belongs to, and how a group looks.

One source for all of it: positions from the MaleCNS annotations (fly/connectome.py), membership from the brain
itself (fly/brain.py masks), colour / plain role / order from fly/groups.yaml. Nothing here is copied into render/.

Soma positions are voxels (x left-right, y dorsal-ventral, z brain -> nerve cord). JO / ORN neurons have no soma in
MaleCNS (their cell bodies sit in the antenna), so they are placed at the synapse-weighted mean soma position of the
brain neurons they send synapses to: a proxy for where their terminals are. Caches, under $FLY_MARIO_FLY_DATA/derived/:
    display_somata.npz     ids, xyz of every neuron that has a soma (141,781)
    display_terminals.npz  ids, xyz of the no-soma neurons placed so far (grows as new brains ask)
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from fly_mario_fly.contracts import FlyConfig
from fly_mario_fly.fly import connectome as cn
from fly_mario_fly.fly import groups as G
from fly_mario_fly.runner import config as C
from fly_mario_fly.runner.session import get_brain

BRAIN_Z_MAX = 50000            # a partner soma further down the cord than this is not a brain neuron: ignored


@dataclass(frozen=True)
class GroupDisplay:
    name: str
    role: str                  # plain words, from groups.yaml
    colour: str                # "#rrggbb", from groups.yaml
    index: int                 # position in groups.yaml: the order the index lists the groups
    body_ids: np.ndarray       # (n,) MaleCNS body ids, in the brain's row order
    xyz: np.ndarray            # (n, 3) voxels; nan where no position could be found

    @property
    def count(self) -> int:
        return len(self.body_ids)

    @property
    def rgb(self) -> tuple:
        return tuple(int(self.colour[i:i + 2], 16) for i in (1, 3, 5))


@dataclass(frozen=True)
class BrainDisplay:
    all_xyz: np.ndarray                              # (N, 3) soma of every MaleCNS neuron that has one: the dim cloud
    groups: dict                                     # name -> GroupDisplay, in groups.yaml order, only groups this brain has
    other_xyz: np.ndarray                            # (m, 3) circuit neurons in no group (relays)
    other_colour: str                                # their colour, from groups.yaml
    n_neurons: int = 0                               # neurons in the brain
    placed_by_terminal: tuple = field(default_factory=tuple)   # groups drawn at a terminal proxy, not a soma
    display: dict = field(default_factory=dict)      # groups.yaml's `display:` section (index rows, big set)


def all_somata() -> tuple:
    """(body ids, (N, 3) float32 voxel xyz) of every neuron with a soma location, sorted by id. Cached."""
    cache = cn.data_dir() / "derived" / "display_somata.npz"
    if cache.exists():
        z = np.load(cache)
        return z["ids"], z["xyz"]
    c = cn.Connectome()
    has = ~np.isnan(c.soma_xyz).any(axis=1)
    ids, xyz = c.ids[has], c.soma_xyz[has]
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez(cache, ids=ids, xyz=xyz)
    return ids, xyz


def terminal_positions(body_ids) -> np.ndarray:
    """(n, 3) positions for bodies with no soma: synapse-weighted mean soma of their brain partners (nan if none)."""
    body_ids = np.asarray(body_ids, dtype=np.int64)
    if len(body_ids) == 0:
        return np.zeros((0, 3))
    cache = cn.data_dir() / "derived" / "display_terminals.npz"
    have: dict = {}
    if cache.exists():
        z = np.load(cache)
        have = dict(zip(z["ids"].tolist(), z["xyz"]))
    todo = np.array(sorted({int(b) for b in body_ids} - set(have)), dtype=np.int64)
    if len(todo):
        sid, sxyz = all_somata()
        sxyz = sxyz.astype(np.float64)
        acc = {int(b): np.zeros(4) for b in todo}
        c = cn.Connectome()
        for pre, post, w in c.edge_batches():             # streamed: the weights file is never loaded whole
            m = np.isin(pre, todo)
            if not m.any():
                continue
            pre, post, w = pre[m], post[m], w[m].astype(np.float64)
            j = np.clip(np.searchsorted(sid, post), 0, len(sid) - 1)
            ok = (sid[j] == post) & (sxyz[j, 2] < BRAIN_Z_MAX)
            for p, jj, ww in zip(pre[ok], j[ok], w[ok]):
                a = acc[int(p)]
                a[:3] += ww * sxyz[jj]
                a[3] += ww
        for b, a in acc.items():
            have[b] = a[:3] / a[3] if a[3] > 0 else np.full(3, np.nan)
        ids = np.array(sorted(have), dtype=np.int64)
        np.savez(cache, ids=ids, xyz=np.array([have[int(i)] for i in ids]))
    return np.array([have[int(b)] for b in body_ids])


def brain_display(fly: FlyConfig) -> BrainDisplay:
    """The display data for the brain this fly runs on."""
    return brain_display_for(C.brain_spec(fly))


def brain_display_for(spec) -> BrainDisplay:
    """The display data for the brain of a mechanism set (what the lite bundle stores for each brain)."""
    brain = get_brain(spec)
    sid, sxyz = all_somata()
    ids = brain.body_ids
    j = np.clip(np.searchsorted(sid, ids), 0, len(sid) - 1)
    has = sid[j] == ids
    xyz = np.full((len(ids), 3), np.nan)
    xyz[has] = sxyz[j[has]]
    if (~has).any():
        xyz[~has] = terminal_positions(ids[~has])
    table, order = G.load_groups(), list(G.load_groups())
    groups, grouped, proxied = {}, np.zeros(len(ids), bool), []
    for name in order:                                    # groups.yaml order
        m = brain.masks.get(name)
        if m is None:
            continue
        grouped |= m
        g = table[name]
        groups[name] = GroupDisplay(name, g.role, g.colour, order.index(name), ids[m], xyz[m])
        if (~has[m]).any():
            proxied.append(name)
    return BrainDisplay(all_xyz=sxyz, groups=groups, other_xyz=xyz[~grouped], other_colour=G.other_colour(),
                        n_neurons=len(ids), placed_by_terminal=tuple(proxied), display=G._table().get("display", {}))
