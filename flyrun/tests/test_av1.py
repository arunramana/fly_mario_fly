"""Part AV1: the headroom factor, the sour cue, the back-up output, and that every toggle off changes nothing."""
import json
import os
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from flyrun import env as E, knobs, level, motor, senses_v2 as S
from flyrun.brain import CACHE
from flyrun.knobs import Knobs
from flyrun.senses import theta_of

from .test_l2b import _floor, _ram

RUNS = Path(__file__).resolve().parents[1] / "runs"


def _goomba(x, feet=176):
    return S.enemy_boxes([(0, 0x06, 0, x, feet + 8)], [])[0]


def test_headroom_factor_is_one_on_open_ground(monkeypatch):
    monkeypatch.setenv("FLYRUN_LEVEL", "1-1")
    ram = _ram()
    _floor(ram, 0, 512)
    assert S.headroom_factor(ram, 100, 176, _goomba(140)) == (1.0, knobs.MAX_JUMP_HEIGHT, 18)
    k = S.headroom_factor(ram, 100, 176, S.enemy_boxes([(0, 0x00, 0, 140, 184)], [])[0])
    assert k[0] == 1.0 and k[2] == 26                              # a Koopa needs its 24 px + 2


def test_headroom_factor_scales_with_the_ceiling(monkeypatch):
    monkeypatch.setenv("FLYRUN_LEVEL", "1-1")
    low = _ram({(140, 7): 81})                                     # a brick over the Goomba: underside y 128, head 160 -> 32 px of rise
    _floor(low, 0, 512)
    assert S.headroom_factor(low, 100, 176, _goomba(140))[0] == 1.0          # 32 >= 18
    tight = _ram({(140, 9): 81})                                   # underside y 160 = his head: no rise at all
    _floor(tight, 0, 512)
    assert S.headroom_factor(tight, 100, 176, _goomba(140))[0] == 0.0
    mid = _ram({(140, 8): 81})                                     # underside 144: 16 px of rise for an 18 px need -> 16 / 18
    _floor(mid, 0, 512)
    assert S.headroom_factor(mid, 100, 176, _goomba(140))[0] == pytest.approx(16 / 18)


def test_headroom_factor_is_zero_under_the_x890_pillar():
    fx = RUNS / "L2b_fixture_1-2_x832_960.json"
    if not fx.exists():
        pytest.skip("fixture comes from python -m flyrun.l2b_structures")
    cols = json.loads(fx.read_text())
    ram = _ram({(int(x), r): t for x, col in cols.items() for r, t in enumerate(col) if t}, left=800)
    os.environ["FLYRUN_LEVEL"] = "1-2"
    try:
        koopa = S.enemy_boxes([(0, 0x00, 0, 882, 184)], [])[0]
        f, rise, need = S.headroom_factor(ram, 850, 176, koopa)
        assert f == 0.0 and rise == 0 and need == 26
        f2 = S.headroom_factor(ram, 900, 176, S.enemy_boxes([(0, 0x00, 0, 912, 184)], [])[0])
        assert f2[0] == 1.0                                         # past the pillar the same Koopa can be jumped
    finally:
        os.environ.pop("FLYRUN_LEVEL", None)


def _masks(K=8):
    names = dict(TTMn=[0], DNp09=[1], DNa_R=[2], DNa_L=[3], MDN=[4, 5])
    return {n: np.isin(np.arange(K), i) for n, i in names.items()}


def _knobs(**kw):
    return replace(Knobs(), SENSES_VERSION="v2", MOTOR_VERSION="v2", **kw)


def test_mdn_above_threshold_presses_left_and_releases_right():
    m = _masks()
    h = np.zeros(8)
    h[1] = 0.2                                                      # DNp09 walking: Right
    k = _knobs(SOUR_SENSE=True)
    a, read = motor.decide(h, m, k, motor.Muscle2(), airborne=False)
    assert a == E.RIGHT and read["mdn"] == 0.0
    h[4] = h[5] = 0.11                                              # MDN above 0.10
    a, read = motor.decide(h, m, k, motor.Muscle2(), airborne=False)
    assert a == E.LEFT and read["mdn"] == pytest.approx(0.11)
    h[0] = 0.5                                                      # the jump circuit still presses A: Left + A
    a, _ = motor.decide(h, m, k, motor.Muscle2(), airborne=False)
    assert a == E.LEFT_A
    h[4] = h[5] = 0.09                                              # below the threshold: Right again
    a, _ = motor.decide(h, m, k, motor.Muscle2(), airborne=False)
    assert a == E.RIGHT_A


