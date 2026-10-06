# What this file does, in plain English:
# A dose-response experiment on walking speed. The 1-1 baseline is run at four
# strengths of the home landmark (the cue that makes the fly walk right), each time
# with the same 20 fresh seeds, once with the real connectome and once with a
# rewired copy. It records how fast Mario walks, whether he survives the first
# Goomba, how far he gets, and whether the Goomba meeting happens at a different
# place or time. No strength is adopted afterwards: it is a curve, not a tuning
# run. The only thing changed is one number fed to the senses; nothing is pressed.
"""brain/dose_response.py -- docs/SPEC_dose_response.md.

    .venv/Scripts/python.exe -m brain.dose_response [--values 5 8 11 15] [--n 20] [--seed0 6200] [--workers 8] [--out r.json]

The override (`SenseSettings.goal_cue_salience`) goes through `settings_for` exactly as in the baseline, so both arms get the same
cue; the registered `calibration.GOAL_CUE_SALIENCE` is never modified. `DoseProbe` is a read-only RAM observer.
"""

from __future__ import annotations

import dataclasses
import json
import multiprocessing as mp
import os
from dataclasses import asdict, dataclass

import numpy as np

from brain import calibration as C
from brain.baseline import (ADDR_GAME_ENGINE, BASELINE_MAX_FRAMES, ENGINE_DYING, EXPERIMENT_ID, SHUFFLED_ARMS, run_baseline_episode, summarize)
from brain.e1 import SPRITE_PX
from brain.e2a import E2A_PIPE_RIGHT_X
from brain.settings import SenseSettings, settings_for

VALUES = (5.0, 8.0, 11.0, 15.0)             # 15 = the registered default (calibration.GOAL_CUE_SALIENCE); window validated 3-25 per neuron
DOSE_SEED0, N = 6200, 20                    # fresh seeds, used for every value
DOSE_ARMS = ("real", "shuffled")
SPEED_WINDOW_FRAMES = 100                   # speed window: frames 1..min(100, first Goomba contact frame, last frame)
FIRST_GOOMBA = ("survived", "died_enemy", "unresolved", "no_contact")


def settings_with_salience(value: float | None) -> SenseSettings:
    """The user defaults with only the landmark strength replaced (None = the registered default, untouched)."""
    base = SenseSettings.user_default()
    return base if value is None else dataclasses.replace(base, goal_cue_salience=float(value))


class DoseProbe:
    """Read-only observer for `run_baseline_episode(probe=...)`. Records Mario's world x per frame and follows the first Goomba that
    comes within SPRITE_PX horizontally of him: its contact frame and Mario's x then, and whether it ends up behind him or removed
    while he is alive (resolved) before the episode ends."""

    def __init__(self):
        self.xs: list[int] = []
        self.contact_frame: int | None = None
        self.contact_x: int | None = None
        self.slot: int | None = None
        self.resolved = False

    def __call__(self, frame, ram, mario_x) -> None:
        from brain.perception import OBJECT_SLOTS
        from mario.entities.registry import GOOMBA_TYPE_BYTE
        from mario.ram.addresses import ADDR_ENEMY_ACTIVE, ADDR_ENEMY_PAGE, ADDR_ENEMY_TYPE, ADDR_ENEMY_X
        self.xs.append(mario_x)
        dying = int(ram[ADDR_GAME_ENGINE]) == ENGINE_DYING

        def goomba_dx(s):
            if ram[ADDR_ENEMY_ACTIVE + s] and ram[ADDR_ENEMY_TYPE + s] == GOOMBA_TYPE_BYTE:
                return int(ram[ADDR_ENEMY_PAGE + s]) * 256 + int(ram[ADDR_ENEMY_X + s]) - mario_x
            return None

        if frame == 0 or dying:
            return
        if self.slot is None:
            for s in range(OBJECT_SLOTS):
                dx = goomba_dx(s)
                if dx is not None and abs(dx) < SPRITE_PX:
                    self.slot, self.contact_frame, self.contact_x = s, frame, mario_x
                    break
        elif not self.resolved:
            dx = goomba_dx(self.slot)
            self.resolved = dx is None or dx <= -SPRITE_PX      # removed (stomped or gone) or entirely behind Mario, Mario alive

    def speed(self) -> float | None:
        """Mean world-x speed (px/frame) over frames 1..W, W = min(SPEED_WINDOW_FRAMES, contact frame, last frame)."""
        last = len(self.xs) - 1
        w = min(SPEED_WINDOW_FRAMES, self.contact_frame if self.contact_frame else last, last)
        return None if w < 1 else (self.xs[w] - self.xs[0]) / w

    def first_goomba(self, outcome: str) -> str:
        if self.contact_frame is None:
            return "no_contact"
        if self.resolved:
            return "survived"
        return "died_enemy" if outcome == "died_enemy" else "unresolved"


