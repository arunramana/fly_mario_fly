# What this file does, in plain English:
# Tests Phase 3: LC10a in the network, the two sensed mechanisms (pursuit of small
# moving objects and the home landmark), the arousal gain, the class-preserving
# shuffle, the E0 and E3 scenes and metrics, and the synthetic checks that must
# hold before any game scene: an approaching object still fires the Giant Fiber
# at 38-48 degrees with the new senses on, and nothing latches at rest. Nothing
# here checks whether the fly wins a game scene.
"""docs/SPEC_phase3.md section 7. Pure tests need no data; network tests use the cached Phase 3 network and skip with a reason
when it has not been built; emulator tests need nes-py."""
from __future__ import annotations

import inspect
import re
from pathlib import Path

import numpy as np
import pytest

import brain.mechanisms as mech_module

import brain
from brain import builder, calibration as C, goal_eval, library, scenes, senses_calibrate as sc
from brain.brain import Brain, StimulusError
from brain.calibration import CALIBRATION_FILE, Calibration
from brain.manifest import Manifest, SENSORY
from brain.mechanisms import HomeLandmarkMechanism, PursuitMechanism, TargetMechanism, azimuth_shares
from brain.motor_map import MotorMap
from brain.settings import PURSUABLE_KINDS, SenseSettings, settings_for

BRAIN_DIR = Path(brain.__file__).parent
needs_net = pytest.mark.skipif(not builder.default_path().exists(), reason="Phase 3 network not built (python -m brain.builder)")
needs_cal = pytest.mark.skipif(not CALIBRATION_FILE.exists(), reason="brain/calibration.json missing")


@pytest.fixture(scope="module")
def net():
    return builder.BuiltNetwork.load(builder.default_path())


@pytest.fixture(scope="module")
def cal():
    return Calibration.load()


# ---- pure: mechanisms, settings, window rules ----------------------------------------------------------------------------
def test_azimuth_split_is_same_side_and_saturates():
    assert azimuth_shares(0.0, 45.0) == (0.5, 0.5)
    assert azimuth_shares(45.0, 45.0) == (0.0, 1.0) and azimuth_shares(-45.0, 45.0) == (1.0, 0.0)
    assert azimuth_shares(90.0, 90.0) == (0.0, 1.0)
    left, right = azimuth_shares(45.0, 90.0)
    assert right > 0.5 > left and left + right == pytest.approx(1.0)       # right of Mario -> right eye
    assert azimuth_shares(-200.0, 30.0) == (1.0, 0.0)


def test_arousal_is_a_tool_setting_in_zero_to_one_and_nothing_reads_the_fly_for_it():
    d = SenseSettings.user_default()
    assert d.pursuit_arousal == C.PURSUIT_AROUSAL == 0.65 and 0.0 <= d.pursuit_arousal <= 1.0
    assert SenseSettings.from_dict({"pursuit_kinds": ["powerup"]}).pursuit_arousal == C.PURSUIT_AROUSAL
    assert SenseSettings.from_dict(SenseSettings(("powerup",), 1.0, 0.3).to_dict()).pursuit_arousal == 0.3
    for bad in (-0.1, 1.1):
        with pytest.raises(ValueError):
            SenseSettings(("powerup",), 0.0, bad)
    assert not hasattr(mech_module, "arousal")                    # the DNp09-feedback helper is gone
    for name in ("mechanisms.py", "policy.py", "settings.py"):
        src = (BRAIN_DIR / name).read_text(encoding="utf-8")
        assert "pooled(" not in src and "last_readout.pooled" not in src and "walk_threshold" not in src, name


def test_sense_settings_validate_and_default_to_a_collectible_not_a_goomba():
    d = SenseSettings.user_default()
    assert d.pursuit_kinds == ("powerup",) and "goomba" not in d.pursuit_kinds and d.goal_cue_salience == C.GOAL_CUE_SALIENCE
    assert SenseSettings.from_dict(d.to_dict()) == d
    assert SenseSettings.from_dict(None) == SenseSettings() and not SenseSettings.from_dict(None).pursuit_kinds
    with pytest.raises(ValueError):
        SenseSettings(("mushroom",))
    with pytest.raises(ValueError):
        SenseSettings((), -1.0)
    assert set(PURSUABLE_KINDS) == {"goomba", "koopa", "enemy", "powerup"}


