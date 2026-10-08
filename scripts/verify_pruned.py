# What this file does, in plain English:
# Proves the pruned network view gives the same run as the full network: for E1, E2a and B11, real and class-shuffled arms,
# it plays each episode twice (full and pruned) and compares a hash of every frame's telemetry row plus the final result.
# Measurement only; run on an otherwise idle machine. docs/SPEC_fast_iteration.md step 3.
"""    .venv/Scripts/python.exe -m scripts.verify_pruned [--n 20] [--seed0 9600] [--workers 8] [--out f.json]"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from dataclasses import asdict

EXPERIMENTS = ("E1", "E2a", "B11")
ARMS = ("real", "shuffled_class")


def _hash(res, rows) -> str:
    h = hashlib.sha256(json.dumps(asdict(res), sort_keys=True, default=str).encode())
    for r in rows:
        h.update(json.dumps(r, sort_keys=True, default=repr).encode())
    return h.hexdigest()[:16]


def _job(args):
    exp, arm, seed, shuffle_seed = args
    from brain import baseline, e1, e2a
    from brain.settings import settings_for
    out = []
    for pruned in (False, True):
        t0 = time.perf_counter()
        if exp == "E1":
            res, rows, _ = e1.run_e1_episode(seed, shuffle_seed, arm=arm, record_rows=True, pruned=pruned)
        elif exp == "E2a":
            res, rows, _ = e2a.run_e2a_episode(seed, arm, shuffle_seed, record_rows=True, pruned=pruned)
        else:
            res, rows, _ = baseline.run_baseline_episode(seed, arm, shuffle_seed, record_rows=True, pruned=pruned)
        out.append((_hash(res, rows), len(rows), time.perf_counter() - t0))
    return exp, arm, seed, out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--seed0", type=int, default=9600)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", default="scratch_verify_pruned.json")
    a = ap.parse_args(argv)
    from brain.workers import WorkerPool
    jobs = [(e, arm, a.seed0 + i, 1 + i if arm == "shuffled_class" else None) for e in EXPERIMENTS for arm in ARMS for i in range(a.n)]
    with WorkerPool(a.workers, [(1 + i, "class") for i in range(a.n)]) as pool:
        rows = pool.map(_job, jobs)
    summary = {}
    for exp, arm, seed, (full, pruned) in rows:
        s = summary.setdefault(f"{exp}/{arm}", {"episodes": 0, "identical": 0, "frames": 0, "t_full": 0.0, "t_pruned": 0.0})
        s["episodes"] += 1
        s["identical"] += int(full[0] == pruned[0])
        s["frames"] += full[1]
        s["t_full"] += full[2]
        s["t_pruned"] += pruned[2]
    for k, s in summary.items():
        print(k, s)
    print("ALL IDENTICAL" if all(s["identical"] == s["episodes"] for s in summary.values()) else "MISMATCH")
    json.dump({"summary": summary, "episodes": rows}, open(a.out, "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