@dataclass
class DoseRow:
    value: float
    arm: str
    seed: int
    shuffle_seed: int | None
    outcome: str
    max_x: int
    frames: int
    speed: float | None
    contact_frame: int | None
    contact_x: int | None
    first_goomba: str
    pipe1_cleared: bool
    goombas_encountered: int
    goombas_jumped: int
    tap: bool
    a_pressed: bool
    a_run_lengths: list


def _job(args) -> DoseRow:
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    value, seed, arm, shuffle_seed, max_frames = args
    probe = DoseProbe()
    res = run_baseline_episode(seed, arm, shuffle_seed, settings_with_salience(value), max_frames=max_frames, probe=probe)[0]
    return DoseRow(value, arm, seed, shuffle_seed, res.outcome, res.max_x, res.frames, probe.speed(), probe.contact_frame, probe.contact_x,
                   probe.first_goomba(res.outcome), res.max_x > E2A_PIPE_RIGHT_X, res.goombas_encountered, res.goombas_jumped, res.tap,
                   res.a_pressed, res.a_run_lengths)


def _stats(vals) -> dict:
    from tool.core.evaluation import bootstrap_ci
    v = [x for x in vals if x is not None]
    return {"n": len(v), "mean": float(np.mean(v)) if v else None, "median": float(np.median(v)) if v else None,
            "ci": list(bootstrap_ci(v)) if v else None}


def summarize_cell(rows: list[DoseRow]) -> dict:
    """One (value, arm) cell: the baseline summary on its fields plus the dose-response metrics."""
    from tool.core.evaluation import wilson_ci
    from brain.baseline import BaselineResult
    base = summarize([BaselineResult(EXPERIMENT_ID, r.arm, r.seed, r.shuffle_seed, r.outcome == "level_complete", r.outcome,
                                     r.outcome.startswith("died"), r.frames, None, r.max_x, False, None, 0.0, 0.0, r.a_pressed, 0, 0, 0, 0,
                                     goombas_encountered=r.goombas_encountered, goombas_jumped=r.goombas_jumped,
                                     a_run_lengths=r.a_run_lengths, tap=r.tap) for r in rows])
    n = len(rows)
    fg = {k: sum(r.first_goomba == k for r in rows) for k in FIRST_GOOMBA}
    contact = [r for r in rows if r.contact_frame is not None]
    return {"n": n, "speed": _stats([r.speed for r in rows]), "first_goomba": fg,
            "survived_ci": list(wilson_ci(fg["survived"], len(contact))) if contact else None, "contacts": len(contact),
            "contact_frame": _stats([r.contact_frame for r in rows]), "contact_x": _stats([r.contact_x for r in rows]),
            "pipe1_cleared": sum(r.pipe1_cleared for r in rows), "max_x": base["max_x_mean"], "max_x_ci": base["max_x_mean_ci"],
            "max_x_median": base["max_x_median"], "end_reasons": base["end_reasons"], "goombas_encountered": base["goombas_encountered"],
            "goombas_jumped": base["goombas_jumped"], "tap_fraction": base["tap_fraction"], "a_episodes": base["a_episodes"],
            "tap_episodes": base["tap_episodes"]}