def test_an_experiment_runs_only_the_mechanisms_its_library_entry_lists():
    user = SenseSettings(("powerup", "goomba"), 12.0, 0.4)
    assert settings_for("E1", user) == SenseSettings((), 0.0, 0.4)                       # looming only, as Phase 2
    assert settings_for("E0", user) == SenseSettings((), 12.0, 0.4)                      # landmark only
    assert settings_for("E3", user) == SenseSettings(("powerup", "goomba"), 0.0, 0.4)    # pursuit only, no landmark
    assert library.experiment("E3").mechanisms == ("pursuit",) and library.experiment("E0").mechanisms == ("goal_direction",)


def test_window_and_value_rules_on_made_up_sweeps():
    ok = {1: False, 2: False, 3: True, 4: True, 5: True, 6: False, 8: True}      # a later pass is not contiguous: ignored
    assert sc.window(ok) == (3, 5) and sc.window({1: False, 2: False}) is None
    assert sc.sig2(16.4567) == 16 and sc.sig2(0.0123456) == 0.012
    grid = (1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40)
    w = {t: {e: 3 <= e <= 25 for e in grid} for t in "RLC"}
    w["B"] = {e: 5 <= e <= 25 for e in grid}
    v = sc.derive_values(w, 0.38)
    assert v["goal_window"] == (5, 25) and v["GOAL_CUE_SALIENCE"] == 15
    assert v["gain_interval"][0] == pytest.approx(3 / 0.38) and v["LC10A_GAIN"] == sc.sig2((3 / 0.38 + 25) / 2)
    empty = sc.derive_values({t: {e: 3 <= e <= 5 for e in grid} for t in "RLCB"}, 0.38)     # 3 / 0.38 = 7.9 > 5: no gain exists
    assert empty["LC10A_GAIN"] is None                                                       # the build stops and reports


def test_arousal_default_is_the_midpoint_of_the_passing_window_of_the_grid():
    ok = {a: 0.3 <= a <= 1.0 for a in sc.AROUSAL_GRID}
    assert sc.derive_arousal(ok) == 0.65 == C.PURSUIT_AROUSAL
    assert sc.derive_arousal({a: False for a in sc.AROUSAL_GRID}) is None           # empty window: the build stops and reports


def test_the_three_phase3_scalars_are_registered_invented_and_counted():
    from brain import scalars
    rows = {s.name: s for s in scalars.all_scalars()}
    for name in ("LC10A_GAIN", "LC10A_AZIMUTH_SPLIT", "GOAL_CUE_SALIENCE", "PURSUIT_AROUSAL"):
        assert rows[name].kind == scalars.INVENTED
    assert rows["GOAL_CUE_SALIENCE"].value == C.GOAL_CUE_SALIENCE == 15.0
    assert {"E0_GOAL_X", "E0_MAX_FRAMES", "E3_MAX_FRAMES"} <= set(rows)
    assert scalars.DOC_PATH.read_text(encoding="utf-8") == scalars.generate()


def test_mechanisms_name_only_lc10a_and_never_write_current():
    for cls in (PursuitMechanism, HomeLandmarkMechanism, TargetMechanism):
        assert cls.populations == ("LC10a",)
    src = (BRAIN_DIR / "mechanisms.py").read_text(encoding="utf-8")
    assert "_current" not in src and ".h[" not in src
    public = {n for n, _ in inspect.getmembers(Brain, callable) if not n.startswith("_")}
    assert public == {"attach", "apply", "stimulate", "reset", "step_frame", "stamp", "population_rate"}   # nothing added for Phase 3


