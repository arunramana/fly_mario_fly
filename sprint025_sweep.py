"""
sprint025_sweep.py -- sigma calibration sweep for the membrane noise
added in dynamics.NoiseConfig (sprint 025). N episodes per sigma, same
seed set reused across every sigma value (so any difference between
sigma values is attributable to sigma, not to which seeds happened to
be drawn), level 1-1, headless (no video -- this is calibration, not a
deliverable run). Reports, per sigma: DNp01 commitment-frame median and
spread, survival rate, and final distance (max_x_abs).

OMP_NUM_THREADS=1 must be set before numpy is imported anywhere in this
process -- done at the very top of the file, before any other import,
because multiprocessing on Windows always spawns (re-executes this
module from scratch in each worker), so this line runs in every worker
before its own numpy/run_steering import.
"""
import os
os.environ["OMP_NUM_THREADS"] = "1"

import json
import sys
from multiprocessing import Pool

import numpy as np

SEEDS = list(range(int(os.environ.get("SWEEP_N", 50))))  # same seed set reused across every sigma value
MAX_FRAMES = 800
LEVEL = "1-1"


def run_one(args):
    sigma, seed = args
    import run_steering as rs
    from commitment_report import find_commitments

    tel, info = rs.main(out_mp4=f"runs/_sweep_s{sigma}_seed{seed}.mp4", level=LEVEL,
                         max_frames=MAX_FRAMES, record_video=False,
                         write_telemetry=False, sigma=sigma, seed=seed)
    events = find_commitments(tel)
    dnp01_events = [e for e in events if e["pathway"] == "DNp01"]
    dnp01_frame = dnp01_events[0]["frame"] if dnp01_events else None
    return {
        "sigma": sigma, "seed": seed,
        "dnp01_commit_frame": dnp01_frame,
        "survived": not info["died_or_flagged"],
        "n_frames": info["n_frames"],
        "max_x_abs": info["max_x_abs"],
    }


def main():
    sigmas_env = os.environ.get("SWEEP_SIGMAS")
    sigmas = [float(s) for s in sigmas_env.split(",")] if sigmas_env else \
        [0.0, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.4]
    tasks = [(sigma, seed) for sigma in sigmas for seed in SEEDS]
    print(f"{len(tasks)} episodes total ({len(sigmas)} sigmas x {len(SEEDS)} seeds), Pool(8)")

    with Pool(8) as pool:
        results = pool.map(run_one, tasks)

    with open("runs/025_sigma_sweep_raw.json", "w") as f:
        json.dump(results, f, indent=1)

    print(f"\n{'sigma':>7} {'n':>4} {'n_commit':>9} {'median_ftc':>11} "
          f"{'spread(iqr)':>12} {'survival%':>10} {'median_dist':>12}")
    for sigma in sigmas:
        rows = [r for r in results if r["sigma"] == sigma]
        commits = [r["dnp01_commit_frame"] for r in rows if r["dnp01_commit_frame"] is not None]
        survival = 100.0 * sum(r["survived"] for r in rows) / len(rows)
        dist = np.median([r["max_x_abs"] for r in rows])
        if commits:
            med = np.median(commits)
            iqr = np.percentile(commits, 75) - np.percentile(commits, 25)
            med_s, iqr_s = f"{med:.1f}", f"{iqr:.1f}"
        else:
            med_s, iqr_s = "--", "--"
        print(f"{sigma:>7} {len(rows):>4} {len(commits):>9} {med_s:>11} "
              f"{iqr_s:>12} {survival:>9.1f}% {dist:>12.0f}")


if __name__ == "__main__":
    main()
