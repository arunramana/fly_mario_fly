# What this file does, in plain English:
# Times a fixed batch of episodes at 1, 2, 4, 8 worker processes and reports per-episode time, total wall time,
# speedup and memory (peak working set per process and summed). Measurement only: it changes nothing in the
# simulation. Run it on an otherwise idle machine.
"""    .venv/Scripts/python.exe -m scripts.bench_workers --exp e1 --n 20 --seed0 9500 --workers 1 2 4 8 [--pool-impl current]

--exp e1  : E1 real arm (max 600 frames).   --exp b11 : baseline B11 real arm (brain.baseline).
--pool-impl legacy : the old plain Pool (every job rebuilds a private network); current : brain.workers.WorkerPool (default).
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import json
import os
import statistics
import sys
import time


def peak_working_set_mb() -> float:
    class PMC(ctypes.Structure):
        _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t)]
    pmc = PMC()
    pmc.cb = ctypes.sizeof(pmc)
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.GetCurrentProcess.restype = wt.HANDLE
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.POINTER(PMC), wt.DWORD]
    psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
    return pmc.PeakWorkingSetSize / 2**20


def _timed(args):
    """Worker entry: time one episode, report pid, peak RSS and the thread env."""
    exp, job = args
    t0 = time.perf_counter()
    if exp == "e1":
        from brain import e1
        e1._job(job)
    else:
        from brain import baseline
        baseline._job(job)
    dt = time.perf_counter() - t0
    env = {k: os.environ.get(k) for k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS")}
    return dt, os.getpid(), peak_working_set_mb(), env


def make_jobs(exp: str, n: int, seed0: int):
    if exp == "e1":
        return [(seed0 + i, None, 600, "real") for i in range(n)]
    from brain.baseline import EXPERIMENT_ID, settings_for
    used = settings_for(EXPERIMENT_ID, None)
    return [(seed0 + i, "real", None, None, used.to_dict()) for i in range(n)]


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exp", choices=("e1", "b11"), default="e1")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--seed0", type=int, default=9500)
    ap.add_argument("--workers", type=int, nargs="+", default=[1, 2, 4, 8])
    ap.add_argument("--pool-impl", choices=("legacy", "current"), default="current")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    import multiprocessing as mp
    jobs = make_jobs(a.exp, a.n, a.seed0)
    rows = []
    base = None
    for w in a.workers:
        tasks = [(a.exp, j) for j in jobs]
        t0 = time.perf_counter()
        if a.pool_impl == "current":
            from brain import workers as wk
            pool = wk.WorkerPool(w)
        else:
            pool = mp.get_context("spawn").Pool(w)
        with pool:
            out = pool.map(_timed, tasks) if a.pool_impl == "current" else pool.map(_timed, tasks, chunksize=1)
        wall = time.perf_counter() - t0
        dts = [o[0] for o in out]
        peak = {}
        for _, pid, mb, _ in out:
            peak[pid] = max(peak.get(pid, 0.0), mb)
        base = base or wall
        row = {"workers": w, "wall_s": round(wall, 1), "speedup": round(base / wall, 2),
               "job_mean_s": round(statistics.mean(dts), 2), "job_median_s": round(statistics.median(dts), 2),
               "peak_rss_mb_max": round(max(peak.values())), "peak_rss_mb_sum": round(sum(peak.values())),
               "procs": len(peak), "env": out[0][3]}
        rows.append(row)
        print(json.dumps(row), flush=True)
    if a.out:
        with open(a.out, "w") as f:
            json.dump(rows, f, indent=1)


if __name__ == "__main__":
    main()
