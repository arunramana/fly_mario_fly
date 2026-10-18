"""Part S2: motor v2 (the fly holds the jump). Synthetic TTMn / airborne traces through Muscle2."""
import pytest

from flyrun.motor import Muscle2

THR = 0.3


def run(trace):
    """trace: [(ttmn, airborne)] -> ([A], [why])"""
    m, a, why = Muscle2(), [], []
    for ttmn, air in trace:
        a.append(int(m.step(ttmn, THR, THR, bool(air))))
        why.append(m.why)
    return a, why


def test_press_hold_release_landing_and_immediate_repress():
    hi, lo = 0.5, 0.1
    trace = [(lo, 0), (hi, 0),      # grounded, loom rises -> press
             (hi, 1), (hi, 1),      # airborne, still above -> hold
             (lo, 1), (hi, 1),      # fades -> release; rising again in the air does NOT re-press
             (hi, 1),
             (hi, 0),               # landing frame: released for exactly this frame
             (hi, 0),               # still above -> pressed again immediately
             (hi, 1)]
    a, why = run(trace)
    assert a == [0, 1, 1, 1, 0, 0, 0, 0, 1, 1]
    assert why[4] == "loom_faded" and why[7] == ""        # already released when it landed -> no landing reset
    assert all(w == "" for i, w in enumerate(why) if i not in (4,))


def test_no_press_while_airborne_and_press_only_when_grounded():
    a, _ = run([(0.9, 1), (0.9, 1), (0.9, 0)])
    assert a == [0, 0, 0]                                 # no press in the air; the landing frame is up
    a, _ = run([(0.9, 0), (0.9, 0)])
    assert a == [1, 1]


def test_wall_retries_never_stays_down_across_a_landing():
    # TTMn stuck high against a wall; he jumps, lands, jumps ... A must be up on every landing frame
    trace = [(0.9, 0)]
    for _ in range(3):
        trace += [(0.9, 1)] * 3 + [(0.9, 0), (0.9, 0)]     # 3 airborne frames, landing frame, grounded frame
    a, why = run(trace)
    assert a == [1] + ([1, 1, 1, 0, 1] * 3)               # A is up on every landing frame, down again the next frame
    assert [i for i, w in enumerate(why) if w == "landing_reset"] == [4, 9, 14]


def test_release_thresh_default_is_ttmn_thresh_hysteresis_optional():
    m = Muscle2()
    assert m.step(0.5, 0.3, 0.3, False) is True
    assert m.step(0.25, 0.3, 0.2, True) is True            # with RELEASE_THRESH 0.2 it holds at 0.25
    assert m.step(0.15, 0.3, 0.2, True) is False


def test_v2_motor_requires_v2_senses():
    from dataclasses import replace
    from flyrun.brain import load_brain
    from flyrun.knobs import Knobs
    from flyrun.run import run_episode
    with pytest.raises(AssertionError, match="requires SENSES_VERSION"):
        run_episode(replace(Knobs(), MOTOR_VERSION="v2"), load_brain(), max_frames=5)


def test_v2_episode_logs_why_and_left_counts():
    from dataclasses import replace
    from flyrun.brain import load_brain
    from flyrun.knobs import Knobs
    from flyrun.run import run_episode
    s, df = run_episode(replace(Knobs(), SENSES_VERSION="v2", MOTOR_VERSION="v2", SENSOR_NOISE=0.0), load_brain(), max_frames=300)
    assert {"y", "a_why"} <= set(df.columns) and "left_presses" in s
    assert set(df.a_why.dropna()) <= {"", "loom_faded", "landing_reset"}
