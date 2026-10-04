# What this file does, in plain English:
# Experiments E0 ("walk to the goal") and E3 ("pursue the mushroom by sight").
# In E0 Mario stands at the start of flat ground with a landmark on the right;
# in E3 he stands under the first power-up block with a mushroom just released.
# From the first frame the fly is in control, once with the real connectome and
# with two kinds of rewired copy. Each run records whether Mario reached the
# goal x (E0) or the mushroom (E3), plus how active the Giant Fiber and the jump
# muscle neuron were. Nothing here presses a button or touches the brain: it only
# watches the game and the fly's outputs and reports.
"""brain/goal_eval.py -- docs/SPEC_phase3.md section 6.

    .venv/Scripts/python.exe -m brain.goal_eval E0 [--n 20] [--seed0 4000] [--workers 8] [--out result.json]
    .venv/Scripts/python.exe -m brain.goal_eval E3 [--n 20] [--seed0 5100] ...

Metrics, fixed before any run (outcome-neutral):
  E0 reached   Mario's world x >= E0_GOAL_X within E0_MAX_FRAMES, alive.
  E3 reached   the first frame Mario's box overlaps the mushroom's (|dx| < 16 px and vertical centre gap < (16 + Mario height) / 2,
               the same box rule as E1's contact), or Mario's size changes (collecting it implies an overlap), within E3_MAX_FRAMES.
               An E3 episode also ends when the mushroom is gone without Mario having reached it ("lost").
Every episode also stores gf_fired (the GF membrane crossed threshold), gf_output_max_hz and ttmn_max_hz.
"""

from __future__ import annotations

import json
import math
import multiprocessing as mp
import os
from dataclasses import asdict, dataclass

import numpy as np

from brain.scenes import (E0_SCENE_ID, E3_SCENE_ID, SceneSpec, apply_rules, build_scene, check_e3_scene, load_scene,
                          powerup_slots)
from brain.settings import SenseSettings, settings_for

E0_SEED0, E3_SEED0, N = 4000, 5100, 20          # held-out (E1 uses 3000-3019; E3's first set 5000-5019 is spent); the experimenter runs them once
E0_GOAL_X = 400                                 # invented: world x of the goal, before the first pipe (x = 448)
E0_MAX_FRAMES = 600                             # invented bound (10 s)
E3_MAX_FRAMES = 150                             # derived from the scene, not the fly: a Mario who presses nothing is reached by the returning mushroom at frame 183 (measured), so the bound is below that
SPRITE_PX = 16
ARMS = ("real", "shuffled", "shuffled_class")
SHUFFLED_ARMS = ("shuffled", "shuffled_class")
# Necessity controls (docs/SPEC_phase3.md section 11B): the REAL connectome with one mechanism removed. Eval only, never in Run / play.
NECESSITY_ARMS = {"real_no_landmark": "E0", "real_no_pursuit": "E3"}
ALL_ARMS = ARMS + tuple(NECESSITY_ARMS)
# Pass criteria of the plan (REDESIGN_PLAN section 4): reported, not tuned. "Shuffled does not" is read as <= 2/20 (as E1).
CRITERIA = {"E0": {"real_reached_min": 18, "shuffled_reached_max": 2, "n": 20},
            "E3": {"real_reached_min": 14, "shuffled_reached_max": 2, "n": 20}}
SCENES = {"E0": E0_SCENE_ID, "E3": E3_SCENE_ID}
MAX_FRAMES = {"E0": E0_MAX_FRAMES, "E3": E3_MAX_FRAMES}
SEED0 = {"E0": E0_SEED0, "E3": E3_SEED0}
METRIC = {"E0": f"reached world x {E0_GOAL_X} within {E0_MAX_FRAMES} frames",
          "E3": f"reached the mushroom within {E3_MAX_FRAMES} frames"}


