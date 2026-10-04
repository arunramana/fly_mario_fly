# What this file does, in plain English:
# Experiment E1, "jump the Goomba". Mario starts stationary in the E1 scene (the shuffled arm's Left presses are looming-driven, not noise) and the
# first Goomba walks toward him; from the first frame the fly (BrainPolicy) is
# in control, once with the real connectome and once with a rewired copy. For
# each run it records whether Mario survived the encounter, whether the Giant
# Fiber fired before the Goomba touched him, and how big the Goomba looked
# (angle and distance) at the moment the Giant Fiber first fired. Nothing here
# presses a button or touches the brain: it only watches the game and the
# fly's outputs, and reports.
"""brain/e1.py -- docs/SPEC_tool_phase2.md sections 3-4.

    .venv/Scripts/python.exe -m brain.e1 [--n 20] [--seed0 3000] [--workers 8] [--out result.json]

Survival, fixed before any run (docs/SPEC_tool_phase2.md section 3):
  contact   first frame where the Goomba's 16 px box and Mario's box overlap (|dx| < 16 and vertical centres closer
            than (16 + Mario height) / 2).
  resolved  first frame where the Goomba is no longer a threat: it is entirely behind Mario (dx <= -16: he went over it
            or it passed him) or its slot no longer holds an active Goomba (stomped and removed).
  survived  Mario is alive E1_GRACE_FRAMES frames after `resolved`. Death at any frame before that is "not survived".
            A run that is still unresolved after E1_MAX_FRAMES is "timeout", not survived.
Only Goomba geometry is used (nothing here relies on Koopa or other sprite sizes).
"""

from __future__ import annotations

import json
import math
import multiprocessing as mp
import os
from dataclasses import asdict, dataclass

import numpy as np

from brain.brain import LESION_CLAMP_HZ
from brain.scenes import E1_SCENE_ID, SceneSpec, build_scene, check_scene, goomba_slots, load_scene

E1_SEED0 = 3000                # held-out: not 1000-1019, 2000-2019 or 9000
E1_N = 20
E1_GRACE_FRAMES = 60           # invented convention: alive 1 s after the Goomba stops being a threat
E1_MAX_FRAMES = 600            # invented bound: the Goomba reaches a Mario who starts stationary in ~150 frames (the shuffled arm's Left presses are looming-driven, not noise)
SPRITE_PX = 16                 # the registry's sprite width (mario/entities/registry.py); Goomba only
# Pass criterion of the plan (REDESIGN_PLAN section 4, E1): clears it in >= 16/20 real, shuffled <= 2/20. Reported, not tuned.
CRITERION = {"real_survived_min": 16, "shuffled_survived_max": 2, "n": 20}
# Control arms. "lesion_gf": the real connectome with both Giant Fiber (DNp01) cells held at zero output (docs/SPEC_tool_phase2.md
# 3b). It can be requested only here (eval/CLI); the tool's Run tab, Watch, play and the mechanism library never pass it.
ARMS = ("real", "shuffled", "lesion_gf")
SHUFFLED_ARMS = ("shuffled", "shuffled_class")     # shuffled_class (docs/SPEC_phase3.md section 5): not a default arm, via --arms
ARM_CHOICES = ARMS + ("shuffled_class",)
LESION_POPULATIONS = ("GF",)
E1_LESION_CLAMP_HZ = LESION_CLAMP_HZ    # invented convention: a lesioned output cell is held at zero activity


@dataclass
class E1Result:
    arm: str                    # "real" | "shuffled" | "lesion_gf" (control)
    seed: int
    shuffle_seed: int | None
    survived: bool
    outcome: str                # "passed" | "stomped" | "died" | "timeout"
    died: bool
    frames: int
    contact_frame: int | None
    resolved_frame: int | None
    gf_fired: bool              # the GF membrane crossed threshold (read before any lesion clamp: "would have fired")
    first_gf_frame: int | None
    gf_before_contact: bool
    theta_at_gf_deg: float | None      # what the fly saw (elevation-weighted theta) on the frame the GF first fired
    distance_at_gf_px: float | None
    a_pressed: bool
    a_frames: int
    max_x: int
    gf_output_max_hz: float = 0.0       # peak GF population output after the clamp (0 in the lesion arm)
    ttmn_max_hz: float = 0.0            # peak TTMn (jump muscle motor neuron) output over the episode