# ---- pure: class-preserving shuffle ---------------------------------------------------------------------------------------
def _toy_net():
    # populations: 0-1 sensory "S", 2-3 output "O", 4-7 interior
    n = 8
    pre = np.array([0, 1, 0, 1, 4, 5, 6, 7, 4, 5, 6, 7, 2, 3])
    post = np.array([4, 5, 6, 7, 2, 2, 3, 3, 5, 6, 7, 4, 4, 5])
    return builder.BuiltNetwork(ids=np.arange(100, 100 + n), side=np.array(list("LRLRLRLR")),
                                signs=np.array([1, 1, -1, 1, 1, -1, 1, 1.0]), pops={"S": np.array([0, 1]), "O": np.array([2, 3])},
                                pre=pre, post=post, syn=np.full(len(pre), 6), total_in=np.full(n, 30.0), rule={"toy": True})


def test_class_shuffle_keeps_tier_groups_degrees_and_signs():
    t = _toy_net()
    g = t.tier_groups()
    for seed in (1, 2, 3):
        s = t.shuffled(seed, "class")
        assert s.twin_of["mode"] == "class" and (s.pre == t.pre).all() and (s.signs == t.signs).all()
        assert (g[s.post] == g[t.post]).all()                                    # every edge keeps the tier group of its target
        assert (np.bincount(s.post, minlength=8) == np.bincount(t.post, minlength=8)).all()      # in-degree per neuron
        assert (np.bincount(s.pre, minlength=8) == np.bincount(t.pre, minlength=8)).all()
    assert any((t.shuffled(k, "class").post != t.post).any() for k in range(1, 6))       # it does rewire
    assert t.shuffled(1, "degree").twin_of["mode"] == "degree"
    with pytest.raises(ValueError):
        t.shuffled(1, "bogus")


# ---- pure: pursuit perception on synthetic RAM -----------------------------------------------------------------------------
def _ram(mario_x=100, slot=5, kind=0x2E, dx=40, ybyte=184, page=0):
    ram = np.zeros(2048, dtype=np.uint8)
    ram[0x86], ram[0x6D], ram[0x4AF], ram[0x756] = mario_x, page, 208, 0
    ram[0x0F + slot], ram[0x16 + slot], ram[0x6E + slot], ram[0x87 + slot], ram[0xCF + slot] = 1, kind, page, mario_x + dx, ybyte
    return ram


def _target(ram, prev, kinds=("powerup",)):
    from bridge.perception import VisibleRegistry
    from brain.perception import pursuit_target
    from mario.entities.registry import DEFAULT
    return pursuit_target(ram, prev, VisibleRegistry(DEFAULT), set(kinds), C.ELEVATION_LIMIT_DEG)


def test_pursuit_needs_a_moving_object_of_a_pursued_kind_and_sees_the_powerup_slot():
    t0, pos0 = _target(_ram(dx=40), {})
    assert t0 is None and 5 in pos0                                              # first sight: nothing to track; slot 5 is read
    t1, pos1 = _target(_ram(dx=41), pos0)                                        # moved by 1 px relative to the background
    assert t1 is not None and t1.kind == "powerup" and t1.slot == 5 and t1.dx_px == 41 and t1.azimuth_deg == 0.0
    t2, _ = _target(_ram(dx=41), pos1)
    assert t2 is None                                                            # now static: a static object drives nothing
    behind, _ = _target(_ram(dx=-39), _target(_ram(dx=-40), {})[1])
    assert behind is not None and behind.dx_px < 0 and behind.azimuth_deg == 0.0  # step 2 (5c): no dx -> azimuth ramp, symmetric


def test_a_goomba_is_not_pursued_unless_its_kind_is_chosen():
    g0 = _target(_ram(slot=1, kind=6, dx=60), {}, ("powerup",))[1]
    assert _target(_ram(slot=1, kind=6, dx=61), g0, ("powerup",))[0] is None
    pursued = _target(_ram(slot=1, kind=6, dx=61), g0, ("powerup", "goomba"))[0]
    assert pursued is not None and pursued.kind == "goomba"


