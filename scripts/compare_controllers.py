"""
compare_controllers.py -- three controllers, same level, same env, compared
button-press-trace by button-press-trace:

  A. The fly circuit as it stands (g=2.0, HybridState, the real W).
  B. Shuffled connectome -- SPEC section 5's control, still owed: same
     neurons, same in/out degree distribution, same signs, edges rewired at
     random (circuit.build_shuffled). Same g/thresholds as A -- only the
     wiring changes.
  C. A one-line baseline: press A when theta > c, with c tuned (by
     bisection) to fire at the same rate as A.

The NES emulator has no RNG -- "same seed" is automatic from env.reset().
The only randomness anywhere is the shuffle's rewiring, seeded and fixed.
Controllers necessarily diverge in trajectory once they press differently
(a jump changes Mario's motion, hence future enemy encounters), so "compare
frame by frame" here means: log each controller's own run in full, then
report the first frame their decisions differ and the aggregate difference,
not force them onto a single fixed input trace that doesn't exist once
actions differ.

A minimal, non-neural "unstick": if mario_x hasn't moved in `UNSTICK_AFTER`
frames (wedged against a pipe -- see README), nudge left for a few frames.
This is a mechanical anti-stall kludge shared identically by all three
controllers, not steering driven by any circuit.

Also does the section-5 shuffle control properly (n=20, each tuned via
Diagnostic 4 -- see shuffle_sweep.py, run that first), a 3-level x 3-seed
battery, and the runs/004*.mp4 recordings CLAUDE.md requires.

    .venv/Scripts/python.exe -m scripts.compare_controllers
"""
from __future__ import annotations

import os
os.environ.setdefault("OMP_NUM_THREADS", "1")     # small-matmul BLAS threading
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")  # overhead otherwise dominates
os.environ.setdefault("MKL_NUM_THREADS", "1")       # -- see diag4.py / shuffle_sweep.py

import multiprocessing as mp
from pathlib import Path

import setuptools  # noqa: F401  -- must import before gym on py3.12
import numpy as np
import pandas as pd
from PIL import Image
import gym_super_mario_bros
from nes_py.wrappers import JoypadSpace

from fly.connectome import circuit
from fly.network import dynamics
from fly.connectome.load_cached import load
from render.video import _ensure_ffmpeg_on_path
from run_mario import (ADDR_MARIO_X, ADDR_ENEMY_X, ADDR_ENEMY_ACTIVE,
                        N_ENEMY_SLOTS, W_TILE, enemy_thetas,
                        JUMP_HOLD_FRAMES, JUMP_COOLDOWN_FRAMES,
                        G, DNP01_SPIKE_THRESHOLD, SPIKE_AMP, TTMN_PRESS_THRESHOLD)

MOVES = [["right", "B"], ["right", "A", "B"], ["left"]]
RUN, JUMP, LEFT = 0, 1, 2

MAX_FRAMES = 4000
UNSTICK_AFTER = 90   # frames with mario_x unchanged before nudging
UNSTICK_FRAMES = 12  # how long to hold left
NOOP_MAX = 600        # widest random run-up before a "seed" starts recording
LEVELS = ["1-1", "1-2", "1-3"]


def make_env(level="1-1"):
    env = gym_super_mario_bros.make(f"SuperMarioBros-{level}-v0")
    return JoypadSpace(env, MOVES)


def noop_frames_for_seed(seed, noop_max=NOOP_MAX):
    """The emulator has no RNG of its own -- this is the only place
    randomness enters. A fixed number of blind run-right frames before
    recording starts, seeded, shifts WHICH part of the level (which enemies,
    in what configuration) the comparison actually sees. Two jump events on
    one fixed run can't separate three controllers (per your point 3); three
    different start offsets per level can."""
    return int(np.random.default_rng(seed).integers(0, noop_max))


