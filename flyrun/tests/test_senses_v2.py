"""Part S1: senses v2 on synthetic scenes (pure functions) + v1 stays reproducible."""
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from flyrun import part7, senses_v2 as S
from flyrun.knobs import Knobs

FEET = 176          # Mario on the ground (RAM 0x00CE)
GOOMBA, KOOPA = 0x06, 0x00


def goomba(ex, feet_y=FEET, slot=0, typ=GOOMBA, state=0):
    return (slot, typ, state, ex, feet_y + 8)         # RAM enemy y = feet + 8


def pick(enemies=(), walls=(), pits=(), mx=0, feet=FEET, **kw):
    return S.choose(mx, feet, list(enemies), list(walls), list(pits), **kw)


def test_two_d_distance_smaller_theta_when_above():
    same = pick([goomba(12 + 40)])                     # gap_x 40 at Mario's height
    above = pick([goomba(12 + 40, feet_y=FEET - 48)])  # same x, 48 px higher
    assert same.d == 40 and above.d == pytest.approx(np.hypot(40, 32))
    assert above.theta < same.theta


def test_koopa_looms_more_than_goomba():
    g, k = pick([goomba(52)]), pick([goomba(52, typ=KOOPA)])
    assert (g.kind, k.kind) == ("goomba", "koopa") and k.theta > g.theta


def test_dead_unknown_and_behind_enemies_are_ignored():
    assert pick([goomba(52, state=4)]) is None                 # stomped
    assert pick([goomba(52, state=0x22)]) is None              # defeated, falling
    assert pick([goomba(52, typ=0x31)]) is None                # unknown type byte
    assert pick([goomba(-30)], mx=0) is None                   # behind
    assert pick([goomba(52)], enemy_input=False) is None       # silence control switch


def test_face_height_is_above_feet():
    pipe = [(64, 32)]                                  # pipe column, top at y 144
    on_ground = pick(walls=pipe)
    assert on_ground.kind == "face" and on_ground.h == 32 and on_ground.theta > 0
    feet_above_top = pick(walls=pipe, feet=136)        # feet 8 px above the pipe top
    assert feet_above_top is None                      # face height floored at 0 -> no threat -> theta 0


def test_step_face_is_16_relative_to_where_he_stands():
    walls = [(0, 16), (16, 32)]                        # step 1 under Mario, step 2 ahead
    t = pick(walls=walls, mx=4, feet=160)
    assert t.kind == "face" and t.h == 16 and t.ident == ("face", 16)


def test_pit_tiles_are_individual_threats():
    pit = [(96, 32)]
    t = pick(pits=pit, mx=40)
    assert t.kind == "pit" and t.ident == ("pit", 96) and t.h == 16 and t.d == 96 - 52
    t2 = pick(pits=pit, mx=100)                        # S2b (B9): the tile under his footprint is still the threat, d 0
    assert t2.ident == ("pit", 96) and t2.d == 0.0
    t3 = pick(pits=pit, mx=116)                        # tile 96 is fully behind his left edge now; 112 is under him
    assert t3.ident == ("pit", 112)
    assert pick(pits=[], mx=40) is None                # floor all the way ahead: no pit threat


def test_nearest_threat_only_no_sum():
    t = pick([goomba(100), goomba(60, slot=1)], walls=[(200, 32)])
    assert t.ident == ("enemy", 1)


def masks(K=6):
    m = {n: np.zeros(K, bool) for n in ("LC4_R", "LPLC2_R", "LC10a_R")}
    for i, n in enumerate(m):
        m[n][i] = True
    return m


def test_dtheta_is_zero_at_target_switch():
    se = S.SensesV2(Knobs(), masks(), 6)
    a1 = S.Threat("goomba", ("enemy", 0), 100, 160, 16, 16, d=60, theta=0.2)
    a2 = S.Threat("goomba", ("enemy", 0), 90, 160, 16, 16, d=50, theta=0.3)
    b = S.Threat("goomba", ("enemy", 1), 80, 160, 16, 16, d=40, theta=0.5)
    se.from_threat(a1)
    _, l2 = se.from_threat(a2)
    assert l2.dtheta == pytest.approx(0.1)
    _, l3 = se.from_threat(b)                          # switch
    assert l3.dtheta == 0.0
    I, l4 = se.from_threat(S.Threat("goomba", ("enemy", 1), 70, 160, 16, 16, d=30, theta=0.7))
    assert l4.dtheta == pytest.approx(0.2) and I[1] == pytest.approx(0.7) and I[0] == pytest.approx(0.2)


