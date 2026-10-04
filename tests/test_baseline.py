"""Tests for the 1-1 innate baseline (docs/SPEC_baseline_1-1.md): the scene is the untouched game, the metric helpers on fake episodes."""
import inspect
import re

import pytest

from brain import baseline
from brain.baseline import BaselineResult, GoombaTracker, a_runs, classify_end, summarize
from brain.scenes import B11_SCENE_ID, load_scene
from brain.settings import SenseSettings, settings_for


def test_scene_has_no_log_no_rules_and_the_runner_never_clears_enemies_or_writes_ram():
    scene = load_scene(B11_SCENE_ID)
    assert scene.log == () and scene.rules == () and scene.level == "1-1" and scene.actions().size == 0
    src = inspect.getsource(baseline.run_baseline_episode)
    assert "apply_rules" not in src and "build_scene" not in src and "clear_enemies" not in src
    assert not re.search(r"ram\[[^\]]+\]\s*=(?!=)", src), "the baseline must not write RAM"
    assert "ram[" not in inspect.getsource(baseline.GoombaTracker)


def test_b11_runs_all_three_mechanisms_with_the_user_defaults():
    used = settings_for("B11")
    assert used == SenseSettings.user_default()
    assert used.pursuit_kinds == ("powerup",) and used.goal_cue_salience > 0


def test_a_runs_and_classify_end():
    assert a_runs([0, 1, 1, 0, 0, 1, 0, 1, 1, 1]) == [2, 1, 3] and a_runs([]) == [] and a_runs([0, 0]) == []
    assert classify_end(True, False, False, False, False) == "level_complete"
    assert classify_end(False, True, True, True, False) == "died_pit"
    assert classify_end(False, True, False, True, False) == "died_enemy"
    assert classify_end(False, True, False, False, False) == "died_other"
    assert classify_end(False, False, False, False, True) == "stuck"
    assert classify_end(False, False, False, False, False) is None


def _feed(tracker, frames):
    for airborne, slots in frames:
        tracker.update(airborne, slots)


def test_goomba_tracker_counts_a_pass_over_and_a_stomp_but_not_a_hit_or_a_walk_by():
    # Goomba in slot 0 approaches; Mario jumps while it is under him and it ends up behind him: jumped (b).
    t = GoombaTracker()
    _feed(t, [(False, {0: (60, False)}), (False, {0: (30, False)}), (True, {0: (10, False)}), (True, {0: (-5, False)}),
              (True, {0: (-20, False)})])
    assert (t.encountered, t.jumped) == (1, 1)
    # Stomp: Goomba removed while overlapping and Mario airborne: jumped (a), even though boxes overlapped in the air.
    t = GoombaTracker()
    _feed(t, [(True, {1: (8, False)}), (True, {1: (2, False)}), (True, {1: None})])
    assert (t.encountered, t.jumped) == (1, 1)
    # Ground contact (a hit), Goomba then behind Mario: encountered, not jumped.
    t = GoombaTracker()
    _feed(t, [(False, {0: (10, True)}), (True, {0: (-4, False)}), (True, {0: (-20, False)})])
    assert (t.encountered, t.jumped) == (1, 0)
    # Mario never airborne: not jumped. A Goomba that never overlaps is not even encountered.
    t = GoombaTracker()
    _feed(t, [(False, {0: (10, False)}), (False, {0: (-20, False)}), (False, {2: (90, False)}), (False, {2: None})])
    assert (t.encountered, t.jumped) == (1, 0)
    # Counted once only, even if the Goomba re-enters the window.
    t = GoombaTracker()
    _feed(t, [(True, {0: (5, False)}), (True, {0: (-17, False)}), (False, {0: (-8, False)}), (False, {0: (-30, False)})])
    assert (t.encountered, t.jumped) == (1, 1)


def _ep(arm, max_x, outcome, runs, collected=False, jumped=0, encountered=0):
    return BaselineResult("B11", arm, 6000, None, outcome == "level_complete", outcome, outcome.startswith("died"), 100, None, max_x,
                          False, None, 0.0, 0.0, bool(runs), sum(runs), 0, 100, 100, collected, None, False, encountered, jumped, list(runs),
                          runs[0] if runs else None, bool(runs) and runs[0] <= 2)


def test_summary_metrics_on_a_fake_episode_set():
    eps = [_ep("real", 300, "died_enemy", [1, 7]), _ep("real", 500, "stuck", [2]),
           _ep("real", 400, "died_pit", [5], jumped=1, encountered=2),
           _ep("real", 3160, "level_complete", [], collected=True, jumped=3, encountered=3)]
    s = summarize(eps)
    assert s["n"] == 4 and s["max_x_median"] == 450.0 and s["max_x_min"] == 300 and s["max_x_max"] == 3160
    lo, hi = s["max_x_mean_ci"]
    assert lo <= s["max_x_mean"] <= hi
    assert s["end_reasons"] == {"level_complete": 1, "died_enemy": 1, "died_pit": 1, "died_other": 0, "stuck": 1, "timeout": 0}
    assert (s["a_episodes"], s["tap_episodes"]) == (3, 2) and s["tap_fraction"] == pytest.approx(2 / 3)
    assert s["a_run_hist"] == {"1": 1, "2": 1, "3-5": 1, "6-10": 1, "11+": 0} and s["a_runs_total"] == 4
    assert (s["goombas_jumped"], s["goombas_encountered"], s["episodes_with_a_jump"]) == (4, 5, 2)
    assert s["collected"] == 1 and s["level_complete"] == 1


def test_arm_validation():
    with pytest.raises(ValueError):
        baseline.run_baseline_episode(1, "shuffled", None)
    with pytest.raises(ValueError):
        baseline.run_baseline_episode(1, "real", 3)
