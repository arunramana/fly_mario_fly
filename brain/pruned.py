# What this file does, in plain English:
# A faster VIEW of the fly brain for runs that only read a few output groups. It keeps exactly the neurons that can
# influence what the run reads (every neuron with a path of synapses to an output group or to a visual input group) and
# drops the rest, so the matrix multiply has fewer rows. Dropping a neuron that cannot reach anything the run reads
# cannot change a single number the run reports, and the noise is still drawn for the full population and then sliced, so
# the random stream is the same one. It never adds current and never touches the committed network or its hash.
"""brain/pruned.py -- docs/SPEC_fast_iteration.md step 3.

Exactness (checked by tests/test_fast_iteration.py and scripts/bench_batch.py digests, not assumed):
  * keep = the closure of the read set under "has a synapse onto a kept neuron" (ancestors). So no dropped neuron has an edge
    into a kept row: the kept rows' non-zeros are the same numbers in the same order, and the float sums are identical.
  * the noise is drawn for all `n_full` neurons each substep and sliced to the kept ones, so the generator state is unchanged.
A neuron that is noise-driven AND projects (through any path) to a read neuron is an ancestor and is kept: only neurons with
no path to the read set are removed. Nothing is approximated.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import scipy.sparse as sp

from brain.builder import BuiltNetwork
from fly.network.dynamics import NoiseConfig

# What E1/E2a/B11 read or stimulate: the output tier (motor map, GF membrane) and the visual inputs the mechanisms drive and
# the telemetry averages (LC4, LPLC2, LC10a). Everything else only matters if it can reach one of these.
READ_POPULATIONS = ("GF", "TTMn", "DNp09", "DNa01", "DNa02", "MDN", "LC4", "LPLC2", "LC10a")


@dataclass
class PrunedView:
    """What a pruned network remembers about the full one."""
    full_hash: str
    n_full: int
    keep: np.ndarray = field(repr=False)          # indices into the full network, ascending

    def noise(self, sigma: float, rng: np.random.Generator) -> "SlicedNoise":
        return SlicedNoise(sigma, rng, self.n_full, self.keep)

    def summary(self) -> dict:
        return {"pruned": True, "full_hash": self.full_hash, "neurons_full": int(self.n_full), "neurons_kept": int(len(self.keep))}


class SlicedNoise(NoiseConfig):
    """The full network's membrane noise, restricted to the kept neurons: draws n_full values, returns the kept ones."""

    def __init__(self, sigma: float, rng: np.random.Generator, n_full: int, keep: np.ndarray):
        super().__init__(sigma, rng)
        self.n_full, self.keep = n_full, keep

    def sample(self, k: int):
        if self.sigma == 0.0:
            return 0.0
        assert k == len(self.keep)
        return self.rng.normal(0.0, self.sigma, size=self.n_full)[self.keep]


def ancestors(W: sp.csr_matrix, targets: np.ndarray) -> np.ndarray:
    """Boolean mask of every neuron with a directed path (any number of hops) of non-zero weights onto a target, targets included."""
    n = W.shape[0]
    A = W.copy()
    A.data = np.ones_like(A.data)
    A.eliminate_zeros()
    # W[j, i] != 0 means i drives j, so the ancestors of a set S are the columns of the rows in S: A.T @ indicator(S).
    At = A.T.tocsr()
    keep = np.zeros(n, dtype=bool)
    keep[targets] = True
    front = keep.copy()
    while front.any():
        reach = (At @ front.astype(np.float64)) > 0
        front = reach & ~keep
        keep |= front
    return keep


def prune_network(net: BuiltNetwork, read: tuple[str, ...] = READ_POPULATIONS) -> BuiltNetwork:
    """The view of `net` that keeps only the ancestors of the populations in `read` (see the module docstring)."""
    if net.view is not None:
        return net
    targets = np.concatenate([net.pops[p] for p in read if p in net.pops])
    mask = ancestors(net.W, targets)
    keep = np.flatnonzero(mask)
    remap = np.full(net.n_neurons, -1, dtype=np.int64)
    remap[keep] = np.arange(len(keep))
    pops = {name: remap[idx][remap[idx] >= 0] for name, idx in net.pops.items()}
    for p in read:
        assert len(pops[p]) == len(net.pops[p]), f"{p}: a read population lost members in the prune"
    edge_ok = (remap[net.pre] >= 0) & (remap[net.post] >= 0)
    W = net.W[keep][:, keep].tocsr()
    W.sort_indices()
    return BuiltNetwork(net.ids[keep], net.side[keep], net.signs[keep], pops, remap[net.pre[edge_ok]], remap[net.post[edge_ok]],
                        net.syn[edge_ok], net.total_in[keep], net.rule, W=W, insub=net.insub[keep], twin_of=net.twin_of,
                        view=PrunedView(net.build_hash(), net.n_neurons, keep))
