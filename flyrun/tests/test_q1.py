"""Part Q1: the hum (JO -> GF) sense and the JO brain."""
import os
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from flyrun import level, senses_v2 as S
from flyrun.knobs import HUM_REACH, Knobs
from flyrun.senses import theta_of

KN = replace(Knobs(), SENSES_VERSION="v2", HUM_SENSE=True)
FEET = 176


def _ram(blocks=(), left=200):
    """A fake RAM: tile buffer with the given {(x, row): tile}; the screen's left edge at `left`."""
    ram = np.zeros(0x800, dtype=np.uint8)
    for (x, row), t in dict(blocks).items():
        ram[level.BUF + level.PAGE_BYTES * ((x // 256) % 2) + 16 * row + (x % 256) // 16] = t
    ram[0x071A], ram[0x071C] = left // 256, left % 256
    return ram


def _masks(K=8):
    m = {k: np.zeros(K, bool) for k in ("LC4_L", "LC4_R", "LPLC2_L", "LPLC2_R", "LC10a_R", "JO")}
    m["JO"][:3] = True
    m["LC4_R"][3] = m["LPLC2_R"][4] = m["LC10a_R"][5] = True
    return m


def test_scan_blocks_unused_only():
    assert level.scan_blocks(_ram({(256, 7): 192, (336, 7): 193})) == [(256, 7), (336, 7)]
    assert level.scan_blocks(_ram({(256, 7): 196})) == []          # used
    assert level.scan_blocks(_ram({(256, 7): 35})) == []           # bumping: no hum


def test_nearest_humming_block_only_and_reach():
    blocks = [(256, 7), (336, 7), (352, 3)]
    assert S.hum_block(200, FEET, blocks)[0] == 256                 # nearest; the row-3 block (underside 112 above ground) never hums
    assert S.hum_block(300, FEET, blocks)[0] == 336                 # 256 is fully behind his left edge
    assert S.hum_block(250, FEET, blocks)[0] == 256                 # he is under it: "above him" still counts
    assert S.hum_block(200, FEET, [(352, 3)]) is None
    assert 176 - (7 + 1) * 16 <= HUM_REACH < 176 - (3 + 1) * 16


def test_hum_level_is_gain_times_block_theta():
    se = S.SensesV2(KN, _masks(), 8)
    ram = _ram({(256, 7): 192})
    ram[0x001D] = 0
    se.read_ram = lambda r: (200, FEET, [], [], [])
    I, lm = se.look(ram)
    d = float(np.hypot(200 + 12 - (256 + 8), (FEET - 16) - 128))
    want = KN.HUM_GAIN * theta_of(d, 16)
    assert lm.extra["hum_level"] == pytest.approx(want) and np.allclose(I[:3], want)
    assert I[3] == 0.0 and I[4] == 0.0                      # no looming input: nothing but the hum reaches the JO neurons
    assert lm.extra["hum_block"][:2] == (256, 128)


def test_silence_no_block_in_view_means_no_jo_input_and_used_block_is_silent():
    se = S.SensesV2(KN, _masks(), 8)
    se.read_ram = lambda r: (200, FEET, [], [], [])
    for blocks in ({}, {(256, 7): 196}, {(256, 7): 35}):
        I, lm = se.look(_ram(blocks))
        assert I[:3].tolist() == [0.0, 0.0, 0.0] and lm.extra["hum_level"] == 0.0 and lm.extra["hum_block"] is None


def test_hum_off_leaves_the_input_untouched():
    kn = replace(KN, HUM_SENSE=False)
    se = S.SensesV2(kn, _masks(), 8)
    se.read_ram = lambda r: (200, FEET, [], [], [])
    I, lm = se.look(_ram({(256, 7): 192}))
    assert not I[:3].any() and "hum_level" not in lm.extra


def test_jo_brain_has_the_20_jo_neurons_and_hum_off_reproduces_s3e():
    os.environ["FLYRUN_WFILE"], os.environ["FLYRUN_BODIES"] = "W_steer_jo.npy", "steer_jo_bodies.parquet"
    try:
        from flyrun.brain import load_brain
        from flyrun.run import run_episode
        b = load_brain()
        assert b.W.shape == (656, 656) and int(b.masks["JO"].sum()) == 20
        assert pd.Series(b.bodies.type[b.masks["JO"]]).value_counts().to_dict() == {"JO-B1_a": 13, "JO-B1_c": 6, "JO-CA1": 1}
        s, df = run_episode(replace(Knobs(), SENSES_VERSION="v2", MOTOR_VERSION="v2", SENSOR_NOISE=0.0), b, noop_start=0, episode_seed=0, max_frames=500)
        ref = pd.read_csv(Path(__file__).resolve().parent.parent / "runs" / "S3e_full_run.csv").iloc[:500]
        assert (df.x.to_numpy() == ref.x.to_numpy()).all() and (df.a.to_numpy() == ref.a.to_numpy()).all()
    finally:
        del os.environ["FLYRUN_WFILE"], os.environ["FLYRUN_BODIES"]
