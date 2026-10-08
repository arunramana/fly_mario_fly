# What this file does, in plain English:
# Times the fixed "240-episode revalidation" batch of docs/SPEC_fast_iteration.md (E1, E2a, B11, E0 on seeds 9600-9619, 8 workers)
# and stores a digest of every episode result, so a later speed-up can be shown to change the time and nothing else. Measurement
# only. Run it on an otherwise idle machine.
"""    .venv/Scripts/python.exe -m scripts.bench_batch --label baseline [--drop-degree-shuffle] [--prune] [--workers 8] [--out f.json]

--drop-degree-shuffle : do not run the 'shuffled' arms (the routine default after step 1); the rest of the batch is unchanged.
--prune               : E1, E2a and B11 use the pruned network view (step 3); E0 never does.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time

SEED0, N, WORKERS = 9600, 20, 8
BATCH = {   # experiment -> arms, all of the 240-episode composition
    "E1": ("real", "shuffled", "shuffled_class", "lesion_gf"),
    "E2a": ("real", "shuffled", "shuffled_class", "real_no_obstacle"),
    "B11": ("real", "shuffled", "shuffled_class"),
    "E0": ("real",),
}


def digest(episodes: list[dict]) -> str:
    keep = sorted(episodes, key=lambda e: (e["arm"], e["seed"]))
    return hashlib.sha256(json.dumps(keep, sort_keys=True, default=str).encode()).hexdigest()[:16]


def probe_ms() -> float:
    """Median ms of one sparse matvec on the real network in this process: a speed-of-the-machine reference, taken
    before and after the batch so runs made under different load or power states can be compared (0.47 ms on the idle box)."""
    import numpy as np
    from brain import builder
    W, h = builder.load_or_build().W, np.random.default_rng(0).random(builder.load_or_build().W.shape[0])
    ts = []
    for _ in range(300):
        t0 = time.perf_counter()
        W @ h
        ts.append(time.perf_counter() - t0)
    return round(float(np.median(ts)) * 1e3, 3)


def run_batch(workers: int, drop_degree: bool, prune: bool, n: int = N, seed0: int = SEED0) -> dict:
    from brain import baseline, e1, e2a, goal_eval
    out = {"probe_ms_before": probe_ms()}
    for exp, arms in BATCH.items():
        arms = tuple(a for a in arms if not (drop_degree and a == "shuffled"))
        kw = {"pruned": True} if prune and exp != "E0" else {}
        t0 = time.perf_counter()
        if exp == "E1":
            res = e1.run_eval(n, seed0, workers, arms=arms, **kw)
        elif exp == "E2a":
            res = e2a.run_eval(n, seed0, workers, arms=arms, **kw)
        elif exp == "B11":
            res = baseline.run_eval(n, seed0, workers, arms=arms, **kw)
        else:
            res = goal_eval.run_eval("E0", n, seed0, workers, arms=arms)
        wall = time.perf_counter() - t0
        eps = res["episodes"]
        out[exp] = {"wall_s": round(wall, 1), "episodes": len(eps), "frames": sum(e["frames"] for e in eps),
                    "frames_by_arm": {a: sum(e["frames"] for e in eps if e["arm"] == a) for a in arms},
                    "digest": digest(eps), "digest_by_arm": {a: digest([e for e in eps if e["arm"] == a]) for a in arms}}
        print(exp, json.dumps({k: v for k, v in out[exp].items() if k != "digest_by_arm"}), flush=True)
    out["probe_ms_after"] = probe_ms()
    out["total_wall_s"] = round(sum(v["wall_s"] for k, v in out.items() if k in BATCH), 1)
    out["total_episodes"] = sum(v["episodes"] for k, v in out.items() if k in BATCH)
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--workers", type=int, default=WORKERS)
    ap.add_argument("--drop-degree-shuffle", action="store_true")
    ap.add_argument("--prune", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    res = {"label": a.label, "workers": a.workers, **run_batch(a.workers, a.drop_degree_shuffle, a.prune)}
    print(f"probe ms {res['probe_ms_before']} -> {res['probe_ms_after']}")
    print(f"{a.label}: {res['total_episodes']} episodes, wall {res['total_wall_s']} s")
    with open(a.out or f"scratch_bench_{a.label}.json", "w") as f:
        json.dump(res, f, indent=1)


if __name__ == "__main__":
    main()
