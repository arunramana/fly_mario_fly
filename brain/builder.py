# What this file does, in plain English:
# Builds the one network the redesigned fly brain runs on, by one rule that is
# saved with it. It streams the connectome's weight file once to collect every
# well-supported connection, keeps every neuron that sits on a short path
# between the senses and the outputs (plus the whole mushroom body), turns
# synapse counts into signed strengths, and can make a randomly rewired twin
# with the same numbers for the control.
"""brain/builder.py -- docs/SPEC_brain_core.md section 3.

Reuses mcns (streaming loader), fly.connectome.circuit (signs table, shuffle) and the weight recipe of
circuit.build_weight_matrix, in sparse form (a 15k x 15k dense matrix is 1.8 GB). Never loads the weights file whole.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.sparse.linalg import eigs

from fly.connectome import circuit
from brain.manifest import Manifest, side_of

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
import mcns  # noqa: E402

CACHE_DIR = mcns.DERIVED
OTHER_BODY = -1
SHUFFLE_MODES = ("degree", "class")


@dataclass
class EdgeTable:
    """Every connection with >= `min_synapses` synapses whose two ends are both annotated bodies, plus each
    annotated body's TRUE total input (summed over all rows, any presynaptic partner)."""
    ids: np.ndarray            # sorted annotated bodyIds
    pre: np.ndarray            # index into ids
    post: np.ndarray
    w: np.ndarray              # synapse count
    total_in: np.ndarray       # per annotated body


def stream_edge_table(min_synapses: int, ann_ids: np.ndarray, cache: bool = True) -> EdgeTable:
    """One streaming pass over the weights file in Arrow record batches (mcns._edge_batches)."""
    path = CACHE_DIR / f"brain_edges_N{min_synapses}.npz"
    ids = np.sort(ann_ids.astype(np.int64))
    if cache and path.exists():
        d = np.load(path)
        if len(d["ids"]) == len(ids) and (d["ids"] == ids).all():
            return EdgeTable(ids, d["pre"], d["post"], d["w"], d["total_in"])
    n = len(ids)
    total_in = np.zeros(n, dtype=np.float64)
    keep_pre, keep_post, keep_w = [], [], []
    seen, t0 = 0, time.time()
    for pre, post, w in mcns._edge_batches():
        ip = np.clip(np.searchsorted(ids, pre), 0, n - 1)
        iq = np.clip(np.searchsorted(ids, post), 0, n - 1)
        ok_pre, ok_post = ids[ip] == pre, ids[iq] == post
        if ok_post.any():
            total_in += np.bincount(iq[ok_post], weights=w[ok_post].astype(np.float64), minlength=n)
        m = ok_pre & ok_post & (w >= min_synapses)
        keep_pre.append(ip[m].astype(np.int32))
        keep_post.append(iq[m].astype(np.int32))
        keep_w.append(w[m].astype(np.int32))
        seen += len(pre)
        sys.stdout.write(f"\r  {seen:,} rows ({seen / max(time.time() - t0, 1e-6) / 1e6:.1f} M/s)   ")
    sys.stdout.write("\n")
    table = EdgeTable(ids, np.concatenate(keep_pre), np.concatenate(keep_post), np.concatenate(keep_w), total_in)
    if cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        np.savez(path, ids=ids, pre=table.pre, post=table.post, w=table.w, total_in=total_in)
    return table


def _hop_distance(adj_t: sp.csr_matrix, sources: np.ndarray, max_k: int) -> np.ndarray:
    """Hop count from `sources` along the edges whose transpose is `adj_t` (rows = destination); 99 = not within max_k."""
    n = adj_t.shape[0]
    dist = np.full(n, 99, dtype=np.int16)
    dist[sources] = 0
    front = np.zeros(n, dtype=np.float32)
    front[sources] = 1.0
    seen = np.zeros(n, dtype=bool)
    seen[sources] = True
    for hop in range(1, max_k + 1):
        nxt = (adj_t @ front) > 0
        nxt &= ~seen
        if not nxt.any():
            break
        dist[nxt] = hop
        seen |= nxt
        front = nxt.astype(np.float32)
    return dist


def path_union(table: EdgeTable, pops: dict[str, np.ndarray], manifest: Manifest) -> np.ndarray:
    """Indices (into table.ids) of every neuron on a walk of <= k hops from a segment's sources to its targets,
    for any segment, plus every neuron of the manifest's whole populations. Sign-agnostic (topology only)."""
    n = len(table.ids)
    fwd = sp.csr_matrix((np.ones(len(table.pre), np.float32), (table.pre, table.post)), shape=(n, n))
    fwd_t, bwd_t = fwd.T.tocsr(), fwd          # forward step = fwd.T @ frontier; backward step = fwd @ frontier
    to_idx = lambda names: np.concatenate([np.searchsorted(table.ids, pops[nm]) for nm in names] + [np.empty(0, np.int64)])
    keep = np.zeros(n, dtype=bool)
    for seg in manifest.segments:
        d_from = _hop_distance(fwd_t, to_idx(seg.sources), manifest.k)
        d_to = _hop_distance(bwd_t, to_idx(seg.targets), manifest.k)
        keep |= d_from.astype(int) + d_to.astype(int) <= manifest.k
    keep[to_idx(manifest.whole)] = True
    return np.flatnonzero(keep)