def test_an_object_far_above_leaves_the_field_and_the_nearest_wins():
    far_up = _target(_ram(dx=30, ybyte=40), _target(_ram(dx=29, ybyte=40), {})[1])[0]
    assert far_up is None                                                        # elevation beyond the field: salience 0
    a = _ram(dx=80)
    a[0x0F + 2], a[0x16 + 2], a[0x6E + 2], a[0x87 + 2], a[0xCF + 2] = 1, 0x2E, 0, 100 + 20, 184
    prev = _target(a, {})[1]
    a[0x87 + 5] += 1
    a[0x87 + 2] += 1
    best = _target(a, prev)[0]
    assert best.slot == 2 and best.dx_px == 21


# ---- pure: scenes and metrics ----------------------------------------------------------------------------------------------
def test_scene_rules_clear_enemies_but_keep_the_powerup():
    spec = scenes.load_scene(scenes.E3_SCENE_ID)
    ram = _ram(dx=40)
    ram[0x0F], ram[0x16] = 1, 6                                                  # a Goomba in slot 0
    scenes.apply_rules(ram, spec)
    assert ram[0x0F] == 0 and ram[0x0F + 5] == 1
    with pytest.raises(ValueError):
        scenes.apply_rules(ram, scenes.SceneSpec("x", "E?", "1-1", "", (), "", ("bogus",)))


def test_e0_e3_defaults_arms_and_criteria():
    assert goal_eval.E0_SEED0 == 4000 and goal_eval.E3_SEED0 == 5100 and goal_eval.N == 20
    banned = set(range(1000, 1020)) | set(range(2000, 2020)) | set(range(3000, 3020)) | set(range(5000, 5020)) | {9000, 9100}
    for s0 in (goal_eval.E0_SEED0, goal_eval.E3_SEED0):
        assert not banned & set(range(s0, s0 + goal_eval.N))
    assert goal_eval.CRITERIA["E0"]["real_reached_min"] == 18 and goal_eval.CRITERIA["E3"]["real_reached_min"] == 14
    assert goal_eval.ARMS == ("real", "shuffled", "shuffled_class")
    # routine defaults omit the degree shuffle (docs/SPEC_fast_iteration.md); the flag restores the full set
    assert goal_eval.default_arms("E0") == ("real", "shuffled_class", "real_no_landmark")
    assert goal_eval.default_arms("E3") == ("real", "shuffled_class", "real_no_pursuit")
    assert goal_eval.default_arms("E0", with_degree_shuffle=True) == goal_eval.ARMS + ("real_no_landmark",)
    assert goal_eval.arm_of("real_no_landmark", None, "E0") == "real_no_landmark"
    for bad in (("real_no_landmark", None, "E3"), ("real_no_pursuit", None, "E0"), ("real_no_pursuit", 1, "E3")):
        with pytest.raises(ValueError):
            goal_eval.arm_of(*bad)
    used = SenseSettings(("powerup",), 15.0, 0.5)
    assert goal_eval.arm_settings("E0", "real_no_landmark", used) == SenseSettings(("powerup",), 0.0, 0.5)
    assert goal_eval.arm_settings("E3", "real_no_pursuit", used) == SenseSettings((), 15.0, 0.5)
    assert goal_eval.arm_settings("E0", "real", used) == used
    assert goal_eval.arm_of("real", None) == "real" and goal_eval.arm_of("shuffled_class", 3) == "shuffled_class"
    for bad in (("real", 1), ("shuffled", None), ("lesion_gf", None)):
        with pytest.raises(ValueError):
            goal_eval.arm_of(*bad)
    from brain import e1
    assert e1.ARMS == ("real", "shuffled", "lesion_gf") and "shuffled_class" in e1.ARM_CHOICES   # an extra arm of E1, not a default


