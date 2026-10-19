"""Contract tests: every sense, shape and action honours contracts.py on every object type."""
import math

import pytest

from fly_mario import registry
from fly_mario.contracts import Action, Box, ButtonIntent, LoomShape, MarioState, ObjectInstance, Sense, SenseOutput
from fly_mario.fly.groups import load_groups
from fly_mario.mario.env import BUTTONS
from fly_mario.mario.facts import load_facts
from fly_mario.runner import config as C
from fly_mario.senses.kit.memory import SenseMemory

FACTS = load_facts("1-1")
MARIO = MarioState(x=100.0, y=160.0, w=12.0, h=16.0, airborne=False, power="small", facing=1)
SENSES = registry.list_plugins("senses")
SHAPES = registry.list_plugins("shapes")
ACTIONS = registry.list_plugins("actions")
OBJECTS = registry.list_plugins("objects")

# a plausible raw box and state for each type, ahead of Mario
BOXES = {"goomba": Box(140, 160, 16, 16), "koopa": Box(140, 152, 16, 24), "piranha": Box(140, 152, 16, 24),
         "mushroom": Box(140, 160, 16, 16), "pipe": Box(140, 144, 32, 32), "step": Box(140, 160, 16, 16),
         "pit": Box(140, 176, 32, 32), "qblock": Box(140, 112, 16, 16), "brick": Box(140, 112, 16, 16),
         "usedblock": Box(140, 112, 16, 16)}
STATES = {"goomba": {"slot": 0, "shell": False}, "koopa": {"slot": 1, "shell": False}, "piranha": {"slot": 2, "shell": False},
          "mushroom": {"slot": 5}, "pit": {"open": False}, "qblock": {"tile": 192, "row": 7}}


def instance(name, **over):
    return ObjectInstance(name, 7, over.get("box", BOXES[name]), "ahead", dict(STATES.get(name, {})))


def knobs_of(components):
    out = {}
    for c in components:
        out.update({k.key: k.default for k in c.knobs})
    return out


ALL_KNOBS = knobs_of(list(SENSES.values()) + list(ACTIONS.values()) + list(SHAPES.values()))


def test_every_object_type_has_a_box_here():
    assert set(OBJECTS) == set(BOXES), "a new object type needs a row in BOXES"


def test_expected_plugins_exist():
    assert set(SENSES) >= {"looming", "hearing", "sweet_smell", "sour_smell", "home", "headroom", "rear_eye"}
    assert set(SHAPES) == {"own_box", "solid_block", "far_edge_tower", "custom_box"}
    assert set(ACTIONS) == {"walk", "steer", "jump", "back_up"}


def test_protocols():
    assert all(isinstance(s, Sense) for s in SENSES.values())
    assert all(isinstance(s, LoomShape) for s in SHAPES.values())
    assert all(isinstance(a, Action) for a in ACTIONS.values())


def test_mario_default_shapes_are_registered():
    for name, o in OBJECTS.items():
        assert o.default_loom_shape in SHAPES, f"{name}: default_loom_shape {o.default_loom_shape!r} is not a shape"


@pytest.mark.parametrize("obj", sorted(OBJECTS))
@pytest.mark.parametrize("sense", sorted(SENSES))
def test_every_sense_runs_on_every_object_type(sense, obj):
    s = SENSES[sense]
    o = instance(obj)
    mem = SenseMemory()
    mem.world = [o]
    out = s.cue([o], MARIO, FACTS, ALL_KNOBS, mem)
    assert isinstance(out, SenseOutput)
    assert len(out.steps) >= 1, "a sense must show at least one calculation step"
    groups = load_groups()
    assert set(out.inputs) <= set(groups), set(out.inputs) - set(groups)
    assert all(math.isfinite(v) and v >= 0 for v in out.inputs.values())
    for item in out.overlay:
        assert item.kind in ("box", "line", "dot", "wedge") and item.line in ("solid", "dotted", "dashed")
        assert all(math.isfinite(g) for g in item.geometry)
    for st in out.steps:
        assert math.isfinite(st.value) and 0.0 <= st.norm <= 1.0


@pytest.mark.parametrize("sense", sorted(SENSES))
def test_every_sense_runs_on_an_empty_frame(sense):
    mem = SenseMemory()
    out = SENSES[sense].cue([], MARIO, FACTS, ALL_KNOBS, mem)
    assert len(out.steps) >= 1
    assert all(v == 0 for g, v in out.inputs.items() if SENSES[sense].scope == "per_object")