def signs_for(body_ids: np.ndarray) -> np.ndarray:
    """Dale's law, one sign per presynaptic body from consensus_nt (circuit.NT_SIGN); 0 = unknown, dropped as a source."""
    nt = mcns.load_neurotransmitters().rename(columns={"body": "bodyId"})[["bodyId", "consensus_nt"]]
    merged = pd.DataFrame({"bodyId": body_ids}).merge(nt, on="bodyId", how="left")
    return merged["consensus_nt"].str.lower().map(circuit.NT_SIGN).fillna(0.0).to_numpy()


def weight_matrix(n: int, pre: np.ndarray, post: np.ndarray, syn: np.ndarray, signs: np.ndarray):
    """circuit.build_weight_matrix, sparse: W[j, i] = sign_i * synapses_ij / (in-network input of j).
    Returns (W csr post x pre, in-network input per neuron)."""
    insub = np.bincount(post, weights=syn.astype(np.float64), minlength=n)
    val = signs[pre] * syn / np.maximum(insub[post], 1.0)
    keep = val != 0.0
    W = sp.csr_matrix((val[keep], (post[keep], pre[keep])), shape=(n, n), dtype=np.float64)
    return W, insub


def spectral_radius(W: sp.csr_matrix, g: float = 1.0) -> float:
    """Largest |eigenvalue| of g*W (sparse ARPACK; dense eigvals for tiny matrices)."""
    if W.shape[0] < 400:
        return circuit.spectral_radius(W.toarray(), g)
    vals = eigs(W, k=6, which="LM", return_eigenvectors=False, tol=1e-6, maxiter=5000,
                v0=np.ones(W.shape[0]) / np.sqrt(W.shape[0]))
    return float(np.max(np.abs(vals)) * abs(g))


@dataclass
class BuiltNetwork:
    """One brain: neurons, signed sparse weights, populations, and the rule that built it."""
    ids: np.ndarray
    side: np.ndarray
    signs: np.ndarray
    pops: dict[str, np.ndarray]            # name -> indices into ids
    pre: np.ndarray                        # edge list (indices into ids), unsigned synapse counts in `syn`
    post: np.ndarray
    syn: np.ndarray
    total_in: np.ndarray                   # true whole-connectome input per neuron
    rule: dict
    W: sp.csr_matrix = field(default=None, repr=False)
    insub: np.ndarray = field(default=None, repr=False)
    twin_of: dict | None = None            # shuffle provenance, None for the real network

    def __post_init__(self):
        if self.W is None:
            self.W, self.insub = weight_matrix(len(self.ids), self.pre, self.post, self.syn, self.signs)

    @property
    def n_neurons(self) -> int:
        return len(self.ids)

    @property
    def n_edges(self) -> int:
        return self.W.nnz

    def build_hash(self) -> str:
        h = hashlib.sha256(json.dumps(self.rule, sort_keys=True).encode())
        for a in (self.ids, self.pre, self.post, self.syn):
            h.update(np.ascontiguousarray(a).tobytes())
        return h.hexdigest()[:16]

    def local(self, body_ids: np.ndarray) -> np.ndarray:
        """Indices into the network for bodyIds (all must be present)."""
        idx = np.clip(np.searchsorted(self.ids, body_ids), 0, len(self.ids) - 1)
        assert (self.ids[idx] == body_ids).all(), "bodyId not in the network"
        return idx

    def shuffled(self, seed: int, mode: str = "degree") -> "BuiltNetwork":
        """The control: same neurons, same signs, same in/out edge counts, edges rewired at random
        (circuit.shuffle_edges, then the identical normalisation). mode "class" (docs/SPEC_phase3.md section 5) permutes
        the post column only among edges whose post neuron is in the same tier group (an output or sensory population by
        name, KC, MBON, DAN, or interior), so random wiring cannot land input on an output cell that has few inputs."""
        if mode not in SHUFFLE_MODES:
            raise ValueError(f"shuffle mode {mode!r} not in {SHUFFLE_MODES}")
        e = pd.DataFrame({"body_pre": self.pre, "body_post": self.post, "weight": self.syn})
        if mode == "degree":
            post = circuit.shuffle_edges(e, seed=seed)["body_post"].to_numpy()
        else:
            post = self.post.copy()
            rng = np.random.default_rng(seed)
            group = self.tier_groups()[self.post]
            for g in np.unique(group):
                rows = np.flatnonzero(group == g)
                post[rows] = self.post[rows[rng.permutation(len(rows))]]
        return BuiltNetwork(self.ids, self.side, self.signs, self.pops, self.pre, post,
                            self.syn, self.total_in, self.rule,
                            twin_of={"seed": seed, "real_hash": self.build_hash(), "mode": mode})

    def tier_groups(self) -> np.ndarray:
        """Group label per neuron: its (first) manifest population, or -1 for interior neurons."""
        group = np.full(self.n_neurons, -1, dtype=np.int64)
        for k, idx in enumerate(self.pops.values()):
            group[idx] = k
        return group

    def edge_report(self) -> dict:
        """Both edge counts, and what dropping unknown-transmitter neurons as sources did. `built_edges` are the
        connections kept by the rule; `nonzero_weights` are those with a sign (a neuron of unknown transmitter has sign 0,
        so its outgoing edges carry no weight). `edges` elsewhere in the stamp is the non-zero count."""
        unk = self.signs == 0
        return {"built_edges": int(len(self.pre)), "nonzero_weights": int(self.n_edges),
                "unknown_transmitter_neurons": int(unk.sum()),
                "unknown_transmitter_by_population": {k: int(unk[v].sum()) for k, v in self.pops.items() if unk[v].any()},
                "edges_dropped_unknown_source": int(unk[self.pre].sum())}

    def summary(self) -> dict:
        return {"build_hash": self.build_hash(), "neurons": self.n_neurons, "edges": self.n_edges,
                "excitatory_sources": int((self.signs > 0).sum()), "inhibitory_sources": int((self.signs < 0).sum()),
                "unsigned_sources": int((self.signs == 0).sum()), "rule": self.rule}

    def save(self, path: Path) -> None:
        np.savez_compressed(path, ids=self.ids, side=self.side, signs=self.signs, pre=self.pre, post=self.post,
                            syn=self.syn, total_in=self.total_in, rule=json.dumps(self.rule),
                            **{f"pop__{k}": v for k, v in self.pops.items()})

    @classmethod
    def load(cls, path: Path) -> "BuiltNetwork":
        d = np.load(path, allow_pickle=False)
        pops = {k[5:]: d[k] for k in d.files if k.startswith("pop__")}
        return cls(d["ids"], d["side"], d["signs"], pops, d["pre"], d["post"], d["syn"], d["total_in"],
                   json.loads(str(d["rule"])))


