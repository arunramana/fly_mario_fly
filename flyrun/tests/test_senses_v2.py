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


TRIGGER_DEG = 43.6          # the real fly's measured trigger angle (S3: runs/S3_robustness.md)


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
    feet_above_top = pick(walls=pipe, mx=56, feet=136, ground=FEET)   # feet 8 px above the pipe top AND over it (S2c)
    assert feet_above_top is None                      # face height 0 -> no threat -> theta 0


def test_step_face_is_16_relative_to_where_he_stands():
    walls = [(0, 16), (16, 32)]                        # step 1 under Mario, step 2 ahead
    t = pick(walls=walls, mx=4, feet=160)
    assert t.kind == "face" and t.h == 16 and t.ident == ("face", 16)


def test_pit_is_the_hole_with_its_true_angular_size():
    pit = [(96, 32)]
    t = pick(pits=pit, mx=40)                          # S3 0b: ONE threat, the hole: near edge -> far edge, one tile deep at floor level
    assert t.kind == "pit" and t.ident == ("pit", 96) and (t.x, t.top, t.w, t.h) == (96, 176, 32, 16)
    assert t.d == 96 - 52
    assert t.theta == pytest.approx(S.hole_theta(40, FEET, 96, 32))
    assert pick(pits=pit, mx=100).kind == "pit"        # under him
    assert pick(pits=pit, mx=127).kind == "pit"        # body not yet past the far edge
    assert pick(pits=pit, mx=128) is None              # body past the far edge: over
    assert pick(pits=[], mx=40) is None                # floor all the way ahead: no pit threat


def test_hole_theta_is_the_angle_the_rectangle_covers_from_the_eye():
    # eye = (mx + 12, feet - 16) = (52, 160); hole x 96..128, y 176..192. Corner directions: near-top, near-bottom, far-top, far-bottom
    ex, ey = 52, FEET - 16
    ang = [np.arctan2(cy - ey, cx - ex) for cx in (96, 128) for cy in (176, 192)]
    assert S.hole_theta(40, FEET, 96, 32) == pytest.approx(max(ang) - min(ang))
    assert S.hole_theta(40, FEET, 96, 32) < S.hole_theta(60, FEET, 96, 32)   # nearer = larger


def test_on_foot_hole_theta_crosses_the_trigger_angle_within_24px_of_the_edge():
    """Report: the distance from his front edge to the near edge where theta first reaches the real fly's trigger angle (43.6 deg)."""
    trig = np.radians(TRIGGER_DEG)
    dist = next(g for g in range(60, -1, -1) if S.hole_theta(100, FEET, 100 + 12 + g, 32) >= trig)
    print("trigger crossing at", dist, "px")
    assert dist <= 24
    assert dist == 17


@pytest.mark.xfail(strict=True, reason="S3 geometry: with the eye at the top-front corner, airborne over a 32 px hole theta is ~23 deg < the 43.6 deg trigger "
                                       "(the hole is far below and behind-below the eye). Reported in runs/S3_robustness.md; the rule is not changed.")
def test_airborne_over_the_gap_theta_stays_above_the_trigger_until_past_the_far_edge():
    trig = np.radians(TRIGGER_DEG)
    for mx in range(84, 128):
        t = pick(pits=[(96, 32)], mx=mx, feet=FEET - 60, ground=FEET)
        assert t.kind == "pit" and t.theta >= trig, mx


def test_airborne_over_the_gap_the_pit_is_the_chosen_threat_until_past_the_far_edge():
    pit = [(96, 32)]
    for mx in range(84, 128):
        assert pick([goomba(mx + 150)], pits=pit, mx=mx, feet=FEET - 60, ground=FEET).kind == "pit", mx
    assert pick([goomba(128 + 150)], pits=pit, mx=128, feet=FEET - 60, ground=FEET).kind == "goomba"


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
    # S2c: feet level with / above the top but NOT yet over the face -> still the full height
    assert pick(walls=pipe, mx=40, feet=top, ground=FEET).h == H
    assert pick(walls=pipe, mx=40, feet=top - 12, ground=FEET).h == H
    assert pick(walls=pipe, mx=56, feet=top, ground=FEET) is None        # over it as well: a step, face height 0
    assert pick(walls=pipe, mx=56, feet=top - 12, ground=FEET) is None


