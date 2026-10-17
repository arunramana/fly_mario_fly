"""Part 5: the Part 4b fly evolution (TRAIN set, same fitness/penalty, popsize 12, sigma0 .25, <=40 gens)
run on the shuffled matrix. 2 restarts: 1 = defaults, 2 = fresh random start (same fresh vector as 4b).
python -m flyrun.evolve5 -> flyrun/evo5/fly_shuf/"""
import json
import os
import time
from pathlib import Path

import numpy as np

EVO5 = Path(__file__).resolve().parent / "evo5"


def main():
    os.environ["FLYRUN_WFILE"] = "W_steer_shuf0.npy"      # inherited by the spawned workers
    from .evolve4 import run_arm
    from .fitness import WorkerPool
    from .genome import SPECS, x0
    fresh = np.random.default_rng(99).uniform(0.05, 0.95, len(SPECS["fly"]))
    EVO5.mkdir(exist_ok=True)
    t0 = time.time()
    with WorkerPool(12) as pool:
        run_arm("fly", pool, restarts=2, d=EVO5 / "fly_shuf", sts=[("default", x0("fly")), ("fresh", fresh)])
    (EVO5 / "timing.json").write_text(json.dumps({"fly_shuf": time.time() - t0}))
    print("done", round(time.time() - t0), "s")


if __name__ == "__main__":
    main()
