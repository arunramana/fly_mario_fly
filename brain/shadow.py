# What this file does, in plain English:
# "Shadow mode": a person plays Super Mario Bros 1-1 with the keyboard while the
# redesigned fly watches the same game, frame by frame, through exactly the senses
# it has in the baseline run. The fly's would-be buttons are written to a log and
# thrown away; only the human's buttons ever reach the emulator, so the fly
# controls nothing and cannot change the game. The log (one row per frame) lets us
# ask afterwards whether the fly's signals were there when the human decided to jump.
"""brain/shadow.py -- docs/SPEC_shadow.md.

    .venv/Scripts/python.exe -m brain.shadow --label clean --out projects/shadow/telemetry/001_clean.csv --seed 9400
    .venv/Scripts/python.exe -m brain.shadow --label clean --out x.csv --replay actions.npy      # headless, no window

Keys: arrows = D-pad, X = A (jump), Z = B (run), Enter = Start (recorded only: the 64-action space has no Start), Esc = quit.

Non-influence (the fly controls nothing): `env.step` receives `human_action` and nothing else. `policy.act()` is called as a bare
statement, its return value (the fly's would-be action index) is dropped, and the fly's buttons are read from `policy.last_buttons`
into the CSV only. tests/test_shadow.py asserts this statically (AST) and behaviourally (identical RAM and screen hashes with and
without the policy). No RAM byte is written here. The brain is the B11 brain: same senses, same `step_frame`/`apply` path, same MotorMap.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from mario.actions.actions import action_from_buttons, buttons_of

SHADOW_EXPERIMENT = "B11"             # the senses of the 1-1 baseline (looming + pursuit + landmark + obstacle expansion)
SHADOW_SEED = 9400                    # noise seed (held out from every earlier seed range)
MAX_FRAMES = 30000                    # bound only so a forgotten window ends; not a game rule
REST_FRAMES, REST_SETTLE_FRAMES = 3000, 60   # the no-stimulus rest run that defines TTMn's resting range (docs/SPEC_shadow.md)
FPS = 60.0
HUMAN_BUTTONS = ("right", "left", "down", "up", "a", "b", "start", "select")
FLY_BUTTONS = HUMAN_BUTTONS           # start/select are never pressed by the fly (and never sendable)
KEY_HELP = "arrows = D-pad, X = A (jump), Z = B (run), Enter = Start (recorded only), Esc = quit"

COLUMNS = (
    ["frame", "label", "mario_x", "mario_sx", "mario_y", "mario_size", "airborne"]
    + [f"human_{b}" for b in HUMAN_BUTTONS] + [f"fly_{b}" for b in FLY_BUTTONS]
    + ["theta", "dtheta", "d_px", "obst_theta", "obst_dtheta", "obst_d_px", "enemy_x", "enemy_dx",
       "gf_l_hz", "gf_r_hz", "ttmn_hz", "ttmn_side_max_hz", "dnp09_hz", "dna01_hz", "dna02_hz", "mdn_hz",
       "gf_mem", "gf_mem_l", "gf_mem_r", "gf_spike", "muscle_drive", "muscle_over", "walk_over",
       "lc10a_l", "lc10a_r", "landmark_on", "goombas_on_screen", "flag_get_after", "life_after", "done_after",
       "lc4_hz", "lplc2_hz", "arousal", "pursuit_az", "pursuit_dx", "ttmn_rest_max"])


# ---- where the human's buttons come from -------------------------------------------------------------------------
class ReplaySource:
    """Headless: the human's buttons come from a recorded array of indices into MOVES_ALL (used by the tests and `--replay`)."""
    def __init__(self, actions):
        self.actions = np.asarray(actions, dtype=np.uint8)
        self._i = 0
        self.start_pressed = False

    def poll(self) -> dict | None:
        if self._i >= len(self.actions):
            return None
        held = buttons_of(int(self.actions[self._i]))
        self._i += 1
        return {"right": held["right"], "left": held["left"], "down": held["down"], "up": held["up"],
                "a": held["A"], "b": held["B"], "start": False, "select": False}

    def show(self, screen) -> None:
        pass

    def close(self) -> None:
        pass


