# What this file does, in plain English:
# Experiment E2a ("get past the pipe"). Mario stands on flat ground about 127 px
# before the first pipe of level 1-1 and the fly takes over, with the home
# landmark on and the pipe seen as an expanding face (looming from static
# obstacles). The run is repeated with the real connectome, two kinds of rewired
# copy, and a control in which the obstacle cue is switched off. Each run records
# whether Mario ended up beyond the pipe, when the Giant Fiber fired relative to
# the pipe, when and for how long the jump button was pressed and where he took
# off. Nothing here presses a button or touches the brain; it only watches.
"""brain/e2a.py -- docs/SPEC_e2a.md section 3.

    .venv/Scripts/python.exe -m brain.e2a [--n 20] [--seed0 7100] [--workers 4] [--out result.json]

Metrics are fixed in the SPEC before any run (outcome-neutral):
  cleared  Mario's world x > E2A_PIPE_RIGHT_X (the pipe's right edge) while alive within E2A_MAX_FRAMES
  other ends: died (dying state), stuck (no new max x for BASELINE_STUCK_FRAMES), timeout
Also: GF fired before the face (first spike while Mario's x < PIPE1_X), first-A frame / x / run, take-off x, tap fraction.
"""

from __future__ import annotations

import dataclasses
import json
import math
import multiprocessing as mp
import os
from dataclasses import asdict, dataclass

import numpy as np

from brain.baseline import ADDR_GAME_ENGINE, BASELINE_STUCK_FRAMES, BASELINE_TAP_MAX_FRAMES, ENGINE_DYING, a_runs
from brain.scenes import E2A_SCENE_ID, SceneSpec, apply_rules, build_scene, load_scene
from brain.settings import SenseSettings, settings_for

EXPERIMENT_ID = "E2a"
E2A_SEED0, N = 7100, 20          # held-out; the experimenter runs them once (smoke tests use 9100)
E2A_MAX_FRAMES = 600             # invented bound (10 s)
PIPE1_X = 448                    # world x of pipe 1's left edge (measured in the tile map; docs/INVESTIGATION_phase6.md (b))
E2A_PIPE_RIGHT_X = 479           # world x of pipe 1's right edge (448 + 32 - 1): cleared = beyond this
ARMS = ("real", "shuffled", "shuffled_class")
SHUFFLED_ARMS = ("shuffled", "shuffled_class")
NECESSITY_ARMS = ("real_no_obstacle",)               # eval only: the real connectome with obstacle expansion removed
ALL_ARMS = ARMS + NECESSITY_ARMS
CRITERION = {"real_cleared_min": 14, "shuffled_cleared_max": 2, "no_obstacle_cleared_max": 2, "n": 20}
METRIC = f"cleared pipe 1 (world x > {E2A_PIPE_RIGHT_X}) alive within {E2A_MAX_FRAMES} frames"
END_REASONS = ("cleared", "died", "stuck", "timeout")


@dataclass
class E2aResult:
    experiment: str
    arm: str
    seed: int
    shuffle_seed: int | None
    cleared: bool
    outcome: str                  # one of END_REASONS
    died: bool
    frames: int
    cleared_frame: int | None
    max_x: int
    gf_fired: bool
    first_gf_frame: int | None
    gf_before_face: bool          # the GF first fired while Mario's x was below PIPE1_X
    first_gf_x: int | None
    theta_at_gf_deg: float | None  # obstacle theta the fly saw on the frame the GF first fired
    d_at_gf_px: float | None       # obstacle distance on that frame
    gf_output_max_hz: float
    ttmn_max_hz: float
    a_pressed: bool
    a_frames: int
    first_a_frame: int | None
    first_a_x: int | None
    first_a_run: int | None
    tap: bool                     # first A run <= BASELINE_TAP_MAX_FRAMES
    takeoff_frame: int | None     # first frame Mario was airborne
    takeoff_x: int | None
    left_frames: int
    right_frames: int
    b_frames: int


