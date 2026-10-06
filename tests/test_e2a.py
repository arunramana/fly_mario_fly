# What this file does, in plain English:
# Tests E2a: the obstacle geometry (what counts as a face, its size and distance,
# that flat floor gives nothing), the rule that obstacle expansion enters only at
# the looming neurons and is off for E0, E1 and E3, the E2a scene and metrics, and
# the synthetic checks that must hold before any game scene: flat ground gives no
# stimulus, the looming disc still fires the Giant Fiber at 38-48 degrees with the
# obstacle mechanism attached, and nothing latches at rest. Nothing here checks
# whether the fly clears the pipe in the game.
"""docs/SPEC_e2a.md sections 1-3. Pure tests need no data; network tests use the cached network and skip with a reason when it
has not been built; emulator tests need nes-py."""
from __future__ import annotations

import math
import re
from pathlib import Path

import numpy as np
import pytest

import brain
from brain import builder, e2a, e2a_synth as S, library, obstacles, scenes
from brain.brain import Brain
from brain.calibration import CALIBRATION_FILE, ELEVATION_LIMIT_DEG, Calibration
from brain.mechanisms import LoomingMechanism, ObstacleExpansion
from brain.settings import SenseSettings, settings_for

BRAIN_DIR = Path(brain.__file__).parent
needs_net = pytest.mark.skipif(not builder.default_path().exists(), reason="network not built (python -m brain.builder)")
needs_cal = pytest.mark.skipif(not CALIBRATION_FILE.exists(), reason="brain/calibration.json missing")


@pytest.fixture(scope="module")
def net():
    return builder.BuiltNetwork.load(builder.default_path())


@pytest.fixture(scope="module")
def cal():
    return Calibration.load()


def _face(world, x, feet=208, h=12):
    return obstacles.nearest_face(S.visible(world, x), x, feet, h)


# ---- pure: the encoding rule -----------------------------------------------------------------------------------------------
def test_pipe_face_is_32_wide_and_its_distance_is_left_edge_minus_mario():
    f = _face(S.GEOMETRIES["pipe_32x32"], 408)
    assert (f.d_px, f.w_px) == (40.0, 32.0) and f.centre_y == 192.0 and (f.top_y, f.bottom_y) == (176.0, 208.0)
    th, d = obstacles.theta_of(f, 196.0, 208.0, ELEVATION_LIMIT_DEG)
    assert d == 40.0 and th == pytest.approx(2 * math.atan(32 / 80))                        # face overlaps the body: elevation 0, weight 1


def test_obstacle_face_is_an_extended_object_its_elevation_is_that_of_its_nearest_point():
    for tiles, w in ((2, 32.0), (3, 48.0), (4, 64.0)):                       # pipes 1/2/3: theta is 2 atan(H / 2d), no centre-point inversion
        f = _face({448: S.stack(tiles)}, 400)
        th = [obstacles.theta_of(_face({448: S.stack(tiles)}, x), 196.0, 208.0, ELEVATION_LIMIT_DEG)[0] for x in range(300, 430, 2)]
        assert f.w_px == w and all(b >= a for a, b in zip(th, th[1:]))
    f = _face({448: S.stack(2)}, 400)                                            # face y 176..208
    assert obstacles.elevation_deg(f, 196.0, 208.0, 48.0) == 0.0                 # overlapping the body: 0 (the old centre rule gave 9.5 deg)
    assert obstacles.elevation_deg(f, 140.0, 172.0, 48.0) == pytest.approx(math.degrees(math.atan2(4.0, 48.0)))  # body above: gap to the top edge
    assert obstacles.elevation_deg(f, 220.0, 240.0, 48.0) == pytest.approx(math.degrees(math.atan2(12.0, 48.0)))  # body below: gap to bottom
    cap = obstacles.theta_of(f, 100.0, 112.0, ELEVATION_LIMIT_DEG)[0]            # 12 px body well above: still weighted down by the unchanged cap
    assert cap < obstacles.theta_of(f, 196.0, 208.0, ELEVATION_LIMIT_DEG)[0]


def test_mario_body_is_the_hitbox_12_small_24_big():
    assert (obstacles.BODY_SMALL_PX, obstacles.BODY_BIG_PX) == (12, 24)
    col = [0] * 13
    col[9] = 0x51                                                                # tile row 9: y 176..192
    assert obstacles.nearest_face([(448, col)], 400, 208, 12) is None            # small hitbox top y 196: below the tile
    assert obstacles.nearest_face([(448, col)], 400, 208, 24) is not None        # big hitbox top y 184 < tile bottom 192: overlaps