def is_contact(active: bool, dx: int | None, vertical_gap: float, mario_height: int) -> bool:
    """Boxes overlap: the Goomba is active, horizontally within one sprite width and vertically within the summed half heights."""
    return bool(active) and abs(dx) < SPRITE_PX and vertical_gap < (SPRITE_PX + mario_height) / 2.0


def resolution(active: bool, dx: int | None) -> str | None:
    """"stomped" when the slot no longer holds an active Goomba, "passed" when it is entirely behind Mario, else None."""
    if not active:
        return "stomped"
    return "passed" if dx <= -SPRITE_PX else None


def _vertical_gap(ram, slot: int) -> tuple[float, int]:
    from brain.perception import MARIO_BIG_PX, MARIO_SMALL_PX, enemy_centre_y, mario_centre_y
    from mario.ram.addresses import ADDR_MARIO_SIZE
    height = MARIO_SMALL_PX if int(ram[ADDR_MARIO_SIZE]) == 0 else MARIO_BIG_PX
    return abs(enemy_centre_y(ram, slot) - mario_centre_y(ram)), height


def run_e1_episode(seed: int, shuffle_seed: int | None = None, scene: SceneSpec | None = None,
                   max_frames: int = E1_MAX_FRAMES, network=None, calibration=None, on_frame=None, should_stop=None,
                   record_rows: bool = False, arm: str | None = None):
    """One E1 episode. Returns (E1Result, rows, stamp); rows are per-frame telemetry dicts when `record_rows`.
    `on_frame(frame, obs, row)` is called after every emulator step (the tool's live view and frame recorder).
    `arm` is "real", "shuffled" or the control "lesion_gf"; default: "shuffled" if a shuffle seed is given, else "real"."""
    from brain.policy import BrainPolicy
    arm = arm or ("real" if shuffle_seed is None else "shuffled")
    if arm not in ARM_CHOICES or (arm in SHUFFLED_ARMS) != (shuffle_seed is not None):
        raise ValueError(f"arm {arm!r} with shuffle_seed {shuffle_seed!r}: shuffled needs a shuffle seed, the others none")
    from mario.emulator.env import make_env
    from mario.ram import screen
    from mario.ram.addresses import (ADDR_ENEMY_ACTIVE, ADDR_ENEMY_PAGE, ADDR_ENEMY_TYPE, ADDR_ENEMY_X, ADDR_MARIO_PAGE,
                                     ADDR_MARIO_SCREEN_X, ADDR_MARIO_X, ADDR_MARIO_Y)
    from mario.entities.registry import GOOMBA_TYPE_BYTE
    scene = scene or load_scene()
    policy = BrainPolicy(network=network, calibration=calibration, shuffle_seed=shuffle_seed,
                         shuffle_mode="class" if arm == "shuffled_class" else "degree",
                         lesion=LESION_POPULATIONS if arm == "lesion_gf" else ())
    env = make_env(scene.level)
    build_scene(env, scene)
    ram = env.unwrapped.ram
    on_screen = [s for s in goomba_slots(ram) if screen.enemy_on_screen(ram, s, SPRITE_PX)]
    if not on_screen:
        raise RuntimeError(f"scene {scene.id}: no Goomba on screen at takeover")
    slot = on_screen[0]
    policy.reset(seed)

    class _Obs:
        pass
    obs = _Obs()
    obs.ram = ram
    contact = resolved = first_gf = None
    theta_gf = dist_gf = None
    a_frames, max_x, died, kind = 0, 0, False, None
    gf_out_max = ttmn_max = 0.0
    rows: list[dict] = []
    frames = 0
    for frames in range(1, max_frames + 1):
        if should_stop is not None and should_stop():
            break
        action = policy.act(obs)
        readout, buttons = policy.last_readout, policy.last_buttons
        if readout.gf_spiked and first_gf is None:
            first_gf, theta_gf = frames, math.degrees(policy.last_theta)
            dist_gf = None if policy.last_distance is None else float(policy.last_distance)
        a_frames += int(buttons.a)
        gf_out_max, ttmn_max = max(gf_out_max, readout.pooled("GF")), max(ttmn_max, readout.pooled("TTMn"))
        screen_obs, _, done, info = env.step(action)
        mario_x = int(ram[ADDR_MARIO_PAGE]) * 256 + int(ram[ADDR_MARIO_X])
        max_x = max(max_x, mario_x)
        active = bool(ram[ADDR_ENEMY_ACTIVE + slot]) and ram[ADDR_ENEMY_TYPE + slot] == GOOMBA_TYPE_BYTE
        dx = int(ram[ADDR_ENEMY_PAGE + slot]) * 256 + int(ram[ADDR_ENEMY_X + slot]) - mario_x if active else None
        if active and contact is None:
            vgap, height = _vertical_gap(ram, slot)
            if is_contact(active, dx, vgap, height):
                contact = frames
        died = info["life"] < 2 or (done and not info.get("flag_get"))
        if resolved is None and not died:
            kind = resolution(active, dx)
            if kind is not None:
                resolved = frames
        if on_frame is not None or record_rows:
            row = _row(frames, ram, policy, readout, buttons, action, mario_x, dx, ADDR_MARIO_SCREEN_X, ADDR_MARIO_Y)
            if record_rows:
                rows.append(row)
            if on_frame is not None:
                on_frame(frames, screen_obs, row)
        if died or (resolved is not None and frames >= resolved + E1_GRACE_FRAMES) or done:
            break
    env.close()
    survived = (not died) and resolved is not None and frames >= resolved + E1_GRACE_FRAMES
    outcome = "died" if died else (kind if survived else "timeout")
    gf_before = first_gf is not None and (contact is None or first_gf <= contact)
    res = E1Result(arm, seed, shuffle_seed, survived, outcome, died, frames,
                   contact, resolved, first_gf is not None, first_gf, gf_before, theta_gf, dist_gf, a_frames > 0,
                   a_frames, max_x, gf_out_max, ttmn_max)
    stamp = {**policy.stamp(), "scene": scene.to_dict(), "experiment": "E1", "grace_frames": E1_GRACE_FRAMES}
    return res, rows, stamp


