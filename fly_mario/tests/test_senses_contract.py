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

# A 16x16 box ahead of Mario, placed by the object's kind, so a new object type needs no edit here.
KIND_Y = {"enemy": 160, "obstacle": 160, "pickup": 160, "terrain": 112}


def box_for(kind):
    return Box(140, KIND_Y[kind], 16, 16)


def instance(name, **over):
    kind = OBJECTS[name].kind if name in OBJECTS else DUMMY_KIND
    return ObjectInstance(name, 7, over.get("box", box_for(kind)), "ahead", {})


DUMMY_KIND = "enemy"


def knobs_of(components):
    out = {}
    for c in components:
        out.update({k.key: k.default for k in c.knobs})
    return out


ALL_KNOBS = knobs_of(list(SENSES.values()) + list(ACTIONS.values()) + list(SHAPES.values()))


def test_a_dummy_object_type_is_covered_automatically(monkeypatch):
    """No per-type table: a freshly registered object type gets a box from its kind and runs through every sense and shape."""
    class Dummy:
        name, label, note, kind, default_loom_shape = "dummy", "Dummy", "", "pickup", "own_box"

        def find(self, ram, facts):
            return []

        def remove(self, env):
            pass

    monkeypatch.setitem(OBJECTS, "dummy", Dummy())
    o = instance("dummy")
    assert o.box == box_for("pickup")
    mem = SenseMemory()
    mem.world = [o]
    for s in SENSES.values():
        assert len(s.cue([o], MARIO, FACTS, ALL_KNOBS, mem).steps) >= 1
    for sh in SHAPES.values():
        assert sh.shape(o, FACTS, ALL_KNOBS).w > 0


def test_expected_plugins_exist():
    assert set(SENSES) >= {"looming", "hearing", "sweet_smell", "sour_smell", "home", "headroom", "rear_eye"}
    assert set(SHAPES) == {"own_box", "solid_block", "far_edge_tower", "custom_box"}
    assert set(ACTIONS) == {"walk", "steer", "jump", "back_up"}


def test_protocols():
    assert all(isinstance(s, Sense) for s in SENSES.values())
    assert all(isinstance(s, LoomShape) for s in SHAPES.values())
    assert all(isinstance(a, Action) for a in ACTIONS.values())


def test_every_modifier_read_is_raised():
    """A sense or action that reads a modifier needs some sense that raises it, or the read is dead."""
    raised = {m for s in SENSES.values() for m in s.raises}
    for c in list(SENSES.values()) + list(ACTIONS.values()):
        reads = set(c.reads)
        assert reads <= raised, (c.name, reads - raised)


def test_knob_kind_is_slider_or_switch():
    for c in list(SENSES.values()) + list(ACTIONS.values()) + list(SHAPES.values()):
        for k in c.knobs:
            assert k.kind in ("slider", "switch")


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
        assert item.anchor in ("level", "screen_right")
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


def test_every_object_declares_block_hit_tile_and_fall_death():
    """session.py reads both directly, so every object type must declare them; a block_hit_tile is a facts["tiles"] key."""
    for name, o in OBJECTS.items():
        assert o.block_hit_tile is None or o.block_hit_tile in FACTS["tiles"], name
        assert isinstance(o.causes_fall_death, bool), name
    assert OBJECTS["pit"].causes_fall_death and OBJECTS["usedblock"].block_hit_tile