def test_goal_summary_counts_and_stores_the_gf_and_ttmn_fields():
    def r(reached, gf, out, ttmn, frame=100):
        return goal_eval.GoalResult("E0", "real", 0, None, reached, "reached" if reached else "timeout", False, 600, frame if reached else None,
                                    400 if reached else 40, gf, 50 if gf else None, out, ttmn, False, 0, 3, 100, 100)
    s = goal_eval.summarize([r(True, False, 0.0, 0.01, 120), r(True, True, 6.0, 0.08, 140), r(False, False, 0.0, 0.0)])
    assert (s["n"], s["reached"], s["gf_fired"]) == (3, 2, 1)
    assert s["gf_output_max_hz"] == 6.0 and s["ttmn_max_hz"] == 0.08 and s["frames_to_reach"]["median"] == 130.0
    assert 0.0 <= s["reached_ci"][0] < 2 / 3 < s["reached_ci"][1] <= 1.0
    assert {"gf_output_max_hz", "ttmn_max_hz", "gf_fired"} <= {f for f in goal_eval.GoalResult.__dataclass_fields__} | {"gf_fired"}


def test_the_docs_no_longer_say_the_shuffled_arm_walks_left_under_noise():
    root = BRAIN_DIR.parent
    for name in ("docs/SPEC_tool_phase2.md", "docs/NOTE_e1_shuffled_contact_spread.md", "brain/e1.py", "brain/scalars.py"):
        text = (root / name).read_text(encoding="utf-8")
        assert "retreats Left under noise" not in text and "noise-driven Left" not in text, name
        assert "looming-driven" in text, name


# ---- emulator: scenes are deterministic and a passive Mario fails both ----------------------------------------------------
def _ram_after(scene_id):
    from mario.emulator.env import make_env
    spec = scenes.load_scene(scene_id)
    env = make_env(spec.level)
    scenes.build_scene(env, spec)
    ram = np.array(env.unwrapped.ram, copy=True)
    env.close()
    return spec, ram


def test_e0_and_e3_scenes_are_deterministic_and_match_their_manifests():
    s0a, r0a = _ram_after(scenes.E0_SCENE_ID)
    _, r0b = _ram_after(scenes.E0_SCENE_ID)
    assert np.array_equal(r0a, r0b) and s0a.n_frames == 0 and s0a.rules == ("clear_enemies",)
    spec, r3a = _ram_after(scenes.E3_SCENE_ID)
    _, r3b = _ram_after(scenes.E3_SCENE_ID)
    assert np.array_equal(r3a, r3b)
    c = scenes.check_e3_scene(r3a)
    assert c["powerup_on_screen"] and c["powerup_ahead"] and c["mario_stationary"] and c["no_enemy"]
    assert spec.n_frames == 165 + 45 + 14 + 60 and spec.experiment == "E3"


def test_a_passive_mario_does_not_reach_the_goal_or_the_mushroom_in_time():
    """The scenes must not be passable by pressing nothing (a property of the game, not of the fly)."""
    from brain.e1 import _vertical_gap, is_contact
    from mario.emulator.env import make_env
    from mario.ram.addresses import ADDR_ENEMY_ACTIVE, ADDR_ENEMY_PAGE, ADDR_ENEMY_X, ADDR_MARIO_PAGE, ADDR_MARIO_X
    from mario.actions.actions import action_from_buttons
    idle = action_from_buttons(right=False, left=False, down=False, up=False, a=False, b=False)
    for exp in ("E0", "E3"):
        spec = scenes.load_scene(goal_eval.SCENES[exp])
        env = make_env(spec.level)
        scenes.build_scene(env, spec)
        ram = env.unwrapped.ram
        reached = False
        for _ in range(goal_eval.MAX_FRAMES[exp]):
            env.step(idle)
            scenes.apply_rules(ram, spec)
            mx = int(ram[ADDR_MARIO_PAGE]) * 256 + int(ram[ADDR_MARIO_X])
            if exp == "E0":
                reached |= mx >= goal_eval.E0_GOAL_X
            else:
                for slot in scenes.powerup_slots(ram):
                    dx = int(ram[ADDR_ENEMY_PAGE + slot]) * 256 + int(ram[ADDR_ENEMY_X + slot]) - mx
                    vgap, h = _vertical_gap(ram, slot)
                    reached |= is_contact(True, dx, vgap, h)
        env.close()
        assert not reached, exp


