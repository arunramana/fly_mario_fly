"""Part AV1 brain: the 881-neuron M2 brain (W_steer_jo_orn) + the L2c DC4 -> MDN set (26 neurons: 13 ORN_DC4, 9 intermediates, 4 MDN), built by the same rule (o0_sim.build:
base rows keep their W_steer edges, an edge with a new endpoint needs >= 5 synapses, rows are normalised by their in-network input, signed by the presynaptic transmitter).
The old brain files stay: saves tutorials/_cache/W_steer_jo_orn_sour.npy + steer_jo_orn_sour_bodies.parquet.   python -m flyrun.av1_brain"""
import json

import numpy as np
import pandas as pd

from . import o0_sim as S
from .brain import CACHE


def main():
    st = set(S.ST.bodyId.astype(int))
    cur = pd.read_parquet(CACHE / "steer_jo_orn_bodies.parquet")
    old_extra = [int(b) for b in cur.bodyId if int(b) not in st]
    adds = json.load(open(S.OUT / "L2c_adds.json"))["smell DC4 (acid, Ir64a)"]
    assert len(adds) == 26, len(adds)
    # sanity: rebuilding the old brain reproduces the file the production runs load
    W0, b0 = S.build(old_extra)
    old = np.load(CACHE / "W_steer_jo_orn.npy")
    assert W0.shape == old.shape and np.allclose(W0, old), "the rebuild of the 881 brain differs from W_steer_jo_orn.npy"
    W, bodies, Wc, sign = S.build(old_extra + adds, return_counts=True)
    # o0_sim.build also keeps every >= 5-synapse edge from a new neuron onto an OLD one (DNpe023 alone puts 322 synapses on DNa02, 171 on DNp09, 9 on the Giant Fiber), which renormalises those rows
    # and changed the old behaviour (7/10 on 1-1 HOLDOUT, no mushroom eaten; even keeping only the 4 old k/N members moved the smell steering). The sour branch is therefore READ-ONLY: edges old -> new
    # and new -> new are kept, new -> old are dropped, so every old row is exactly as before. MDN responds identically without them (steady MDN at level 20: 0.264 with and without; runs/AV1.md).
    n0 = old.shape[0]
    Wc[:n0, n0:] = 0.0
    rs = Wc.sum(1, keepdims=True)
    W = np.divide(Wc, rs, out=np.zeros_like(Wc), where=rs > 0) * sign[None, :]
    np.save(CACHE / "W_steer_jo_orn_sour.npy", W)
    out = pd.DataFrame(dict(bodyId=bodies.bodyId, type=bodies.type, somaSide=bodies.side, sign=sign))
    st_b = pd.read_parquet(CACHE / "steer_bodies.parquet")
    out["nt"] = list(st_b.nt) + [""] * (len(out) - len(st_b))
    out.to_parquet(CACHE / "steer_jo_orn_sour_bodies.parquet", index=False)
    print("sour brain", W.shape, "(old", old.shape, ") new types:", out.iloc[len(cur):].type.value_counts().to_dict())
    # how much the existing rows moved (row normalisation): rows of the old neurons, old columns
    n0 = old.shape[0]
    d = np.abs(W[:n0, :n0] - old)
    print("old block max |dW|", d.max(), "rows changed", int((d.max(1) > 1e-12).sum()), [(out.type[i], round(float(d[i].max()), 4)) for i in np.argsort(-d.max(1))[:6]])


if __name__ == "__main__":
    main()