def test_step_face_stays_16_until_feet_clear_the_next_step():
    walls = [(0, 16), (16, 32)]                        # standing on step 1 (feet 160); step 2 top at 144
    assert pick(walls=walls, mx=4, feet=160, ground=160).h == 16
    for feet in range(160, 144, -1):
        assert pick(walls=walls, mx=4, feet=feet, ground=160).h == 16
    assert pick(walls=walls, mx=4, feet=144, ground=160).h == 16     # S2c: feet at the top but not over step 2 yet
    assert pick(walls=walls, mx=8, feet=144, ground=160) is None     # over it too


def test_senses_tracks_the_take_off_ground():
    se = S.SensesV2(Knobs(), masks(), 6)
    se.read_ram = lambda ram: (40, ram["feet"], [], [(64, 32)], [])
    for feet, air, want in [(176, 0, 32), (160, 1, 32), (146, 1, 32), (140, 1, 32)]:     # S2c: not over the pipe yet
        I, lm = se.look({0x001D: air, "feet": feet})
        assert (lm.extra["box"][3] if lm.extra["box"] else None) == want, (feet, air)


# ---------------------------------------------------------------- S2c: face "above AND over", pit virtual wall (B6 / B9)
def test_pipe_48_above_but_not_over_keeps_full_height_over_it_is_zero():
    pipe = [(64, 48)]                                   # top at y 128
    assert pick(walls=pipe, mx=40, feet=120, ground=FEET).h == 48     # feet above the top, body not over: still 48
    assert pick(walls=pipe, mx=50, feet=120, ground=FEET).h == 48     # mx + 12 = 62 < 64: still not over
    assert pick(walls=pipe, mx=53, feet=120, ground=FEET) is None     # body overlaps column 64: over -> 0
    assert pick(walls=pipe, mx=60, feet=120, ground=FEET) is None


def test_two_column_pipe_is_one_face_over_means_over_either_column():
    pipe = [(64, 48), (80, 48)]
    assert pick(walls=pipe, mx=70, feet=120, ground=FEET) is None     # over the pipe (columns 64-96)
    t = pick(walls=pipe, mx=40, feet=120, ground=FEET)
    assert t.ident == ("face", 64) and t.w == 32 and t.h == 48


# ---------------------------------------------------------------- S3 0a: rim tiles
def _ram_with_pipe(rim, x=912):
    from flyrun import level
    ram = np.zeros(0x800, dtype=np.uint8)
    page, col = x // 256, (x % 256) // 16
    for c, (top, body) in enumerate(((rim[0], 20), (rim[1], 21))):
        base = level.BUF + level.PAGE_BYTES * (page % 2) + col + c
        ram[base + 16 * 7] = top
        for r in (8, 9, 10):
            ram[base + 16 * r] = body
        ram[base + 16 * 11] = ram[base + 16 * 12] = 84
    ram[0x071A], ram[0x071C] = x // 256, 0
    return ram


def test_rim_tiles_16_17_make_pipe_4_read_64px_in_v2_only():
    from flyrun import level
    ram = _ram_with_pipe((16, 17))
    assert level.scan_visible(ram, rim=True)[0] == [(912, 64), (928, 64)]
    assert level.scan_visible(ram)[0] == [(912, 48), (928, 48)]              # v1 reads are unchanged
    assert level.scan_visible(_ram_with_pipe((18, 19)), rim=True)[0] == [(912, 64), (928, 64)]   # pipes 1-3 unchanged