# ---- network: LC10a, policy wiring ------------------------------------------------------------------------------------------
@needs_net
def test_lc10a_is_a_sensory_population_with_both_sides_in_the_new_network(net):
    assert "LC10a" in Manifest().names(SENSORY)
    idx = net.pops["LC10a"]
    assert len(idx) == 275 and (net.side[idx] == "L").sum() == 135 and (net.side[idx] == "R").sum() == 140
    assert net.rule["counts"]["neurons"] == net.n_neurons == 16464
    assert any(s["name"] == "LC10a->outputs" for s in net.rule["segments"])
    assert net.edge_report()["nonzero_weights"] == net.n_edges == 612566


@needs_net
@needs_cal
def test_calibration_belongs_to_the_new_network(net, cal):
    assert cal.network_hash == net.build_hash()


@needs_net
@needs_cal
def test_lc10a_stimulus_is_accepted_and_a_deeper_neuron_is_refused(net, cal):
    b = Brain(net, cal)
    mech = HomeLandmarkMechanism(net)
    b.apply(mech.encode())
    right = net.local(net.ids[net.pops["LC10a"][net.side[net.pops["LC10a"]] == "R"]])
    assert set(np.flatnonzero(b._current)) == set(right) and (b._current[right] == C.GOAL_CUE_SALIENCE).all()
    with pytest.raises(StimulusError):
        b.stimulate([net.ids[net.pops["GF"][0]]], [1.0])
    with pytest.raises(StimulusError):
        b.stimulate([net.ids[net.pops["KC"][0]]], [1.0])


@needs_net
@needs_cal
def test_policy_attaches_mechanisms_by_settings_and_shuffled_arms_get_the_same_cue(net, cal):
    from brain.policy import BrainPolicy
    assert BrainPolicy(network=net, calibration=cal).stamp()["mechanisms"] == ["looming"]
    s = SenseSettings(("powerup",), 15.0)
    real = BrainPolicy(network=net, calibration=cal, settings=s)
    twin = BrainPolicy(network=net, calibration=cal, settings=s, shuffle_seed=1, shuffle_mode="class")
    assert real.stamp()["mechanisms"] == twin.stamp()["mechanisms"] == ["looming", "pursuit", "home_landmark"]
    assert real.landmark.salience == twin.landmark.salience == 15.0
    assert twin.stamp()["shuffled"]["mode"] == "class" and real.stamp()["senses"] == s.to_dict()


@needs_net
@needs_cal
def test_pursuit_drive_scales_with_the_arousal_state_and_is_zero_at_zero_arousal(net, cal):
    p = PursuitMechanism(net)
    assert not p.encode(30.0, 1.0, 0.0).values.any()
    lo, hi = p.encode(30.0, 1.0, 0.4).values.max(), p.encode(30.0, 1.0, 1.0).values.max()
    assert hi == pytest.approx(C.LC10A_GAIN * azimuth_shares(30.0, C.LC10A_AZIMUTH_SPLIT)[1]) and lo == pytest.approx(0.4 * hi)


# ---- network: synthetic checks BEFORE any game scene (SPEC section 7) -------------------------------------------------------
def _disc_with(brain, mech, extra, lv):
    """The looming disc with `extra` (a callable returning a Stimulus or None) added every frame through Brain.apply."""
    import math
    from bridge.loom_disc import FRAME_MS, THETA0_DEG
    tau0 = lv / math.tan(math.radians(THETA0_DEG) / 2.0)
    brain.reset(0)
    prev, fired = 0.0, None
    for f in range(int(tau0 / FRAME_MS) + 3):
        tau = tau0 - f * FRAME_MS
        if tau <= 0:
            break
        th = 2.0 * math.atan(lv / tau)
        dth, prev = th - prev, th
        brain.apply(mech.encode({"L": th, "R": th}, {"L": dth, "R": dth}))
        st = extra(th)
        for one in (st if isinstance(st, list) else [st]):
            if one is not None:
                brain.apply(one)
        r = brain.step_frame()
        if r.gf_spiked and fired is None:
            fired = math.degrees(th)
    return fired