class KeyboardSource:
    """The pyglet window of nes-py (`nes_py._image_viewer.ImageViewer`), as `nes_py.app.play_human` uses it, with a 60 fps pace.
    Written by reading play_human; it opens a window, so it is not exercised by the headless tests."""
    END_REASON = "quit"

    def __init__(self, scale: int = 2, fps: float = FPS):
        self.scale, self.dt = scale, 1.0 / fps
        self._viewer = None
        self._next = None
        self.start_pressed = False

    def _open(self, screen):
        from nes_py._image_viewer import ImageViewer
        import pyglet
        k = pyglet.window.key
        self._keys = {"left": k.LEFT, "right": k.RIGHT, "up": k.UP, "down": k.DOWN, "a": k.X, "b": k.Z, "start": ord("\r")}
        relevant = set(self._keys.values())

        class _Viewer(ImageViewer):
            def _handle_key_event(self, symbol, is_press):         # set semantics: a release without a press must not raise
                symbol = self.KEY_MAP.get(symbol, symbol)
                if symbol == k.ESCAPE:
                    self._is_escape_pressed = is_press
                elif symbol in relevant:
                    if is_press and symbol not in self._pressed_keys:
                        self._pressed_keys.append(symbol)
                    elif not is_press and symbol in self._pressed_keys:
                        self._pressed_keys.remove(symbol)

        self._viewer = _Viewer("fly_mario shadow mode (you play; the fly only watches)", screen.shape[0] * self.scale,
                               screen.shape[1] * self.scale, monitor_keyboard=True, relevant_keys=relevant)

    def poll(self) -> dict | None:
        now = time.perf_counter()
        if self._next is None:
            self._next = now
        while time.perf_counter() < self._next:                   # real-time pace: emulation is not throttled below 60 fps
            pass
        self._next = max(self._next + self.dt, time.perf_counter() - self.dt)
        if self._viewer is None:
            return {b: False for b in HUMAN_BUTTONS}
        if self._viewer.is_escape_pressed:
            return None
        down = set(self._viewer.pressed_keys)
        return {b: (self._keys[b] in down) for b in ("right", "left", "down", "up", "a", "b", "start")} | {"select": False}

    def show(self, screen) -> None:
        if self._viewer is None:
            self._open(screen)
        self._viewer.show(screen)

    def close(self) -> None:
        if self._viewer is not None:
            self._viewer.close()


# ---- helpers (read-only) -----------------------------------------------------------------------------------------
def rest_noise_range(policy, seed: int, frames: int = REST_FRAMES, settle: int = REST_SETTLE_FRAMES) -> float:
    """TTMn's resting range, defined in the SPEC before any play: max over `frames` frames (after `settle`) of the pooled TTMn rate when
    the brain gets NO stimulus at all. Uses only `Brain.reset` and `step_frame` on the shadow brain, then resets it for the run."""
    policy.brain.reset(seed)
    peak = 0.0
    for i in range(frames):
        r = policy.brain.step_frame()
        if i >= settle:
            peak = max(peak, r.pooled("TTMn"))
    policy.reset(seed)
    return peak


def _gf_membrane_by_side(policy) -> tuple[float, float]:
    """GF membrane per hemisphere at the last substep (a spike resets it to 0). Read-only."""
    net = policy.brain.network
    mem = policy.brain._net.integrator.mem
    sides = net.side[net.pops["GF"]]
    pick = lambda s: float(mem[sides == s].max()) if (sides == s).any() else float("nan")
    return pick("L"), pick("R")


def _lc10a_drive(policy) -> tuple[float, float]:
    """The LC10a drive (left, right) the attached mechanisms add this frame, from their pure `encode` functions (nothing is applied)."""
    left = right = 0.0
    stims = []
    if policy.pursuit is not None and policy.last_target is not None:
        stims.append(policy.pursuit.encode(policy.last_target.azimuth_deg, policy.last_target.salience, policy.last_arousal))
    if policy.landmark is not None:
        stims.append(policy.landmark.encode())
    for s in stims:
        left, right = left + float(s.values[0]), right + float(s.values[-1])      # TargetMechanism.drive: left ids first
    return left, right


def _enemy_view(ram) -> tuple[float, float, int]:
    """(nearest on-screen enemy's world x, its dx from Mario, Goombas on screen). Descriptive only; power-ups are not enemies."""
    from mario.entities.kinds import EntityKind
    from mario.entities.registry import DEFAULT
    from mario.ram import screen
    from mario.ram.addresses import ADDR_ENEMY_PAGE, ADDR_ENEMY_X, ADDR_MARIO_PAGE, ADDR_MARIO_X
    mario_x = int(ram[ADDR_MARIO_PAGE]) * 256 + int(ram[ADDR_MARIO_X])
    best, goombas = None, 0
    for slot, rec in enumerate(DEFAULT.enemy_records(ram)):
        if not rec.active or rec.kind == EntityKind.POWERUP or not screen.enemy_on_screen(ram, slot, rec.width):
            continue
        goombas += int(rec.kind == EntityKind.GOOMBA)
        x = int(ram[ADDR_ENEMY_PAGE + slot]) * 256 + int(ram[ADDR_ENEMY_X + slot])
        if best is None or abs(x - mario_x) < abs(best - mario_x):
            best = x
    return (float("nan"), float("nan"), 0) if best is None else (float(best), float(best - mario_x), goombas)


def _nan(v) -> float:
    return float("nan") if v is None else float(v)


