# What this file does, in plain English:
# Works out, from the real connectome, how strongly the pC1 "arousal"
# neurons push on each neuron of the six simulated circuits: directly, and
# (optionally) through one in-between neuron. Each strength is the share of
# the target neuron's total input that comes from pC1. The one slow database
# pass is saved to disk so later runs load instantly.
"""fly/circuits/pc1_arousal_weights.py -- docs/SPEC_arousal_pc1.md.

Per circuit, over that circuit's neurons (in its loader's body order):
  direct[j] = synapses(pC1 -> j) / total input synapses of j
  hop[j]    = sum_X [synapses(pC1 -> X) / total input of X] * sign(X)
              * synapses(X -> j) / total input of j          (two-hop, Dale-signed)
`sign(X)` comes from consensus_nt via `fly.connectome.circuit.NT_SIGN`
(acetylcholine +1, GABA/glutamate -1, unknown 0). pC1 itself is cholinergic
(all 156 neurons), so the first hop is excitatory.

Streams the weights file twice (~90 s) and caches to ../data/derived/.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)
CACHE = Path(__file__).resolve().parents[3] / "data" / "derived" / "pc1_arousal_weights.npz"
CIRCUITS = ("jump", "steering", "takeoff", "speed", "mdn", "dnp02")


def _compute(circuit_ids: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    import pandas as pd
    import mcns
    from fly.connectome.circuit import NT_SIGN

    ann = mcns.load_annotations(["bodyId", "type"])
    pc1 = np.array(sorted(ann.loc[ann["type"].astype(str).str.match(r"^pC1"), "bodyId"]), dtype=np.int64)
    first = []
    for pre, post, w in mcns._edge_batches():
        m = np.isin(pre, pc1)
        if m.any():
            first.append(pd.DataFrame({"post": post[m], "w": w[m].astype(np.int64)}))
    to_x = pd.concat(first).groupby("post")["w"].sum()            # pC1 -> X synapses, summed over pC1 neurons
    x_ids = np.array(to_x.index, dtype=np.int64)
    circ = np.unique(np.concatenate(list(circuit_ids.values())))
    watch = np.union1d(circ, x_ids)

    tot_in: dict[int, int] = {}
    direct, hop = [], []
    for pre, post, w in mcns._edge_batches():
        w = w.astype(np.int64)
        m = np.isin(post, watch)
        if m.any():
            for k, v in pd.Series(w[m]).groupby(post[m]).sum().items():
                tot_in[k] = tot_in.get(k, 0) + int(v)
        in_circ = np.isin(post, circ)
        md = in_circ & np.isin(pre, pc1)
        if md.any():
            direct.append(pd.DataFrame({"post": post[md], "w": w[md]}))
        mh = in_circ & np.isin(pre, x_ids)
        if mh.any():
            hop.append(pd.DataFrame({"pre": pre[mh], "post": post[mh], "w": w[mh]}))
    tin = pd.Series(tot_in)
    d_sum = pd.concat(direct).groupby("post")["w"].sum().to_dict()
    nt = mcns.load_neurotransmitters().set_index("body")["consensus_nt"].str.lower()
    sign = nt.reindex(to_x.index).map(NT_SIGN).fillna(0.0)
    share = (to_x / tin.reindex(to_x.index)).fillna(0.0)          # fraction of X's input that is pC1
    H = pd.concat(hop)
    H["raw"] = H["pre"].map(share) * H["pre"].map(sign) * H["w"]
    h_sum = H.groupby("post")["raw"].sum().to_dict()

    out = {}
    for name, ids in circuit_ids.items():
        tot = np.array([float(tin.get(int(i), 0.0)) for i in ids])
        ok = tot > 0

        def norm(d):
            v = np.array([float(d.get(int(i), 0.0)) for i in ids])
            return np.where(ok, v / np.where(ok, tot, 1.0), 0.0)
        out[f"{name}_ids"] = ids.astype(np.int64)
        out[f"{name}_direct"] = norm(d_sum)
        out[f"{name}_hop"] = norm(h_sum)
    return out


def load_arousal_weights(circuit_ids: dict[str, np.ndarray]) -> dict[str, dict[str, np.ndarray]]:
    """{circuit: {"direct": vec, "hop": vec}}; computed once, then cached."""
    circuit_ids = {k: np.asarray(v, dtype=np.int64) for k, v in circuit_ids.items()}
    if CACHE.exists():
        z = np.load(CACHE)
        if all(f"{k}_ids" in z.files and np.array_equal(z[f"{k}_ids"], v) for k, v in circuit_ids.items()):
            return {k: {"direct": z[f"{k}_direct"], "hop": z[f"{k}_hop"]} for k in circuit_ids}
    log.info("computing pC1 arousal weights (two streaming passes)...")
    out = _compute(circuit_ids)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    np.savez(CACHE, **out)
    return {k: {"direct": out[f"{k}_direct"], "hop": out[f"{k}_hop"]} for k in circuit_ids}


def pc1_body_ids() -> np.ndarray:
    """The 156 pC1 neurons (the brain overlay's "pC1" population)."""
    import mcns
    ann = mcns.load_annotations(["bodyId", "type"])
    return np.array(sorted(ann.loc[ann["type"].astype(str).str.match(r"^pC1"), "bodyId"]), dtype=np.int64)