@dataclass
class GoalResult:
    experiment: str
    arm: str                    # "real" | "shuffled" | "shuffled_class" | "real_no_landmark" (E0) | "real_no_pursuit" (E3)
    seed: int
    shuffle_seed: int | None
    reached: bool
    outcome: str                # "reached" | "died" | "lost" (E3: the mushroom is gone) | "timeout"
    died: bool
    frames: int
    reached_frame: int | None
    max_x: int
    gf_fired: bool              # the GF membrane crossed threshold ("would have fired")
    first_gf_frame: int | None
    gf_output_max_hz: float     # peak GF population output over the episode
    ttmn_max_hz: float          # peak TTMn (jump muscle motor neuron) over the episode
    a_pressed: bool
    a_frames: int
    left_frames: int            # frames with the Left button pressed (reported so a shuffled Left is visible)
    right_frames: int
    b_frames: int
    collected: bool = False     # E3: Mario's size changed (he picked the mushroom up)


def default_arms(experiment: str) -> tuple[str, ...]:
    """real, both shuffles, and the experiment's own necessity arm."""
    return ARMS + tuple(a for a, e in NECESSITY_ARMS.items() if e == experiment)


def arm_settings(experiment: str, arm: str, used: SenseSettings) -> SenseSettings:
    """The settings an arm runs with: a necessity arm drops its one mechanism, every other arm keeps the experiment's."""
    if arm == "real_no_landmark":
        return SenseSettings(used.pursuit_kinds, 0.0, used.pursuit_arousal)
    if arm == "real_no_pursuit":
        return SenseSettings((), used.goal_cue_salience, used.pursuit_arousal)
    return used


def arm_of(arm: str, shuffle_seed: int | None, experiment: str | None = None) -> str:
    if arm in NECESSITY_ARMS and experiment is not None and NECESSITY_ARMS[arm] != experiment:
        raise ValueError(f"arm {arm!r} belongs to {NECESSITY_ARMS[arm]}, not {experiment}")
    if arm not in ALL_ARMS or (arm in SHUFFLED_ARMS) != (shuffle_seed is not None):
        raise ValueError(f"arm {arm!r} with shuffle_seed {shuffle_seed!r}: shuffled arms need a shuffle seed, real none")
    return arm