def arm_settings(arm: str, used: SenseSettings) -> SenseSettings:
    """The necessity arm drops obstacle expansion (nothing else); every other arm keeps the experiment's settings."""
    return dataclasses.replace(used, obstacle_expansion=False) if arm == "real_no_obstacle" else used


def arm_of(arm: str, shuffle_seed: int | None) -> str:
    if arm not in ALL_ARMS or (arm in SHUFFLED_ARMS) != (shuffle_seed is not None):
        raise ValueError(f"arm {arm!r} with shuffle_seed {shuffle_seed!r}: shuffled arms need a shuffle seed, real arms none")
    return arm


def run_e2a_episode(seed: int, arm: str = "real", shuffle_seed: int | None = None, settings: SenseSettings | None = None,
                    scene: SceneSpec | None = None, max_frames: int | None = None, network=None, calibration=None,
                    on_frame=None, should_stop=None, record_rows: bool = False):
    """One E2a episode. Returns (E2aResult, rows, stamp)."""
    arm = arm_of(arm, shuffle_seed)
    from brain.e1 import _row
    from brain.policy import BrainPolicy
    from mario.emulator.env import make_env
    from mario.ram.addresses import (ADDR_MARIO_PAGE, ADDR_MARIO_SCREEN_X, ADDR_MARIO_X, ADDR_MARIO_Y, ADDR_PLAYER_STATE)
    scene = scene or load_scene(E2A_SCENE_ID)
    max_frames = max_frames or E2A_MAX_FRAMES
    used = arm_settings(arm, settings_for(EXPERIMENT_ID, settings))
    policy = BrainPolicy(network=network, calibration=calibration, shuffle_seed=shuffle_seed,
                         shuffle_mode="class" if arm == "shuffled_class" else "degree", settings=used)
    env = make_env(scene.level)
    build_scene(env, scene)
    ram = env.unwrapped.ram
    policy.reset(seed)

    class _Obs:
        pass
    obs = _Obs()
    obs.ram = ram

    def world_x() -> int:
        return int(ram[ADDR_MARIO_PAGE]) * 256 + int(ram[ADDR_MARIO_X])

    mario_x = max_x = last_progress = world_x()
    first_gf = first_gf_x = theta_gf = d_gf = cleared_frame = takeoff_frame = takeoff_x = None
    a_seq: list[bool] = []
    first_a_frame = first_a_x = None
    left_frames = right_frames = b_frames = 0
    gf_out_max = ttmn_max = 0.0
    end = None
    rows: list[dict] = []
    frames = 0
    for frames in range(1, max_frames + 1):
        if should_stop is not None and should_stop():
            break
        x_before = mario_x
        action = policy.act(obs)
        readout, buttons = policy.last_readout, policy.last_buttons
        if readout.gf_spiked and first_gf is None:
            first_gf, first_gf_x = frames, x_before
            theta_gf = math.degrees(policy.last_obstacle_theta)
            d_gf = None if policy.last_obstacle_distance is None else float(policy.last_obstacle_distance)
        if buttons.a and first_a_frame is None:
            first_a_frame, first_a_x = frames, x_before
        a_seq.append(bool(buttons.a))
        left_frames += int(buttons.left)
        right_frames += int(buttons.right)
        b_frames += int(buttons.b)
        gf_out_max, ttmn_max = max(gf_out_max, readout.pooled("GF")), max(ttmn_max, readout.pooled("TTMn"))
        screen_obs, _, done, info = env.step(action)
        apply_rules(ram, scene)                              # scene setup: enemies stay removed (never touches the fly)
        mario_x = world_x()
        if mario_x > max_x:
            max_x, last_progress = mario_x, frames
        if takeoff_frame is None and int(ram[ADDR_PLAYER_STATE]) != 0:
            takeoff_frame, takeoff_x = frames, x_before      # the position of the frame whose action left the ground
        dying = int(ram[ADDR_GAME_ENGINE]) == ENGINE_DYING
        if dying or (done and not info.get("flag_get")):
            end = "died"
        elif mario_x > E2A_PIPE_RIGHT_X:
            end, cleared_frame = "cleared", frames
        elif frames - last_progress >= BASELINE_STUCK_FRAMES:
            end = "stuck"
        if on_frame is not None or record_rows:
            row = _row(frames, ram, policy, readout, buttons, action, mario_x, None, ADDR_MARIO_SCREEN_X, ADDR_MARIO_Y)
            row["theta"] = policy.last_obstacle_theta          # what the fly saw: the obstacle face (E2a has no enemy)
            row["d_px"] = policy.last_obstacle_distance if policy.last_obstacle_distance is not None else float("nan")
            if record_rows:
                rows.append(row)
            if on_frame is not None:
                on_frame(frames, screen_obs, row)
        if end is not None or done:
            break
    env.close()
    outcome = end or "timeout"
    runs = a_runs(a_seq)
    res = E2aResult(EXPERIMENT_ID, arm, seed, shuffle_seed, outcome == "cleared", outcome, outcome == "died", frames, cleared_frame,
                    max_x, first_gf is not None, first_gf, first_gf_x is not None and first_gf_x < PIPE1_X, first_gf_x, theta_gf,
                    d_gf, gf_out_max, ttmn_max, bool(runs), sum(a_seq), first_a_frame, first_a_x, runs[0] if runs else None,
                    bool(runs) and runs[0] <= BASELINE_TAP_MAX_FRAMES, takeoff_frame, takeoff_x, left_frames, right_frames, b_frames)
    stamp = {**policy.stamp(), "scene": scene.to_dict(), "experiment": EXPERIMENT_ID, "senses_used": used.to_dict()}
    return res, rows, stamp


