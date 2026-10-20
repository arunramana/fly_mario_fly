"""Soma positions from the MaleCNS annotation file, cached under $FLY_MARIO_DATA/derived.

The runner does not expose positions, so this reads the data file directly (pyarrow only).
JO / ORN neurons have no soma in MaleCNS (cell bodies sit in the antenna), so they are drawn at the
synapse-weighted mean position of the brain somata of their postsynaptic partners: a proxy for their terminals.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.feather as pf

FOLDER = "malecns_v1.0"
ANNOT = "body-annotations-male-cns-v1.0-minconf-0.5.feather"
WEIGHTS = "connectome-weights-male-cns-v1.0-minconf-0.5.feather"
BRAIN_Z_MAX = 50000


def data_dir() -> Path:
    return Path(os.environ["FLY_MARIO_DATA"])


def all_somata() -> tuple:
    """(body ids, (N, 3) voxel xyz) of every neuron that has a soma location (141,781), sorted by id."""
    cache = data_dir() / "derived" / "render_somata.npz"
    if cache.exists():
        z = np.load(cache)
        return z["ids"], z["xyz"]
    t = pf.read_table(data_dir() / FOLDER / ANNOT, columns=["bodyId", "somaLocation"]).to_pandas()
    t = t.dropna(subset=["somaLocation"])
    ids, xyz = t.bodyId.to_numpy().astype(np.int64), np.stack(t.somaLocation.to_numpy()).astype(np.float32)
    o = np.argsort(ids)
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez(cache, ids=ids[o], xyz=xyz[o])
    return ids[o], xyz[o]


def terminal_positions(body_ids) -> np.ndarray:
    """Positions for bodies with no soma: the synapse-weighted mean soma of their brain partners (nan if none)."""
    body_ids = np.asarray(body_ids, dtype=np.int64)
    if len(body_ids) == 0:
        return np.zeros((0, 3))
    cache = data_dir() / "derived" / "render_terminals.npz"
    if cache.exists():
        z = np.load(cache)
        have = dict(zip(z["ids"].tolist(), z["xyz"]))
        if all(int(b) in have for b in body_ids):
            return np.array([have[int(b)] for b in body_ids])
    sid, sxyz = all_somata()
    sxyz = sxyz.astype(np.float64)
    want = np.sort(body_ids)
    acc = {int(b): np.zeros(4) for b in body_ids}
    rd = pa.ipc.open_file(pa.memory_map(str(data_dir() / FOLDER / WEIGHTS)))
    for i in range(rd.num_record_batches):                  # streamed: the weights file is never loaded whole
        b = rd.get_batch(i)
        pre = b.column("body_pre").to_numpy()
        m = np.isin(pre, want)
        if not m.any():
            continue
        pre, post = pre[m], b.column("body_post").to_numpy()[m]
        w = b.column("weight").to_numpy()[m].astype(np.float64)
        j = np.clip(np.searchsorted(sid, post), 0, len(sid) - 1)
        ok = (sid[j] == post) & (sxyz[j, 2] < BRAIN_Z_MAX)
        for p, jj, ww in zip(pre[ok], j[ok], w[ok]):
            a = acc[int(p)]
            a[:3] += ww * sxyz[jj]
            a[3] += ww
    xyz = np.array([acc[int(b)][:3] / acc[int(b)][3] if acc[int(b)][3] > 0 else [np.nan] * 3 for b in body_ids])
    np.savez(cache, ids=body_ids, xyz=xyz)
    return xyz