def run_episode(decide_fn, max_frames=MAX_FRAMES, level="1-1", seed=0,
                 hold_frames=JUMP_HOLD_FRAMES, cooldown_frames=JUMP_COOLDOWN_FRAMES,
                 unstick_after=UNSTICK_AFTER, unstick_frames=UNSTICK_FRAMES,
                 capture_telemetry=False, capture_frames_dir=None, force_noop=None):
    """Shared mechanical layer: every controller gets identical button-hold,
    cooldown, unstick, level, and seeded-run-up handling. `decide_fn(frame,
    theta, dtheta)` is called every frame (so any internal dynamics keep
    evolving even while a jump/unstick is in progress) and returns
    (raw_signal, extra_dict); the harness only acts on raw_signal when not
    already mid-jump/cooldown/stuck.

    `capture_frames_dir`, if given, dumps the raw game frame *for* each
    logged step (the frame decide_fn/telemetry were computed from, not the
    one produced by stepping past it) as PNG, for brain_panel.render_run.

    `force_noop`, if given, overrides the seed-derived warm-up length (e.g.
    0, for an isolated with/without-warm-up comparison) -- diagnostic only,
    not used by the battery.
    """
    env = make_env(level)
    obs = env.reset()
    ram = env.unwrapped.ram

    noop = noop_frames_for_seed(seed) if force_noop is None else force_noop
    for _ in range(noop):
        obs, _, done, _ = env.step(RUN)
        if done:
            obs = env.reset()
            ram = env.unwrapped.ram

    prev_theta = {"L": 0.0, "R": 0.0}
    jump_hold = jump_cooldown = 0
    n_jumps = 0
    n_unsticks = 0
    stuck_count = 0
    unstick_remaining = 0
    last_x = None

    log = {"frame": [], "mario_x": [], "theta": [], "raw_signal": [], "press": [], "extra": []}
    if capture_frames_dir is not None:
        capture_frames_dir = Path(capture_frames_dir)
        capture_frames_dir.mkdir(parents=True, exist_ok=True)

    frame = 0
    done = False
    while frame < max_frames and not done:
        mario_x = int(ram[ADDR_MARIO_X])
        theta, dtheta, d_out = enemy_thetas(ram, mario_x, prev_theta)
        prev_theta = theta

        raw_signal, extra = decide_fn(frame, theta, dtheta)

        if unstick_remaining > 0:
            action = LEFT
            press = False
            unstick_remaining -= 1
        else:
            if jump_cooldown > 0:
                jump_cooldown -= 1
            elif jump_hold == 0 and raw_signal:
                jump_hold = hold_frames
                n_jumps += 1
            if jump_hold > 0:
                action = JUMP
                press = True
                jump_hold -= 1
                if jump_hold == 0:
                    jump_cooldown = cooldown_frames
            else:
                action = RUN
                press = False

        if unstick_remaining == 0 and jump_hold == 0 and last_x is not None and mario_x == last_x:
            stuck_count += 1
        else:
            stuck_count = 0
        last_x = mario_x
        if stuck_count >= unstick_after:
            unstick_remaining = unstick_frames
            n_unsticks += 1
            stuck_count = 0

        log["frame"].append(frame)
        log["mario_x"].append(mario_x)
        log["theta"].append(max(theta["L"], theta["R"]))
        log["raw_signal"].append(bool(raw_signal))
        log["press"].append(bool(press))
        if capture_telemetry:
            log["extra"].append(extra)
        if capture_frames_dir is not None:
            Image.fromarray(obs).save(capture_frames_dir / f"{frame:05d}.png")

        obs, reward, done, info = env.step(action)
        frame += 1

    env.close()
    for k in ("frame", "mario_x", "theta", "raw_signal", "press"):
        log[k] = np.array(log[k])
    log["n_jumps"] = n_jumps
    log["n_unsticks"] = n_unsticks
    log["n_frames"] = frame
    log["died_or_flagged"] = done
    log["level"] = level
    log["seed"] = seed
    log["noop_frames"] = noop
    return log


def make_circuit_decider(W, bodies, g, spike_threshold, spike_amp, ttmn_threshold):
    K = W.shape[0]
    m = lambda t, s: ((bodies["type"] == t) & (bodies["somaSide"] == s)).to_numpy()
    msk = {
        "LC4_L": m("LC4", "L"), "LC4_R": m("LC4", "R"),
        "LPLC2_L": m("LPLC2", "L"), "LPLC2_R": m("LPLC2", "R"),
        "LC4_all": (bodies["type"] == "LC4").to_numpy(),
        "LPLC2_all": (bodies["type"] == "LPLC2").to_numpy(),
        "TTMn_L": m("TTMn", "L"), "TTMn_R": m("TTMn", "R"),
        "DNp01_L": m("DNp01", "L"), "DNp01_R": m("DNp01", "R"),
    }
    dnp01_idx = np.concatenate([np.where(msk["DNp01_L"])[0], np.where(msk["DNp01_R"])[0]])
    st = dynamics.HybridState(K, dnp01_idx, spike_threshold=spike_threshold, spike_amp=spike_amp)

    def decide(frame, theta, dtheta):
        I = np.zeros(K)
        I[msk["LC4_L"]] = abs(dtheta["L"])
        I[msk["LPLC2_L"]] = theta["L"]
        I[msk["LC4_R"]] = abs(dtheta["R"])
        I[msk["LPLC2_R"]] = theta["R"]
        for _ in range(dynamics.SUBSTEPS):
            h = st.step(W, g, I)
        ttmn_val = max(h[msk["TTMn_L"]].mean(), h[msk["TTMn_R"]].mean())
        # brain_panel.render_run wants lc4/lplc2/mem/spike/ttmn per frame
        extra = {"ttmn": ttmn_val, "lc4": h[msk["LC4_all"]].mean(),
                  "lplc2": h[msk["LPLC2_all"]].mean(),
                  "mem": float(st.mem.max()), "spike": bool(st.just_spiked.any())}
        return ttmn_val >= ttmn_threshold, extra

    return decide


