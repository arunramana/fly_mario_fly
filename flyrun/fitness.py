"""fitness = max_x + FLAG_BONUS * flag_get, averaged over episode seeds. One emulator per worker process,
no rendering. The scripted driver must never be inside fitness: _one() raises if any frame has
driver == "script" (baselines are driver "baseline", the circuit "fly")."""
import multiprocessing as mp
import time
from dataclasses import replace

import numpy as np

from .baselines import CONTROLLERS
from .brain import load_brain
from .knobs import FLAG_BONUS   # INVENTED (fixed)
from .run import run_episode

_BRAIN = None


def fitness_of(summary, blind_penalty=0):
    return (summary["max_x"] + FLAG_BONUS * int(summary["flag_get"])
            - blind_penalty * summary.get("blind_presses", 0))


def _init():
    global _BRAIN
    _BRAIN = load_brain()


def _one(job):
    knobs, seed, controller, kw = job
    kw = dict(kw)
    penalty = kw.pop("blind_penalty", 0)
    ctl = CONTROLLERS[controller] if controller else None
    t0 = time.time()
    s, df = run_episode(knobs, _BRAIN, episode_seed=seed, controller=ctl, stuck_frames=150, **kw)
    n_script = int((df["driver"] == "script").sum())
    if n_script:   # audit 006 #6: every fitness / HOLDOUT / evolution path goes through here
        raise RuntimeError(f"scripted (non-fly) frames inside a fitness evaluation: seed {seed}, {n_script} frames")
    s = dict(s, seed=seed, secs=time.time() - t0, n_nonfly=n_script, fitness=fitness_of(s, penalty))
    return s


class WorkerPool:
    """Persistent pool (one emulator + brain per worker) so an evolution run pays the spawn cost once."""

    def __init__(self, workers):
        self.pool = mp.get_context("spawn").Pool(workers, initializer=_init)

    def close(self):
        self.pool.close()
        self.pool.join()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.pool.terminate()


def evaluate(knobs, W, seeds, workers=1, controller=None, pool=None, **run_kwargs):
    """-> dict(mean_fitness, per_seed=[summary...], secs). W is a Brain (used when workers == 1;
    worker processes load their own copy). run_kwargs go to run_episode (e.g. enemy_input)."""
    jobs = [(knobs, int(sd), controller, run_kwargs) for sd in seeds]
    t0 = time.time()
    if pool is not None:
        res = pool.pool.map(_one, jobs)
    elif workers <= 1:
        global _BRAIN
        _BRAIN = W
        res = [_one(j) for j in jobs]
    else:
        with mp.get_context("spawn").Pool(workers, initializer=_init) as pool:
            res = pool.map(_one, jobs)
    if any(r["n_nonfly"] for r in res):
        raise RuntimeError("scripted (non-fly) frames inside fitness evaluation: "
                           f"{[(r['seed'], r['n_nonfly']) for r in res if r['n_nonfly']]}")
    return dict(mean_fitness=float(np.mean([r["fitness"] for r in res])), per_seed=res,
                secs=time.time() - t0)
