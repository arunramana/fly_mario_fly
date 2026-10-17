"""Part 3: combine A/B, episode variation, fitness, baselines. Numbers -> runs/002_test_numbers.json."""
import os
import time
from dataclasses import replace

import numpy as np
import pytest

from flyrun import env as E
from flyrun.fitness import evaluate
from flyrun.knobs import Knobs
from flyrun.run import run_episode
from .conftest import NUMBERS, record

OUT = NUMBERS.with_name("002_test_numbers.json")
SEEDS = list(range(10))
WORKERS = min(8, os.cpu_count() or 1)


def rec(key, value):
    record(key, value, OUT)


def stats(res):
    xs = [p["max_x"] for p in res["per_seed"]]
    ends = [(p["end_reason"], p["x_at_end"]) for p in res["per_seed"]]
    return dict(mean_fitness=res["mean_fitness"], mean_max_x=float(np.mean(xs)), min_max_x=int(min(xs)),
                max_max_x=int(max(xs)), max_x_per_seed=xs, ends=ends, distinct_max_x=len(set(xs)),
                n_flag=int(sum(p["flag_get"] for p in res["per_seed"])))


def test_combine_ab(brain):
    out = {}
    for comb in ("max", "sum"):
        res = evaluate(replace(Knobs(), STIM_COMBINE=comb), brain, SEEDS, workers=WORKERS)
        out[comb] = stats(res)
    winner = max(out, key=lambda c: (out[c]["mean_fitness"], c == "max"))
    out["winner"] = winner
    rec("combine_ab", out)
    print("COMBINE", {c: (out[c]["mean_max_x"], out[c]["min_max_x"], out[c]["ends"]) for c in ("max", "sum")})
    assert Knobs().STIM_COMBINE == winner, f"knob default must be the A/B winner ({winner})"


def test_variation(brain):
    r1 = evaluate(Knobs(), brain, SEEDS, workers=WORKERS)
    st = stats(r1)
    s_a, _ = run_episode(Knobs(), brain, episode_seed=3, max_frames=1500)
    s_b, _ = run_episode(Knobs(), brain, episode_seed=3, max_frames=1500)
    rec("variation", dict(sigma=Knobs().SENSOR_NOISE, **st, same_seed_max_x=[s_a["max_x"], s_b["max_x"]]))
    assert s_a == s_b
    assert st["distinct_max_x"] >= 3, st["max_x_per_seed"]


def test_sigma_ladder(brain):
    """How much variation does each noise structure/size give? (sum combine, fly only, 10 seeds)"""
    out = {}
    for mode in ("neuron", "common"):
        for sg in (0.02, 0.05, 0.10, 0.20, 0.30):
            res = evaluate(replace(Knobs(), NOISE_MODE=mode, SENSOR_NOISE=sg), brain, SEEDS, workers=WORKERS)
            st = stats(res)
            out[f"{mode}_{sg:.2f}"] = dict(distinct=st["distinct_max_x"], max_x=sorted(st["max_x_per_seed"]),
                                          mean_fitness=st["mean_fitness"])
    rec("sigma_ladder", out)
    print("LADDER", {k: (v["distinct"], v["max_x"]) for k, v in out.items()})


def test_fitness_guard(brain):
    with pytest.raises(RuntimeError):
        evaluate(Knobs(), brain, [0], workers=1, takeover_x=1037)


def test_baseline_ranking(brain):
    arms = {}
    for name, ctl in (("stand", "stand"), ("right", "right"), ("right_randA", "right_randA"),
                      ("theta_rule", "theta_rule"), ("fly", None)):
        res = evaluate(Knobs(), brain, SEEDS, workers=WORKERS, controller=ctl)
        st = stats(res)
        st["death_x"] = [x for (r, x) in st["ends"] if r == "died"]
        arms[name] = st
    # context arm (not asserted): the fly with no sensor noise, i.e. its noise-free behaviour
    res = evaluate(replace(Knobs(), SENSOR_NOISE=0.0), brain, SEEDS, workers=WORKERS)
    st = stats(res)
    st["death_x"] = [x for (r, x) in st["ends"] if r == "died"]
    arms["fly_sigma0"] = st
    rec("baselines", arms)
    print("BASELINES", {k: (round(v["mean_fitness"]), v["min_max_x"], v["max_max_x"]) for k, v in arms.items()})
    assert arms["stand"]["mean_fitness"] < arms["right"]["mean_fitness"] <= arms["fly"]["mean_fitness"]


def test_timing(brain):
    t0 = time.time()
    r = evaluate(Knobs(), brain, SEEDS[:4], workers=1)
    per = (time.time() - t0) / 4
    frames = float(np.mean([p["frames"] for p in r["per_seed"]]))
    out = dict(secs_per_episode_1worker=per, mean_frames=frames, ms_per_frame=1000 * per / frames)
    for n in (1, 4, 8, 12):
        t0 = time.time()
        evaluate(Knobs(), brain, list(range(2 * n)) if n > 1 else [0, 1], workers=n)
        dt = time.time() - t0
        out[f"episodes_per_min_{n}w"] = (2 * n if n > 1 else 2) / dt * 60
    rec("timing", out)
    print("TIMING", out)


def test_level_complete():
    from flyrun.levelmap import scan_level
    df, best, flag = scan_level()
    df.to_csv(NUMBERS.with_name("001_level_map.csv"), index=False)
    rec("level_map_full", dict(reached_x=best, flag_get=flag, n_walls=int((df.kind == "wall").sum()),
                               n_pits=int((df.kind == "pit").sum())))
    assert flag