def test_block_and_first_stair_step_are_16_px_faces_and_only_the_nearest_column_counts():
    assert _face(S.GEOMETRIES["block_16"], 400).w_px == 16.0
    stairs = _face(S.GEOMETRIES["stairs_1_2_3_4"], 400)
    assert (stairs.d_px, stairs.w_px) == (48.0, 16.0)


def test_flat_floor_is_not_an_obstacle_and_gives_theta_zero():
    flat = {c * 16: S.stack(0) for c in range(0, 200)}
    assert all(_face(flat, x) is None for x in range(40, 3000, 7))
    assert obstacles.theta_of(None, 196.0, 208.0, 60.0) == (0.0, None)
    assert all(r["theta"] == 0.0 and r["d"] is None for r in S.face_trace(flat, 3.0, 40, 400))


def test_a_face_must_be_ahead_and_overlap_mario_body():
    pipe = S.GEOMETRIES["pipe_32x32"]
    assert _face(pipe, 464) is None and _face(pipe, 470) is None                 # at or behind the face: nothing ahead
    assert _face(pipe, 300) is None                                              # not drawn yet: screen left 189 + 256 = 445 < 448
    assert _face(pipe, 312) is not None
    assert _face(pipe, 400, feet=176) is None                                    # Mario above the pipe top (feet at y 176): nothing at body height
    block_high = {448: [0] * 8 + [0x51] + [0] * 4}                               # one floating tile in row 8 (y 160-176)
    assert _face(block_high, 400, h=12) is None                                  # small Mario's body is row 10
    assert _face(block_high, 400, h=24) is None                                  # big Mario: body y 184-208, still below it
    assert _face(block_high, 400, feet=176, h=12).w_px == 16.0                   # standing on a pipe top: it is level with him


def test_a_tall_wall_is_one_run_and_the_longest_overlapping_run_wins():
    col = [0] * 13
    col[8] = col[9] = col[10] = 0x51                                             # rows 8-10 form one run of 3 tiles
    f = obstacles.nearest_face([(448, col)], 400, 208, 24)
    assert f.w_px == 48.0


def test_obstacle_motion_is_only_mario_motion():
    tr = S.face_trace(S.GEOMETRIES["pipe_32x32"], 3.0, 318, 80)
    still = S.face_trace(S.GEOMETRIES["pipe_32x32"], 0.0, 318, 40)
    assert all(r["dtheta"] == 0.0 for r in still[1:])                            # Mario not moving: theta constant, no expansion
    d = [r["d"] for r in tr]
    assert all(a - b == pytest.approx(3.0) for a, b in zip(d, d[1:]) if b is not None and b > 14)


# ---- pure: settings, library, scalars, source rules --------------------------------------------------------------------------
def test_obstacle_expansion_is_off_by_default_and_changes_no_recorded_stamp():
    assert SenseSettings().obstacle_expansion is False and SenseSettings.user_default().obstacle_expansion is False
    assert "obstacle_expansion" not in SenseSettings().to_dict() and "obstacle_expansion" not in SenseSettings.user_default().to_dict()
    on = SenseSettings(obstacle_expansion=True)
    assert on.to_dict()["obstacle_expansion"] is True and SenseSettings.from_dict(on.to_dict()) == on
    assert SenseSettings.from_dict({"pursuit_kinds": ["powerup"]}).obstacle_expansion is False


def test_experiments_use_obstacle_expansion_only_when_their_entry_lists_it():
    user = SenseSettings(("powerup",), 12.0, 0.4)
    for off in ("E0", "E1", "E3"):
        assert settings_for(off, user).obstacle_expansion is False and "expanding_obstacle" not in library.experiment(off).mechanisms
    for on in ("E2a", "B11"):
        assert settings_for(on, user).obstacle_expansion is True and "expanding_obstacle" in library.experiment(on).mechanisms
    assert settings_for("E2a", user) == SenseSettings((), 12.0, 0.4, True)       # looming + landmark + obstacle, no pursuit
    e = library.experiment("E2a")
    assert e.status == "runnable" and e.runner == "brain.e2a" and e.scene == scenes.E2A_SCENE_ID
    m = library.mechanism("expanding_obstacle")
    assert m.status == "built" and "Mario's-eye-view assumption" in m.evidence and "no source for obstacle-triggered jumps" in m.evidence
    assert ObstacleExpansion.label.startswith("looming from static obstacles (biology: expansion cue; no source for obstacle-triggered jumps")


def test_the_mechanism_names_only_the_looming_populations_and_the_policy_adds_no_other_path():
    assert ObstacleExpansion.populations == LoomingMechanism.populations == ("LC4", "LPLC2")
    for name in ("obstacles.py", "mechanisms.py"):
        src = (BRAIN_DIR / name).read_text(encoding="utf-8")
        assert "_current" not in src and ".h[" not in src and "stimulate(" not in src, name
    src = (BRAIN_DIR / "obstacles.py").read_text(encoding="utf-8")
    assert not re.search(r"ram\[[^\]]*\]\s*=[^=]", src)                                  # reads RAM only, never writes it