def make_baseline_decider(c):
    """No neurons -- brain_panel still gets the same telemetry columns,
    all zero, so its panel honestly shows a controller with no brain rather
    than needing a special no-panel code path."""
    def decide(frame, theta, dtheta):
        theta_val = max(theta["L"], theta["R"])
        extra = {"theta_val": theta_val, "ttmn": 0.0, "lc4": 0.0, "lplc2": 0.0,
                  "mem": 0.0, "spike": False}
        return theta_val > c, extra
    return decide


def tune_baseline_c(target_jumps, c_lo=0.0, c_hi=1.5, tol=1e-3, max_iter=25):
    """Bisection on c: lower c -> more frequent jumps (monotonic). Finds the
    c whose jump count is closest to target_jumps."""
    def n_jumps_at(c):
        log = run_episode(make_baseline_decider(c))
        return log["n_jumps"], log

    lo, hi = c_lo, c_hi
    n_lo, _ = n_jumps_at(lo)
    n_hi, _ = n_jumps_at(hi)
    best = None
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        n_mid, log_mid = n_jumps_at(mid)
        if best is None or abs(n_mid - target_jumps) < abs(best[1] - target_jumps):
            best = (mid, n_mid, log_mid)
        if n_mid == target_jumps:
            return best
        if n_mid > target_jumps:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return best


def first_divergence(log_a, log_b):
    n = min(len(log_a["press"]), len(log_b["press"]))
    diff = log_a["press"][:n] != log_b["press"][:n]
    idx = np.where(diff)[0]
    return int(idx[0]) if len(idx) else None, n


def corr(x, y):
    x, y = np.asarray(x), np.asarray(y)
    if np.std(x) < 1e-12 or np.std(y) < 1e-12:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


def _build_decider_for_task(kind, shuffle_seed, g_or_c):
    """Rebuilds a decide_fn from picklable primitives instead of a closure --
    a closure over a live HybridState/W array can't cross a
    multiprocessing.Pool boundary, so each worker reconstructs what it needs
    itself. `kind` is 'real' | 'shuffle' | 'baseline'."""
    if kind == "baseline":
        return make_baseline_decider(g_or_c)
    bodies_, edges_, total_input_, signs_, W_, order_, diag_ = load(N=60)
    if kind == "real":
        W_use = W_
    elif kind == "shuffle":
        W_use, order_s, _ = build_shuffled_quiet(bodies_, edges_, total_input_, signs_, shuffle_seed)
        assert (order_ == order_s).all()
    else:
        raise ValueError(f"unknown controller kind: {kind}")
    return make_circuit_decider(W_use, bodies_, g_or_c, DNP01_SPIKE_THRESHOLD, SPIKE_AMP, TTMN_PRESS_THRESHOLD)


def _run_battery_task(task):
    """One independent (controller, level, seed) run -- top-level function so
    multiprocessing (spawn, the Windows default) can pickle a reference to
    it. Each worker process re-imports this module fresh, which re-runs the
    OMP_NUM_THREADS=1 etc. os.environ.setdefault calls at the top of the
    file before numpy is ever imported -- so every worker gets a
    single-threaded BLAS automatically, no extra plumbing needed."""
    label, param_desc, kind, shuffle_seed, g_or_c, level, seed, max_frames = task
    decide = _build_decider_for_task(kind, shuffle_seed, g_or_c)
    log = run_episode(decide, level=level, seed=seed, max_frames=max_frames)
    return {
        "controller": label, "param": param_desc, "level": level, "seed": seed,
        "noop_frames": log["noop_frames"], "survival_frames": log["n_frames"],
        "jumps": log["n_jumps"], "unsticks": log["n_unsticks"],
        "died_or_flagged": log["died_or_flagged"],
    }