@needs_net
@needs_cal
def test_an_approaching_object_still_fires_the_gf_at_38_to_48_deg_with_the_landmark_on(net, cal):
    from brain.mechanisms import LoomingMechanism
    brain_ = Brain(net, cal)
    land = HomeLandmarkMechanism(net)
    angles = [_disc_with(brain_, LoomingMechanism(net), lambda th: land.encode(), lv) for lv in (10, 20, 40, 80)]
    assert all(a is not None and 38.0 <= a <= 48.0 for a in angles), angles
    assert max(angles) - min(angles) <= 8.0, angles


@needs_net
@needs_cal
def test_an_approaching_object_still_fires_the_gf_at_38_to_48_deg_with_pursuit_on_even_if_the_goomba_is_pursued(net, cal):
    """Worst case: the approaching object is itself a pursued, moving target dead ahead, with the landmark on as well, at the
    default arousal and at the maximum 1.0 (SPEC section 11)."""
    from brain.mechanisms import LoomingMechanism
    brain_ = Brain(net, cal)
    land, pur = HomeLandmarkMechanism(net), PursuitMechanism(net)
    angles = [_disc_with(brain_, LoomingMechanism(net), lambda th: [pur.encode(0.0, 1.0, 1.0), land.encode()], lv) for lv in (10, 20, 40, 80)]
    both = [_disc_with(brain_, LoomingMechanism(net), lambda th: [pur.encode(0.0, 1.0, C.PURSUIT_AROUSAL), land.encode()], lv)
            for lv in (10, 20, 40, 80)]
    assert all(a is not None and 38.0 <= a <= 48.0 for a in angles + both), (angles, both)
    assert max(angles) - min(angles) <= 8.0 and max(both) - min(both) <= 8.0, (angles, both)


@needs_net
@needs_cal
def test_nothing_latches_at_rest_with_the_mechanisms_attached_and_no_cue(net, cal):
    """No stimulus: no GF spike and no button press of any kind over a long rest, several seeds; and after a cue is removed
    nothing stays pressed."""
    brain_ = Brain(net, cal)
    mm = MotorMap(cal.motor)
    for seed in (9500, 9501, 9502):
        brain_.reset(seed)
        mm.reset()
        presses = spikes = 0
        for f in range(2000):
            r = brain_.step_frame()
            spikes += int(r.gf_spiked)
            b = mm.read(r)
            presses += int(f >= 100 and (b.a or b.b or b.right or b.left or b.down or b.up))
        assert spikes == 0 and presses == 0, (seed, spikes, presses)
    land, pur = HomeLandmarkMechanism(net), PursuitMechanism(net)
    brain_.reset(9510)
    mm.reset()
    for f in range(100):
        brain_.apply(land.encode())
        brain_.apply(pur.encode(-60.0, 1.0, 1.0))
        brain_.step_frame()
    late = []
    for f in range(200):
        b = mm.read(brain_.step_frame())
        late.append(f >= 40 and (b.b or b.right or b.left))
    assert not any(late)                                                          # the cue is gone: no walking or steering


@needs_net
@needs_cal
def test_landmark_alone_walks_right_and_a_dot_steers_to_its_side_and_a_static_dot_does_nothing(net, cal):
    from brain.senses_calibrate import hold
    brain_ = Brain(net, cal)
    tm = TargetMechanism(net)
    goal = [hold(brain_, tm, 0.0, C.GOAL_CUE_SALIENCE, s) for s in (9520, 9521)]
    assert all(h.right >= 0.9 and h.b >= 0.9 and h.left <= 0.05 and h.gf == 0 for h in goal)
    pur = PursuitMechanism(net)
    for az, side in ((60.0, "R"), (-60.0, "L")):
        left, right = azimuth_shares(az, pur.split_deg)
        k = pur.gain
        holds = [hold(brain_, tm, k * left, k * right, s) for s in (9520, 9521)]
        assert sc.passes(side, holds), (az, holds)
    quiet = [hold(brain_, tm, 0.0, 0.0, s) for s in (9520, 9521)]                # a static object: no stimulus
    assert all(h.right == 0 and h.left == 0 and h.b == 0 and h.gf == 0 for h in quiet)