# ---- evaluation ----------------------------------------------------------------------------------------------------
def _job(args) -> E2aResult:
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    seed, arm, shuffle_seed, max_frames, settings = args
    return run_e2a_episode(seed, arm, shuffle_seed, SenseSettings.from_dict(settings), max_frames=max_frames)[0]


def summarize(results: list[E2aResult]) -> dict:
    from tool.core.evaluation import wilson_ci
    n = len(results)
    k = sum(r.cleared for r in results)
    a_eps = [r for r in results if r.a_pressed]
    taps = sum(r.tap for r in a_eps)
    ends = {e: sum(r.outcome == e for r in results) for e in END_REASONS}
    cf = [r.cleared_frame for r in results if r.cleared and r.cleared_frame is not None]

    def med(vals):
        vals = [v for v in vals if v is not None]
        return float(np.median(vals)) if vals else None
    return {"n": n, "cleared": k, "cleared_ci": list(wilson_ci(k, n)), "end_reasons": ends,
            "gf_fired": sum(r.gf_fired for r in results), "gf_before_face": sum(r.gf_before_face for r in results),
            "a_pressed_runs": len(a_eps), "tap_episodes": taps, "tap_fraction": taps / len(a_eps) if a_eps else None,
            "takeoff_runs": sum(r.takeoff_frame is not None for r in results),
            "first_a_run_median": med([r.first_a_run for r in results]),
            "first_a_x_median": med([r.first_a_x for r in results]), "takeoff_x_median": med([r.takeoff_x for r in results]),
            "first_gf_x_median": med([r.first_gf_x for r in results]), "theta_at_gf_deg_median": med([r.theta_at_gf_deg for r in results]),
            "gf_output_max_hz": max((r.gf_output_max_hz for r in results), default=0.0),
            "ttmn_max_hz": max((r.ttmn_max_hz for r in results), default=0.0),
            "frames_to_clear": {"n": len(cf), "median": float(np.median(cf)) if cf else None},
            "max_x_median": float(np.median([r.max_x for r in results])) if n else 0.0}


