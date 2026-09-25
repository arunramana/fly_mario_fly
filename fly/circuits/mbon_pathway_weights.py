# What this file does, in plain English:
# Works out, from the real connectome, how strongly each mushroom-body output
# neuron (MBON) reaches each motor pathway (jump, long jump, speed, backing up)
# through the neurons in between, so learning can act on those pathways. The
# slow one-time database pass is cached to disk.
"""fly/circuits/mbon_pathway_weights.py -- per-MBON effective weights onto DNp01,
DLMn, DNp09 and MDN: direct MBON->target synapses plus two-hop
MBON->X->target paths (sum of w1*w2 over intermediates X), normalised so each
target's weights sum to 1. Counts from docs/CONTROL_AUDIT.md / the sprint's
connectome query (only DNa02 and MDN are direct; jump/speed are two-hop).
Streams the weights file once (~25 s) and caches to ../data/derived.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)
CACHE = Path(__file__).resolve().parents[3] / "data" / "derived" / "mbon_readout_weights.npz"
GROUPS = {"dnp01": r"^DNp01$", "dlmn": r"^DLMn", "dnp09": r"^DNp09$", "mdn": r"^MDN$"}


def _compute(mbon_ids: np.ndarray) -> dict[str, np.ndarray]:
    import pandas as pd
    import mcns
    ann = mcns.load_annotations()
    types = ann["type"].astype(str)
    gid = {}
    for g, pat in GROUPS.items():
        for b in ann.loc[types.str.match(pat), "bodyId"]:
            gid[int(b)] = g
    targets = np.array(list(gid))
    keep = []
    for pre, post, w in mcns._edge_batches():
        m = np.isin(pre, mbon_ids) | np.isin(post, targets)
        if m.any():
            keep.append(pd.DataFrame({"pre": pre[m], "post": post[m], "w": w[m].astype(float)}))
    E = pd.concat(keep, ignore_index=True)
    out = E[E.pre.isin(mbon_ids)]
    into = E[E.post.isin(targets) & ~E.pre.isin(mbon_ids)]
    into = into.assign(group=into.post.map(gid))
    direct = out[out.post.isin(targets)].assign(group=lambda d: d.post.map(gid))
    index = {int(b): i for i, b in enumerate(mbon_ids)}
    result = {g: np.zeros(len(mbon_ids)) for g in GROUPS}
    for row in direct.itertuples():
        result[row.group][index[int(row.pre)]] += row.w
    hop = out.rename(columns={"post": "mid", "w": "w1"})[["pre", "mid", "w1"]].merge(
        into.rename(columns={"pre": "mid", "w": "w2"})[["mid", "group", "w2"]], on="mid")
    hop["path"] = hop.w1 * hop.w2
    for (g, pre), val in hop.groupby(["group", "pre"])["path"].sum().items():
        result[g][index[int(pre)]] += val
    for g in result:
        total = result[g].sum()
        result[g] = result[g] / total if total > 0 else np.full(len(mbon_ids), 1.0 / len(mbon_ids))
    return result


def load_readout_weights(mbon_ids) -> dict[str, np.ndarray]:
    """{group: weights over `mbon_ids` (sum 1)}; computed once, then cached."""
    mbon_ids = np.asarray(mbon_ids, dtype=np.int64)
    if CACHE.exists():
        z = np.load(CACHE)
        if np.array_equal(z["mbon_ids"], mbon_ids):
            return {g: z[g] for g in GROUPS}
    log.info("computing MBON readout weights (one streaming pass)...")
    result = _compute(mbon_ids)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    np.savez(CACHE, mbon_ids=mbon_ids, **result)
    return result
