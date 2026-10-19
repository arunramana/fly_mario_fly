"""What each sense does with a hand-built frame: the rules from the old tool, one at a time."""
import math

import numpy as np
import pytest

from fly_mario import registry
from fly_mario.contracts import Box, MarioState, ObjectInstance
from fly_mario.mario.facts import load_facts
from fly_mario.senses.kit.geom import theta_of
from fly_mario.senses.kit.memory import SenseMemory

FACTS = load_facts("1-1")
SENSES = registry.list_plugins("senses")
KNOBS = {k.key: k.default for c in list(SENSES.values()) + list(registry.list_plugins("actions").values())
         + list(registry.list_plugins("shapes").values()) for k in c.knobs}


def mario(x=100.0, feet=176.0, airborne=False, h=16.0):
    return MarioState(x=x, y=feet - h, w=12.0, h=h, airborne=airborne, power="small", facing=1)


def enemy(slot, x, kind="goomba", top=160.0, h=16.0, **state):
    return ObjectInstance(kind, slot, Box(x, top, 16, h), "ahead", {"slot": slot, "shell": False, **state})


def pipe(x=200, height=32):
    return ObjectInstance("pipe", x, Box(x, 176 - height, 32, height), "ahead")


def pit(x=200, w=32):
    return ObjectInstance("pit", x, Box(x, 176, w, 32), "ahead", {"open": False})


