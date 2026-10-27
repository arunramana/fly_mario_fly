"""MaleCNS v1.0 (Janelia FlyEM) access: body ids, types, soma positions, transmitter signs, synapses.

Files live under $FLY_MARIO_FLY_DATA/malecns_v1.0/ and are downloaded there when missing. The 152M-row weights
file (3.6 GB uncompressed) is never loaded whole: it is streamed in Arrow record batches.
Derived aggregates are cached under $FLY_MARIO_FLY_DATA/derived/.
"""
from __future__ import annotations

import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np

from fly_mario_fly.fly.groups import type_counts

ENV_VAR = "FLY_MARIO_FLY_DATA"
GCS = "https://storage.googleapis.com/flyem-male-cns/v1.0/connectome-data/flat-connectome"
FILES = {
    "annotations": "body-annotations-male-cns-v1.0-minconf-0.5.feather",
    "neurotransmitters": "body-neurotransmitters-male-cns-v1.0.feather",
    "weights": "connectome-weights-male-cns-v1.0-minconf-0.5.feather",
}

# Dale's law: one sign per presynaptic neuron from its consensus transmitter; unknown = 0 (dropped as a source).
NT_SIGN = {"acetylcholine": 1.0, "dopamine": 1.0, "gaba": -1.0, "glutamate": -1.0}

# Verified against the downloaded data; a changed file fails loudly at load time (per-type counts: groups.yaml).
N_BODIES = 211_577
MIN_SYN = 5   # a connection to or from an added neuron needs this many synapses (the project's N = 5 rule)


def _arrow():
    """pyarrow, imported when the connectome files are actually read (a server that only runs cached brains never needs it)."""
    import pyarrow as pa
    import pyarrow.feather as feather
    return pa, feather


def data_dir() -> Path:
    root = os.environ.get(ENV_VAR)
    if not root:
        raise RuntimeError(f"set ${ENV_VAR} to the folder that holds the MaleCNS data and the brain caches")
    return Path(root)


def _human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:,.1f} {unit}"
        n /= 1024