def test_mdn_does_nothing_when_sour_is_off():
    m = _masks()
    h = np.zeros(8)
    h[1], h[4], h[5] = 0.2, 0.9, 0.9
    a, read = motor.decide(h, m, _knobs(), motor.Muscle2(), airborne=False)
    assert a == E.RIGHT and "mdn" not in read


def test_sour_enemy_is_the_nearest_live_sour_one_and_a_shell_is_not():
    enemies = [(1, 0x00, 0, 220, 184), (0, 0x06, 0, 150, 184)]
    se = S.sour_enemy(100, 176, enemies, [])
    assert se.kind == "goomba" and se.theta == pytest.approx(theta_of(se.d, 16))
    assert S.sour_enemy(100, 176, [(0, 0x00, 2, 150, 184)], []) is None        # a Koopa shell (state 2) does not smell sour
    assert S.sour_enemy(100, 176, [(0, 0x06, 0, 40, 184)], []) is None         # behind his left edge


def _ram_with_goomba(x_enemy, mx=100):
    ram = _ram()
    _floor(ram, 0, 512)
    ram[E.ADDR_MARIO_PAGE], ram[E.ADDR_MARIO_X] = mx // 256, mx % 256
    ram[0x00CE] = 176
    ram[E.ADDR_ENEMY_ACTIVE], ram[E.ADDR_ENEMY_TYPE] = 1, 0x06
    ram[E.ADDR_ENEMY_PAGE], ram[E.ADDR_ENEMY_X], ram[0x00CF], ram[0x001E] = x_enemy // 256, x_enemy % 256, 184, 0
    return ram


def _brain_like(K=12):
    names = ["LC4_R", "LPLC2_R", "LC10a_R", "DC4_L", "DC4_R", "MDN", "LC4_L", "LPLC2_L", "TTMn", "DNp09", "DNa_L", "DNa_R"]
    return {n: np.isin(np.arange(K), [i]) for i, n in enumerate(names)}


def test_sour_level_is_gain_times_theta_into_both_dc4_sides():
    k = _knobs(SOUR_SENSE=True, SOUR_GAIN=8.0, SENSOR_NOISE=0.0)
    sn = S.SensesV2(k, _brain_like(), 12)
    I, lm = sn.look(_ram_with_goomba(140))
    se = S.sour_enemy(100, 176, [(0, 0x06, 0, 140, 184)], [])
    assert lm.extra["sour_theta"] == pytest.approx(se.theta) and lm.extra["sour_level"] == pytest.approx(8.0 * se.theta)
    assert I[sn.m["DC4_L"]][0] == I[sn.m["DC4_R"]][0] == pytest.approx(8.0 * se.theta)


def test_all_toggles_off_changes_nothing():
    ram = _ram_with_goomba(140)
    I0, lm0 = S.SensesV2(_knobs(), _brain_like(), 12).look(ram)
    assert not ({"sour_level", "headroom_factor"} & set(lm0.extra))
    on = S.SensesV2(_knobs(SOUR_SENSE=True, SOUR_GAIN=0.0, HEADROOM_LOOM=True), _brain_like(), 12)
    I1, lm1 = on.look(ram)
    assert np.array_equal(I0, I1) and lm0.theta == lm1.theta           # open ground: factor 1, gain 0: the same drive
    assert knobs.toggle_set(_knobs()) == dict(looming_enemy=True, looming_pipe=True, looming_pit=True, home=True, hum=False, smell=False)


def test_headroom_loom_scales_the_enemy_theta():
    ram = _ram_with_goomba(140)
    ram[level.BUF + 16 * 9 + 140 // 16] = 81                            # a block at his head height over the Goomba -> factor 0
    off = S.SensesV2(_knobs(), _brain_like(), 12).look(ram)[1]
    on = S.SensesV2(_knobs(HEADROOM_LOOM=True), _brain_like(), 12).look(ram)[1]
    assert off.theta > 0 and on.theta == 0.0 and on.extra["headroom_factor"] == 0.0 and on.extra["theta_unscaled"] == pytest.approx(off.theta)


@pytest.mark.skipif(not (CACHE / "W_steer_jo_orn_sour.npy").exists(), reason="python -m flyrun.av1_brain")
def test_sour_brain_has_dc4_and_mdn_and_leaves_the_old_rows_alone():
    import pandas as pd
    W = np.load(CACHE / "W_steer_jo_orn_sour.npy")
    old = np.load(CACHE / "W_steer_jo_orn.npy")
    b = pd.read_parquet(CACHE / "steer_jo_orn_sour_bodies.parquet")
    assert W.shape == (907, 907) and (b.type == "MDN").sum() == 4 and (b.type == "ORN_DC4").sum() == 13
    assert np.array_equal(W[:881, :881], old)                          # old rows exactly as before
    assert not W[:881, 881:].any()                                     # nothing from the new neurons feeds back into the old brain