def _row(frame, ram, policy, readout, buttons, action, mario_x, dx, addr_sx, addr_y) -> dict:
    """One telemetry row, with the column names the tool's player, plots and brain map already read."""
    th = policy.last_theta
    direction = "L" if buttons.left else ("R" if buttons.right else "")
    return {"frame": frame, "mario_x": mario_x, "mario_sx": int(ram[addr_sx]), "mario_y": int(ram[addr_y]),
            "theta": th, "dtheta": 0.0, "d_px": policy.last_distance if policy.last_distance is not None else float("nan"),
            "goomba_dx": dx if dx is not None else float("nan"),
            "lc4": policy.brain.population_rate("LC4"), "lplc2": policy.brain.population_rate("LPLC2"),
            "mem": readout.gf_membrane, "spike": int(readout.gf_spiked), "ttmn": readout.pooled("TTMn"),
            "dna01": readout.pooled("DNa01"), "dna02": readout.pooled("DNa02"), "dnp09": readout.pooled("DNp09"),
            "mdn": readout.pooled("MDN"), "direction": direction, "press_a": int(buttons.a),
            "press_b": int(buttons.b), "action": int(action)}


# ---- evaluation ----------------------------------------------------------------------------------------------------
def _job(args) -> E1Result:
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    seed, shuffle_seed, max_frames, arm = args
    return run_e1_episode(seed, shuffle_seed, max_frames=max_frames, arm=arm)[0]


def summarize(results: list[E1Result]) -> dict:
    from tool.core.evaluation import wilson_ci
    n = len(results)
    k = sum(r.survived for r in results)
    g = sum(r.gf_before_contact for r in results)
    lo, hi = wilson_ci(k, n)
    glo, ghi = wilson_ci(g, n)
    th = [r.theta_at_gf_deg for r in results if r.theta_at_gf_deg is not None]
    dd = [r.distance_at_gf_px for r in results if r.distance_at_gf_px is not None]
    return {"n": n, "survived": k, "survived_ci": [lo, hi], "deaths": sum(r.died for r in results),
            "timeouts": sum(r.outcome == "timeout" for r in results),
            "gf_before_contact": g, "gf_before_contact_ci": [glo, ghi], "gf_fired": sum(r.gf_fired for r in results),
            "a_pressed_runs": sum(r.a_pressed for r in results),
            "gf_output_max_hz": max((r.gf_output_max_hz for r in results), default=0.0),
            "ttmn_max_hz": max((r.ttmn_max_hz for r in results), default=0.0),
            "theta_at_gf_deg": {"n": len(th), "median": float(np.median(th)) if th else None,
                                "min": min(th) if th else None, "max": max(th) if th else None},
            "distance_at_gf_px": {"n": len(dd), "median": float(np.median(dd)) if dd else None}}


