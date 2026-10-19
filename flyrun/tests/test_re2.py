"""Part RE2: looming from behind (REAR_EYE) and sour from behind (REAR_SOUR, honest / gated). Every toggle off changes nothing."""
import json
from dataclasses import replace

import numpy as np
import pytest

from flyrun import env as E, motor, senses_v2 as S
from flyrun.brain import CACHE
from flyrun.knobs import Knobs

from .test_av1 import _brain_like, _knobs, _masks
from .test_l2b import _floor, _ram

MX = 100


def _ram_enemy(x_enemy, mx=MX, kind=0x06, state=0):
    ram = _ram()
    _floor(ram, 0, 512)
    ram[E.ADDR_MARIO_PAGE], ram[E.ADDR_MARIO_X] = mx // 256, mx % 256
    ram[0x00CE] = 176
    ram[E.ADDR_ENEMY_ACTIVE], ram[E.ADDR_ENEMY_TYPE] = 1, kind
    ram[E.ADDR_ENEMY_PAGE], ram[E.ADDR_ENEMY_X], ram[0x00CF], ram[0x001E] = x_enemy // 256, x_enemy % 256, 184, state
    return ram


def _walk(sn, xs, mx=MX):
    return [sn.look(_ram_enemy(x, mx)) for x in xs]


def test_rear_gap_is_measured_from_his_left_edge():
    assert S.gap(100, 176, 70, 160, 16, 16, rear=True) == 14.0         # enemy right edge 86, his left edge 100
    assert S.gap(100, 176, 150, 160, 16, 16) == 38.0                   # ahead: from his right edge (112), unchanged


def test_off_is_identical_to_before():
    for xs in ([150, 140, 130], [60, 65, 70], [120, 110, 100]):
        a, b = S.SensesV2(_knobs(), _brain_like(), 12), S.SensesV2(_knobs(REAR_EYE=False, REAR_SOUR=False), _brain_like(), 12)
        for (I0, l0), (I1, l1) in zip(_walk(a, xs), _walk(b, xs)):
            assert np.array_equal(I0, I1) and l0.theta == l1.theta and l0.extra == l1.extra
    assert "threat_rear" not in S.SensesV2(_knobs(), _brain_like(), 12).look(_ram_enemy(60))[1].extra
    assert S.choose(100, 176, [(0, 0x06, 0, 70, 184)], [], []) is None  # ahead-only: an enemy behind is ignored


def test_rear_enemy_closing_is_chosen_and_theta_grows():
    sn = S.SensesV2(_knobs(REAR_EYE=True, SENSOR_NOISE=0.0), _brain_like(), 12)
    out = _walk(sn, [40, 46, 52, 58, 64, 70, 76, 82])
    assert out[0][1].src == "none"                                      # first sight: no previous gap, not known to be closing
    th = [lm.theta for _, lm in out[1:]]
    assert all(lm.src == "goomba" and lm.extra["threat_rear"] for _, lm in out[1:])
    assert all(b > a for a, b in zip(th, th[1:])) and th[-1] > 0.9
    assert all(lm.dtheta > 0 for _, lm in out[2:])


def test_rear_enemy_moving_away_is_never_chosen():
    sn = S.SensesV2(_knobs(REAR_EYE=True, SENSOR_NOISE=0.0), _brain_like(), 12)
    out = _walk(sn, [84, 80, 76, 72, 68, 64, 60])
    assert all(lm.src == "none" and lm.theta == 0.0 and lm.dtheta == 0.0 for _, lm in out)
    assert all(I[sn.m["LC4_R"]][0] == 0 and I[sn.m["LPLC2_R"]][0] == 0 for I, _ in out)


def test_a_threat_ahead_wins_over_a_farther_rear_one_and_loses_to_a_nearer_one():
    near_rear = [(0, 0x06, 0, 80, 184), (1, 0x06, 0, 180, 184)]
    t = S.choose(100, 176, near_rear, [], [], rear_closing=frozenset({("enemy", 0)}))
    assert t.ident == ("enemy", 0) and t.rear                          # gap 4 behind < gap 68 ahead
    far_rear = [(0, 0x06, 0, 20, 184), (1, 0x06, 0, 130, 184)]
    t = S.choose(100, 176, far_rear, [], [], rear_closing=frozenset({("enemy", 0)}))
    assert t.ident == ("enemy", 1) and not t.rear


def test_rear_eye_leaves_faces_and_pits_ahead_only():
    walls = [(60, 64), (76, 64)]                                        # a pipe face fully behind him
    t = S.choose(100, 176, [], walls, [(40, 32)], rear_closing=frozenset({("enemy", 9)}))
    assert t is None