@pytest.mark.parametrize("sense", sorted(SENSES))
def test_step_labels_are_the_same_every_frame(sense):
    """The recorder makes one csv column per step label, so the label set must not depend on what is in view."""
    s = SENSES[sense]
    mem = SenseMemory()
    labels = None
    for objs in ([], [instance("goomba")], [instance("pit")], []):
        mem.world = list(objs)
        got = [st.label for st in s.cue(list(objs), MARIO, FACTS, ALL_KNOBS, mem).steps]
        labels = labels or got
        assert got == labels


@pytest.mark.parametrize("sense", sorted(SENSES))
def test_sense_declarations(sense):
    s = SENSES[sense]
    assert s.scope in ("per_object", "whole_fly") and s.label and s.effect
    assert s.line in ("solid", "dotted", "dashed") and s.colour.startswith("#")
    mechs = registry.list_plugins("mechanisms")
    assert s.feeds and set(s.feeds) <= set(mechs)


@pytest.mark.parametrize("obj", sorted(OBJECTS))
@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_every_shape_returns_a_valid_box(shape, obj):
    o = instance(obj)
    b = SHAPES[shape].shape(o, FACTS, ALL_KNOBS)
    assert isinstance(b, Box)
    assert all(math.isfinite(v) for v in (b.x, b.y, b.w, b.h)) and b.w > 0 and b.h > 0


def test_every_shape_works_without_any_knobs():
    for shape in SHAPES.values():
        assert shape.shape(instance("pit"), FACTS, {}).h > 0


def test_every_shape_declares_a_family():
    assert {s.name: s.family for s in SHAPES.values()} == {
        "own_box": "free", "solid_block": "wall", "far_edge_tower": "tower", "custom_box": "free"}


def test_far_edge_tower_stands_on_the_far_edge_on_the_highest_rim():
    pit = instance("pit", box=Box(160, 176, 32, 32))
    flat = SHAPES["far_edge_tower"].shape(pit, FACTS, {})
    assert (flat.x, flat.w, flat.h, flat.y + flat.h) == (192, 16, 32, 176)       # width 32 < the jump, base on the floor
    wide = SHAPES["far_edge_tower"].shape(instance("pit", box=Box(160, 176, 96, 32)), FACTS, {})
    assert wide.h == FACTS["mario"]["jump_apex"]                                 # capped at a full jump
    stair = ObjectInstance("pit", 1, Box(160, 176, 32, 32), "ahead", {"loom_rims": (176, 144)})
    assert SHAPES["far_edge_tower"].shape(stair, FACTS, {}).y == 144 - 32       # anchored to the highest rim


@pytest.mark.parametrize("key", sorted(ALL_KNOBS))
def test_knob_specs_are_sane(key):
    spec = {k.key: k for c in list(SENSES.values()) + list(ACTIONS.values()) + list(SHAPES.values()) for k in c.knobs}[key]
    assert spec.label and spec.lo_label and spec.hi_label
    assert spec.lo <= spec.default <= spec.hi
    assert spec.origin in ("fly", "invented")
    if spec.floor is not None:
        assert spec.floor <= spec.lo + 1e-9 or spec.floor <= spec.default
    if spec.scale == "log":
        assert spec.lo > 0


def test_knob_keys_are_unique_across_components():
    keys = [k.key for c in list(SENSES.values()) + list(ACTIONS.values()) + list(SHAPES.values()) for k in c.knobs]
    assert len(keys) == len(set(keys))


def test_nothing_is_tagged_as_coming_from_the_fly_without_a_connectome_source():
    """Invariant 3: no scalar is connectome-derived. Every knob here is a hand-set number, so every one says so."""
    specs = [k for c in list(SENSES.values()) + list(ACTIONS.values()) + list(SHAPES.values()) for k in c.knobs]
    assert all(k.origin == "invented" for k in specs)


@pytest.mark.parametrize("action", sorted(ACTIONS))
def test_actions_decide_with_and_without_rates(action):
    a = ACTIONS[action]
    for rates in ({}, {g: 1.0 for g in a.source_groups}, {g: 0.0 for g in a.source_groups}):
        it = a.decide(rates, ALL_KNOBS, {"airborne": False, "mods": {}})
        assert isinstance(it, ButtonIntent) and it.priority == a.priority
        assert (it.press | it.release) <= set(BUTTONS)
    assert set(a.source_groups) <= set(load_groups())


def test_groups_driven_by_senses_belong_to_their_mechanisms():
    mechs = registry.list_plugins("mechanisms")
    for s in SENSES.values():
        out = s.cue([], MARIO, FACTS, ALL_KNOBS, SenseMemory())
        allowed = {g for m in s.feeds for g in mechs[m].input_groups}
        assert set(out.inputs) <= allowed or s.name == "looming", (s.name, set(out.inputs) - allowed)
    looming = SENSES["looming"].cue([], MARIO, FACTS, ALL_KNOBS, SenseMemory())
    assert set(looming.inputs) <= set(mechs["escape"].input_groups)