def run_eval(n: int = E1_N, seed0: int = E1_SEED0, workers: int = 1, max_frames: int = E1_MAX_FRAMES,
             arms: tuple[str, ...] = ARMS) -> dict:
    """Real connectome vs degree-preserving shuffle (shuffle seed 1 + i) vs the GF-lesion control (real connectome, both GF
    cells silenced), seeds seed0..seed0+n-1, same noise seeds in every arm."""
    from brain.policy import BrainPolicy
    jobs = [(seed0 + i, 1 + i if arm in SHUFFLED_ARMS else None, max_frames, arm) for arm in arms for i in range(n)]
    if workers > 1:
        with mp.get_context("spawn").Pool(workers) as pool:
            results = pool.map(_job, jobs)
    else:
        results = [_job(j) for j in jobs]
    out = {"experiment": "E1", "metric": "survived the encounter", "seeds": [seed0, seed0 + n - 1],
           "max_frames": max_frames, "grace_frames": E1_GRACE_FRAMES, "scene": load_scene().to_dict(),
           "stamp": BrainPolicy().stamp(), "criterion": dict(CRITERION)}
    out["arms"] = list(arms)
    for arm in arms:
        out[arm] = summarize([r for r in results if r.arm == arm])
    out["episodes"] = [asdict(r) for r in results]
    return out


def format_eval(res: dict) -> str:
    st = res["stamp"]
    lines = [f"E1 jump the Goomba, scene {res['scene']['id']} ({res['scene']['scene_hash']}), seeds "
             f"{res['seeds'][0]}-{res['seeds'][1]}, max {res['max_frames']} frames, grace {res['grace_frames']}",
             f"network {st['build_hash']}, calibration {st['calibration_hash']}"]
    for arm in res.get("arms", ["real", "shuffled"]):
        s = res[arm]
        th, dd = s["theta_at_gf_deg"], s["distance_at_gf_px"]
        lines.append(
            f"{arm:9s} survived {s['survived']}/{s['n']} (95% CI {s['survived_ci'][0]:.0%}-{s['survived_ci'][1]:.0%}); "
            f"deaths {s['deaths']}; timeouts {s['timeouts']}; GF before contact {s['gf_before_contact']}/{s['n']}; "
            f"A-press runs {s['a_pressed_runs']}; GF fired {s['gf_fired']}/{s['n']}; "
            f"GF output max {s.get('gf_output_max_hz', 0.0):.2f} Hz, TTMn max {s.get('ttmn_max_hz', 0.0):.3f} Hz; theta at GF " +
            ("none fired" if th["n"] == 0 else f"median {th['median']:.1f} deg ({th['min']:.1f}-{th['max']:.1f}), "
                                              f"distance median {dd['median']:.0f} px"))
    return "\n".join(lines)


def main(argv=None) -> None:
    import argparse
    ap = argparse.ArgumentParser(description="E1 jump the Goomba: real vs shuffled connectome, plus the GF-lesion control")
    ap.add_argument("--n", type=int, default=E1_N)
    ap.add_argument("--seed0", type=int, default=E1_SEED0)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--max-frames", type=int, default=E1_MAX_FRAMES)
    ap.add_argument("--arms", nargs="+", choices=ARM_CHOICES, default=list(ARMS),
                    help="arms to run; lesion_gf is the control-only GF silencing arm")
    ap.add_argument("--out", default=None, help="write the full result (per-episode rows included) as JSON")
    args = ap.parse_args(argv)
    res = run_eval(args.n, args.seed0, args.workers, args.max_frames, tuple(args.arms))
    print(format_eval(res))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=1, default=str)


if __name__ == "__main__":
    main()