@pytest.mark.skipif(not (CACHE / "W_steer_jo_orn_sour.npy").exists(), reason="brain cache")
def test_rear_enemy_closing_makes_the_giant_fiber_fire_and_a_receding_one_does_not():
    from flyrun import av1_run as A, e1s_genome as G, re2_run as R
    from flyrun.brain import step
    net = A.brain(G.WFILE)
    k, _ = R.knobs_for("B")
    k = replace(k, SOUR_SENSE=False, HEADROOM_LOOM=False)

    def peak(xs):
        sn, h, top = S.SensesV2(k, net.masks, net.K), np.zeros(net.K), 0.0
        for x in xs:
            I, _ = sn.look(_ram_enemy(x))
            for _ in range(k.SUBSTEPS):
                h = step(h, net.W, k.G, I, k.ALPHA, k.CLIP)
            top = max(top, float(h[net.masks["TTMn"]].mean()))
        return top
    closing = peak([30 + 2 * i for i in range(27)] + [84] * 3)         # walks up to 4 px behind him
    receding = peak([84 - 2 * i for i in range(27)])
    assert closing >= k.TTMN_THRESH and receding < 0.01


def _sour_sense(mode, rear=True, **kw):
    return S.SensesV2(_knobs(SOUR_SENSE=True, SOUR_GAIN=8.0, SENSOR_NOISE=0.0, REAR_SOUR=rear, REAR_SOUR_MODE=mode, **kw), _brain_like(), 12)


def test_sour_off_ignores_an_enemy_behind_and_honest_smells_it_like_one_ahead():
    ram = _ram_enemy(70)
    assert _sour_sense("honest", rear=False).look(ram)[1].extra["sour_level"] == 0.0
    ex = _sour_sense("honest").look(ram)[1].extra
    se = S.sour_enemy(100, 176, [(0, 0x06, 0, 70, 184)], [], rear=True)
    assert ex["sour_rear"] and ex["sour_level"] > 0 and ex["sour_level"] == pytest.approx(8.0 * se.theta)
    ahead = S.sour_enemy(100, 176, [(0, 0x06, 0, 126, 184)], [])         # the mirror image: same 2-D gap (14 px) ahead -> same level
    assert se.d == ahead.d and se.theta == pytest.approx(ahead.theta)


def test_sour_source_is_the_nearest_on_either_side():
    en = [(0, 0x06, 0, 80, 184), (1, 0x06, 0, 140, 184)]               # 4 px behind vs 28 px ahead
    assert S.sour_enemy(100, 176, en, [], rear=True).ident == ("enemy", 0)
    assert S.sour_enemy(100, 176, en, []).ident == ("enemy", 1)


def test_gated_blocks_left_only_while_the_source_is_behind():
    m = _masks()
    h = np.zeros(8)
    h[1], h[4], h[5] = 0.2, 0.5, 0.5                                    # walking, MDN well above the threshold
    k = _knobs(SOUR_SENSE=True)
    assert motor.decide(h, m, k, motor.Muscle2(), airborne=False)[0] == E.LEFT
    a, read = motor.decide(h, m, k, motor.Muscle2(), airborne=False, block_backup=True)
    assert a == E.RIGHT and read["mdn"] == pytest.approx(0.5)           # MDN still reported, Left is not pressed


def test_gated_flag_follows_the_nearest_source_side():
    g = _sour_sense("gated")
    assert g.look(_ram_enemy(70))[1].extra["sour_rear"] is True
    assert g.look(_ram_enemy(140))[1].extra["sour_rear"] is False
    assert "sour_rear" not in _sour_sense("honest", rear=False).look(_ram_enemy(70))[1].extra


def test_toggle_set_records_the_rear_toggles():
    from flyrun.knobs import toggle_set
    assert "rear_eye" not in toggle_set(_knobs())
    t = toggle_set(_knobs(REAR_EYE=True, REAR_SOUR=True, REAR_SOUR_MODE="gated"))
    assert t["rear_eye"] is True and t["rear_sour"] == "gated"


def test_arm_a_reproduces_the_e1s_dev_set_trajectories():
    """The recorded RE2 arm A (both toggles off) run on the 10 dev-set episodes gives the E1s trajectories (hashes equal): off changes nothing."""
    from pathlib import Path
    runs = Path(__file__).resolve().parents[1] / "runs"
    if not ((runs / "RE2_holdout_A.json").exists() and (runs / "E1s_holdout.json").exists()):
        pytest.skip("python -m flyrun.re2_run holdout A")
    a = json.load(open(runs / "RE2_holdout_A.json"))["episodes"]
    e = json.load(open(runs / "E1s_holdout.json"))["episodes"]
    assert [r["traj"] for r in a] == [r["traj"] for r in e] and all(r["flag"] for r in a)
