"""Part Q1 brain: W_steer + the 20 JO neurons with a >= 5-synapse edge straight onto the Giant Fiber (13 JO-B1_a, 6 JO-B1_c, 1 JO-CA1). NOT the k/N expansion.
Built exactly as in O0 (flyrun/o0_sim.build: base block = the W_steer recipe on its own edges, edges touching a new neuron kept at >= 5 synapses, rows
normalised by in-network input, signed by the presynaptic transmitter). Saves tutorials/_cache/W_steer_jo.npy + steer_jo_bodies.parquet (the default
W_steer.npy / steer_bodies.parquet are untouched) and the 5 row-renormalised degree + sign shuffles of the SAME 656-neuron count matrix (JO rows / columns
shuffled with the same rule as Part 6b): W_steer_jo_shuf{0..4}_rn.npy.
python -m flyrun.q1_brain"""
import numpy as np
import pandas as pd

from . import o0_sim as S
from .brain import CACHE
from .shuffle import build_W, degree_shuffle


def jo20():
    jo = np.char.startswith(S.TYPES, "JO")
    sel = (S.TYPES[S.POST] == "DNp01") & jo[S.PRE]
    m = np.zeros(len(S.IDS), bool)
    m[S.PRE[sel]] = True
    return S.IDS[m]


def main():
    ids = jo20()
    assert len(ids) == 20
    W, bodies, counts, sign = S.build(list(ids), return_counts=True)
    assert np.allclose(build_W(counts, sign), W, atol=1e-12)
    np.save(CACHE / "W_steer_jo.npy", W)
    out = pd.DataFrame(dict(bodyId=bodies.bodyId, type=bodies.type, somaSide=bodies.side, sign=sign))
    st = pd.read_parquet(CACHE / "steer_bodies.parquet")
    out["nt"] = list(st.nt) + [""] * (len(out) - len(st))
    out.to_parquet(CACHE / "steer_jo_bodies.parquet", index=False)
    print("W_steer_jo", W.shape, "types of the 20:", pd.Series(bodies.type[-20:]).value_counts().to_dict())
    for seed in range(5):
        cs, done = degree_shuffle(counts, seed=seed)
        np.save(CACHE / f"W_steer_jo_shuf{seed}_rn.npy", build_W(cs, sign))
        print("shuffle", seed, "swaps", done)


if __name__ == "__main__":
    main()
