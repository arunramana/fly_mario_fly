"""Part M2: the smell sense (mushroom -> attractive ORNs on its side) and the ORN brain."""
import os
from dataclasses import replace

import numpy as np
import pytest

from flyrun import env as E, senses_v2 as S
from flyrun.knobs import Knobs
from flyrun.senses import theta_of

KN = replace(Knobs(), SENSES_VERSION="v2", SMELL_SENSE=True)
SL = E.N_ENEMY_SLOTS


def _masks(K=10):
    m = {k: np.zeros(K, bool) for k in ("LC4_L", "LC4_R", "LPLC2_L", "LPLC2_R", "LC10a_R", "ORN_L", "ORN_R")}
    m["ORN_L"][:3] = True
    m["ORN_R"][3:6] = True
    m["LC4_R"][6] = m["LPLC2_R"][7] = m["LC10a_R"][8] = True
    return m


def _ram(x=None, y=184):
    ram = np.zeros(0x800, dtype=np.uint8)
    ram[0x071A] = 0
    if x is not None:
        ram[E.ADDR_ENEMY_ACTIVE + SL], ram[E.ADDR_ENEMY_TYPE + SL] = 1, E.POWERUP_ID
        ram[E.ADDR_ENEMY_PAGE + SL], ram[E.ADDR_ENEMY_X + SL], ram[0x00CF + SL] = x // 256, x % 256, y
    return ram


def _look(mx, mush_x, kn=KN):
    se = S.SensesV2(kn, _masks(), 10)
    se.read_ram = lambda r: (mx, 176, [], [], [])
    return se.look(_ram(mush_x))


def test_mushroom_is_the_live_powerup_in_slot_5():
    assert S.mushroom(_ram(300)) == (300, 184 - 8 - 16)
    assert S.mushroom(_ram(None)) is None
    r = _ram(300)
    r[E.ADDR_ENEMY_TYPE + SL] = 0x06                        # a Goomba id in that slot is not a mushroom
    assert S.mushroom(r) is None


def test_behind_smells_into_the_left_antenna_ahead_into_the_right():
    I, lm = _look(560, 496)                                  # 64 px behind
    d = float(np.hypot(560 + 12 - (496 + 8), 160 - 168))
    want = KN.SMELL_GAIN * theta_of(d, 16)
    assert np.allclose(I[:3], want) and not I[3:6].any() and lm.extra["smell_R"] == 0.0 and lm.extra["smell_L"] == pytest.approx(want)
    I, lm = _look(560, 640)                                  # ahead
    assert not I[:3].any() and np.all(I[3:6] > 0) and lm.extra["smell_L"] == 0.0
    assert lm.extra["smell_box"] == (640, 160, 16, 16)


def test_no_mushroom_means_no_smell_and_off_leaves_the_input_untouched():
    I, lm = _look(560, None)
    assert not I[:6].any() and lm.extra["smell_box"] is None
    I, lm = _look(560, 496, replace(KN, SMELL_SENSE=False))
    assert not I[:6].any() and "smell_L" not in lm.extra


def test_orn_brain_has_ipsilateral_orn_masks_and_smell_off_reproduces_s3e():
    from pathlib import Path
    import pandas as pd
    os.environ["FLYRUN_WFILE"], os.environ["FLYRUN_BODIES"] = "W_steer_jo_orn.npy", "steer_jo_orn_bodies.parquet"
    try:
        from flyrun.brain import load_brain
        from flyrun.run import run_episode
        b = load_brain()
        assert b.W.shape == (881, 881) and b.masks["ORN_L"].sum() > 0 and b.masks["ORN_R"].sum() > 0 and int(b.masks["JO"].sum()) == 20
        assert not (b.masks["ORN_L"] & b.masks["ORN_R"]).any()
        s, df = run_episode(replace(Knobs(), SENSES_VERSION="v2", MOTOR_VERSION="v2", SENSOR_NOISE=0.0), b, noop_start=0, episode_seed=0, max_frames=500)
        ref = pd.read_csv(Path(__file__).resolve().parent.parent / "runs" / "S3e_full_run.csv").iloc[:500]
        assert (df.x.to_numpy() == ref.x.to_numpy()).all() and (df.a.to_numpy() == ref.a.to_numpy()).all()
    finally:
        del os.environ["FLYRUN_WFILE"], os.environ["FLYRUN_BODIES"]
