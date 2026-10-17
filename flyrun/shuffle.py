"""Part 5 control: degree-preserving, sign-preserving shuffle of W_steer.
W[i, j] is the weight j -> i (drive_i = sum_j W[i, j] h_j), so column j is neuron j's outgoing edges.
Double edge swap: take two edges (r1, c1), (r2, c2) and exchange their TARGETS -> (r2, c1), (r1, c2).
Every edge keeps its source column and its weight, so each neuron keeps its out-degree, in-degree
and the sign (and weight multiset) of its outgoing edges. Swaps that would create a self-loop or a
duplicate edge are skipped. python -m flyrun.shuffle --legacy -> tutorials/_cache/W_steer_shuf0.npy  (Part 5; NOT row-normalised, see below)

Part 6b (audit 006 #1): the Part 5 shuffle moved already-normalised weights between rows, so row sums ran
0.006-3.55 instead of 1.0 and a TTMn row (one input, weight 1.0) was handed a ~0.05 edge. That confounded
"fine wiring" with "input normalisation". The fair control shuffles the SYNAPSE-COUNT matrix and then rebuilds
W exactly as tutorials/20_steering.ipynb Step 3 built W_steer: W = (counts / row_sum) * sign(source column).
Same degree sequence, same source signs, every row with inputs sums to |1|.
python -m flyrun.shuffle -> tutorials/_cache/W_steer_shuf{0..4}_rn.npy + runs/007_shuffle_feeders.json"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from .brain import CACHE


def degree_shuffle(W, seed=0, sweeps=20):
    rng = np.random.default_rng(seed)
    S = W.copy()
    r, c = np.nonzero(S)
    n_edges = len(r)
    done = 0
    for _ in range(sweeps * n_edges):
        i, j = rng.integers(n_edges, size=2)
        r1, c1, r2, c2 = r[i], c[i], r[j], c[j]
        if r1 == r2 or c1 == c2 or r2 == c1 or r1 == c2:   # same row/col is a no-op; no self loops
            continue
        if S[r2, c1] != 0 or S[r1, c2] != 0:               # no duplicate edges
            continue
        w1, w2 = S[r1, c1], S[r2, c2]
        S[r1, c1] = S[r2, c2] = 0.0
        S[r2, c1], S[r1, c2] = w1, w2
        r[i], r[j] = r2, r1
        done += 1
    return S, done


def build_W(counts, signs):
    """The exact rule of tutorials/20_steering.ipynb Step 3: row-normalise counts, signed by the source cell."""
    row_sum = counts.sum(axis=1, keepdims=True)
    return np.divide(counts, row_sum, out=np.zeros_like(counts), where=row_sum > 0) * signs[np.newaxis, :]


def load_counts(cache=CACHE):
    """-> (synapse-count matrix, source signs, bodies). Rebuilt from steer_edges.parquet; build_W(counts, signs)
    must reproduce W_steer.npy exactly (asserted)."""
    bodies = pd.read_parquet(Path(cache) / "steer_bodies.parquet")
    edges = pd.read_parquet(Path(cache) / "steer_edges.parquet")
    order = bodies["bodyId"].to_numpy(np.int64)
    idx = {int(b): i for i, b in enumerate(order)}
    counts = np.zeros((len(order), len(order)))
    for r in edges.itertuples(index=False):
        if int(r.body_pre) in idx and int(r.body_post) in idx:
            counts[idx[int(r.body_post)], idx[int(r.body_pre)]] += r.weight
    signs = bodies["sign"].to_numpy(float)
    assert np.allclose(build_W(counts, signs), np.load(Path(cache) / "W_steer.npy"), atol=1e-12),         "count matrix does not rebuild W_steer"
    return counts, signs, bodies


def renormalised_shuffle(seed, cache=CACHE):
    """-> (W_shuf_rn, swaps). Degree + source-sign preserving edge swap on the counts, then build_W."""
    counts, signs, _ = load_counts(cache)
    cs, done = degree_shuffle(counts, seed=seed)
    return build_W(cs, signs), done


LOOMING = ("LC4", "LPLC2")   # the two looming detector types the stimulus is injected into


def ttmn_feeders(W, bodies):
    """For each TTMn: who feeds it (type, side, weight) and whether that cell is a looming detector."""
    t = bodies["type"].to_numpy()
    out = []
    for i in np.where(t == "TTMn")[0]:
        src = [dict(source=int(j), type=str(t[j]), side=str(bodies["somaSide"].fillna("").iloc[j]),
                    weight=round(float(W[i, j]), 4), looming_detector=bool(t[j] in LOOMING))
               for j in np.nonzero(W[i])[0]]
        out.append(dict(ttmn=int(i), feeders=src))
    return out


def main_rn(seeds=range(5)):
    counts, signs, bodies = load_counts()
    W = np.load(CACHE / "W_steer.npy")
    rep = {"real": ttmn_feeders(W, bodies)}
    for sd in seeds:
        S, done = renormalised_shuffle(sd)
        np.save(CACHE / f"W_steer_shuf{sd}_rn.npy", S)
        rep[f"shuf{sd}_rn"] = ttmn_feeders(S, bodies)
        print("seed", sd, "swaps", done, "edges kept in place", int(((W != 0) & (S != 0)).sum()),
              "row |sum| min/max", round(float(np.abs(S).sum(1).min()), 6), round(float(np.abs(S).sum(1).max()), 6),
              "TTMn feeders", [[(f["type"], f["looming_detector"]) for f in r["feeders"]] for r in rep[f"shuf{sd}_rn"]])
    (Path(__file__).resolve().parent / "runs" / "007_shuffle_feeders.json").write_text(json.dumps(rep, indent=1))


def main():
    W = np.load(CACHE / "W_steer.npy")
    S, done = degree_shuffle(W, seed=0)
    np.save(CACHE / "W_steer_shuf0.npy", S)
    print("swaps", done, "edges", int((W != 0).sum()), "edges kept in place",
          int(((W != 0) & (S != 0) & (W == S)).sum()))


if __name__ == "__main__":
    if "--legacy" in sys.argv:
        main()
    else:
        main_rn()
