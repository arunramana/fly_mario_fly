# What this file does, in plain English:
# Tests experiment E1 ("jump the Goomba") and its scene: the saved action log
# builds the same scene every time (a Goomba on screen ahead of a standing
# Mario), the survival and contact rules behave on made-up numbers, an episode
# records what it should, and the experiment/mechanism library is complete and
# honest about where each input enters the brain. None of it checks whether the
# fly wins.
"""docs/SPEC_tool_phase2.md section 8. Emulator tests need nes-py; episode tests need the cached network and skip with a
reason when it has not been built."""
from __future__ import annotations

import math

import numpy as np
import pytest

from brain import builder, e1, library, scenes
from brain.calibration import CALIBRATION_FILE

needs_net = pytest.mark.skipif(not builder.default_path().exists(), reason="unified network not built (python -m brain.builder)")
needs_cal = pytest.mark.skipif(not CALIBRATION_FILE.exists(), reason="brain/calibration.json missing")


# ---- the scene -------------------------------------------------------------------------------------------------------
def test_scene_manifest_is_a_fixed_explicit_action_log():
    spec = scenes.load_scene()
    assert spec.level == "1-1" and spec.experiment == "E1"
    a = spec.actions()
    assert a.dtype == np.uint8 and len(a) == spec.n_frames == 110
    assert len(set(a[:60])) == 1 and len(set(a[60:])) == 1 and a[0] != a[-1]
    assert spec.hash() == scenes.load_scene().hash()


def _ram_after_scene():
    from mario.emulator.env import make_env
    spec = scenes.load_scene()
    env = make_env(spec.level)
    scenes.build_scene(env, spec)
    ram = np.array(env.unwrapped.ram, copy=True)
    env.close()
    return ram


def test_scene_replay_is_deterministic_and_matches_the_manifest():
    r1, r2 = _ram_after_scene(), _ram_after_scene()
    assert np.array_equal(r1, r2)
    c = scenes.check_scene(r1)
    assert c["goomba_on_screen"] and c["goomba_ahead"] and c["mario_stationary"]
    assert c["goomba_dx_px"] > e1.SPRITE_PX


# ---- the survival definition (made-up numbers, no game) ---------------------------------------------------------------
def test_contact_needs_horizontal_and_vertical_overlap_of_an_active_goomba():
    assert e1.is_contact(True, 10, 0.0, 16)
    assert not e1.is_contact(True, 16, 0.0, 16)           # exactly one sprite width apart: touching edges, no overlap
    assert not e1.is_contact(True, 5, 16.0, 16)           # Mario is over the Goomba (jumped): no contact
    assert not e1.is_contact(False, 0, 0.0, 16)           # an inactive slot is not a Goomba
    assert e1.is_contact(True, -15, 20.0, 32)             # big Mario is taller: more vertical overlap allowed


def test_resolution_is_passed_when_behind_mario_or_stomped_when_removed():
    assert e1.resolution(True, 40) is None and e1.resolution(True, -15) is None
    assert e1.resolution(True, -16) == "passed"
    assert e1.resolution(False, None) == "stomped"


def test_defaults_are_held_out_seeds_and_the_criterion_is_the_plans():
    assert e1.E1_SEED0 == 3000 and e1.E1_N == 20
    banned = set(range(1000, 1020)) | set(range(2000, 2020)) | {9000}
    assert not banned & set(range(e1.E1_SEED0, e1.E1_SEED0 + e1.E1_N))
    assert e1.CRITERION == {"real_survived_min": 16, "shuffled_survived_max": 2, "n": 20}


def test_summary_counts_and_intervals():
    def r(survived, gf, theta=None):
        return e1.E1Result("real", 0, None, survived, "passed" if survived else "died", not survived, 100, 90, None, gf, 80 if gf else None,
                           gf, theta, 21.0 if gf else None, gf, 2 if gf else 0, 226)
    s = e1.summarize([r(True, True, 41.0), r(False, True, 43.0), r(False, False)])
    assert (s["n"], s["survived"], s["deaths"], s["gf_before_contact"], s["a_pressed_runs"]) == (3, 1, 2, 2, 2)
    assert s["theta_at_gf_deg"]["median"] == pytest.approx(42.0)
    assert 0.0 <= s["survived_ci"][0] < 1 / 3 < s["survived_ci"][1] <= 1.0


# ---- an episode (real network) ---------------------------------------------------------------------------------------
@needs_net
@needs_cal
def test_one_episode_records_what_the_spec_says():
    seen = []
    res, rows, stamp = e1.run_e1_episode(9100, None, max_frames=200, record_rows=True,
                                         on_frame=lambda f, obs, row: seen.append(f))
    assert res.arm == "real" and res.frames == len(rows) == len(seen)
    assert stamp["experiment"] == "E1" and stamp["scene"]["id"] == scenes.E1_SCENE_ID and "build_hash" in stamp
    assert {"frame", "mario_x", "mario_sx", "mario_y", "theta", "d_px", "lc4", "lplc2", "mem", "spike", "ttmn", "dna01",
            "dna02", "dnp09", "press_a", "press_b", "action"} <= set(rows[0])
    assert res.gf_fired == (res.first_gf_frame is not None)
    if res.gf_fired:
        assert res.theta_at_gf_deg == pytest.approx(math.degrees(rows[res.first_gf_frame - 1]["theta"]))
        assert res.distance_at_gf_px is not None
        assert sum(r["spike"] for r in rows) >= 1
    assert res.a_pressed == (res.a_frames > 0) == (sum(r["press_a"] for r in rows) > 0)
    assert res.outcome in ("passed", "stomped", "died", "timeout") and res.survived == (res.outcome in ("passed", "stomped"))


