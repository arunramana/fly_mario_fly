# What this file does, in plain English:
# The "1-1 innate baseline": the fly plays the real first level of Super Mario
# Bros from power-on, with nothing scripted, no enemies removed and no game
# memory edited. Looming, pursuit of power-ups and the home landmark are all on.
# It is run once with the real connectome and with two rewired copies, and for
# each run it records how far Mario got, how the run ended (and why), how many
# Goombas he jumped over, whether his jump button presses were brief taps, and
# whether he got the mushroom. There is no pass or fail: it is a reference
# point for later experiments. Nothing here presses a button or touches the
# brain; it only watches the game and the fly's outputs.
"""brain/baseline.py -- docs/SPEC_baseline_1-1.md.

    .venv/Scripts/python.exe -m brain.baseline [--n 20] [--seed0 6100] [--workers 8] [--out result.json]

Metrics are defined in the SPEC before any run (outcome-neutral); the pure helpers here (`GoombaTracker`, `a_runs`,
`classify_end`) take plain values so they can be tested on a fake episode.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field

import numpy as np

from brain.workers import WorkerPool
from brain.e1 import SPRITE_PX
from brain.scenes import B11_SCENE_ID, SceneSpec, load_scene
from brain.settings import SenseSettings, settings_for

EXPERIMENT_ID = "B11"
BASELINE_SEED0, N = 6100, 20      # fresh seeds for the obstacle-expansion-ON baseline (docs/SPEC_baseline_1-1.md); the first baseline (obstacle expansion off) used 6000-6019, which were also noise seeds of Phase 3b diagnostics
BASELINE_MAX_FRAMES = 3000        # invented bound (50 s)
BASELINE_STUCK_FRAMES = 300       # invented convention: no new max_x for 5 s ends the episode as "stuck"
BASELINE_TAP_MAX_FRAMES = 2       # invented convention (docs/INVESTIGATION_phase3b.md): a "tap" is a first A run of <= 2 frames
ARMS = ("real", "shuffled", "shuffled_class")
SHUFFLED_ARMS = ("shuffled", "shuffled_class")
END_REASONS = ("level_complete", "died_enemy", "died_pit", "died_other", "stuck", "timeout")
A_RUN_BINS = (("1", 1, 1), ("2", 2, 2), ("3-5", 3, 5), ("6-10", 6, 10), ("11+", 11, 10**9))
# RAM bytes read here that the legacy address module does not name (SMB disassembly): game-engine subroutine (0x0B = dying),
# Player_Y_HighPos (1 = on the screen, > 1 = below it).
ADDR_GAME_ENGINE, ENGINE_DYING = 0x000E, 0x0B
ADDR_MARIO_Y_HIGH = 0x00B5
ENEMY_NEAR_DX_PX, ENEMY_NEAR_DY_PX = 24, 32      # an enemy this close to Mario on the dying frame = "died_enemy"
METRIC = (f"max world x, end reason, Goombas jumped, A-tap fraction, power-up reached; max {BASELINE_MAX_FRAMES} frames "
          f"(baseline, no pass/fail)")


@dataclass
class BaselineResult:
    experiment: str
    arm: str                    # "real" | "shuffled" | "shuffled_class"
    seed: int
    shuffle_seed: int | None
    reached: bool               # level complete (flag reached)
    outcome: str                # one of END_REASONS
    died: bool
    frames: int
    reached_frame: int | None   # the level-complete frame
    max_x: int
    gf_fired: bool
    first_gf_frame: int | None
    gf_output_max_hz: float
    ttmn_max_hz: float
    a_pressed: bool
    a_frames: int
    left_frames: int
    right_frames: int
    b_frames: int
    collected: bool = False             # Mario's size state changed (mushroom collected)
    collected_frame: int | None = None
    powerup_released: bool = False      # a power-up object was ever active
    goombas_encountered: int = 0
    goombas_jumped: int = 0
    a_run_lengths: list = field(default_factory=list)
    first_a_run: int | None = None
    tap: bool = False                   # first A run <= BASELINE_TAP_MAX_FRAMES


# ---- pure metric helpers (tested on fake episodes) ----------------------------------------------------------------
def a_runs(presses) -> list[int]:
    """Lengths of the maximal runs of consecutive pressed frames."""
    runs, cur = [], 0
    for p in presses:
        if p:
            cur += 1
        elif cur:
            runs.append(cur)
            cur = 0
    if cur:
        runs.append(cur)
    return runs


def classify_end(level_complete: bool, dying: bool, below_screen: bool, enemy_near: bool, stuck: bool, game_over: bool = False) -> str | None:
    """The end reason of an episode on this frame, or None while it continues (first matching rule of the SPEC)."""
    if level_complete:
        return "level_complete"
    if dying or game_over:
        return "died_pit" if below_screen else ("died_enemy" if enemy_near else "died_other")
    if stuck:
        return "stuck"
    return None


def enemy_near_mario(ram, mario_x: int, mario_y_centre: float) -> bool:
    """Any active non-power-up enemy slot within ENEMY_NEAR_DX_PX horizontally and ENEMY_NEAR_DY_PX vertically of Mario."""
    from brain.perception import OBJECT_SLOTS, enemy_centre_y
    from mario.ram.addresses import (ADDR_ENEMY_ACTIVE, ADDR_ENEMY_PAGE, ADDR_ENEMY_TYPE, ADDR_ENEMY_X, POWERUP_ID)
    for s in range(OBJECT_SLOTS):
        if ram[ADDR_ENEMY_ACTIVE + s] and ram[ADDR_ENEMY_TYPE + s] != POWERUP_ID:
            dx = int(ram[ADDR_ENEMY_PAGE + s]) * 256 + int(ram[ADDR_ENEMY_X + s]) - mario_x
            if abs(dx) < ENEMY_NEAR_DX_PX and abs(enemy_centre_y(ram, s) - mario_y_centre) < ENEMY_NEAR_DY_PX:
                return True
    return False


class GoombaTracker:
    """Counts the Goombas Mario jumped (docs/SPEC_baseline_1-1.md metric 3). One instance per slot from the frame it becomes
    an active Goomba until it is inactive. `update` gets, per frame, whether Mario is airborne and, per slot, `(dx, ground_contact)`
    for an active Goomba or None. Inside the overlap window (|dx| < SPRITE_PX) it remembers whether Mario was ever airborne and whether
    his box overlapped the Goomba's while he stood on the ground (a hit). It counts the instance as jumped once, when the window
    closes by (a) the slot becoming inactive with Mario airborne at some point in the window (stomped and removed) or (b) the Goomba
    ending up entirely behind Mario (dx <= -SPRITE_PX) with Mario airborne at some point and no ground contact (passed over).
    Metric correction: a ground box overlap before Mario's first airborne frame in the window (approach, take-off frame) is not a hit;
    a hit is a ground box overlap after he has been airborne in the window (landing into the Goomba). A walk-in death closes no window."""

    def __init__(self):
        self.encountered = 0
        self.jumped = 0
        self._inst: dict[int, dict] = {}

    def update(self, airborne: bool, slots: dict[int, tuple[int, bool] | None]) -> None:
        for slot, cur in slots.items():
            st = self._inst.get(slot)
            if cur is None:
                if st is not None and st["in_window"] and st["air"] and not st["counted"]:
                    self.jumped += 1                                  # (a) removed while overlapping, Mario was airborne: stomped
                self._inst.pop(slot, None)
                continue
            dx, ground_contact = cur
            if st is None:
                st = self._inst[slot] = {"in_window": False, "air": False, "hit": False, "counted": False, "seen": False}
            if abs(dx) < SPRITE_PX:
                if not st["seen"]:
                    st["seen"] = True
                    self.encountered += 1
                st["in_window"] = True
                st["hit"] = st["hit"] or (ground_contact and st["air"])   # ground box overlap only counts after a take-off
                st["air"] = st["air"] or airborne
            elif st["in_window"]:
                if dx <= -SPRITE_PX and st["air"] and not st["hit"] and not st["counted"]:
                    self.jumped += 1                                  # (b) ended up behind Mario with an airborne frame and no hit
                    st["counted"] = True
                st["in_window"], st["air"], st["hit"] = False, False, False


# ---- one episode --------------------------------------------------------------------------------------------------
def run_baseline_episode(seed: int, arm: str = "real", shuffle_seed: int | None = None, settings: SenseSettings | None = None,
                         scene: SceneSpec | None = None, max_frames: int | None = None, network=None, calibration=None,
                         on_frame=None, should_stop=None, record_rows: bool = False, probe=None):
    """One 1-1 episode from reset. Returns (BaselineResult, rows, stamp). No scene rule is applied and no RAM byte is written.
    `probe(frame, ram, mario_x)` is an optional read-only observer (frame 0 = after reset, then once per frame after the step);
    brain/dose_response.py uses it. It is None in every other run, which are unchanged."""
    if arm not in ARMS or (arm in SHUFFLED_ARMS) != (shuffle_seed is not None):
        raise ValueError(f"arm {arm!r} with shuffle_seed {shuffle_seed!r}: shuffled arms need a shuffle seed, real none")
    from brain.e1 import _row, _vertical_gap, is_contact
    from brain.perception import OBJECT_SLOTS, mario_centre_y
    from brain.policy import BrainPolicy
    from mario.emulator.env import make_env
    from mario.entities.registry import GOOMBA_TYPE_BYTE
    from mario.ram.addresses import (ADDR_ENEMY_ACTIVE, ADDR_ENEMY_PAGE, ADDR_ENEMY_TYPE, ADDR_ENEMY_X, ADDR_MARIO_PAGE,
                                     ADDR_MARIO_SCREEN_X, ADDR_MARIO_SIZE, ADDR_MARIO_X, ADDR_MARIO_Y, ADDR_PLAYER_STATE,
                                     POWERUP_ID)
    scene = scene or load_scene(B11_SCENE_ID)
    max_frames = max_frames or BASELINE_MAX_FRAMES
    used = settings_for(EXPERIMENT_ID, settings)
    policy = BrainPolicy(network=network, calibration=calibration, shuffle_seed=shuffle_seed,
                         shuffle_mode="class" if arm == "shuffled_class" else "degree", settings=used)
    env = make_env(scene.level)
    env.reset()                                          # power-on; the scene has no log and no rules
    ram = env.unwrapped.ram
    size0 = int(ram[ADDR_MARIO_SIZE])
    policy.reset(seed)
    if probe is not None:
        probe(0, ram, int(ram[ADDR_MARIO_PAGE]) * 256 + int(ram[ADDR_MARIO_X]))

    class _Obs:
        pass
    obs = _Obs()
    obs.ram = ram
    tracker = GoombaTracker()
    first_gf = collected_frame = reached_frame = None
    a_seq: list[bool] = []
    left_frames = right_frames = b_frames = max_x = last_progress = 0
    gf_out_max = ttmn_max = 0.0
    powerup_released = False
    end = None
    rows: list[dict] = []
    frames = 0
    for frames in range(1, max_frames + 1):
        if should_stop is not None and should_stop():
            break
        action = policy.act(obs)
        readout, buttons = policy.last_readout, policy.last_buttons
        if readout.gf_spiked and first_gf is None:
            first_gf = frames
        a_seq.append(bool(buttons.a))
        left_frames += int(buttons.left)
        right_frames += int(buttons.right)
        b_frames += int(buttons.b)
        gf_out_max, ttmn_max = max(gf_out_max, readout.pooled("GF")), max(ttmn_max, readout.pooled("TTMn"))
        screen_obs, _, done, info = env.step(action)
        mario_x = int(ram[ADDR_MARIO_PAGE]) * 256 + int(ram[ADDR_MARIO_X])
        if probe is not None:
            probe(frames, ram, mario_x)
        if mario_x > max_x:
            max_x, last_progress = mario_x, frames
        if collected_frame is None and int(ram[ADDR_MARIO_SIZE]) != size0:
            collected_frame = frames
        airborne = int(ram[ADDR_PLAYER_STATE]) != 0
        slots: dict[int, tuple[int, bool] | None] = {}
        for s in range(OBJECT_SLOTS):
            active = bool(ram[ADDR_ENEMY_ACTIVE + s])
            powerup_released = powerup_released or (active and ram[ADDR_ENEMY_TYPE + s] == POWERUP_ID)
            if active and ram[ADDR_ENEMY_TYPE + s] == GOOMBA_TYPE_BYTE:
                dx = int(ram[ADDR_ENEMY_PAGE + s]) * 256 + int(ram[ADDR_ENEMY_X + s]) - mario_x
                vgap, height = _vertical_gap(ram, s)
                slots[s] = (dx, (not airborne) and is_contact(True, dx, vgap, height))
            else:
                slots[s] = None
        dying = int(ram[ADDR_GAME_ENGINE]) == ENGINE_DYING
        if not dying:
            tracker.update(airborne, slots)              # a dying Mario closes no window as jumped
        flag = bool(info.get("flag_get"))
        end = classify_end(flag, dying, int(ram[ADDR_MARIO_Y_HIGH]) > 1,
                           dying and enemy_near_mario(ram, mario_x, mario_centre_y(ram)),
                           frames - last_progress >= BASELINE_STUCK_FRAMES, game_over=done and not flag and not dying)
        if flag and reached_frame is None:
            reached_frame = frames
        if on_frame is not None or record_rows:
            row = _row(frames, ram, policy, readout, buttons, action, mario_x, None, ADDR_MARIO_SCREEN_X, ADDR_MARIO_Y)
            tgt = policy.last_target
            row.update({"arousal": policy.last_arousal, "pursuit_az": tgt.azimuth_deg if tgt else float("nan"),
                        "pursuit_dx": tgt.dx_px if tgt else float("nan")})
            if record_rows:
                rows.append(row)
            if on_frame is not None:
                on_frame(frames, screen_obs, row)
        if end is not None or done:
            break
    env.close()
    outcome = end or "timeout"
    runs = a_runs(a_seq)
    res = BaselineResult(EXPERIMENT_ID, arm, seed, shuffle_seed, outcome == "level_complete", outcome, outcome.startswith("died"),
                         frames, reached_frame, max_x, first_gf is not None, first_gf, gf_out_max, ttmn_max, bool(runs),
                         sum(a_seq), left_frames, right_frames, b_frames, collected_frame is not None, collected_frame,
                         powerup_released, tracker.encountered, tracker.jumped, runs, runs[0] if runs else None,
                         bool(runs) and runs[0] <= BASELINE_TAP_MAX_FRAMES)
    stamp = {**policy.stamp(), "scene": scene.to_dict(), "experiment": EXPERIMENT_ID, "senses_used": used.to_dict()}
    return res, rows, stamp


# ---- evaluation ----------------------------------------------------------------------------------------------------
def _job(args) -> BaselineResult:
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    seed, arm, shuffle_seed, max_frames, settings = args
    return run_baseline_episode(seed, arm, shuffle_seed, SenseSettings.from_dict(settings), max_frames=max_frames)[0]


def summarize(results: list[BaselineResult]) -> dict:
    """Per-arm summary. max_x: mean with a percentile-bootstrap 95% CI (continuous variable) and the median; rates carry Wilson CIs."""
    from tool.core.evaluation import bootstrap_ci, wilson_ci
    n = len(results)
    xs = [r.max_x for r in results]
    ends = {e: sum(r.outcome == e for r in results) for e in END_REASONS}
    a_eps = [r for r in results if r.a_pressed]
    taps = sum(r.tap for r in a_eps)
    all_runs = [length for r in results for length in r.a_run_lengths]
    hist = {label: sum(lo <= length <= hi for length in all_runs) for label, lo, hi in A_RUN_BINS}
    k = ends["level_complete"]
    return {"n": n, "max_x_mean": float(np.mean(xs)) if n else 0.0, "max_x_mean_ci": list(bootstrap_ci(xs)),
            "max_x_median": float(np.median(xs)) if n else 0.0, "max_x_min": min(xs, default=0), "max_x_max": max(xs, default=0),
            "level_complete": k, "level_complete_ci": list(wilson_ci(k, n)), "end_reasons": ends,
            "goombas_encountered": sum(r.goombas_encountered for r in results),
            "goombas_jumped": sum(r.goombas_jumped for r in results),
            "episodes_with_a_jump": sum(r.goombas_jumped > 0 for r in results),
            "a_episodes": len(a_eps), "tap_episodes": taps, "tap_fraction": taps / len(a_eps) if a_eps else None,
            "tap_ci": list(wilson_ci(taps, len(a_eps))), "a_run_hist": hist, "a_runs_total": len(all_runs),
            "powerup_released_runs": sum(r.powerup_released for r in results),
            "collected": sum(r.collected for r in results), "collected_ci": list(wilson_ci(sum(r.collected for r in results), n)),
            "gf_fired": sum(r.gf_fired for r in results),
            "gf_output_max_hz": max((r.gf_output_max_hz for r in results), default=0.0),
            "ttmn_max_hz": max((r.ttmn_max_hz for r in results), default=0.0),
            "frames_median": float(np.median([r.frames for r in results])) if n else 0.0}


def run_eval(n: int = N, seed0: int | None = None, workers: int = 1, max_frames: int | None = None,
             arms: tuple[str, ...] = ARMS, settings: SenseSettings | None = None) -> dict:
    """real vs degree-preserving shuffle vs class-preserving shuffle (shuffle seed 1 + i), seeds seed0..seed0+n-1, same noise
    seed and same sense settings in every arm."""
    from brain.policy import BrainPolicy
    seed0 = BASELINE_SEED0 if seed0 is None else seed0
    used = settings_for(EXPERIMENT_ID, settings)
    jobs = [(seed0 + i, arm, 1 + i if arm in SHUFFLED_ARMS else None, max_frames, used.to_dict()) for arm in arms for i in range(n)]
    if workers > 1:
        with WorkerPool(workers, [(j[2], "class" if j[1] == "shuffled_class" else "degree") for j in jobs if j[2] is not None]) as pool:
            results = pool.map(_job, jobs)
    else:
        results = [_job(j) for j in jobs]
    out = {"experiment": EXPERIMENT_ID, "metric": METRIC, "seeds": [seed0, seed0 + n - 1],
           "max_frames": max_frames or BASELINE_MAX_FRAMES, "stuck_frames": BASELINE_STUCK_FRAMES,
           "tap_max_frames": BASELINE_TAP_MAX_FRAMES, "scene": load_scene(B11_SCENE_ID).to_dict(),
           "stamp": BrainPolicy(settings=used).stamp(), "criterion": None, "arms": list(arms)}
    for arm in arms:
        out[arm] = summarize([r for r in results if r.arm == arm])
    out["episodes"] = [asdict(r) for r in results]
    return out


def format_eval(res: dict) -> str:
    st = res["stamp"]
    lines = [f"B11 1-1 innate baseline (no pass/fail), scene {res['scene']['id']} ({res['scene']['scene_hash']}), seeds "
             f"{res['seeds'][0]}-{res['seeds'][1]}, max {res['max_frames']} frames, stuck {res['stuck_frames']}",
             f"network {st['build_hash']}, calibration {st['calibration_hash']}, senses {st.get('senses')}"]
    for arm in res["arms"]:
        s = res[arm]
        lo, hi = s["max_x_mean_ci"]
        tf = "no A presses" if s["tap_fraction"] is None else f"{s['tap_episodes']}/{s['a_episodes']} (CI {s['tap_ci'][0]:.0%}-{s['tap_ci'][1]:.0%})"
        ends = ", ".join(f"{k} {v}" for k, v in s["end_reasons"].items() if v)
        lines.append(
            f"{arm:14s} max_x mean {s['max_x_mean']:.0f} (bootstrap 95% CI {lo:.0f}-{hi:.0f}), median {s['max_x_median']:.0f}; ends: {ends}; "
            f"Goombas jumped {s['goombas_jumped']}/{s['goombas_encountered']} encountered ({s['episodes_with_a_jump']} episodes); "
            f"A-tap episodes {tf}, A runs {s['a_run_hist']}; power-up released {s['powerup_released_runs']}/{s['n']}, collected "
            f"{s['collected']}/{s['n']}; GF fired {s['gf_fired']}/{s['n']}; GF output max {s['gf_output_max_hz']:.2f} Hz, "
            f"TTMn max {s['ttmn_max_hz']:.3f} Hz")
    return "\n".join(lines)


def main(argv=None) -> None:
    import argparse
    ap = argparse.ArgumentParser(description="1-1 innate baseline: real vs degree-preserving vs class-preserving shuffled connectome")
    ap.add_argument("--n", type=int, default=N)
    ap.add_argument("--seed0", type=int, default=BASELINE_SEED0)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--max-frames", type=int, default=None)
    ap.add_argument("--arms", nargs="+", choices=ARMS, default=list(ARMS))
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    res = run_eval(args.n, args.seed0, args.workers, args.max_frames, tuple(args.arms))
    print(format_eval(res))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=1, default=str)


if __name__ == "__main__":
    main()