@dataclass
class ShadowResult:
    label: str
    seed: int
    frames: int
    end_reason: str
    ttmn_rest_max: float
    human_actions: np.ndarray
    state_hashes: list = field(default_factory=list)
    stamp: dict = field(default_factory=dict)


def _human_action(h: dict) -> int:
    return action_from_buttons(right=h["right"], left=h["left"], down=h["down"], up=h["up"], a=h["a"], b=h["b"])


# ---- the harness -------------------------------------------------------------------------------------------------
def run_shadow(source, label: str, seed: int = SHADOW_SEED, out_csv: str | Path | None = None, max_frames: int = MAX_FRAMES,
               with_policy: bool = True, settings=None, network=None, calibration=None, hash_states: bool = False,
               rest_frames: int = REST_FRAMES, rest_settle: int = REST_SETTLE_FRAMES) -> ShadowResult:
    """Play one 1-1 episode with the human's buttons from `source`. The brain runs alongside when `with_policy` (the False case
    exists for the test that proves it makes no difference to the game). Rows are flushed to `out_csv` as they are made."""
    from brain.scenes import B11_SCENE_ID, load_scene
    from brain.settings import SenseSettings, settings_for
    from mario.emulator.env import make_env
    from mario.ram.addresses import (ADDR_MARIO_PAGE, ADDR_MARIO_SCREEN_X, ADDR_MARIO_SIZE, ADDR_MARIO_X, ADDR_MARIO_Y,
                                     ADDR_PLAYER_STATE)
    scene = load_scene(B11_SCENE_ID)
    used = settings_for(SHADOW_EXPERIMENT, settings or SenseSettings.user_default())
    policy, rest_max = None, float("nan")
    if with_policy:
        from brain.policy import BrainPolicy
        policy = BrainPolicy(network=network, calibration=calibration, settings=used)
        policy.reset(seed)
        rest_max = rest_noise_range(policy, seed, rest_frames, rest_settle)
        a_thr, walk_thr = policy.cal.motor.a_threshold, policy.cal.motor.walk_threshold
    env = make_env(scene.level)
    env.reset()
    ram = env.unwrapped.ram

    class _Obs:                                           # the observation object BrainPolicy.act reads (.ram), as in brain/baseline.py
        pass
    obs = _Obs()
    obs.ram = ram

    writer = fh = None
    if out_csv is not None:
        out_csv = Path(out_csv)
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        if out_csv.exists():
            raise FileExistsError(f"{out_csv} exists; run counters are never reused or overwritten")
        fh = open(out_csv, "w", newline="", encoding="utf-8")
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        fh.flush()

    actions: list[int] = []
    hashes: list[str] = []
    prev_theta = prev_obst = 0.0
    info = {}
    end_reason, frames = "max_frames", 0
    try:
        source.show(env.unwrapped.screen)
        for frames in range(1, max_frames + 1):
            human = source.poll()
            if human is None:
                end_reason, frames = getattr(source, "END_REASON", "replay_end"), frames - 1
                break
            human_action = _human_action(human)
            if policy is not None:
                policy.act(obs)           # the fly senses and decides; its returned action is deliberately dropped (never sent)
            if writer is not None:
                row = _row(frames, label, ram, policy, human, prev_theta, prev_obst, rest_max, a_thr if policy else None,
                           walk_thr if policy else None, (ADDR_MARIO_PAGE, ADDR_MARIO_X, ADDR_MARIO_SCREEN_X, ADDR_MARIO_Y,
                                                          ADDR_MARIO_SIZE, ADDR_PLAYER_STATE))
            if policy is not None:
                prev_theta, prev_obst = policy.last_theta, policy.last_obstacle_theta
            screen_obs, _, done, info = env.step(human_action)       # ONLY the human's buttons reach the emulator
            actions.append(human_action)
            if hash_states:
                hashes.append(hashlib.blake2b(bytes(ram) + env.unwrapped.screen.tobytes(), digest_size=16).hexdigest())
            if writer is not None:
                row.update({"flag_get_after": int(bool(info.get("flag_get"))), "life_after": int(info.get("life", -1)),
                            "done_after": int(bool(done))})
                writer.writerow(row)
                fh.flush()
            source.show(env.unwrapped.screen)
            if info.get("flag_get"):
                end_reason = "level_complete"
                break
            if done:
                end_reason = "died"
                break
    finally:
        source.close()
        env.close()
        if fh is not None:
            fh.close()
    acts = np.asarray(actions, dtype=np.uint8)
    stamp = {**(policy.stamp() if policy is not None else {}), "scene": scene.to_dict(), "experiment": SHADOW_EXPERIMENT,
             "senses_used": used.to_dict(), "mode": "shadow (the fly controls nothing)"}
    res = ShadowResult(label, seed, len(acts), end_reason, rest_max, acts, hashes, stamp)
    if out_csv is not None:
        stem = str(out_csv)[:-4] if str(out_csv).endswith(".csv") else str(out_csv)
        np.save(stem + "_actions.npy", acts)
        Path(stem + "_meta.json").write_text(json.dumps(
            {"label": label, "seed": seed, "frames": res.frames, "end_reason": end_reason, "ttmn_rest_max": rest_max,
             "rest_rule": f"max pooled TTMn over {rest_frames} no-stimulus frames after {rest_settle} settling frames",
             "keys": KEY_HELP, "stamp": stamp}, indent=1, default=str), encoding="utf-8")
    return res