@needs_net
@needs_cal
def test_episode_is_reproducible_for_a_seed():
    a = e1.run_e1_episode(9100, None, max_frames=160)[0]
    b = e1.run_e1_episode(9100, None, max_frames=160)[0]
    assert a == b


# ---- the GF-lesion control arm ---------------------------------------------------------------------------------------
def test_lesion_is_control_only_removal_and_unreachable_from_the_tool():
    import re
    from pathlib import Path
    from brain import brain as brain_mod
    assert e1.ARMS == ("real", "shuffled", "lesion_gf") and e1.LESION_POPULATIONS == ("GF",)
    assert brain_mod.LESION_CLAMP_HZ == e1.E1_LESION_CLAMP_HZ == 0.0          # silenced = zero, never a positive value
    with pytest.raises(ValueError):
        e1.run_e1_episode(1, 5, arm="lesion_gf")                               # a lesion with a shuffle seed is refused
    root = Path(__file__).resolve().parent.parent
    # the word 'lesion' appears in the brain path only in brain.py, policy.py (pass-through), e1.py, scalars.py and library.py (a text line) ...
    users = {p.relative_to(root).as_posix() for p in (root / "brain").glob("*.py") if re.search(r"lesion", p.read_text(encoding="utf-8"))}
    assert users == {"brain/brain.py", "brain/policy.py", "brain/e1.py", "brain/scalars.py", "brain/library.py"}, users
    # ... and nowhere in the tool except as a display label of a saved evaluation (Results tab).
    tool_users = {p.relative_to(root).as_posix() for p in (root / "tool").rglob("*.py")
                  if "tests" not in p.parts and re.search(r"lesion", p.read_text(encoding="utf-8"))}
    assert tool_users <= {"tool/ui/tabs/results.py", "tool/ui/brain_runs.py"}, tool_users     # labels only; no Run/Watch/library code


def test_lesion_arm_is_not_an_option_of_the_run_path():
    import inspect
    from tool.core import brain_runner
    assert "arm" not in inspect.signature(brain_runner.run_brain_one).parameters
    assert "lesion" not in inspect.getsource(brain_runner).lower()


@needs_net
@needs_cal
def test_lesion_arm_gf_output_is_zero_and_a_never_pressed_across_seeds():
    # The control's purpose: with the GF silenced the fly cannot jump. Smoke seeds, not held-out seeds.
    for seed in (9100, 9101, 9102):
        res, rows, stamp = e1.run_e1_episode(seed, None, max_frames=160, record_rows=True, arm="lesion_gf")
        assert res.arm == "lesion_gf" and stamp["lesion"] == ["GF"]
        assert res.gf_output_max_hz == 0.0                                   # GF output exactly 0 Hz over the episode
        assert rows and all(r["gf_output"] == 0.0 for r in rows if "gf_output" in r)
        assert not res.a_pressed and res.a_frames == 0                       # A is never pressed
        assert all(not r["press_a"] for r in rows)
        assert res.outcome != "stomped"                                      # no jump, so no stomp
    real = e1.run_e1_episode(9100, None, max_frames=160)[0]
    assert real.gf_output_max_hz > 0.0


# ---- library ---------------------------------------------------------------------------------------------------------
def test_library_is_complete_and_labels_the_input_tier():
    ids = {m.id for m in library.MECHANISMS}
    assert [e.id for e in library.EXPERIMENTS] == ["E0", "E1", "E2a", "E2b", "E3", "E4", "E5", "E6", "E7", "E8", "B11"]
    for e in library.EXPERIMENTS:
        assert set(e.mechanisms) <= ids and e.origin and e.criterion and e.controls
    for m in library.MECHANISMS:
        assert m.origin and m.evidence and m.entry_neurons and m.status in ("built", "planned", "investigation", "no innate effect")
        assert m.entry_tier in ("feature-level (D1)", "receptor", "n/a")
    looming = library.mechanism("looming")
    assert looming.status == "built" and looming.entry_tier == "feature-level (D1)"
    assert [e.id for e in library.EXPERIMENTS if e.status == "runnable"] == ["E0", "E1", "E2a", "E3", "B11"]
    assert library.experiment("E1").runner == "brain.e1"


def test_looming_library_entry_matches_the_mechanism_class():
    from brain.mechanisms import LoomingMechanism
    for pop in LoomingMechanism.populations:
        assert pop in library.mechanism("looming").entry_neurons
