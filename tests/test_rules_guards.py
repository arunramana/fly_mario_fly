"""Runtime guards: weights are read-only, neurons cannot be fired directly, actions and senses stay inside their declarations."""
import os
from dataclasses import replace

import numpy as np
import pytest

from fly_mario_fly.contracts import ButtonIntent, Scene
from fly_mario_fly.fly.brain import Brain, allowed_input_groups
from fly_mario_fly.fly.spec import BrainSpec
from fly_mario_fly.rules import guards as G
from fly_mario_fly.rules.lookup import _modules, declaration_of


def toy_brain():
    types = ["LC4", "LC4", "LPLC2", "DNp01", "TTMn"]
    sides = ["L", "R", "R", "", ""]
    W = np.array([[0.0, 0.2, 0.0, 0.0, 0.0],
                  [0.2, 0.0, 0.0, 0.0, 0.0],
                  [0.0, 0.0, 0.0, 0.0, 0.0],
                  [0.5, 0.5, 0.0, 0.0, 0.0],
                  [0.0, 0.0, 0.0, 1.0, 0.0]])
    return Brain(BrainSpec(), W, [1, 2, 3, 4, 5], types, sides, np.ones(5))


# ---- N1: weights are read-only -------------------------------------------------------------------------------------

def test_the_weights_cannot_be_written():
    b = toy_brain()
    with pytest.raises(ValueError, match="read-only"):
        b.W[0, 1] = 5.0
    with pytest.raises(ValueError):
        b.W *= 2
    with pytest.raises(AttributeError):
        b.W = np.zeros((5, 5))


def test_the_brain_keeps_its_own_copy_of_the_weights():
    W = np.eye(3)
    b = Brain(BrainSpec(), W, [1, 2, 3], ["LC4"] * 3, ["L"] * 3, np.ones(3))
    W[0, 0] = 99.0                                    # the caller's array is theirs; the brain is not affected
    assert b.W[0, 0] == 1.0 and W.flags.writeable


def test_a_copy_of_the_weights_is_free_to_experiment_on():
    b = toy_brain()
    c = b.W.copy()
    c[0, 1] = 0.0
    assert c[0, 1] == 0.0 and b.W[0, 1] == 0.2


def test_forcing_the_buffer_writable_is_caught_by_the_fingerprint():
    b = toy_brain()
    b.verify_weights()
    b.W.setflags(write=True)                          # going out of the way to defeat the read-only flag...
    b.W[0, 1] = 5.0
    with pytest.raises(G.RuleViolation, match="read-only"):
        b.verify_weights()                            # ...is still caught, and the runner checks this at the end of a run


# ---- N2: no firing neurons directly --------------------------------------------------------------------------------

def test_only_input_groups_can_be_driven():
    b = toy_brain()
    assert "LPLC2_R" in allowed_input_groups() and "DNp01" not in allowed_input_groups()
    b.drive({"LPLC2_R": 0.3, "LC4_R": 0.1})
    for group in ("DNp01", "TTMn"):
        with pytest.raises(G.RuleViolation, match="cannot|only be read|not an input group"):
            b.drive({group: 1.0})


def test_a_raw_input_vector_cannot_fire_a_descending_neuron():
    b = toy_brain()
    h = b.new_state()
    b.advance(h, b.drive({"LC4_R": 0.5}))             # the normal path works
    I = np.zeros(b.n)
    I[3] = 1.0                                        # DNp01, the Giant Fiber
    with pytest.raises(G.RuleViolation, match="not in any input group"):
        b.advance(h, I)


def test_an_unknown_group_is_still_a_key_error():
    with pytest.raises(KeyError):
        toy_brain().drive({"JO": 1.0})                # a real input group, but this brain has no JO neurons


# ---- D3: a sense writes only the groups it declares ------------------------------------------------------------------

def test_a_sense_writing_an_undeclared_group_is_stopped():
    drives = declaration_of("senses", "looming").drives
    G.check_sense_output("looming", {"LPLC2_R": 0.3, "LC4_R": 0.1}, drives)
    with pytest.raises(G.RuleViolation, match="DNp01"):
        G.check_sense_output("looming", {"LPLC2_R": 0.3, "DNp01": 9.0}, drives)


# ---- D1 / N3: an action sees only its own motor or descending neurons and presses only its own buttons ----------------

def test_an_action_can_read_only_its_declared_groups():
    rates = {"TTMn": 0.2, "LPLC2_R": 3.0, "DNp09": 0.1}
    seen = G.GuardedRates(rates, ["TTMn"], "jump")
    assert seen.get("TTMn", 0.0) == 0.2 and seen["TTMn"] == 0.2 and dict(seen) == {"TTMn": 0.2}
    for read in (lambda: seen.get("LPLC2_R", 0.0), lambda: seen["LPLC2_R"], lambda: seen.get("DNp09")):
        with pytest.raises(G.RuleViolation, match="declares only"):
            read()


def test_the_real_actions_decide_from_guarded_rates_unchanged():
    from fly_mario_fly import registry
    for name, plugin in registry.list_plugins("actions").items():
        d = declaration_of("actions", name)
        knobs = {k.key: k.default for k in plugin.knobs}
        rates = {g: 0.3 for g in d.reads_groups}
        want = plugin.decide(dict(rates), knobs, {"airborne": False, "mods": {}})
        got = plugin.decide(G.GuardedRates({**rates, "LPLC2_R": 9.0}, d.reads_groups, name), knobs, {"airborne": False, "mods": {}})
        assert (got.press, got.release) == (want.press, want.release), name


def test_an_action_pressing_an_undeclared_button_is_stopped():
    G.check_buttons("jump", ButtonIntent(press=frozenset({"A"})), ("A",))
    with pytest.raises(G.RuleViolation, match="B"):
        G.check_buttons("jump", ButtonIntent(press=frozenset({"A", "B"})), ("A",))


# ---- the runner really uses the guards (needs the brain data) -------------------------------------------------------------

@pytest.mark.skipif(not os.environ.get("FLY_MARIO_FLY_DATA"), reason="FLY_MARIO_FLY_DATA not set")
def test_the_runner_stops_a_sense_that_leaves_its_declaration(monkeypatch):
    from fly_mario_fly.runner import Run, load_fly
    mod = _modules("senses")["looming"]
    monkeypatch.setattr(mod, "DECLARATION", replace(mod.DECLARATION, drives=("LC4_L",)))   # looming also writes LPLC2_R / LC4_R
    run = Run(load_fly("looming_only"), Scene("1-1", noop=3, seed=1, max_frames=900))
    with pytest.raises(G.RuleViolation, match="looming"):
        run.play()