def run_goal_episode(experiment: str, seed: int, arm: str = "real", shuffle_seed: int | None = None,
                     settings: SenseSettings | None = None, scene: SceneSpec | None = None, max_frames: int | None = None,
                     network=None, calibration=None, on_frame=None, should_stop=None, record_rows: bool = False):
    """One E0 or E3 episode. `settings` are the user's sense settings; the experiment's own mechanism list decides which apply
    (brain.settings.settings_for). Returns (GoalResult, rows, stamp)."""
    if experiment not in SCENES:
        raise ValueError(f"experiment {experiment!r} is not one of {tuple(SCENES)}")
    arm = arm_of(arm, shuffle_seed, experiment)
    from brain.e1 import _row, _vertical_gap, is_contact
    from brain.policy import BrainPolicy
    from mario.emulator.env import make_env
    from mario.ram.addresses import (ADDR_ENEMY_ACTIVE, ADDR_ENEMY_PAGE, ADDR_ENEMY_X, ADDR_MARIO_PAGE, ADDR_MARIO_SCREEN_X,
                                     ADDR_MARIO_SIZE, ADDR_MARIO_X, ADDR_MARIO_Y)
    scene = scene or load_scene(SCENES[experiment])
    max_frames = max_frames or MAX_FRAMES[experiment]
    used = arm_settings(experiment, arm, settings_for(experiment, settings))
    policy = BrainPolicy(network=network, calibration=calibration, shuffle_seed=shuffle_seed,
                         shuffle_mode="class" if arm == "shuffled_class" else "degree", settings=used)
    env = make_env(scene.level)
    build_scene(env, scene)
    ram = env.unwrapped.ram
    slot = None
    if experiment == "E3":
        on_screen = powerup_slots(ram)
        if not on_screen:
            raise RuntimeError(f"scene {scene.id}: no power-up on screen at takeover ({check_e3_scene(ram)})")
        slot = on_screen[0]
    size0 = int(ram[ADDR_MARIO_SIZE])
    policy.reset(seed)

    class _Obs:
        pass
    obs = _Obs()
    obs.ram = ram
    reached_frame = first_gf = None
    a_frames = left_frames = right_frames = b_frames = max_x = 0
    gf_out_max = ttmn_max = 0.0
    died = lost = collected = False
    rows: list[dict] = []
    frames = 0
    for frames in range(1, max_frames + 1):
        if should_stop is not None and should_stop():
            break
        action = policy.act(obs)
        readout, buttons = policy.last_readout, policy.last_buttons
        if readout.gf_spiked and first_gf is None:
            first_gf = frames
        a_frames += int(buttons.a)
        left_frames += int(buttons.left)
        right_frames += int(buttons.right)
        b_frames += int(buttons.b)
        gf_out_max, ttmn_max = max(gf_out_max, readout.pooled("GF")), max(ttmn_max, readout.pooled("TTMn"))
        screen_obs, _, done, info = env.step(action)
        apply_rules(ram, scene)
        mario_x = int(ram[ADDR_MARIO_PAGE]) * 256 + int(ram[ADDR_MARIO_X])
        max_x = max(max_x, mario_x)
        died = info["life"] < 2 or (done and not info.get("flag_get"))
        dx = None
        if experiment == "E0":
            if not died and mario_x >= E0_GOAL_X and reached_frame is None:
                reached_frame = frames
        else:
            collected = collected or int(ram[ADDR_MARIO_SIZE]) != size0
            active = bool(ram[ADDR_ENEMY_ACTIVE + slot])
            dx = (int(ram[ADDR_ENEMY_PAGE + slot]) * 256 + int(ram[ADDR_ENEMY_X + slot]) - mario_x) if active else None
            if not died and reached_frame is None:
                if collected:
                    reached_frame = frames
                elif active:
                    vgap, height = _vertical_gap(ram, slot)
                    if is_contact(active, dx, vgap, height):
                        reached_frame = frames
                else:
                    lost = True
        if on_frame is not None or record_rows:
            row = _row(frames, ram, policy, readout, buttons, action, mario_x, dx, ADDR_MARIO_SCREEN_X, ADDR_MARIO_Y)
            tgt = policy.last_target
            row.update({"arousal": policy.last_arousal, "pursuit_az": tgt.azimuth_deg if tgt else float("nan"),
                        "pursuit_dx": tgt.dx_px if tgt else float("nan")})
            if record_rows:
                rows.append(row)
            if on_frame is not None:
                on_frame(frames, screen_obs, row)
        if died or reached_frame is not None or lost or done:
            break
    env.close()
    reached = reached_frame is not None and not died
    outcome = "reached" if reached else ("died" if died else ("lost" if lost else "timeout"))
    res = GoalResult(experiment, arm, seed, shuffle_seed, reached, outcome, died, frames, reached_frame, max_x,
                     first_gf is not None, first_gf, gf_out_max, ttmn_max, a_frames > 0, a_frames, left_frames,
                     right_frames, b_frames, collected)
    stamp = {**policy.stamp(), "scene": scene.to_dict(), "experiment": experiment, "senses_used": used.to_dict()}
    return res, rows, stamp


# ---- evaluation ----------------------------------------------------------------------------------------------------
def _job(args) -> GoalResult:
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    experiment, seed, arm, shuffle_seed, max_frames, settings = args
    return run_goal_episode(experiment, seed, arm, shuffle_seed, SenseSettings.from_dict(settings), max_frames=max_frames)[0]


def summarize(results: list[GoalResult]) -> dict:
    from tool.core.evaluation import wilson_ci
    n = len(results)
    k = sum(r.reached for r in results)
    lo, hi = wilson_ci(k, n)
    fr = [r.reached_frame for r in results if r.reached_frame is not None and r.reached]
    return {"n": n, "reached": k, "reached_ci": [lo, hi], "deaths": sum(r.died for r in results),
            "timeouts": sum(r.outcome == "timeout" for r in results), "lost": sum(r.outcome == "lost" for r in results),
            "collected": sum(r.collected for r in results), "gf_fired": sum(r.gf_fired for r in results),
            "a_pressed_runs": sum(r.a_pressed for r in results),
            "gf_output_max_hz": max((r.gf_output_max_hz for r in results), default=0.0),
            "ttmn_max_hz": max((r.ttmn_max_hz for r in results), default=0.0),
            "frames_to_reach": {"n": len(fr), "median": float(np.median(fr)) if fr else None},
            "left_frames_mean": float(np.mean([r.left_frames for r in results])) if n else 0.0,
            "max_x_median": float(np.median([r.max_x for r in results])) if n else 0.0}