def test_e2a_scalars_are_registered_and_the_encoding_adds_none():
    from brain import scalars
    rows = {s.name: s for s in scalars.all_scalars()}
    assert {"E2A_MAX_FRAMES", "E2A_SCENE_WALK_FRAMES", "E2A_SCENE_SETTLE_FRAMES", "E2A_PIPE_RIGHT_X"} <= set(rows)
    assert rows["E2A_MAX_FRAMES"].kind == scalars.INVENTED and rows["E2A_PIPE_RIGHT_X"].kind == scalars.MEASURED
    assert not [n for n in rows if "OBSTACLE" in n]                                # no scalar of the encoding itself
    assert scalars.DOC_PATH.read_text(encoding="utf-8") == scalars.generate()


# ---- pure: arms, metrics, episode source ---------------------------------------------------------------------------------------
def test_arms_and_the_necessity_arm_drops_only_obstacle_expansion():
    used = settings_for("E2a")
    assert e2a.arm_settings("real", used) == used and e2a.arm_settings("shuffled", used) == used
    no = e2a.arm_settings("real_no_obstacle", used)
    assert no.obstacle_expansion is False and no.goal_cue_salience == used.goal_cue_salience and no.pursuit_kinds == used.pursuit_kinds
    assert e2a.arm_of("real_no_obstacle", None) == "real_no_obstacle"
    for bad in (("shuffled", None), ("real", 1), ("real_no_obstacle", 3), ("bogus", None)):
        with pytest.raises(ValueError):
            e2a.arm_of(*bad)


def test_e2a_module_writes_no_ram_and_presses_nothing():
    src = (BRAIN_DIR / "e2a.py").read_text(encoding="utf-8")
    assert not re.search(r"ram\[[^\]]*\]\s*=[^=]", src)
    assert "action_from_buttons" not in src and "env.step(action)" in src          # only the policy's action is stepped
    assert e2a.CRITERION == {"real_cleared_min": 14, "shuffled_cleared_max": 2, "no_obstacle_cleared_max": 2, "n": 20}
    assert e2a.E2A_SEED0 == 7100 and e2a.E2A_PIPE_RIGHT_X == 479 and e2a.PIPE1_X == 448


def _fake(arm, outcome, **kw):
    base = dict(experiment="E2a", arm=arm, seed=1, shuffle_seed=None, cleared=outcome == "cleared", outcome=outcome,
                died=outcome == "died", frames=100, cleared_frame=90 if outcome == "cleared" else None, max_x=500, gf_fired=True,
                first_gf_frame=40, gf_before_face=True, first_gf_x=400, theta_at_gf_deg=44.0, d_at_gf_px=40.0, gf_output_max_hz=12.0,
                ttmn_max_hz=0.3, a_pressed=True, a_frames=5, first_a_frame=45, first_a_x=410, first_a_run=3, tap=False,
                takeoff_frame=46, takeoff_x=411, left_frames=0, right_frames=80, b_frames=70)
    base.update(kw)
    return e2a.E2aResult(**base)


def test_summary_counts_cleared_ends_taps_and_gf_before_the_face():
    rs = [_fake("real", "cleared"), _fake("real", "cleared", first_a_run=1, tap=True), _fake("real", "stuck", gf_before_face=False),
          _fake("real", "died", a_pressed=False, first_a_run=None, first_a_x=None, takeoff_x=None, takeoff_frame=None)]
    s = e2a.summarize(rs)
    assert s["cleared"] == 2 and s["n"] == 4 and s["end_reasons"] == {"cleared": 2, "died": 1, "stuck": 1, "timeout": 0}
    assert s["gf_before_face"] == 3 and s["a_pressed_runs"] == 3 and s["tap_episodes"] == 1 and s["tap_fraction"] == pytest.approx(1 / 3)
    assert s["frames_to_clear"] == {"n": 2, "median": 90.0} and s["takeoff_runs"] == 3


# ---- emulator: the scene and the flat start ----------------------------------------------------------------------------------------
def _scene_ram():
    from mario.emulator.env import make_env
    spec = scenes.load_scene(scenes.E2A_SCENE_ID)
    env = make_env(spec.level)
    scenes.build_scene(env, spec)
    return spec, env.unwrapped.ram


