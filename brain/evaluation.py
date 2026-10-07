# What this file does, in plain English:
# The standard test for the redesigned brain: Mario starts level 1-1 controlled
# only by the brain, once with the real connectome and once with a randomly
# rewired copy (same neurons and counts), on fresh seeds 2000-2019 nobody has
# tuned on. The score is how often Mario gets past the first Goomba, with 95%
# confidence intervals. It reuses the interval maths of the old evaluation but
# none of its project machinery, and it never changes the brain or the game.
"""brain/evaluation.py -- docs/SPEC_brain_core.md section 9 (the Phase 1 gate).

    .venv/Scripts/python.exe -m scripts.eval_brain [--n 20] [--seed0 2000] [--workers 8] [--max-frames 1500]

Metric "past the first Goomba": Mario's world x exceeds the world x at which the level's first Goomba (type byte 0x06) was
first seen active, while Mario is still alive. A Goomba only walks left, so being right of its spawn point means Mario
is past it whether he jumped it, stomped it or it left the screen. An episode ends at death, the flag, the metric being
met, or max_frames. Both arms use the same seeds for the brain noise; the shuffled arm rewires with shuffle seed 1 + i
(as tool/core/evaluation.py).
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass

import numpy as np

from brain.workers import WorkerPool

DEFAULT_N = 20
DEFAULT_SEED0 = 2000          # fresh and held out: earlier work used 1000-1019 and a 9000 smoke seed
DEFAULT_MAX_FRAMES = 1500
LEVEL = "1-1"
GOOMBA_TYPE_BYTE = 0x06


@dataclass
class EpisodeResult:
    arm: str                # "real" | "shuffled"
    seed: int
    passed: bool            # past the first Goomba
    died: bool
    flag: bool
    frames: int
    max_x: int              # Mario's furthest world x
    goomba_x: int | None    # world x where the first Goomba was first seen active
    gf_spikes: int          # frames with a Giant Fiber spike
    a_frames: int           # frames with A pressed


class _Observation:
    """What a policy reads: the emulator's RAM (the policy never sees pixels)."""

    def __init__(self, ram):
        self.ram = ram


def run_episode(seed: int, shuffle_seed: int | None = None, max_frames: int = DEFAULT_MAX_FRAMES,
                network=None, calibration=None) -> EpisodeResult:
    """One 1-1 episode under BrainPolicy: the real connectome, or its degree-preserving shuffle `shuffle_seed`."""
    from brain.policy import BrainPolicy
    from mario.emulator.env import make_env
    from mario.ram.addresses import (ADDR_ENEMY_ACTIVE, ADDR_ENEMY_PAGE, ADDR_ENEMY_TYPE, ADDR_ENEMY_X,
                                     ADDR_MARIO_PAGE, ADDR_MARIO_X)
    policy = BrainPolicy(network=network, calibration=calibration, shuffle_seed=shuffle_seed)
    env = make_env(LEVEL)
    env.reset()
    ram = env.unwrapped.ram
    policy.reset(seed)
    obs = _Observation(ram)
    goomba_x, max_x, spikes, a_frames = None, 0, 0, 0
    passed = died = flag = False
    frames = 0
    for frames in range(1, max_frames + 1):
        action = policy.act(obs)
        spikes += int(policy.last_readout.gf_spiked)
        a_frames += int(policy.last_buttons.a)
        _, _, done, info = env.step(action)
        mario_x = int(ram[ADDR_MARIO_PAGE]) * 256 + int(ram[ADDR_MARIO_X])
        max_x = max(max_x, mario_x)
        if goomba_x is None:
            seen = [i for i in range(5) if ram[ADDR_ENEMY_ACTIVE + i] and ram[ADDR_ENEMY_TYPE + i] == GOOMBA_TYPE_BYTE]
            if seen:
                goomba_x = int(ram[ADDR_ENEMY_PAGE + seen[0]]) * 256 + int(ram[ADDR_ENEMY_X + seen[0]])
        died = info["life"] < 2 or (done and not info.get("flag_get"))
        flag = bool(info.get("flag_get"))
        if died:
            break
        if goomba_x is not None and mario_x > goomba_x:
            passed = True
            break
        if flag or done:
            break
    env.close()
    return EpisodeResult("real" if shuffle_seed is None else "shuffled", seed, passed, died, flag, frames, max_x,
                         goomba_x, spikes, a_frames)


