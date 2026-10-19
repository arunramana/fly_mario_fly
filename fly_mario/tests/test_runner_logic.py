"""The runner's rules that need no emulator: button priorities, the jump muscle, fly configs."""
import pytest

from fly_mario import registry
from fly_mario.contracts import ButtonIntent, FlyConfig
from fly_mario.runner import (brain_spec, dump_fly, fly_from_dict, fly_to_dict, load_fly, resolve_buttons, resolve_knobs,
                              validate)
from fly_mario.runner import config as C

ACTIONS = registry.list_plugins("actions")
K = {k.key: k.default for a in ACTIONS.values() for k in a.knobs}


def intents(rates, airborne=False, states=None, mods=None, actions=("walk", "steer", "jump", "back_up")):
    states = states if states is not None else {a: {} for a in actions}
    out = []
    for a in actions:
        states[a]["airborne"], states[a]["mods"] = airborne, mods or {}
        out.append(ACTIONS[a].decide(rates, K, states[a]))
    return out


# ---- priorities -----------------------------------------------------------------------------------------
def test_walk_alone_holds_right():
    assert resolve_buttons(intents({"DNp09": 0.2})) == {"right"}


def test_nothing_active_presses_nothing():
    assert resolve_buttons(intents({})) == set()


def test_steer_left_overrides_walk_and_lets_go_of_right():
    assert resolve_buttons(intents({"DNp09": 0.2, "DNa_L": 0.5, "DNa_R": 0.0})) == {"left"}


def test_steer_right_alone_presses_right_without_walking():
    assert resolve_buttons(intents({"DNa_R": 0.5})) == {"right"}


def test_back_up_overrides_walk_and_steering_to_the_right():
    assert resolve_buttons(intents({"DNp09": 0.2, "DNa_R": 0.5, "MDN": 0.5})) == {"left"}


def test_back_up_does_not_touch_the_jump():
    assert resolve_buttons(intents({"TTMn": 0.5, "MDN": 0.5}))  == {"A", "left"}


def test_back_up_stands_down_for_the_rear_gate():
    got = resolve_buttons(intents({"DNp09": 0.2, "MDN": 0.5}, mods={"sour_rear_gate": 1.0}))
    assert got == {"right"}


def test_release_beats_a_press_of_equal_priority():
    a = ButtonIntent(press=frozenset({"A"}), priority=3)
    b = ButtonIntent(release=frozenset({"A"}), priority=3)
    assert resolve_buttons([a, b]) == set() == resolve_buttons([b, a])


def test_a_higher_priority_press_beats_a_lower_release():
    assert resolve_buttons([ButtonIntent(release=frozenset({"A"}), priority=1),
                            ButtonIntent(press=frozenset({"A"}), priority=2)]) == {"A"}


# ---- the jump muscle (the fly holds the button) ---------------------------------------------------------------
def test_jump_presses_holds_releases_and_resets_on_landing():
    jump, st = ACTIONS["jump"], {}
    thr, rel = K["jump.ttmn_thresh"], K["jump.release_thresh"]

    def frame(ttmn, air):
        st["airborne"] = air
        return "A" in jump.decide({"TTMn": ttmn}, K, st).press
    assert not frame(thr * 0.9, False)                    # below the bar: nothing
    assert frame(thr * 1.1, False)                        # press on the ground
    assert frame((thr + rel) / 2, True)                   # held in the air while above the release bar
    assert not frame(rel * 0.5, True) and st["why"] == "loom_faded"
    assert not frame(thr * 2, True)                       # in the air a new press is not allowed
    assert not frame(thr * 2, False)                      # that was the landing frame: A is up for exactly one frame
    assert frame(thr * 2, False)                          # on the ground again: press
    assert frame(thr * 2, True)                           # airborne, still held
    st2 = {}
    st2["airborne"] = False
    jump.decide({"TTMn": thr * 2}, K, st2)
    st2["airborne"] = True
    jump.decide({"TTMn": thr * 2}, K, st2)
    st2["airborne"] = False                               # landing frame: up for exactly one frame
    assert "A" not in jump.decide({"TTMn": thr * 2}, K, st2).press and st2["why"] == "landing_reset"
    assert "A" in jump.decide({"TTMn": thr * 2}, K, st2).press


# ---- fly configs -------------------------------------------------------------------------------------------
@pytest.mark.parametrize("name", ["champion_e1s", "looming_only", "blank"])
def test_shipped_flies_load_and_round_trip(name):
    fly = load_fly(name)
    assert fly.name == name
    assert fly_from_dict(fly_to_dict(fly)) == fly
    import yaml
    assert fly_from_dict(yaml.safe_load(dump_fly(fly))) == fly


def test_champion_attachments():
    fly = load_fly("champion_e1s")
    assert fly.attachments["looming"] == {"goomba", "koopa", "piranha", "pipe", "step", "pit"}
    assert fly.attachments["hearing"] == {"qblock"} and fly.attachments["sweet_smell"] == {"mushroom"}
    assert fly.whole_fly == {"home", "headroom"} and fly.actions == {"walk", "steer", "jump", "back_up"}


def test_the_brain_follows_the_fly():
    assert brain_spec(load_fly("champion_e1s")).mechanisms == ("attraction", "aversion", "escape", "hearing", "walking")
    assert brain_spec(load_fly("looming_only")).mechanisms == ("escape", "walking")       # the 636-neuron base, no extras
    assert "aversion" in brain_spec(load_fly("blank")).mechanisms                          # back_up reads MDN


def test_knobs_resolve_to_defaults_then_the_flys_own():
    k = resolve_knobs(load_fly("champion_e1s"))
    assert k["home.drive"] == load_fly("champion_e1s").knobs["home.drive"]
    assert k["walk.thresh"] == 0.05 and k["loom.eyes"] == 0.0 and k["headroom.clearance"] == 2.0


@pytest.mark.parametrize("change,message", [
    ({"attachments": {"nonsense": ["goomba"]}}, "unknown sense"),
    ({"attachments": {"looming": ["unicorn"]}}, "unknown object"),
    ({"attachments": {"home": ["goomba"]}}, "whole_fly sense"),
    ({"whole_fly": ["looming"]}, "not a whole_fly"),
    ({"actions": ["fly_away"]}, "unknown action"),
    ({"loom_shapes": {"goomba": "blob"}}, "does not exist"),
    ({"knobs": {"no.such": 1.0}}, "unknown knob"),
    ({"knobs": {"home.drive": 99.0}}, "outside its range"),
])
def test_bad_flies_are_refused(change, message):
    d = fly_to_dict(load_fly("blank"))
    d.update(change)
    with pytest.raises(ValueError, match=message):
        validate(fly_from_dict(d))


def test_out_of_range_can_be_allowed_for_sweeps():
    d = fly_to_dict(load_fly("blank"))
    d["knobs"] = {"home.drive": 99.0}
    validate(fly_from_dict(d), strict_range=False)


def test_active_senses_run_in_a_fixed_order():
    names = [s.name for s in C.active_senses(load_fly("champion_e1s"))]
    assert names == ["headroom", "looming", "sour_smell", "hearing", "sweet_smell", "home"]