def test_the_e2a_scene_matches_its_manifest_and_the_pipe_is_a_32_px_face():
    spec, ram = _scene_ram()
    assert spec.experiment == "E2a" and spec.rules == ("clear_enemies",) and spec.n_frames == 205
    c = scenes.check_e2a_scene(ram)
    assert c["face_on_screen"] and c["mario_stationary"] and c["no_enemy"]
    assert c["face_w_px"] == 32.0 and c["face_dx_px"] == 448 - (int(ram[0x6D]) * 256 + int(ram[0x86]))
    _, ram2 = _scene_ram()
    assert bytes(ram[:0x800]) == bytes(ram2[:0x800])                                # deterministic


def test_flat_start_of_level_gives_no_obstacle_stimulus_until_the_pipe_is_drawn():
    from mario.actions.actions import action_from_buttons
    from mario.emulator.env import make_env
    env = make_env("1-1")
    env.reset()
    ram = env.unwrapped.ram
    run = action_from_buttons(right=True, b=True)
    prev = {"L": 0.0, "R": 0.0}
    first_seen = None
    for f in range(140):
        env.step(run)
        for s in range(5):
            ram[0x0F + s] = 0                                                       # the test removes the Goomba, as the scene rule does
        theta, _, dist = obstacles.obstacle_thetas(ram, prev, ELEVATION_LIMIT_DEG)
        x = int(ram[0x6D]) * 256 + int(ram[0x86])
        if theta["L"] == 0.0:
            assert dist["L"] is None
            assert first_seen is None
        elif first_seen is None:
            first_seen = x
            assert dist["L"] == 448 - x                                             # the first obstacle ever seen is pipe 1
        prev = theta
    assert first_seen is not None and 300 <= first_seen <= 320                     # drawn once the screen scrolls it in (x > 303)


# ---- network: synthetic checks (docs/SPEC_e2a.md section 2 (ii), (iii)) ------------------------------------------------------------
@needs_net
@needs_cal
def test_flat_ground_stimulus_is_nothing_and_attaching_the_mechanism_changes_no_readout(net, cal):
    """Zero obstacle drive adds exactly zero current: with the mechanism attached the run is bit-identical to without it."""
    loom, z = None, {"L": 0.0, "R": 0.0}
    runs = []
    for attach in (False, True):
        brain_ = Brain(net, cal, seed=5)
        mech = ObstacleExpansion(net)
        if attach:
            brain_.attach(mech)
        loom = LoomingMechanism(net)
        trace = []
        for f in range(60):
            brain_.apply(loom.encode({"L": 0.02 * f, "R": 0.02 * f}, {"L": 0.02, "R": 0.02}))
            if attach:
                brain_.apply(mech.encode(z, z))
            r = brain_.step_frame()
            trace.append((r.gf_membrane, r.gf_spiked, r.pooled("TTMn"), r.pooled("DNp09")))
        runs.append(trace)
    assert runs[0] == runs[1]


@needs_net
@needs_cal
def test_disc_still_fires_the_gf_at_38_to_48_deg_with_obstacle_expansion_and_the_landmark_on(net, cal):
    for lv in (10, 20, 40, 80):
        ang = S.run_disc_with_obstacle(net, cal, lv, landmark=True, seed=7000)
        assert ang is not None and 38.0 <= ang <= 48.0, (lv, ang)


@needs_net
@needs_cal
def test_rest_is_silent_with_the_mechanism_attached(net, cal):
    assert S.rest_gf_spikes(net, cal, 600, seed=3) == 0
    assert S.rest_gf_spikes(net, cal, 600, seed=3, landmark=True) == 0


@needs_net
@needs_cal
def test_stimulus_ids_are_only_looming_neurons_and_brain_refuses_anything_else(net, cal):
    from brain.brain import StimulusError
    mech = ObstacleExpansion(net)
    st = mech.encode({"L": 0.5, "R": 0.5}, {"L": 0.1, "R": 0.1})
    b = Brain(net, cal)
    allowed = np.concatenate([net.ids[net.pops["LC4"]], net.ids[net.pops["LPLC2"]]])
    assert np.isin(st.body_ids, allowed).all() and st.source == "obstacle_expansion"
    b.apply(st)
    with pytest.raises(StimulusError):
        b.stimulate(net.ids[net.pops["GF"]], 1.0)


@needs_net
@needs_cal
def test_the_pipe_approach_runs_through_the_synthetic_bench(net, cal):
    """Smoke of the bench itself (numbers are reported by audit/e2a_synth.py, not asserted here): it returns a coherent record."""
    tr = S.face_trace(S.GEOMETRIES["pipe_32x32"], S.RUN_PX_PER_FRAME, 318, 70)
    r = S.run_approach(net, cal, tr, landmark=False, seed=9100)
    assert r.max_theta_deg > 40.0 and len(tr) == 70
    if r.first_gf_frame is not None:
        assert r.px_before_stall_at_gf == S.STALL_X - r.x_at_gf
