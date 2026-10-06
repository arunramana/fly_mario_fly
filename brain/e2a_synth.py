# What this file does, in plain English:
# The synthetic test bench for the obstacle cue, no game needed. It builds a tiny
# fake world (a pipe, a block or a staircase on flat ground), walks a pretend
# Mario toward it at a fixed speed and records what the fly sees and does: the
# angular size of the face, when the Giant Fiber fires, and when the jump button
# would be pressed. It also checks that flat ground gives no stimulus and that the
# looming disc still fires the Giant Fiber at 38-48 degrees with the obstacle
# mechanism attached. These numbers validate the encoding; nothing is tuned on them.
"""brain/e2a_synth.py -- docs/SPEC_e2a.md section 2 (validation plan), shared by audit/e2a_synth.py and tests/test_e2a.py.

Open loop like docs/INVESTIGATION_phase6.md: Mario's x follows a fixed trace (speed px/frame) and stops at the stall point (14 px
before the face, measured), so the stimulus changes only through Mario's own motion. Everything enters through the mechanisms and
`Brain.apply`; the motor map only reads.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from brain.brain import Brain
from brain.calibration import ELEVATION_LIMIT_DEG
from brain.mechanisms import HomeLandmarkMechanism, LoomingMechanism, ObstacleExpansion
from brain.motor_map import MotorMap
from brain.obstacles import BODY_SMALL_PX, FLOOR_ROW, nearest_face, theta_of
from brain.perception import front_edge_offset_px

FACE_X = 448                      # pipe 1's left edge
STALL_X = 434                     # measured: small Mario stalls here at the pipe (docs/INVESTIGATION_phase6.md (b))
WALK_PX_PER_FRAME, RUN_PX_PER_FRAME = 2.57, 3.0   # walking / running speed (Phase 5c bench values; was 1.75 walking)
FEET_Y, SMALL_PX = 208, BODY_SMALL_PX   # small Mario standing on the floor; body = the 12 px hitbox (5c step 3)
TAKEOFF_WINDOW_1FRAME = (5, 29)   # px before the stall point where a 1-frame A tap clears pipe 1 (INVESTIGATION_phase6 (b))
SCREEN_PX = 256
SCROLL_DRAWN_X = 111              # Mario's drawn x once the screen scrolls (measured at the stall: 0x03AD = 111)


def empty_column() -> list[int]:
    return [0] * 13


def stack(height_tiles: int) -> list[int]:
    """A column with `height_tiles` solid tiles standing on the floor (rows 11-12 are the floor itself)."""
    col = [0] * 13
    for r in range(FLOOR_ROW - height_tiles, FLOOR_ROW):
        col[r] = 0x12
    col[11] = col[12] = 0x54
    return col


GEOMETRIES = {
    "pipe_32x32": {FACE_X: stack(2), FACE_X + 16: stack(2)},                      # pipe 1: two columns, two tiles high
    "pipe_48x3": {FACE_X: stack(3), FACE_X + 16: stack(3)},                       # pipe 2: three tiles high
    "pipe_64x4": {FACE_X: stack(4), FACE_X + 16: stack(4)},                       # pipe 3: four tiles high
    "step_16": {FACE_X: stack(1), FACE_X + 16: stack(1)},                         # a one-tile step (two columns wide)
    "block_16": {FACE_X: stack(1)},                                                # one 16 px block
    "stairs_1_2_3_4": {FACE_X + 16 * i: stack(i + 1) for i in range(4)},           # staircase, first step one tile
}


def visible(world: dict[int, list[int]], mario_x: float) -> list[tuple[int, list[int]]]:
    """Columns drawn on screen for a Mario at `mario_x` (the screen scrolls so Mario is drawn at most at x = 111)."""
    left = max(0.0, mario_x - SCROLL_DRAWN_X)
    return [(x, t) for x, t in sorted(world.items()) if left <= x + 15 and x < left + SCREEN_PX]


def face_trace(world: dict[int, list[int]], speed: float, x0: float, frames: int, stall_x: float = STALL_X) -> list[dict]:
    """The open-loop stimulus: per frame Mario x, obstacle distance, theta (rad), dtheta."""
    out, prev = [], 0.0
    for f in range(frames):
        x = min(x0 + speed * f, stall_x)
        face = nearest_face(visible(world, x), x, FEET_Y, SMALL_PX)
        th, d = theta_of(face, FEET_Y - SMALL_PX, FEET_Y, ELEVATION_LIMIT_DEG, front_edge_offset_px(0))
        out.append({"frame": f, "x": x, "d": d, "theta": th, "dtheta": th - prev})
        prev = th
    return out


@dataclass
class ApproachResult:
    first_gf_frame: int | None
    x_at_gf: float | None
    d_at_gf: float | None
    theta_deg_at_gf: float | None
    px_before_stall_at_gf: float | None
    first_a_frame: int | None
    x_at_a: float | None
    px_before_stall_at_a: float | None
    gf_spikes: int
    a_frames: int
    max_theta_deg: float


def run_approach(network, cal, trace: list[dict], landmark: bool, seed: int = 0, shuffle_seed: int | None = None,
                 obstacle: bool = True, shuffle_mode: str = "degree") -> ApproachResult:
    """Play a face trace into a fresh brain (real or shuffled twin), obstacle cue through `ObstacleExpansion`, optional home landmark."""
    net = network if shuffle_seed is None else network.shuffled(shuffle_seed, shuffle_mode)
    brain = Brain(net, cal, seed=seed)
    mech = ObstacleExpansion(net)
    brain.attach(mech)
    lm = HomeLandmarkMechanism(net) if landmark else None
    if lm is not None:
        brain.attach(lm)
    motor = MotorMap(cal.motor)
    brain.reset(seed)
    gf_frame = a_frame = None
    spikes = a_frames = 0
    for rec in trace:
        th = {"L": rec["theta"], "R": rec["theta"]}
        brain.apply(mech.encode(th, {"L": rec["dtheta"], "R": rec["dtheta"]}))
        if lm is not None:
            brain.apply(lm.encode())
        r = brain.step_frame()
        b = motor.read(r)
        spikes += int(r.gf_spiked)
        a_frames += int(b.a)
        if r.gf_spiked and gf_frame is None:
            gf_frame = rec["frame"]
        if b.a and a_frame is None:
            a_frame = rec["frame"]
    by = {rec["frame"]: rec for rec in trace}

    def at(frame, key):
        return None if frame is None else by[frame][key]
    xg, xa = at(gf_frame, "x"), at(a_frame, "x")
    return ApproachResult(gf_frame, xg, at(gf_frame, "d"), None if gf_frame is None else math.degrees(by[gf_frame]["theta"]),
                          None if xg is None else STALL_X - xg, a_frame, xa, None if xa is None else STALL_X - xa, spikes, a_frames,
                          math.degrees(max(rec["theta"] for rec in trace)))


def run_disc_with_obstacle(network, cal, lv_ms: float, landmark: bool, seed: int = 0, shuffle_seed: int | None = None) -> float | None:
    """The calibration disc (brain.disc.run_disc's bookkeeping) with `ObstacleExpansion` attached and fed the flat-ground stimulus
    (theta 0 every frame, which is what `obstacle_thetas` returns on flat ground) and optionally the landmark. Returns the angle (deg)
    at which the GF first spikes (None if never)."""
    from bridge.loom_disc import FRAME_MS, THETA0_DEG
    net = network if shuffle_seed is None else network.shuffled(shuffle_seed)
    brain = Brain(net, cal, seed=seed)
    loom, obst = LoomingMechanism(net), ObstacleExpansion(net)
    brain.attach(loom)
    brain.attach(obst)
    lm = HomeLandmarkMechanism(net) if landmark else None
    if lm is not None:
        brain.attach(lm)
    tau0 = lv_ms / math.tan(math.radians(THETA0_DEG) / 2.0)
    brain.reset(seed)
    prev = 0.0
    zero = {"L": 0.0, "R": 0.0}
    for f in range(int(tau0 / FRAME_MS) + 3):
        tau = tau0 - f * FRAME_MS
        if tau <= 0:
            break
        th = 2.0 * math.atan(lv_ms / tau)
        dth, prev = th - prev, th
        brain.apply(loom.encode({"L": th, "R": th}, {"L": dth, "R": dth}))
        brain.apply(obst.encode(zero, zero))
        if lm is not None:
            brain.apply(lm.encode())
        if brain.step_frame().gf_spiked:
            return math.degrees(th)
    return None


def rest_gf_spikes(network, cal, frames: int = 1000, seed: int = 0, landmark: bool = False, shuffle_seed: int | None = None) -> int:
    """GF spikes over `frames` frames with no stimulus except flat-ground zeros through the obstacle mechanism (and the landmark if on)."""
    net = network if shuffle_seed is None else network.shuffled(shuffle_seed)
    brain = Brain(net, cal, seed=seed)
    obst = ObstacleExpansion(net)
    brain.attach(obst)
    lm = HomeLandmarkMechanism(net) if landmark else None
    zero = {"L": 0.0, "R": 0.0}
    brain.reset(seed)
    n = 0
    for _ in range(frames):
        brain.apply(obst.encode(zero, zero))
        if lm is not None:
            brain.apply(lm.encode())
        n += int(brain.step_frame().gf_spiked)
    return n