def build(manifest: Manifest | None = None, cache: bool = True) -> BuiltNetwork:
    """The unified network: streams the weights file once (cached under data/derived/ afterwards)."""
    manifest = manifest or Manifest()
    ann = mcns.load_annotations(["bodyId", "type", "instance", "class", "superclass", "somaSide", "rootSide"])
    pops_body = manifest.resolve(ann)
    table = stream_edge_table(manifest.min_synapses, ann["bodyId"].to_numpy(), cache)
    nodes = path_union(table, pops_body, manifest)
    remap = np.full(len(table.ids), OTHER_BODY, dtype=np.int64)
    remap[nodes] = np.arange(len(nodes))
    inside = (remap[table.pre] >= 0) & (remap[table.post] >= 0)
    ids = table.ids[nodes]
    ann_i = ann.set_index("bodyId").loc[ids].reset_index()
    # A population keeps the members that lie on a path; the ones that do not are counted, not hidden.
    pops = {nm: np.searchsorted(ids, b[np.isin(b, ids)]) for nm, b in pops_body.items()}
    rule = manifest.rule()
    net = BuiltNetwork(
        ids=ids, side=side_of(ann_i), signs=signs_for(ids), pops=pops,
        pre=remap[table.pre[inside]].astype(np.int64), post=remap[table.post[inside]].astype(np.int64),
        syn=table.w[inside].astype(np.int64), total_in=table.total_in[nodes], rule=rule)
    rule["counts"] = {"neurons": net.n_neurons, "edges": net.n_edges,
                      "populations_in_network": {nm: int(len(i)) for nm, i in pops.items()},
                      "members_not_on_a_path": {nm: int(len(b) - len(pops[nm])) for nm, b in pops_body.items()}}
    return net


def default_path() -> Path:
    return CACHE_DIR / "brain_k3_N5_p3.npz"     # Phase 3: LC10a in the manifest (the Phase 1 file brain_k3_N5.npz is kept)


def load_or_build(path: Path | None = None) -> BuiltNetwork:
    """The saved brain (rule, k, N and counts inside), or build and save it."""
    path = path or default_path()
    if path.exists():
        return BuiltNetwork.load(path)
    net = build()
    net.save(path)
    return net


if __name__ == "__main__":
    n = build()
    n.save(default_path())
    print(json.dumps(n.summary(), indent=1, default=str)[:3000])