def _download(url: str, dest: Path) -> None:
    """Resumable download (HTTP Range); public CC-BY 4.0 files, no auth."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=30) as r:
        total = int(r.headers["Content-Length"])
    have = dest.stat().st_size if dest.exists() else 0
    if have > total:
        dest.unlink()
        have = 0
    if have == total:
        return
    req = urllib.request.Request(url, headers={"Range": f"bytes={have}-"} if have else {})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "ab" if have else "wb") as f:
        if have and resp.status != 206:
            raise RuntimeError("server ignored the Range header; delete the partial file and retry")
        done = have
        while chunk := resp.read(1 << 20):
            f.write(chunk)
            done += len(chunk)
            sys.stdout.write(f"\r  {dest.name}: {_human(done)} / {_human(total)} ({_human((done - have) / (time.time() - t0 + 1e-6))}/s)  ")
    sys.stdout.write("\n")
    if dest.stat().st_size != total:
        raise RuntimeError(f"{dest.name}: got {dest.stat().st_size} bytes, expected {total}; re-run to resume")


def ensure_data(root: Path | None = None) -> Path:
    """Folder holding the three MaleCNS files; downloads (about 1.2 GB) whatever is missing."""
    folder = (root or data_dir()) / "malecns_v1.0"
    for fname in FILES.values():
        if not (folder / fname).exists():
            print(f"downloading {fname} -> {folder}")
            _download(f"{GCS}/{fname}", folder / fname)
    return folder


class Connectome:
    """Annotated bodies (sorted by id) plus streaming access to the synapse weights."""

    def __init__(self, root: Path | None = None):
        self.root = root or data_dir()
        self.folder = ensure_data(self.root)
        self.derived = self.root / "derived"
        self.derived.mkdir(parents=True, exist_ok=True)
        self.paths = {k: self.folder / v for k, v in FILES.items()}
        self._load_annotations()
        self._check()

    # ---- bodies -----------------------------------------------------------------------------------
    def _load_annotations(self) -> None:
        _, feather = _arrow()
        t = feather.read_table(self.paths["annotations"],
                               columns=["bodyId", "type", "instance", "rootSide", "somaSide", "subclass", "somaLocation"])
        order = np.argsort(t.column("bodyId").to_numpy(), kind="stable")
        s = lambda name: np.array([("" if v is None else v) for v in t.column(name).to_pylist()], dtype="U40")[order]
        self.ids = t.column("bodyId").to_numpy()[order].astype(np.int64)
        self.type = s("type")
        self.subclass = s("subclass")
        self.soma_side = s("somaSide")
        instance, root_side = s("instance"), s("rootSide")
        # Side of a body: the _L/_R suffix of its instance name, else its root side, else its soma side.
        suffix = np.where(np.char.endswith(instance, "_L"), "L", np.where(np.char.endswith(instance, "_R"), "R", ""))
        self.side = np.where(suffix != "", suffix, np.where(root_side != "", root_side, np.where(self.soma_side != "", self.soma_side, "?")))
        loc = t.column("somaLocation").to_pylist()
        xyz = np.full((len(loc), 3), np.nan, dtype=np.float32)
        for i, v in enumerate(loc):
            if v is not None and len(v) == 3:
                xyz[i] = v
        self.soma_xyz = xyz[order]

    def _check(self) -> None:
        assert len(self.ids) == N_BODIES, f"annotations changed: {len(self.ids)} bodies, expected {N_BODIES}"
        for t, n in type_counts().items():             # the counts sit in groups.yaml, beside the groups they define
            got = int((self.type == t).sum())
            assert got == n, f"{t}: {got} neurons in the annotations, expected {n}; the data changed underneath us"

    def index(self, body_ids) -> np.ndarray:
        """Row of each body id in the annotation arrays."""
        body_ids = np.asarray(body_ids, dtype=np.int64)
        i = np.clip(np.searchsorted(self.ids, body_ids), 0, len(self.ids) - 1)
        assert (self.ids[i] == body_ids).all(), "unknown body id"
        return i

    def body_ids(self, types=(), prefix=None, side=None) -> np.ndarray:
        m = np.isin(self.type, list(types)) if types else np.zeros(len(self.ids), bool)
        if prefix:
            m |= np.char.startswith(self.type, prefix)
        if side:
            m &= self.side == side
        return self.ids[m]

    def soma_positions(self, body_ids) -> np.ndarray:
        """(n, 3) soma location in voxels (nan where the body has no soma annotation)."""
        return self.soma_xyz[self.index(body_ids)]

    def signs(self, body_ids) -> np.ndarray:
        """+1 / -1 / 0 per body from its consensus transmitter (the file holds one row per body)."""
        _, feather = _arrow()
        t = feather.read_table(self.paths["neurotransmitters"], columns=["body", "consensus_nt"])
        body, nt = t.column("body").to_numpy(), t.column("consensus_nt").to_pylist()
        sign = np.array([NT_SIGN.get(v.lower(), 0.0) if v else 0.0 for v in nt])
        order = np.argsort(body)
        body, sign = body[order], sign[order]
        want = np.asarray(body_ids, dtype=np.int64)
        i = np.clip(np.searchsorted(body, want), 0, len(body) - 1)
        return np.where(body[i] == want, sign[i], 0.0)

    # ---- synapses (streamed) ----------------------------------------------------------------------
    def edge_batches(self):
        """(pre, post, weight) numpy arrays, one Arrow record batch at a time."""
        path = str(self.paths["weights"])
        pa, feather = _arrow()
        try:
            reader = pa.ipc.open_file(path)
            batches = (reader.get_batch(i) for i in range(reader.num_record_batches))
        except pa.ArrowInvalid:
            batches = feather.read_table(path).to_batches(max_chunksize=2_000_000)
        for b in batches:
            yield (b.column("body_pre").to_numpy(zero_copy_only=False),
                   b.column("body_post").to_numpy(zero_copy_only=False),
                   b.column("weight").to_numpy(zero_copy_only=False))

    def edge_table(self, min_syn: int = MIN_SYN):
        """Every connection of >= min_syn synapses between annotated bodies -> (pre, post, w); pre/post are
        rows of self.ids. One streaming pass, cached."""
        path = self.derived / f"edges_N{min_syn}.npz"
        if path.exists():
            d = np.load(path)
            if len(d["pre"]) and int(d["n_bodies"]) == len(self.ids):
                return d["pre"], d["post"], d["w"]
        n, keep_pre, keep_post, keep_w = len(self.ids), [], [], []
        for pre, post, w in self.edge_batches():
            ip, iq = np.clip(np.searchsorted(self.ids, pre), 0, n - 1), np.clip(np.searchsorted(self.ids, post), 0, n - 1)
            m = (self.ids[ip] == pre) & (self.ids[iq] == post) & (w >= min_syn)
            keep_pre.append(ip[m].astype(np.int32))
            keep_post.append(iq[m].astype(np.int32))
            keep_w.append(w[m].astype(np.int32))
        pre, post, w = np.concatenate(keep_pre), np.concatenate(keep_post), np.concatenate(keep_w)
        np.savez(path, pre=pre, post=post, w=w, n_bodies=len(self.ids))
        return pre, post, w

    def edges_among(self, body_ids):
        """All connections, any weight, with BOTH ends in body_ids -> (pre_id, post_id, summed weight). One pass."""
        want = np.sort(np.asarray(body_ids, dtype=np.int64))
        parts = []
        for pre, post, w in self.edge_batches():
            m = np.isin(pre, want) & np.isin(post, want)
            if m.any():
                parts.append(np.stack([pre[m], post[m], w[m]], axis=1))
        a = np.concatenate(parts)
        key, inv = np.unique(a[:, :2], axis=0, return_inverse=True)
        return key[:, 0], key[:, 1], np.bincount(inv.ravel(), weights=a[:, 2].astype(np.float64))

    def through_scores(self, source_ids, target_ids):
        """For every body: total synapses it receives from source_ids, and total it sends to target_ids.
        -> (ids_from_source, weight_from_source, ids_to_target, weight_to_target). One pass."""
        src, dst = np.sort(np.asarray(source_ids, dtype=np.int64)), np.sort(np.asarray(target_ids, dtype=np.int64))
        a, b = [], []
        for pre, post, w in self.edge_batches():
            m = np.isin(pre, src)
            if m.any():
                a.append(np.stack([post[m], w[m]], axis=1))
            m = np.isin(post, dst)
            if m.any():
                b.append(np.stack([pre[m], w[m]], axis=1))

        def fold(parts):
            x = np.concatenate(parts)
            k, inv = np.unique(x[:, 0], return_inverse=True)
            return k, np.bincount(inv.ravel(), weights=x[:, 1].astype(np.float64))
        return (*fold(a), *fold(b))
