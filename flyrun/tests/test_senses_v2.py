"""Part S1: senses v2 on synthetic scenes (pure functions) + v1 stays reproducible."""
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from flyrun import part7, senses_v2 as S
from flyrun.knobs import MAX_JUMP_HEIGHT, Knobs

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


def test_pit_is_a_base_plus_a_tower():
    pit = [(96, 32)]
    t = pick(pits=pit, mx=40)                          # S3c (B9): tower 16 px wide on the FAR edge (x 128..144), height = W
    assert t.kind == "pit" and t.ident == ("pit", 96) and (t.x, t.top, t.w, t.h) == (128, 176 - 32, 16, 32)
    assert t.base == (96, 176, 32, 16)
    assert t.d == 128 - 52 and t.theta == pytest.approx(S.theta_of(76, 32))      # the pipe-face height rule on the tower
    assert t.dsel == 96 - 52                           # it competes with other threats by the gap to the base
    assert pick(pits=pit, mx=100).kind == "pit"        # under him
    assert pick(pits=pit, mx=127).kind == "pit"        # body not yet past the far edge
    assert pick(pits=pit, mx=128) is None              # body past the far edge: over
    assert pick(pits=[], mx=40) is None                # floor all the way ahead: no pit threat


def test_tower_height_is_W_capped_at_max_jump_height():
    for W, want in ((32, 32), (48, 48), (64, 64), (80, MAX_JUMP_HEIGHT), (160, MAX_JUMP_HEIGHT)):
        assert pick(pits=[(300, W)], mx=40).h == want, W


def _onset_distance(W):
    """Distance from his front edge to the pit's NEAR edge where theta first reaches the trigger angle, on foot."""
    trig = np.radians(TRIGGER_DEG)
    return next(g for g in range(200, -1, -1) if pick(pits=[(100 + 12 + g, W)], mx=100).theta >= trig)


def test_on_foot_trigger_fires_within_12px_of_quarter_W_plus_8_on_every_1_1_pit():
    import csv
    rows = [(int(r["x"]), int(r["size"])) for r in csv.DictReader(open(Path(__file__).resolve().parent.parent / "runs" / "001_level_map.csv")) if r["kind"] == "pit"]
    assert [w for _, w in rows] == [32, 48, 32]
    for px, W in rows:
        g = _onset_distance(W)
        print("pit", px, "W", W, "trigger at", g, "px before the near edge; 0.25 W + 8 =", 0.25 * W + 8)
        assert abs(g - (0.25 * W + 8)) <= 12, (px, W, g)
        assert g == {32: 8, 48: 12}[W]


PIT3_WALLS = [(2400, 48), (2416, 64), (2432, 64), (2480, 64), (2496, 48), (2512, 32), (2528, 16)]   # 1-1: the staircase, pit 3 (2448, W 32), the staircase


def test_pit_3_from_the_top_step_trigger_fires_within_12px_of_quarter_W_plus_8():
    """S3d: he stands on the 64 px step (feet 112); the tower is anchored to the highest rim (112), not the floor."""
    trig = np.radians(TRIGGER_DEG)
    t = pick(walls=PIT3_WALLS, pits=[(2448, 32)], mx=2420, feet=112, ground=112)
    assert t.kind == "pit" and (t.top, t.h) == (112 - 32, 32)
    mx = next(m for m in range(2300, 2437) if pick(walls=PIT3_WALLS, pits=[(2448, 32)], mx=m, feet=112, ground=112).theta >= trig)
    g = 2448 - (mx + 12)
    print("pit 3 trigger at", g, "px before the near edge; 0.25 W + 8 =", 0.25 * 32 + 8)
    assert abs(g - (0.25 * 32 + 8)) <= 12 and g == 8


def test_tower_is_anchored_to_the_highest_rim():
    pit = [(96, 32)]                                   # near rim = floor (176); far rim column x 128 is 32 px high -> y 144
    walls = [(128, 32)]
    t = pick(walls=walls, pits=pit, mx=40, ground=FEET)
    assert t.rims[:2] == (176, 144) and t.top == 144 - 32 and t.h == FEET - (144 - 32)   # measured from the far rim (the higher one)
    walls = [(80, 48)]                                 # now the NEAR rim (column 80) is the higher one: y 128
    t = pick(walls=walls, pits=pit, mx=40, ground=FEET, pipe_sense=False)     # (the rim column's own face would win otherwise)
    assert t.rims[:2] == (128, 176) and t.top == 128 - 32
    assert pick(pits=pit, mx=40).top == 176 - 32       # no raised rim: the floor, as in S3c (pits 1 and 2 unchanged)


def test_airborne_the_tower_is_the_chosen_threat_until_the_release_rule_fires():
    pit = [(96, 32)]                                   # base x 96..128, tower x 128..144, top 144
    for feet in range(FEET, 144, -1):                  # rising, feet below the tower top: full height from the take-off ground
        t = pick([goomba(60 + 150)], pits=pit, mx=60, feet=feet, ground=FEET)
        assert t.kind == "pit" and t.h == 32, feet
    t = pick(pits=pit, mx=100, feet=130, ground=FEET)  # feet above the top but not over the tower (mx + 12 = 112 < 128): still the full tower
    assert t.kind == "pit" and t.h == 32
    t = pick(pits=pit, mx=117, feet=144, ground=FEET)  # feet level with the top AND over it (mx + 12 = 129 > 128): released
    assert t.kind == "pit" and t.h == 0 and t.theta == 0.0
    t = pick([goomba(127 + 150)], pits=pit, mx=117, feet=100, ground=FEET)   # released: the pit (base) is still THE threat, theta 0
    assert t.kind == "pit" and t.theta == 0.0
    assert pick([goomba(128 + 150)], pits=pit, mx=128, feet=100, ground=FEET).kind == "goomba"   # past the far edge


def test_released_tower_does_not_reappear_until_landing():
    se = S.SensesV2(Knobs(), masks(), 6)
    st = {}
    se.read_ram = lambda ram: (st["mx"], ram["feet"], [], [], [(96, 32)])
    def look(mx, feet, air):
        st["mx"] = mx
        return se.look({0x001D: air, "feet": feet})[1].extra["box"][3]
    assert look(60, 176, 0) == 32                       # on the ground: full tower
    assert look(100, 150, 1) == 32                      # rising, not over it
    assert look(117, 144, 1) == 0                       # feet at the top AND over it: released
    assert look(118, 150, 1) == 0                       # falling below the top while still over it: stays released (S3b flickered to 32 here)
    assert look(119, 170, 1) == 0
    assert look(120, 176, 0) == 32                      # landing reset: a new tower for the next jump


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