def brick(x, y):
    return ObjectInstance("brick", x, Box(x, y, 16, 16), "ahead", {"tile": 81, "row": int(y // 16)})


def cue(sense, objs, m, mem=None, world=None, mods=None, knobs=None, **kw):
    mem = SenseMemory() if mem is None else mem
    mem.world = list(objs if world is None else world)
    mem.mods = mods if mods is not None else {}
    return SENSES[sense].cue(list(objs), m, FACTS, {**KNOBS, **(knobs or {})}, mem)


# ---- looming ------------------------------------------------------------------------------------------
def test_goomba_drives_lplc2_with_theta_and_lc4_with_the_change():
    mem = SenseMemory()
    g1 = enemy(0, 152)                                    # Mario's right edge is 112: gap 40
    out1 = cue("looming", [g1], mario(), mem)
    assert out1.inputs["LPLC2_R"] == pytest.approx(theta_of(40, 16))
    assert out1.inputs["LC4_R"] == 0.0                    # a new target: no change to report
    out2 = cue("looming", [enemy(0, 142)], mario(), mem)  # same slot, 10 px closer
    assert out2.inputs["LC4_R"] == pytest.approx(theta_of(30, 16) - theta_of(40, 16))


def test_only_the_right_eye_unless_both_are_asked_for():
    out = cue("looming", [enemy(0, 152)], mario())
    assert set(out.inputs) == {"LC4_R", "LPLC2_R"}
    both = cue("looming", [enemy(0, 152)], mario(), knobs={"loom.eyes": 1.0})
    assert set(both.inputs) == {"LC4_R", "LPLC2_R", "LC4_L", "LPLC2_L"}
    assert both.inputs["LPLC2_L"] == both.inputs["LPLC2_R"]


def test_the_nearer_creature_wins_and_a_switch_gives_no_change():
    mem = SenseMemory()
    cue("looming", [enemy(0, 152)], mario(), mem)
    out = cue("looming", [enemy(0, 152), enemy(1, 130)], mario(), mem)       # a nearer one appears
    assert out.inputs["LPLC2_R"] == pytest.approx(theta_of(18, 16))
    assert out.inputs["LC4_R"] == 0.0


def test_a_creature_behind_does_not_loom():
    assert cue("looming", [enemy(0, 40)], mario()).inputs["LPLC2_R"] == 0.0


def test_cleared_creature_hands_over_to_the_next_threat_until_landing():
    mem = SenseMemory()
    far = enemy(1, 200)
    over_it = enemy(0, 100, top=160)                      # right under Mario
    up = mario(feet=158, airborne=True)                   # his feet are above its top (160) with his body over it
    out = cue("looming", [over_it, far], up, mem)
    assert out.inputs["LPLC2_R"] == pytest.approx(theta_of(math.hypot(200 - 112, 2), 16))          # the far one took over (2 px below his feet)
    assert ("slot", 0) in mem["cleared"]
    down = mario(feet=176, airborne=False)
    cue("looming", [far], down, mem)
    assert not mem["cleared"]                              # landing forgets it


def test_wall_looms_from_the_take_off_ground_and_stops_when_stood_on():
    w = pipe(200, 32)
    out = cue("looming", [w], mario())
    assert out.inputs["LPLC2_R"] == pytest.approx(theta_of(200 - 112, 32))
    mem = SenseMemory()
    cue("looming", [w], mario(), mem)                       # on the floor: take-off ground 176
    on_top = mario(x=205.0, feet=144.0, airborne=True)       # feet at the top, body over it
    assert cue("looming", [w], on_top, mem).inputs["LPLC2_R"] == 0.0
    high = mario(x=150.0, feet=120.0, airborne=True)         # in the air short of it: still the full 32 from the ground he left
    assert cue("looming", [w], high, mem).inputs["LPLC2_R"] == pytest.approx(
        theta_of(math.hypot(200 - 162, 144 - 120), 32))


def test_only_the_nearest_rising_wall_is_a_candidate():
    near, far = pipe(200, 16), pipe(260, 64)
    out = cue("looming", [far, near], mario())
    assert out.inputs["LPLC2_R"] == pytest.approx(theta_of(200 - 112, 16))


def test_a_block_in_the_air_is_not_a_wall():
    b = ObjectInstance("brick", 1, Box(200, 112, 16, 16), "ahead", {"tile": 81})
    out = cue("looming", [b], mario())
    assert out.inputs["LPLC2_R"] == pytest.approx(theta_of(math.hypot(200 - 112, 32), 16))   # its own 16 px box, 32 px above his head


def test_pit_tower_looms_and_a_released_pit_holds_the_channel_at_zero():
    p = pit(200, 32)
    mem = SenseMemory()
    out = cue("looming", [p], mario(), mem)
    assert out.inputs["LPLC2_R"] > 0
    flying = mario(x=222.0, feet=100.0, airborne=True)        # his body reaches the tower columns 232..248, feet above its top
    far_goomba = enemy(3, 300)
    out2 = cue("looming", [p, far_goomba], flying, mem)
    assert out2.inputs["LPLC2_R"] == 0.0 and any(i.line == "dashed" for i in out2.overlay)
    assert ("pit", 200) in mem["released"]
    out3 = cue("looming", [p, far_goomba], mario(x=205.0, feet=140.0, airborne=True), mem)
    assert out3.inputs["LPLC2_R"] == 0.0                      # stays released until landing, the far Goomba does not leak in


def test_headroom_quiets_a_creature_under_a_low_ceiling():
    g = enemy(0, 152)
    ceiling = brick(120, 144)                                # underside at 160 = exactly his head: no room at all
    plain = cue("looming", [g], mario(), world=[g, ceiling])
    mods = {"headroom": 1.0, "headroom_clearance": 2.0}
    quiet = cue("looming", [g], mario(), world=[g, ceiling], mods=mods)
    assert quiet.inputs["LPLC2_R"] == 0.0 < plain.inputs["LPLC2_R"]
    roomy = cue("looming", [g], mario(), world=[g], mods=mods)
    assert roomy.inputs["LPLC2_R"] == pytest.approx(plain.inputs["LPLC2_R"])      # a clear sky leaves it alone
    partial = cue("looming", [g], mario(), world=[g, brick(120, 112)], mods=mods)  # underside 128: 32 px of rise vs 18 needed
    assert partial.inputs["LPLC2_R"] == pytest.approx(plain.inputs["LPLC2_R"])
    low = cue("looming", [g], mario(), world=[g, brick(120, 128)], mods=mods)       # underside 144: 16 px of rise vs 18 needed
    assert low.inputs["LPLC2_R"] == pytest.approx(plain.inputs["LPLC2_R"] * 16 / 18)


def test_rear_eye_lets_a_closing_enemy_behind_loom_but_not_a_receding_one():
    m = mario()
    behind = lambda x: enemy(0, x, top=160)
    mem = SenseMemory()
    on = {"rear_eye": 1.0}
    assert cue("looming", [behind(60)], m, mem, mods=on).inputs["LPLC2_R"] == 0.0           # first sight: no history
    closing = cue("looming", [behind(70)], m, mem, mods=on)                                   # gap 100-86 -> 100-76... shrinking
    assert closing.inputs["LPLC2_R"] > 0
    receding = cue("looming", [behind(60)], m, mem, mods=on)
    assert receding.inputs["LPLC2_R"] == 0.0
    off = cue("looming", [behind(75)], m, SenseMemory(), mods={})
    assert off.inputs["LPLC2_R"] == 0.0


def test_noise_draws_two_numbers_per_frame_only_when_sigma_is_set():
    mem = SenseMemory()
    mem.rng, mem.sigma = np.random.default_rng(5), 0.0
    cue("looming", [enemy(0, 152)], mario(), mem)
    assert mem.rng.bit_generator.state == np.random.default_rng(5).bit_generator.state     # nothing drawn
    mem.sigma = 0.05
    out = SENSES["looming"].cue([enemy(0, 152)], mario(), FACTS, KNOBS, mem)
    ref = np.random.default_rng(5)
    n1, n2 = ref.standard_normal(), ref.standard_normal()
    assert out.inputs["LC4_R"] == 0.0 * (1 + 0.05 * n1)
    assert out.inputs["LPLC2_R"] == theta_of(40, 16) * (1 + 0.05 * n2)


# ---- smells and hum -----------------------------------------------------------------------------------
def test_sour_smell_is_gain_times_theta_for_both_antennae_and_skips_shells_and_the_cleared():
    g = enemy(0, 152)
    out = cue("sour_smell", [g], mario(), knobs={"sour_smell.gain": 5.0})
    assert out.inputs == {"DC4_L": pytest.approx(5.0 * theta_of(40, 16)), "DC4_R": pytest.approx(5.0 * theta_of(40, 16))}
    shell = enemy(0, 152, kind="koopa", h=16.0, shell=True)
    assert cue("sour_smell", [shell], mario()).inputs["DC4_L"] == 0.0
    mem = SenseMemory()
    cue("sour_smell", [enemy(0, 100, top=160)], mario(feet=158, airborne=True), mem)
    assert cue("sour_smell", [enemy(0, 100, top=160)], mario(feet=150, airborne=True), mem).inputs["DC4_L"] == 0.0


def test_sour_rear_is_honest_by_default_and_can_be_gated():
    behind = enemy(0, 60)
    assert cue("sour_smell", [behind], mario()).inputs["DC4_L"] == 0.0
    honest = cue("sour_smell", [behind], mario(), knobs={"sour_smell.rear": 1.0})
    assert honest.inputs["DC4_L"] > 0 and not honest.modifiers
    gated = cue("sour_smell", [behind], mario(), knobs={"sour_smell.rear": 1.0, "sour_smell.rear_gated": 1.0})
    assert gated.modifiers == {"sour_rear_gate": 1.0}


def test_hum_only_from_reachable_blocks_ahead():
    q = lambda y, x=140: ObjectInstance("qblock", x, Box(x, y, 16, 16), "ahead", {"tile": 192, "row": int(y // 16)})
    assert cue("hearing", [q(112)], mario()).inputs["JO"] > 0                    # underside 128: 48 above the floor
    assert cue("hearing", [q(80)], mario()).inputs["JO"] == 0.0                  # underside 96: 80 > 64, out of reach
    assert cue("hearing", [q(112, x=60)], mario()).inputs["JO"] == 0.0           # fully behind him
    near, far = q(112, 130), q(112, 200)
    d = math.hypot(112 - (130 + 8), (176 - 16 - 0) - 128)
    out = cue("hearing", [far, near], mario(), knobs={"hearing.gain": 10.0})
    assert out.inputs["JO"] == pytest.approx(10.0 * theta_of(d, 16))


def test_sweet_smell_goes_to_the_antenna_on_the_objects_side():
    m = ObjectInstance("mushroom", 5, Box(60, 160, 16, 16), "behind", {"slot": 5})
    left = cue("sweet_smell", [m], mario())
    assert left.inputs["ORN_L"] > 0 and left.inputs["ORN_R"] == 0.0
    right = cue("sweet_smell", [ObjectInstance("mushroom", 5, Box(160, 160, 16, 16), "ahead", {"slot": 5})], mario())
    assert right.inputs["ORN_R"] > 0 and right.inputs["ORN_L"] == 0.0


def test_a_smell_works_on_any_object_type():
    for t in ("goomba", "pipe", "pit", "brick"):
        o = ObjectInstance(t, 1, Box(160, 160, 16, 16), "ahead", {"slot": 1})
        assert cue("sweet_smell", [o], mario()).inputs["ORN_R"] > 0


def test_home_is_a_constant_drive_into_lc10a_right():
    out = cue("home", [], mario(), knobs={"home.drive": 0.3})
    assert out.inputs == {"LC10a_R": 0.3}


def test_colour_language():
    assert SENSES["looming"].colour != SENSES["sour_smell"].colour != SENSES["hearing"].colour
    assert SENSES["sour_smell"].line == "dotted" and SENSES["hearing"].colour == SENSES["sweet_smell"].colour
    assert SENSES["home"].colour == "#ffffff"