def run_eval(experiment: str, n: int = N, seed0: int | None = None, workers: int = 1, max_frames: int | None = None,
             arms: tuple[str, ...] | None = None, settings: SenseSettings | None = None) -> dict:
    """Real vs degree-preserving shuffle vs class-preserving shuffle (shuffle seed 1 + i for both), plus the experiment's
    necessity arm (real connectome, one mechanism off), seeds seed0..seed0+n-1, the same noise seed in every arm and the same
    sense settings (the shuffled arms get exactly the same cues)."""
    arms = default_arms(experiment) if arms is None else arms
    from brain.policy import BrainPolicy
    seed0 = SEED0[experiment] if seed0 is None else seed0
    used = settings_for(experiment, settings)
    jobs = [(experiment, seed0 + i, arm, 1 + i if arm in SHUFFLED_ARMS else None, max_frames, used.to_dict())
            for arm in arms for i in range(n)]
    if workers > 1:
        with mp.get_context("spawn").Pool(workers) as pool:
            results = pool.map(_job, jobs)
    else:
        results = [_job(j) for j in jobs]
    scene = load_scene(SCENES[experiment])
    out = {"experiment": experiment, "metric": METRIC[experiment], "seeds": [seed0, seed0 + n - 1],
           "max_frames": max_frames or MAX_FRAMES[experiment], "scene": scene.to_dict(),
           "stamp": BrainPolicy(settings=used).stamp(), "criterion": dict(CRITERIA[experiment]), "arms": list(arms)}
    for arm in arms:
        out[arm] = summarize([r for r in results if r.arm == arm])
    out["episodes"] = [asdict(r) for r in results]
    return out


def format_eval(res: dict) -> str:
    st = res["stamp"]
    lines = [f"{res['experiment']} {res['metric']}, scene {res['scene']['id']} ({res['scene']['scene_hash']}), seeds "
             f"{res['seeds'][0]}-{res['seeds'][1]}, max {res['max_frames']} frames",
             f"network {st['build_hash']}, calibration {st['calibration_hash']}, senses {st.get('senses')}"]
    for arm in res["arms"]:
        s = res[arm]
        fr = s["frames_to_reach"]
        lines.append(
            f"{arm:14s} reached {s['reached']}/{s['n']} (95% CI {s['reached_ci'][0]:.0%}-{s['reached_ci'][1]:.0%}); deaths {s['deaths']}; "
            f"timeouts {s['timeouts']}; lost {s['lost']}; GF fired {s['gf_fired']}/{s['n']}; A-press runs {s['a_pressed_runs']}; "
            f"GF output max {s['gf_output_max_hz']:.2f} Hz, TTMn max {s['ttmn_max_hz']:.3f} Hz; "
            + ("none reached" if fr["n"] == 0 else f"median frames to reach {fr['median']:.0f}"))
    return "\n".join(lines)


def main(argv=None) -> None:
    import argparse
    ap = argparse.ArgumentParser(description="E0 / E3: real vs degree-preserving vs class-preserving shuffled connectome")
    ap.add_argument("experiment", choices=tuple(SCENES))
    ap.add_argument("--n", type=int, default=N)
    ap.add_argument("--seed0", type=int, default=None, help="default: the held-out seeds of the experiment")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--max-frames", type=int, default=None)
    ap.add_argument("--arms", nargs="+", choices=ALL_ARMS, default=None, help="default: real, shuffled, shuffled_class and the necessity arm")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    res = run_eval(args.experiment, args.n, args.seed0, args.workers, args.max_frames, tuple(args.arms) if args.arms else None)
    print(format_eval(res))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=1, default=str)


if __name__ == "__main__":
    main()
