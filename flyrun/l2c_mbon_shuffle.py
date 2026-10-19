"""Part L2c: re-check 'MBON -> MDN is 2.7x the shuffle'. Degree-preserving shuffle = the post column permuted among all N5 edges (every neuron keeps its in- and out-edge counts and weights).
Metric: direct MBON->MDN synapses, and |signed 2-hop mass| MBON -> MDN. 20 shuffles. python -m flyrun.l2c_mbon_shuffle -> runs/L2c_mbon_shuffle.json"""
import json
from pathlib import Path

import numpy as np
import scipy.sparse as sp

from . import o0_sim as S

n = len(S.IDS)
MB = np.char.startswith(S.TYPES, "MBON")
MDN = S.TYPES == "MDN"


def metrics(post):
    # in-weight normalisation kept per post neuron (total_in of the post stays the same, as the real neuron's input does)
    Wc = sp.csr_matrix((S.WSYN, (post, S.PRE)), shape=(n, n))
    Wn = sp.csr_matrix((S.SIGNS[S.PRE] * S.WSYN / np.maximum(S.TOTAL_IN[post], 1.0), (post, S.PRE)), shape=(n, n))
    x = MB.astype(float)
    v1 = Wn @ x
    v2 = Wn @ v1
    return dict(direct_syn=float(Wc[np.flatnonzero(MDN)][:, np.flatnonzero(MB)].sum()), mass_h1=float(abs(v1[MDN].sum())), mass_h2=float(abs(v2[MDN].sum())))


real = metrics(S.POST)
rng = np.random.default_rng(0)
sh = [metrics(rng.permutation(S.POST)) for _ in range(20)]
out = dict(real=real, shuffled_mean={k: float(np.mean([s[k] for s in sh])) for k in real}, shuffled_max={k: float(np.max([s[k] for s in sh])) for k in real})
out["ratio"] = {k: out["real"][k] / max(out["shuffled_mean"][k], 1e-30) for k in real}
print(json.dumps(out, indent=1))
json.dump(out, open(Path(__file__).resolve().parent / "runs" / "L2c_mbon_shuffle.json", "w"), indent=1)
