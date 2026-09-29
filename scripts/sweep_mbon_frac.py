# What this file does, in plain English:
# Answers "how strong does the mushroom body's readout have to be before the
# fly's behaviour changes?". It plays level 1-1 on one seed with the per-MBON
# readout switched on at several strengths (the same value for all four motor
# pathways), once with the untrained brain and once with a trained, frozen
# one, and compares each run with the strength-0 run: did the fly's state
# start to differ, when did Mario's position start to differ, and did it end
# up somewhere else. Prints a table; the finding goes in docs/RUNS.md.
"""scripts/sweep_mbon_frac.py -- docs/SPEC_learning_v2.md section 3.

    .venv/Scripts/python.exe -m scripts.sweep_mbon_frac [--seed 0] [--frames 2000]

Runs are independent, so they go through a process pool (one thread each,
CLAUDE.md "Do these first" item 2). Learning is frozen (rate 0) so the only
thing that differs between runs of one weight set is the readout strength.
"""

from __future__ import annotations

import argparse
import dataclasses
import multiprocessing as mp
import os
import tempfile

os.environ.setdefault("OMP_NUM_THREADS", "1")

FRACS = (0.0, 0.005, 0.02, 0.05, 0.2)      # 0.005 is MbonReadoutParams' shipped default
PROJECT = "win_attempt"                     # the project the trained checkpoints belong to
TRAINED = "real_ep029.npy"


def _one(args):
    seed, frames, weights_name, frac = args
    import numpy as np
    import setuptools  # noqa: F401
    from config.output_routing import PROJECTS_ROOT
    from config.params import MbonReadoutParams
    from config.project_config import load
    from sim.project_runner import run_from_config

    cfg = load(str(PROJECTS_ROOT / PROJECT / "config.json"))
    cfg = dataclasses.replace(
        cfg,
        scenario=dataclasses.replace(cfg.scenario, max_frames=frames),
        mushroom_body=dataclasses.replace(cfg.mushroom_body, learning_rate=0.0),
        modules=dataclasses.replace(cfg.modules, mbon_readout=MbonReadoutParams(
            dnp01_frac=frac, dlmn_frac=frac, dnp09_frac=frac, mdn_frac=frac)))
    weights = np.load(PROJECTS_ROOT / PROJECT / "checkpoints" / weights_name) if weights_name else None
    with tempfile.TemporaryDirectory() as tmp:
        tel, info = run_from_config(cfg, "sweep.mp4", seed=seed, record_video=False, write_telemetry=False,
                                    mb_weights=weights, telemetry_path=os.path.join(tmp, "t.csv"))
    return (weights_name, frac), tel, {k: info[k] for k in
                                       ("max_x_abs", "n_frames", "died_or_flagged", "n_escape_jumps", "n_long_jumps")}


def first_difference(a, b, columns) -> int | None:
    import numpy as np
    n = min(len(a), len(b))
    for c in columns:
        x, y = a[c].to_numpy()[:n], b[c].to_numpy()[:n]
        bad = np.flatnonzero(~np.isclose(x, y, rtol=0, atol=1e-9, equal_nan=True))
        if len(bad):
            yield_ = int(bad[0])
            return yield_
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--frames", type=int, default=2000)
    args = ap.parse_args()
    jobs = [(args.seed, args.frames, w, f) for w in (None, TRAINED) for f in FRACS]
    with mp.get_context("spawn").Pool(min(len(jobs), 6)) as pool:
        results = {key: (tel, info) for key, tel, info in pool.map(_one, jobs)}

    print(f"seed {args.seed}, {args.frames} frames, level 1-1, learning frozen, all four fracs = value\n")
    print("weights      frac    max_x  frames  died  jumps(long)  state differs @   Mario x differs @")
    for w in (None, TRAINED):
        ref_tel, _ = results[(w, 0.0)]
        state_cols = [c for c in ref_tel.columns if not c.startswith("mbon_") and c != "frame"
                      and ref_tel[c].dtype.kind in "fiu"]
        for f in FRACS:
            tel, info = results[(w, f)]
            state = None if f == 0.0 else first_difference(ref_tel, tel, state_cols)
            xdiff = None if f == 0.0 else first_difference(ref_tel, tel, ["mario_x"])
            print(f"{(w or 'fresh'):12s} {f:5.3f}  {info['max_x_abs']:6d}  {info['n_frames']:6d}  "
                  f"{str(bool(info['died_or_flagged'])):5s} {info['n_escape_jumps']:3d} ({info['n_long_jumps']})"
                  f"      {('-' if state is None else state)!s:>10}        {('-' if xdiff is None else xdiff)!s:>10}")


if __name__ == "__main__":
    main()