def battery(controllers, levels=LEVELS, seeds=(0, 1, 2), max_frames=MAX_FRAMES, n_workers=8):
    """controllers: list of (label, param_desc, kind, shuffle_seed, g_or_c)
    -- see _build_decider_for_task. Every (controller, level, seed) run is
    independent (a fresh decider, a fresh env, no shared state), so they run
    as separate tasks in a multiprocessing.Pool(n_workers). Returns a list
    of row dicts, order not guaranteed (imap_unordered) -- no verdict, just
    the numbers."""
    tasks = [
        (label, param_desc, kind, shuffle_seed, g_or_c, level, seed, max_frames)
        for (label, param_desc, kind, shuffle_seed, g_or_c) in controllers
        for level in levels
        for seed in seeds
    ]
    rows = []
    with mp.Pool(n_workers) as pool:
        for i, row in enumerate(pool.imap_unordered(_run_battery_task, tasks)):
            rows.append(row)
            print(f"  [{i + 1}/{len(tasks)}] {row['controller']:14s} level={row['level']} "
                  f"seed={row['seed']} noop={row['noop_frames']:4d}  "
                  f"survival={row['survival_frames']:5d} jumps={row['jumps']:2d} "
                  f"unsticks={row['unsticks']:2d} "
                  f"ended={'died/flagged' if row['died_or_flagged'] else 'hit max_frames'}",
                  flush=True)
    return rows


def build_telemetry_df(log):
    ex = log["extra"]
    return pd.DataFrame({
        "frame": log["frame"], "theta": log["theta"],
        "lc4": [e.get("lc4", 0.0) for e in ex], "lplc2": [e.get("lplc2", 0.0) for e in ex],
        "mem": [e.get("mem", 0.0) for e in ex], "spike": [e.get("spike", False) for e in ex],
        "ttmn": [e.get("ttmn", 0.0) for e in ex],
    })


def record_hero_run(decide_fn, label, out_mp4, level="1-1", seed=0, max_frames=MAX_FRAMES,
                     caption=""):
    """One full episode with telemetry + per-frame PNGs captured, composited
    into runs/<...>.mp4 via brain_panel.render_run (CLAUDE.md: every
    behaviour-changing sprint ends with a video in runs/)."""
    import tempfile
    _ensure_ffmpeg_on_path()
    from render import brain_panel

    with tempfile.TemporaryDirectory() as tmp:
        log = run_episode(decide_fn, level=level, seed=seed, max_frames=max_frames,
                           capture_telemetry=True, capture_frames_dir=tmp)
        print(f"  {label}: {log['n_frames']} frames, {log['n_jumps']} jumps -> {out_mp4}")
        tel = build_telemetry_df(log)
        brain_panel.render_run(tel, tmp, out_mp4, caption=caption)
    return log


def build_shuffled_quiet(bodies, edges, total_input, signs, seed):
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        return circuit.build_shuffled(bodies, edges, total_input, signs, seed=seed)


def pick_best_shuffle(sweep, bodies, edges, total_input, signs, level="1-1", seed=0):
    """Rank by LIVE performance (survival frames, then jumps), not just by
    having passed Diagnostic 4 -- passing the diagnostic means well-behaved,
    not necessarily good at the game. Prefer confirmed-g shuffles; only fall
    back to every shuffle (at its best screen candidate, or g_real if it
    never even screened) if none confirmed."""
    confirmed = [k for k in sweep if k.startswith("shuffle") and sweep[k]["g"] is not None]
    pool = confirmed if confirmed else [k for k in sweep if k.startswith("shuffle")]
    best = None
    for k in pool:
        seed_idx = int(k.replace("shuffle", ""))
        v = sweep[k]
        g_try = v["g"] if v["g"] is not None else (
            v["screen_candidates"][-1] if v["screen_candidates"] else sweep["real"]["g"])
        W_s, order_s, _ = build_shuffled_quiet(bodies, edges, total_input, signs, seed_idx)
        log = run_episode(make_circuit_decider(W_s, bodies, g_try, DNP01_SPIKE_THRESHOLD,
                                                SPIKE_AMP, TTMN_PRESS_THRESHOLD),
                           level=level, seed=seed)
        score = (log["n_frames"], log["n_jumps"])
        print(f"  shuffle{seed_idx:02d} g={g_try:<6} confirmed={v['g'] is not None} "
              f"-> survival={log['n_frames']} jumps={log['n_jumps']}", flush=True)
        if best is None or score > best[0]:
            best = (score, seed_idx, g_try, v["g"] is not None)
    return best  # (score, seed_idx, g, was_confirmed)