def _job(args) -> EpisodeResult:
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    seed, shuffle_seed, max_frames = args
    return run_episode(seed, shuffle_seed, max_frames)


def summarize(results: list[EpisodeResult]) -> dict:
    from tool.core.evaluation import wilson_ci
    n, k = len(results), sum(r.passed for r in results)
    lo, hi = wilson_ci(k, n)
    return {"n": n, "passed": k, "pass_rate": k / n if n else 0.0, "pass_rate_ci": [lo, hi],
            "died": sum(r.died for r in results), "flag": sum(r.flag for r in results),
            "runs_with_gf_spike": sum(r.gf_spikes > 0 for r in results),
            "runs_with_a_press": sum(r.a_frames > 0 for r in results),
            "mean_max_x": float(np.mean([r.max_x for r in results])) if n else 0.0}


def run_eval(n: int = DEFAULT_N, seed0: int = DEFAULT_SEED0, workers: int = 1,
             max_frames: int = DEFAULT_MAX_FRAMES) -> dict:
    """Real connectome vs degree-preserving shuffle (shuffle seed 1 + i) on seeds seed0..seed0+n-1."""
    jobs = [(seed0 + i, None, max_frames) for i in range(n)] + [(seed0 + i, 1 + i, max_frames) for i in range(n)]
    if workers > 1:
        with WorkerPool(workers, [(j[1], "degree") for j in jobs if j[1] is not None]) as pool:
            results = pool.map(_job, jobs)
    else:
        results = [_job(j) for j in jobs]
    from brain.policy import BrainPolicy
    out = {"metric": "past the first Goomba", "level": LEVEL, "seeds": [seed0, seed0 + n - 1], "max_frames": max_frames,
           "stamp": BrainPolicy().stamp()}
    for arm in ("real", "shuffled"):
        out[arm] = summarize([r for r in results if r.arm == arm])
    out["episodes"] = [asdict(r) for r in results]
    return out


def format_eval(res: dict) -> str:
    st = res["stamp"]
    lines = [f"Brain eval, {res['level']}, metric: {res['metric']}, seeds {res['seeds'][0]}-{res['seeds'][1]}, "
             f"max {res['max_frames']} frames",
             f"network {st['build_hash']} ({st['built_edges']} built edges, {st['nonzero_weights']} non-zero weights), "
             f"calibration {st['calibration_hash']}"]
    for arm in ("real", "shuffled"):
        s = res[arm]
        lines.append(f"{arm:9s} past first Goomba {s['passed']}/{s['n']} ({s['pass_rate']:.0%}, 95% CI "
                     f"{s['pass_rate_ci'][0]:.0%}-{s['pass_rate_ci'][1]:.0%}); died {s['died']}; "
                     f"GF-spike runs {s['runs_with_gf_spike']}; A-press runs {s['runs_with_a_press']}; "
                     f"mean max x {s['mean_max_x']:.0f}")
    return "\n".join(lines)


def main(argv=None) -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Brain evaluation: real vs shuffled, past the first Goomba, 1-1")
    ap.add_argument("--n", type=int, default=DEFAULT_N)
    ap.add_argument("--seed0", type=int, default=DEFAULT_SEED0)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--max-frames", type=int, default=DEFAULT_MAX_FRAMES)
    ap.add_argument("--out", default=None, help="write the full result (per-episode rows included) as JSON")
    args = ap.parse_args(argv)
    res = run_eval(args.n, args.seed0, args.workers, args.max_frames)
    print(format_eval(res))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=1, default=str)