def run_dose_response(values=VALUES, n: int = N, seed0: int = DOSE_SEED0, workers: int = 1, max_frames: int | None = None,
                      arms=DOSE_ARMS) -> dict:
    """Same seeds seed0..seed0+n-1 for every value; shuffle seed 1 + i. Registry value untouched."""
    jobs = [(float(v), seed0 + i, arm, 1 + i if arm in SHUFFLED_ARMS else None, max_frames) for v in values for arm in arms for i in range(n)]
    if workers > 1:
        with mp.get_context("spawn").Pool(workers) as pool:
            rows = pool.map(_job, jobs)
    else:
        rows = [_job(j) for j in jobs]
    out = {"experiment": EXPERIMENT_ID, "kind": "dose_response", "goal_salience_values": [float(v) for v in values],
           "registered_default": C.GOAL_CUE_SALIENCE, "seeds": [seed0, seed0 + n - 1], "max_frames": max_frames or BASELINE_MAX_FRAMES,
           "speed_window_frames": SPEED_WINDOW_FRAMES, "arms": list(arms),
           "senses_used": {str(v): settings_for(EXPERIMENT_ID, settings_with_salience(v)).to_dict() for v in values}, "curve": {}}
    for v in values:
        out["curve"][str(float(v))] = {arm: summarize_cell([r for r in rows if r.value == float(v) and r.arm == arm]) for arm in arms}
    out["episodes"] = [asdict(r) for r in rows]
    return out


def format_curve(res: dict) -> str:
    lines = [f"B11 dose-response on GOAL_CUE_SALIENCE (registered default {res['registered_default']:g}, not changed), seeds "
             f"{res['seeds'][0]}-{res['seeds'][1]}, speed = mean px/frame over frames 1..min({res['speed_window_frames']}, first contact, end)",
             "value arm      speed  contacts contact_f contact_x surv/died/unres  max_x mean (CI) med  pipe1  jumped/enc  tap  ends"]
    for v, cell in res["curve"].items():
        for arm, s in cell.items():
            def m(d, f="{:.1f}"):
                return "-" if d["mean"] is None else f.format(d["mean"])
            fg = s["first_goomba"]
            tf = "-" if s["tap_fraction"] is None else f"{s['tap_episodes']}/{s['a_episodes']}"
            ends = ",".join(f"{k}{c}" for k, c in s["end_reasons"].items() if c)
            lines.append(f"{float(v):5g} {arm:9s} {m(s['speed'], '{:.3f}'):>6s} {s['contacts']:>3d}/{s['n']:<3d} {m(s['contact_frame']):>8s} "
                         f"{m(s['contact_x']):>8s}  {fg['survived']}/{fg['died_enemy']}/{fg['unresolved']}+{fg['no_contact']}nc  "
                         f"{s['max_x']:.0f} ({s['max_x_ci'][0]:.0f}-{s['max_x_ci'][1]:.0f}) {s['max_x_median']:.0f}  {s['pipe1_cleared']}/{s['n']}  "
                         f"{s['goombas_jumped']}/{s['goombas_encountered']}  {tf}  {ends}")
    return "\n".join(lines)


def main(argv=None) -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Walking-speed dose-response on GOAL_CUE_SALIENCE (docs/SPEC_dose_response.md); adopts no value")
    ap.add_argument("--values", type=float, nargs="+", default=list(VALUES))
    ap.add_argument("--n", type=int, default=N)
    ap.add_argument("--seed0", type=int, default=DOSE_SEED0)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--max-frames", type=int, default=None)
    ap.add_argument("--arms", nargs="+", choices=DOSE_ARMS, default=list(DOSE_ARMS))
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    res = run_dose_response(tuple(args.values), args.n, args.seed0, args.workers, args.max_frames, tuple(args.arms))
    print(format_curve(res))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=1, default=str)


if __name__ == "__main__":
    main()
