# What this file does, in plain English:
# The one place that starts the worker processes for every evaluation (E1, E0/E3, E2a, B11, dose-response, ...).
# The parent loads the network once and puts its big arrays (the sparse weight matrix above all) into shared memory;
# each worker wraps those same bytes instead of loading and rebuilding its own copy, and the shuffled-control networks
# are built once in the parent and shared the same way. Every worker is told to use one thread. Nothing about the
# simulation changes: the arrays hold the same bits, so results equal the serial path exactly.
"""brain/workers.py -- measured in docs/SPEC_redesign_phase6c_part2.md.

Why: N workers each holding a private 7.4 MB weight matrix (612,566 non-zeros x (8 B value + 4 B index)) overflow the
shared L3 cache and run the sparse matvec out of DRAM; one shared copy stays resident in L3 for everyone.

    with WorkerPool(workers, variants=[(shuffle_seed, "degree"), ...]) as pool:
        results = pool.map(_job, jobs)

`variants` is only an optimisation: a shuffled network not listed is built privately in the worker, as before.
"""

from __future__ import annotations

import multiprocessing as mp
import os
from contextlib import contextmanager
from multiprocessing import shared_memory

import numpy as np
import scipy.sparse as sp

THREAD_VARS = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS")
MAX_SHARED_VARIANT_MB = 1536      # invented cap on parent-side shared shuffled networks; beyond it workers build privately
MAX_WORKERS = 8                   # measured default ceiling, see docs/SPEC_redesign_phase6c_part2.md


def default_workers() -> int:
    """A sensible worker count for this machine: logical CPUs, never above MAX_WORKERS."""
    return max(1, min(os.cpu_count() or 1, MAX_WORKERS))


@contextmanager
def single_thread_env():
    """Spawned workers inherit os.environ, so setting the BLAS/OpenMP caps here applies before they import numpy."""
    old = {k: os.environ.get(k) for k in THREAD_VARS}
    os.environ.update({k: "1" for k in THREAD_VARS})
    try:
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ---- parent side ----------------------------------------------------------------------------------------------------
class SharedNetworkSet:
    """Owns the shared-memory copies of the real network and of the requested shuffled variants."""

    def __init__(self, net, variants=()):
        self._blocks: list[shared_memory.SharedMemory] = []
        real = {"ids": net.ids, "side": net.side, "signs": net.signs, "pre": net.pre, "post": net.post, "syn": net.syn,
                "total_in": net.total_in, "insub": net.insub, **self._csr(net.W)}
        self.desc = {"real": {k: self._put(v) for k, v in real.items()},
                     "pops": {k: self._put(v) for k, v in net.pops.items()},
                     "shape": net.W.shape, "rule": net.rule, "real_hash": net.build_hash(), "variants": {}}
        per_mb = sum(v.nbytes for v in (net.post, net.insub, net.W.data, net.W.indices, net.W.indptr)) / 2**20
        for seed, mode in dict.fromkeys(variants):
            if (len(self.desc["variants"]) + 1) * per_mb > MAX_SHARED_VARIANT_MB:
                break
            s = net.shuffled(seed, mode)
            self.desc["variants"][(seed, mode)] = {"post": self._put(s.post), "insub": self._put(s.insub), **{
                k: self._put(v) for k, v in self._csr(s.W).items()}}

    @staticmethod
    def _csr(W) -> dict:
        return {"w_data": W.data, "w_indices": W.indices, "w_indptr": W.indptr}

    def _put(self, a: np.ndarray) -> tuple:
        a = np.ascontiguousarray(a)
        shm = shared_memory.SharedMemory(create=True, size=max(a.nbytes, 1))
        np.ndarray(a.shape, dtype=a.dtype, buffer=shm.buf)[...] = a
        self._blocks.append(shm)
        return (shm.name, a.shape, a.dtype.str)

    def close(self) -> None:
        for b in self._blocks:
            b.close()
            try:
                b.unlink()
            except FileNotFoundError:
                pass
        self._blocks = []


class WorkerPool:
    """spawn Pool whose workers share the parent's network. `workers` <= 1 runs serially in-process (no sharing needed)."""

    def __init__(self, workers: int, variants=()):
        self.workers, self.variants = workers, list(variants)
        self._set = self._pool = None

    def __enter__(self):
        if self.workers > 1:
            from brain import builder
            self._set = SharedNetworkSet(builder.load_or_build(), self.variants)
            with single_thread_env():
                self._pool = mp.get_context("spawn").Pool(self.workers, initializer=_init_worker,
                                                          initargs=(self._set.desc,))
        return self

    def map(self, fn, jobs):
        jobs = list(jobs)
        if self._pool is None:
            return [fn(j) for j in jobs]
        return self._pool.map(fn, jobs, chunksize=1)

    def __exit__(self, *exc):
        if self._pool is not None:
            self._pool.terminate()
            self._pool.join()
        if self._set is not None:
            self._set.close()


# ---- worker side ----------------------------------------------------------------------------------------------------
_KEEP: list = []        # SharedMemory handles must outlive the numpy views over them


def _view(t) -> np.ndarray:
    name, shape, dtype = t
    shm = shared_memory.SharedMemory(name=name)
    _KEEP.append(shm)
    return np.ndarray(shape, dtype=np.dtype(dtype), buffer=shm.buf)


class _SharedProvider:
    """Installed as builder._SHARED inside a worker: hands out networks backed by the shared arrays."""

    def __init__(self, desc: dict):
        from brain.builder import BuiltNetwork
        self.desc = desc
        r = {k: _view(t) for k, t in desc["real"].items()}
        W = self._csr(r["w_data"], r["w_indices"], r["w_indptr"])
        pops = {k: _view(t) for k, t in desc["pops"].items()}
        self._real = BuiltNetwork(r["ids"], r["side"], r["signs"], pops, r["pre"], r["post"], r["syn"], r["total_in"],
                                  desc["rule"], W=W, insub=r["insub"])
        self._cache: dict = {}

    def _csr(self, data, indices, indptr):
        return sp.csr_matrix((data, indices, indptr), shape=self.desc["shape"], copy=False)

    def real(self):
        return self._real

    def variant(self, net, seed: int, mode: str):
        v = self.desc["variants"].get((seed, mode))
        if v is None or net is not self._real:
            return None
        if (seed, mode) not in self._cache:
            from brain.builder import BuiltNetwork
            r = self._real
            self._cache = {(seed, mode): BuiltNetwork(
                r.ids, r.side, r.signs, r.pops, r.pre, _view(v["post"]), r.syn, r.total_in, r.rule,
                W=self._csr(_view(v["w_data"]), _view(v["w_indices"]), _view(v["w_indptr"])), insub=_view(v["insub"]),
                twin_of={"seed": seed, "real_hash": self.desc["real_hash"], "mode": mode})}
        return self._cache[(seed, mode)]


def _init_worker(desc: dict) -> None:
    for k in THREAD_VARS:
        os.environ.setdefault(k, "1")
    from brain import builder
    builder.install_shared(_SharedProvider(desc))
