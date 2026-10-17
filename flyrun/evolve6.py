"""Part 6b: equal-budget evolution, real vs row-renormalised shuffles (audit 006 #5).
Every arm: the Part 4b fly evolution (TRAIN set, same fitness/penalty, popsize 12, sigma0 .25, <=40 gens,
patience 10), 3 restarts = [default knobs, fresh vector (rng 99), fresh vector (rng 98)], CMA seeds 1,2,3.
No restart is warm-started from a Part 4 genome. Arms: real, shuf0_rn, shuf1_rn, shuf2_rn.
python -m flyrun.evolve6 [arm ...] -> flyrun/evo6/<arm>/"""
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

EVO6 = Path(__file__).resolve().parent / "evo6"
WFILE = {"real": None, **{f"shuf{i}_rn": f"W_steer_shuf{i}_rn.npy" for i in range(5)}}


def main(arms):
    from .evolve4 import run_arm
    from .fitness import WorkerPool
    from .genome import SPECS, x0
    n = len(SPECS["fly"])
    sts = [("default", x0("fly")), ("fresh99", np.random.default_rng(99).uniform(0.05, 0.95, n)),
           ("fresh98", np.random.default_rng(98).uniform(0.05, 0.95, n))]
    EVO6.mkdir(exist_ok=True)
    tp = EVO6 / "timing.json"
    timing = json.loads(tp.read_text()) if tp.exists() else {}
    for arm in arms:
        if WFILE[arm]:
            os.environ["FLYRUN_WFILE"] = WFILE[arm]     # inherited by the spawned workers
        else:
            os.environ.pop("FLYRUN_WFILE", None)
        t0 = time.time()
        with WorkerPool(12) as pool:
            run_arm("fly", pool, restarts=3, d=EVO6 / arm, sts=sts)
        timing[arm] = timing.get(arm, 0.0) + time.time() - t0
        tp.write_text(json.dumps(timing, indent=1))
        print(arm, "done", round(timing[arm]), "s", flush=True)
    os.environ.pop("FLYRUN_WFILE", None)


if __name__ == "__main__":
    main(sys.argv[1:] or ["real", "shuf0_rn", "shuf1_rn", "shuf2_rn"])