if __name__ == "__main__":
    import json

    print("Loading the expanded N=60 circuit (cached)...")
    bodies, edges, total_input, signs, W, order, diag = load(N=60)

    with open("projects/legacy/telemetry/shuffle_sweep_results.json") as f:
        sweep = json.load(f)
    g_real = sweep["real"]["g"]
    n_confirmed = sum(1 for k, v in sweep.items() if k.startswith("shuffle") and v["g"] is not None)
    print(f"\nshuffle_sweep_results.json: real g={g_real}; "
          f"{n_confirmed}/20 shuffles found a confirmed g.")

    print("\nPicking the best-performing shuffle by live play (level 1-1, seed 0)...")
    (score, best_seed, g_best, was_confirmed) = pick_best_shuffle(
        sweep, bodies, edges, total_input, signs)
    print(f"Best: shuffle{best_seed:02d}, g={g_best}, confirmed={was_confirmed}, "
          f"live score (survival, jumps)={score}")
    W_best, order_best, _ = build_shuffled_quiet(bodies, edges, total_input, signs, best_seed)
    assert (order == order_best).all()

    print(f"\nTuning C's threshold c to match A's jump rate on level 1-1, seed 0...")
    log_a0 = run_episode(make_circuit_decider(W, bodies, g_real, DNP01_SPIKE_THRESHOLD,
                                               SPIKE_AMP, TTMN_PRESS_THRESHOLD))
    c_star, n_c, log_c0 = tune_baseline_c(log_a0["n_jumps"])
    print(f"A: survival={log_a0['n_frames']} jumps={log_a0['n_jumps']} "
          f"ended={'died/flagged' if log_a0['died_or_flagged'] else 'hit max_frames'}")
    print(f"c={c_star:.4f} -> C jumps={n_c} (target {log_a0['n_jumps']}), "
          f"survival={log_c0['n_frames']} "
          f"ended={'died/flagged' if log_c0['died_or_flagged'] else 'hit max_frames'}")

    deciders = {
        "A_real": (lambda: make_circuit_decider(W, bodies, g_real, DNP01_SPIKE_THRESHOLD,
                                                 SPIKE_AMP, TTMN_PRESS_THRESHOLD),
                   f"g={g_real} (Diagnostic-4 screen+confirm on real W)"),
        f"B_shuffle{best_seed:02d}": (lambda: make_circuit_decider(W_best, bodies, g_best,
                                                                    DNP01_SPIKE_THRESHOLD, SPIKE_AMP,
                                                                    TTMN_PRESS_THRESHOLD),
                                      f"g={g_best} (best of 20 shuffles, "
                                      f"{'confirmed' if was_confirmed else 'unconfirmed, best screen candidate'} "
                                      f"Diagnostic-4, ranked by live play)"),
        "C_theta": (lambda: make_baseline_decider(c_star), f"c={c_star:.4f} (tuned to A's jump rate, 1-1 seed 0)"),
    }

    controllers_spec = [
        ("A_real", deciders["A_real"][1], "real", None, g_real),
        (f"B_shuffle{best_seed:02d}", deciders[f"B_shuffle{best_seed:02d}"][1], "shuffle", best_seed, g_best),
        ("C_theta", deciders["C_theta"][1], "baseline", None, c_star),
    ]

    print("\n=== Battery: 3 levels x 3 seeds x 3 controllers (multiprocessing.Pool(8)) ===")
    rows = battery(controllers_spec, levels=LEVELS, seeds=(0, 1, 2), n_workers=8)
    df = pd.DataFrame(rows)
    df.to_csv("projects/legacy/telemetry/compare_controllers_battery.csv", index=False)
    print("\nSaved projects/legacy/telemetry/compare_controllers_battery.csv. No conclusions drawn here --"
          " see the README once this is reviewed.")

    print("\n=== Recording hero runs (level 1-1, seed 0) for runs/004*.mp4 ===")
    record_hero_run(deciders["A_real"][0](), "A", "runs/004a_real.mp4", level="1-1", seed=0,
                     caption=f"A: real connectome, {deciders['A_real'][1]}")
    record_hero_run(deciders[f"B_shuffle{best_seed:02d}"][0](), "B", "runs/004b_shuffled_best.mp4",
                     level="1-1", seed=0,
                     caption=f"B: shuffled connectome (best of 20), {deciders[f'B_shuffle{best_seed:02d}'][1]}")
    record_hero_run(deciders["C_theta"][0](), "C", "runs/004c_theta.mp4", level="1-1", seed=0,
                     caption=f"C: theta > c baseline, {deciders['C_theta'][1]}")
