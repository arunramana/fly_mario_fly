"""Part 4b episode sets. TRAIN is what evolution sees; HOLDOUT is never used in training.
Noise is applied to every arm's input (the fly's detectors and the theta rule's theta, same rng stream);
the spam arms sense nothing so noise cannot touch them."""
from dataclasses import replace

import numpy as np

from .knobs import BLIND_PENALTY   # INVENTED (fixed); fitness = max_x + FLAG_BONUS*flag - BLIND_PENALTY*blind_presses

TRAIN = [dict(noop_start=n, seed=sd, sigma=0.05) for n, sd in ((0, 1), (7, 2), (17, 3))]
HOLDOUT = [dict(noop_start=n, seed=100 + i + 1, sigma=sg)
           for sg in (0.0, 0.05) for i, n in enumerate((3, 11, 25, 33, 41))]


def jobs(knobs, controller, episodes):
    return [(replace(knobs, SENSOR_NOISE=e["sigma"]), e["seed"], controller,
             dict(noop_start=e["noop_start"], blind_penalty=BLIND_PENALTY)) for e in episodes]


def aggregate(results):
    xs = [r["max_x"] for r in results]
    return dict(fitness=float(np.mean([r["fitness"] for r in results])),
                mean_max_x=float(np.mean(xs)), min_max_x=int(min(xs)),
                flag_rate=float(np.mean([r["flag_get"] for r in results])),
                a_frac=float(np.mean([r["a_frac"] for r in results])),
                blind_presses=float(np.mean([r["blind_presses"] for r in results])),
                n_onsets=float(np.mean([r["n_onsets"] for r in results])),
                n_episodes=len(xs), n_traj=len({(r["max_x"], r["x_at_end"]) for r in results}),   # distinct (max_x, death x)
                max_x=xs, ends=[(r["end_reason"], r["x_at_end"], r["cause"]) for r in results])