def test_threat_reaches_the_left_right_detectors_only_via_R_inputs():
    # the v2 eye feeds LC4_R / LPLC2_R / LC10a_R exactly like v1 (steering inputs unchanged)
    se = S.SensesV2(replace(Knobs(), HOME_R=0.5), masks(), 6)
    I, _ = se.from_threat(None)
    assert list(I) == [0, 0, 0.5, 0, 0, 0]


def test_default_is_v1_and_v1_reproduces_7e_logged_max_x():
    assert Knobs().SENSES_VERSION == "v1"
    root = Path(__file__).resolve().parent.parent
    cfg = part7.load_config(root / "configs" / "part7.yaml")
    g = json.loads((root / "runs" / "008e_final_genome.json").read_text(encoding="utf-8"))
    kn, _ = part7.decode(cfg, g["u"])
    logged = json.loads((root / "runs" / "008e_holdout.json").read_text(encoding="utf-8"))["final"]["episodes"][0]
    from flyrun.brain import load_brain
    from flyrun.run import run_episode
    ep = cfg["episodes"]["holdout"][0]
    s, _ = run_episode(replace(kn, SENSOR_NOISE=ep["sigma"]), load_brain(), noop_start=ep["noop_start"],
                       episode_seed=ep["seed"], stuck_frames=150)
    assert s["max_x"] == logged["max_x"] == 1532


def test_v2_episode_runs_and_logs_the_chosen_threat():
    from flyrun.brain import load_brain
    from flyrun.run import run_episode
    s, df = run_episode(replace(Knobs(), SENSES_VERSION="v2", SENSOR_NOISE=0.0), load_brain(), max_frames=200)
    assert {"threat_kind", "threat_id", "box"} <= set(df.columns)
    assert set(df.threat_kind.dropna()) <= {"goomba", "koopa", "shell", "face", "pit", "none"}


# ---------------------------------------------------------------- S2b: face rule (B6/B8) and pit-below rule (B9)
@pytest.mark.parametrize("H", [32, 64])
def test_face_height_constant_while_rising_until_feet_clear_the_top(H):
    top = FEET - H
    pipe = [(64, H)]
    for feet in range(FEET, top, -1):                  # every frame of the rise, feet below the top
        t = pick(walls=pipe, mx=40, feet=feet, ground=FEET)
        assert t.kind == "face" and t.h == H, feet
    assert pick(walls=pipe, mx=40, feet=top, ground=FEET) is None        # feet level with / above the top: a step, face height 0
    assert pick(walls=pipe, mx=40, feet=top - 12, ground=FEET) is None


def test_step_face_stays_16_until_feet_clear_the_next_step():
    walls = [(0, 16), (16, 32)]                        # standing on step 1 (feet 160); step 2 top at 144
    assert pick(walls=walls, mx=4, feet=160, ground=160).h == 16
    for feet in range(160, 144, -1):
        assert pick(walls=walls, mx=4, feet=feet, ground=160).h == 16
    assert pick(walls=walls, mx=4, feet=144, ground=160) is None


def test_airborne_over_a_32px_gap_the_pit_under_him_is_the_threat_every_frame():
    pit = [(96, 32)]
    for mx in range(84, 128):                          # from the take-off to just before his left edge passes the far edge
        t = pick([goomba(mx + 150)], pits=pit, mx=mx, feet=140, ground=FEET)
        assert t.kind == "pit", mx                     # never a far Goomba mid-gap
        if mx > 84:
            assert t.d == 0.0 or t.x >= mx
    t = pick([goomba(128 + 150)], pits=pit, mx=128, feet=140, ground=FEET)
    assert t.kind == "goomba"                          # past the far edge: the pit threat is over


def test_senses_tracks_the_take_off_ground():
    se = S.SensesV2(Knobs(), masks(), 6)
    se.read_ram = lambda ram: (40, ram["feet"], [], [(64, 32)], [])
    for feet, air, want in [(176, 0, 32), (160, 1, 32), (146, 1, 32), (140, 1, None)]:
        I, lm = se.look({0x001D: air, "feet": feet})
        assert (lm.extra["box"][3] if lm.extra["box"] else None) == want, (feet, air)