def _row(frame, label, ram, policy, human, prev_theta, prev_obst, rest_max, a_thr, walk_thr, addrs) -> dict:
    page, x, sx, y, size, state = addrs
    row = {c: float("nan") for c in COLUMNS}
    row.update({"frame": frame, "label": label, "mario_x": int(ram[page]) * 256 + int(ram[x]), "mario_sx": int(ram[sx]),
                "mario_y": int(ram[y]), "mario_size": int(ram[size]), "airborne": int(int(ram[state]) != 0),
                "ttmn_rest_max": rest_max})
    row.update({f"human_{b}": int(bool(human[b])) for b in HUMAN_BUTTONS})
    enemy_x, enemy_dx, goombas = _enemy_view(ram)
    row.update({"enemy_x": enemy_x, "enemy_dx": enemy_dx, "goombas_on_screen": goombas})
    if policy is None:
        return row
    r, b = policy.last_readout, policy.last_buttons
    mem_l, mem_r = _gf_membrane_by_side(policy)
    lc_l, lc_r = _lc10a_drive(policy)
    tgt = policy.last_target
    ttmn_side = max(r.side("TTMn", "L"), r.side("TTMn", "R"))
    row.update({f"fly_{k}": int(bool(getattr(b, k))) for k in ("right", "left", "down", "up", "a", "b")})
    row.update({"fly_start": 0, "fly_select": 0,
                "theta": policy.last_theta, "dtheta": policy.last_theta - prev_theta, "d_px": _nan(policy.last_distance),
                "obst_theta": policy.last_obstacle_theta, "obst_dtheta": policy.last_obstacle_theta - prev_obst,
                "obst_d_px": _nan(policy.last_obstacle_distance),
                "gf_l_hz": r.side("GF", "L"), "gf_r_hz": r.side("GF", "R"), "ttmn_hz": r.pooled("TTMn"),
                "ttmn_side_max_hz": ttmn_side, "dnp09_hz": r.pooled("DNp09"), "dna01_hz": r.pooled("DNa01"),
                "dna02_hz": r.pooled("DNa02"), "mdn_hz": r.pooled("MDN"), "gf_mem": r.gf_membrane, "gf_mem_l": mem_l,
                "gf_mem_r": mem_r, "gf_spike": int(r.gf_spiked), "muscle_drive": policy.motor.drive,
                "muscle_over": int(policy.motor.drive >= a_thr), "walk_over": int(r.pooled("DNp09") > walk_thr),
                "lc10a_l": lc_l, "lc10a_r": lc_r, "landmark_on": int(policy.landmark is not None),
                "lc4_hz": policy.brain.population_rate("LC4"), "lplc2_hz": policy.brain.population_rate("LPLC2"),
                "arousal": policy.last_arousal, "pursuit_az": tgt.azimuth_deg if tgt else float("nan"),
                "pursuit_dx": tgt.dx_px if tgt else float("nan")})
    return row


def main(argv=None) -> None:
    import argparse
    ap = argparse.ArgumentParser(description="shadow mode: you play 1-1, the fly's signals are recorded and its buttons discarded. " + KEY_HELP)
    ap.add_argument("--label", required=True, help="run label written on every row (clean / slow)")
    ap.add_argument("--out", required=True, help="telemetry CSV, e.g. projects/shadow/telemetry/001_clean.csv (never overwritten)")
    ap.add_argument("--seed", type=int, default=SHADOW_SEED)
    ap.add_argument("--replay", default=None, help="actions.npy: drive the human buttons from a recorded array (headless)")
    ap.add_argument("--max-frames", type=int, default=MAX_FRAMES)
    ap.add_argument("--scale", type=int, default=2, help="window scale")
    args = ap.parse_args(argv)
    source = ReplaySource(np.load(args.replay)) if args.replay else KeyboardSource(args.scale)
    if not args.replay:
        print(KEY_HELP)
    res = run_shadow(source, args.label, args.seed, args.out, args.max_frames)
    print(f"{res.label}: {res.frames} frames, ended: {res.end_reason}; TTMn rest max {res.ttmn_rest_max:.5f}; wrote {args.out}")


if __name__ == "__main__":
    main()
