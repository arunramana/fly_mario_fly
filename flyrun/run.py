"""One episode of 1-1 driven by the fly. CLI: python -m flyrun.run --out runs/NAME [--video]."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import env as E
from . import level
from . import scripted
from . import motor
from .brain import Brain, load_brain, step
from .knobs import BLIND_PX, Knobs   # BLIND_PX: INVENTED (fixed), see knobs.py
from .senses import Senses
from .senses_v2 import SensesV2

_ENV = None  # one emulator per process; reset() is deterministic


def _get_env():
    global _ENV
    if _ENV is None:
        _ENV = E.make_env()
    return _ENV


def run_episode(knobs, W, noop_start=0, max_frames=3000, stuck_frames=150, record=False,
                enemy_input=True, takeover_x=None, episode_seed=None, controller=None, record_h=False, probe=None):
    """W is a Brain (weights + masks). enemy_input=False is the silence control (test switch,
    not a knob). takeover_x (ASSISTED, diagnostic): a scripted player drives until Mario is on the
    ground at x >= takeover_x, then the fly takes over from a silent brain; rows carry
    driver="script"/"fly". With record=True the RGB frames are returned in df.attrs["frames"]."""
    brain = W if isinstance(W, Brain) else None
    assert brain is not None, "pass the Brain from load_brain()"
    env = _get_env()
    state = env.reset()
    frames = [np.asarray(state).copy()] if record else None
    # episode_seed=None: no sensor noise (and baselines needing randomness get seed 0)
    rng = np.random.default_rng(episode_seed) if episode_seed is not None else None
    v2 = knobs.SENSES_VERSION == "v2"
    senses = (SensesV2 if v2 else Senses)(knobs, brain.masks, brain.K, rng)
    if controller is not None:
        controller = controller(knobs, rng if rng is not None else np.random.default_rng(0))   # no-brain baseline policy
    h = np.zeros(brain.K)
    assert knobs.MOTOR_VERSION == "v1" or v2, "MOTOR_VERSION v2 requires SENSES_VERSION v2"
    muscle = motor.Muscle2() if knobs.MOTOR_VERSION == "v2" else motor.Muscle()
    left_frames, left_presses, prev_left = 0, 0, 0
    driver = scripted.Driver() if takeover_x is not None else None
    rows, info = [], {}
    Hs = []
    max_x, best_x_frame = 0, 0
    end_reason = "timeout"
    prev_a, blind, n_onsets, counting = 0, 0, 0, False

    for frame in range(max_frames):
        ram = env.unwrapped.ram
        mx, _ = E.nearest_threat_d(ram)
        goombas = E.threats_ahead(ram)
        who = "baseline" if controller is not None else "fly"   # the guard in fitness._one rejects "script" only
        counting, near_d = False, None
        if driver is not None and not (mx >= takeover_x and int(ram[0x001D]) == 0):
            who = "script"
            action = driver.act(ram)
            loom = dict(theta=0.0, dtheta=0.0, tau=np.nan, stim_src="script", stim_d=None)
            read = dict(ttmn=0.0, dnp09=0.0, steer=0.0)
        elif frame < noop_start:
            # brain has not taken over yet: it sees nothing and presses nothing
            action = E.NOOP
            loom = dict(theta=0.0, dtheta=0.0, tau=np.nan, stim_src="none", stim_d=None)
            read = dict(ttmn=0.0, dnp09=0.0, steer=0.0)
        else:
            driver = None   # handed over for good
            face, pit = level.obstacles_ahead(ram)
            # ground truth for the blind-press count: nearest enemy / pipe face / pit ahead (px)
            ahead = [d_ for _, d_ in goombas]
            if face is not None:
                ahead.append(face.x - mx)
            if pit is not None and pit.x - mx > 0:
                ahead.append(pit.x - mx)
            near_d, counting = (min(ahead) if ahead else None), True
            I, lm = senses.look(ram, enemy_input) if v2 else senses.look(mx, goombas, enemy_input, face, pit)
            if controller is not None:
                if hasattr(controller, "airborne"):      # S3 controls with a landing reset read the same airborne flag as motor v2
                    controller.airborne = int(ram[0x001D]) != 0
                action = controller.act(lm)
                read = dict(ttmn=0.0, dnp09=0.0, steer=0.0)
            else:
                for _ in range(knobs.SUBSTEPS):
                    h = step(h, brain.W, knobs.G, I, knobs.ALPHA, knobs.CLIP)
                if knobs.MOTOR_VERSION == "v2":
                    action, read = motor.decide(h, brain.masks, knobs, muscle, airborne=int(ram[0x001D]) != 0)
                else:
                    action, read = motor.decide(h, brain.masks, knobs, muscle)
            loom = dict(theta=lm.theta, dtheta=lm.dtheta, tau=lm.tau, stim_src=lm.src, stim_d=lm.dist)
            if v2:
                loom.update(lm.extra)

        if record_h:
            Hs.append(h.astype(np.float32))
        a_now = int(action in (E.RIGHT_A, E.LEFT_A))
        if counting and a_now and not prev_a:
            n_onsets += 1
            if near_d is None or near_d > BLIND_PX:
                blind += 1
        prev_a = a_now
        left_now = int(action in (E.LEFT, E.LEFT_A))
        left_frames += left_now
        left_presses += int(left_now and not prev_left)
        prev_left = left_now
        state, _, done, info = env.step(action)
        if record:
            frames.append(np.asarray(state).copy())
        x = int(info.get("x_pos", mx))
        rows.append(dict(
            frame=frame, x=x, score=int(info.get("score", 0)), **loom,
            ttmn=read["ttmn"], dnp09=read["dnp09"], steer=read["steer"],
            buttons=E.NAMES[action], driver=who, air=int(int(ram[0x001D]) != 0),
            a=int(action in (E.RIGHT_A, E.LEFT_A)),
            right=int(action in (E.RIGHT, E.RIGHT_A)),
            left=int(action in (E.LEFT, E.LEFT_A)),
            **(dict(y=int(ram[0x00CE]), a_why=read.get("why", "")) if knobs.MOTOR_VERSION == "v2" else {}),
            **(dict(mdn=read.get("mdn", 0.0), backup=int(read.get("mdn", 0.0) > knobs.MDN_THRESH)) if knobs.SOUR_SENSE else {}),
            **(probe(ram) if probe is not None else {}),     # C1: extra per-frame columns read from RAM (never fed back)
        ))
        if x > max_x:
            max_x, best_x_frame = x, frame
        if info.get("flag_get"):
            end_reason = "flag"
            break
        if done:
            end_reason = "died"
            break
        if frame - best_x_frame >= stuck_frames:
            end_reason = "stuck"
            break

    df = pd.DataFrame(rows)
    if record:
        df.attrs["frames"] = frames
    if record_h:
        df.attrs["H"] = np.array(Hs)   # (frames, neurons), for the brain-panel clips
    summary = dict(
        max_x=int(max_x), score=int(info.get("score", 0)),
        flag_get=bool(info.get("flag_get", False)), frames=len(df),
        end_reason=end_reason, x_at_end=int(df["x"].iloc[-1]),
        cause=cause_of(env.unwrapped.ram, end_reason, int(df["x"].iloc[-1])),
        blind_presses=int(blind), n_onsets=int(n_onsets), a_frac=float(df["a"].mean()),
    )
    if knobs.MOTOR_VERSION == "v2":
        summary.update(left_frames=left_frames, left_presses=left_presses)
        if left_presses:
            summary["LEFT_PRESS_WARNING"] = f"{left_presses} Left presses ({left_frames} frames)"
    return summary, df


def cause_of(ram, end_reason, x):
    """Short label for why an episode ended (diagnostic only; never used in fitness)."""
    if end_reason in ("flag", "timeout"):
        return end_reason
    near = [(sl, dx) for sl, dx in ((sl, d) for sl, d in _signed_enemies(ram)) if abs(dx) <= 20]
    walls, pits = level.scan_visible(ram)
    in_pit = any(px - 12 <= x <= px + pw + 12 for px, pw in pits)
    face, _ = level.obstacles_ahead(ram)
    if end_reason == "died":
        if in_pit:
            return "pit"
        return f"enemy dx={near[0][1]}" if near else "died (other)"
    if face is not None and face.x - x <= 20:
        return f"wall H{face.h} @{face.x}"
    return "stuck (open ground)"


def _signed_enemies(ram):
    mx = E.mario_x(ram)
    out = []
    for sl in range(E.N_ENEMY_SLOTS):
        if int(ram[E.ADDR_ENEMY_ACTIVE + sl]) and int(ram[E.ADDR_ENEMY_TYPE + sl]) != E.POWERUP_ID:
            out.append((sl, int(ram[E.ADDR_ENEMY_PAGE + sl]) * 256 + int(ram[E.ADDR_ENEMY_X + sl]) - mx))
    return out


def save_video(frames, path, fps=30):
    import cv2
    path = Path(path)
    h, w = frames[0].shape[:2]
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    for f in frames:
        vw.write(cv2.cvtColor(np.ascontiguousarray(f), cv2.COLOR_RGB2BGR))
    vw.release()
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="output stem, e.g. runs/000_default")
    ap.add_argument("--video", action="store_true")
    ap.add_argument("--noop-start", type=int, default=0)
    ap.add_argument("--max-frames", type=int, default=3000)
    args = ap.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    summary, df = run_episode(Knobs(), load_brain(), noop_start=args.noop_start,
                              max_frames=args.max_frames, record=args.video)
    df.to_csv(out.with_name(out.name + "_log.csv"), index=False)
    out.with_name(out.name + "_summary.json").write_text(json.dumps(summary, indent=2))
    if args.video:
        save_video(df.attrs["frames"], out.with_suffix(".mp4"))
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