def run_eval(n: int = N, seed0: int | None = None, workers: int = 1, max_frames: int | None = None,
             arms: tuple[str, ...] | None = None, settings: SenseSettings | None = None) -> dict:
    """Real vs degree vs class shuffle (shuffle seed 1 + i) and the real_no_obstacle necessity arm, seeds seed0..seed0+n-1, the
    same noise seed and the same sense settings in every arm (the necessity arm drops obstacle expansion only)."""
    arms = ARMS + NECESSITY_ARMS if arms is None else arms
    from brain.policy import BrainPolicy
    seed0 = E2A_SEED0 if seed0 is None else seed0
    used = settings_for(EXPERIMENT_ID, settings)
    jobs = [(seed0 + i, arm, 1 + i if arm in SHUFFLED_ARMS else None, max_frames, used.to_dict()) for arm in arms for i in range(n)]
    if workers > 1:
        with mp.get_context("spawn").Pool(workers) as pool:
            results = pool.map(_job, jobs)
    else:
        results = [_job(j) for j in jobs]
    out = {"experiment": EXPERIMENT_ID, "metric": METRIC, "seeds": [seed0, seed0 + n - 1],
           "max_frames": max_frames or E2A_MAX_FRAMES, "stuck_frames": BASELINE_STUCK_FRAMES,
           "scene": load_scene(E2A_SCENE_ID).to_dict(), "stamp": BrainPolicy(settings=used).stamp(),
           "criterion": dict(CRITERION), "arms": list(arms)}
    for arm in arms:
        out[arm] = summarize([r for r in results if r.arm == arm])
    out["episodes"] = [asdict(r) for r in results]
    return out


def format_eval(res: dict) -> str:
    st = res["stamp"]
    lines = [f"E2a {res['metric']}, scene {res['scene']['id']} ({res['scene']['scene_hash']}), seeds "
             f"{res['seeds'][0]}-{res['seeds'][1]}, max {res['max_frames']} frames",
             f"network {st['build_hash']}, calibration {st['calibration_hash']}, senses {st.get('senses')}"]
    for arm in res["arms"]:
        s = res[arm]
        lo, hi = s["cleared_ci"]
        tf = "no A presses" if s["tap_fraction"] is None else f"taps {s['tap_episodes']}/{s['a_pressed_runs']}"
        ends = ", ".join(f"{k} {v}" for k, v in s["end_reasons"].items() if v)
        fr = s["frames_to_clear"]
        lines.append(
            f"{arm:17s} cleared {s['cleared']}/{s['n']} (95% CI {lo:.0%}-{hi:.0%}); ends: {ends}; GF fired {s['gf_fired']}/{s['n']} "
            f"(before the face {s['gf_before_face']}); A-press runs {s['a_pressed_runs']} ({tf}), first-A run median "
            f"{s['first_a_run_median']}, first-A x median {s['first_a_x_median']}, take-off x median {s['takeoff_x_median']}; "
            f"GF output max {s['gf_output_max_hz']:.2f} Hz, TTMn max {s['ttmn_max_hz']:.3f} Hz; "
            + ("none cleared" if fr["n"] == 0 else f"median frames to clear {fr['median']:.0f}"))
    c = res["criterion"]
    lines.append(f"criterion (stated in docs/SPEC_e2a.md before running): real >= {c['real_cleared_min']}/{c['n']}, degree shuffle <= "
                 f"{c['shuffled_cleared_max']}/{c['n']}, real_no_obstacle expected <= {c['no_obstacle_cleared_max']}/{c['n']}; class shuffle informative only")
    return "\n".join(lines)


def main(argv=None) -> None:
    import argparse
    ap = argparse.ArgumentParser(description="E2a: get past pipe 1; real vs shuffled vs class-shuffled vs no obstacle cue")
    ap.add_argument("--n", type=int, default=N)
    ap.add_argument("--seed0", type=int, default=E2A_SEED0, help="default: the held-out seeds 7100-7119")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--max-frames", type=int, default=None)
    ap.add_argument("--arms", nargs="+", choices=ALL_ARMS, default=list(ALL_ARMS))
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    res = run_eval(args.n, args.seed0, args.workers, args.max_frames, tuple(args.arms))
    print(format_eval(res))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=1, default=str)


if __name__ == "__main__":
    main()
