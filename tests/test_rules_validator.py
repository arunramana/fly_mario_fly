"""The compliance layer: the validator accepts the real repository and REJECTS each rule when it is deliberately broken."""
import ast
import textwrap
from dataclasses import replace
from pathlib import Path

import pytest

from fly_mario_fly import registry
from fly_mario_fly.contracts import KnobSpec
from fly_mario_fly.rules import RULES, Declaration, Route, declare
from fly_mario_fly.rules import validate as V
from fly_mario_fly.rules.__main__ import main as rules_main
from fly_mario_fly.rules.lookup import declaration_of

CTX = V.make_context()
LOOMING = registry.list_plugins("senses")["looming"]
LOOMING_D = declaration_of("senses", "looming")
JUMP = registry.list_plugins("actions")["jump"]
JUMP_D = declaration_of("actions", "jump")
ESCAPE = registry.list_plugins("mechanisms")["escape"]
ESCAPE_D = declaration_of("mechanisms", "escape")
GOOMBA = registry.list_plugins("objects")["goomba"]
GOOMBA_D = declaration_of("objects", "goomba")


def rules_of(violations):
    return {v.rule for v in violations}


def check(kind, name, plugin, decl):
    return V.check_declaration(kind, name, plugin, decl, CTX)


# ---- the real repository complies ------------------------------------------------------------------------------

def test_every_real_plugin_complies():
    assert V.validate_all() == []


def test_every_plugin_of_every_kind_has_a_declaration_of_the_right_kind():
    for kind in registry.KINDS:
        for name, mod in registry.list_modules(kind).items():
            d = getattr(mod, "DECLARATION", None)
            assert isinstance(d, Declaration), f"{kind}/{name}"
            allowed = (V.DECL_KIND[kind], "character") if kind == "objects" else (V.DECL_KIND[kind],)     # creatures live with the objects
            assert d.kind in allowed and d.origin in ("fly", "invented"), f"{kind}/{name}"


def test_only_mechanisms_are_teal():
    for kind in registry.KINDS:
        for name in registry.list_modules(kind):
            assert (declaration_of(kind, name).origin == "fly") == (kind == "mechanisms"), f"{kind}/{name}"


def test_the_cli_validates_and_lists(capsys):
    assert rules_main(["validate"]) == 0
    assert "comply" in capsys.readouterr().out
    assert rules_main(["list"]) == 0
    out = capsys.readouterr().out
    assert all(r.id in out for r in RULES) and all(r.enforced_by for r in RULES)


# ---- S1: every plug-in declares its origin ---------------------------------------------------------------------

def test_a_plugin_without_a_declaration_is_rejected():
    v = check("object", "goomba", GOOMBA, None)
    assert rules_of(v) == {"R-DECLARED"} and "no DECLARATION" in str(v[0])


@pytest.mark.parametrize("decl", [
    replace(GOOMBA_D, kind="sense"),
    replace(GOOMBA_D, origin="maybe"),
    replace(GOOMBA_D, what="  "),
], ids=["wrong kind", "bad origin", "empty what"])
def test_a_malformed_declaration_is_rejected(decl):
    assert "R-DECLARED" in rules_of(check("object", "goomba", GOOMBA, decl))


def test_a_sense_cannot_claim_to_be_real_wiring():
    v = check("sense", "looming", LOOMING, replace(LOOMING_D, origin="fly"))
    assert "R-ORIGIN-KIND" in rules_of(v) and "orange" in str(v[0])


def test_a_mechanism_must_be_teal():
    assert "R-ORIGIN-KIND" in rules_of(check("mechanism", "escape", ESCAPE, replace(ESCAPE_D, origin="invented")))


# ---- S2: a fly item cites the real route -----------------------------------------------------------------------

@pytest.mark.parametrize("route", [
    None,
    Route("no_such_circuit", ("LC4",), "x"),
    Route("escape", (), "x"),
    Route("escape", ("LC4", "NotACellType"), "x"),
], ids=["no route", "unknown mechanism", "no cell types", "cell type not in that circuit"])
def test_a_fly_item_must_cite_a_real_route(route):
    assert "R-FLY-ROUTE" in rules_of(check("mechanism", "escape", ESCAPE, replace(ESCAPE_D, route=route)))


# ---- D3 / N2: senses drive only declared input neurons on their route ---------------------------------------------

def test_a_sense_without_a_route_is_rejected():
    assert "R-FLY-ROUTE" in rules_of(check("sense", "looming", LOOMING, replace(LOOMING_D, route=None)))


@pytest.mark.parametrize("group", ["DNp01", "TTMn"])
def test_a_sense_cannot_drive_a_descending_or_motor_neuron(group):
    v = check("sense", "looming", LOOMING, replace(LOOMING_D, drives=LOOMING_D.drives + (group,)))
    assert "R-SENSE-ROUTE" in rules_of(v)
    assert "cannot be driven" in " ".join(str(x) for x in v)


def test_a_sense_must_ride_the_circuit_it_feeds():
    other = Route("walking", ("LC10a",), "x")
    assert "R-SENSE-ROUTE" in rules_of(check("sense", "looming", LOOMING, replace(LOOMING_D, route=other)))


def test_a_sense_must_cite_the_cell_types_it_drives():
    v = check("sense", "looming", LOOMING, replace(LOOMING_D, route=Route("escape", ("LC4",), "x")))
    assert "R-FLY-ROUTE" in rules_of(v) and "LPLC2" in str(v)


def test_a_sense_that_drives_nothing_must_declare_what_it_modulates():
    head = registry.list_plugins("senses")["headroom"]
    d = declaration_of("senses", "headroom")
    assert check("sense", "headroom", head, d) == []
    assert "R-SENSE-ROUTE" in rules_of(check("sense", "headroom", head, replace(d, modulates=())))


# ---- D1 / N3: actions decide only from declared motor or descending neurons ----------------------------------------

def test_an_action_cannot_read_a_sensory_group():
    v = check("action", "jump", JUMP, replace(JUMP_D, reads_groups=("LPLC2_R",)))
    assert "R-ACTION-SOURCE" in rules_of(v)


def test_an_action_must_declare_exactly_its_source_groups():
    assert "R-ACTION-SOURCE" in rules_of(check("action", "jump", JUMP, replace(JUMP_D, reads_groups=("TTMn", "DNp01"))))
    assert "R-ACTION-SOURCE" in rules_of(check("action", "jump", JUMP, replace(JUMP_D, reads_groups=())))


def test_an_action_declares_real_buttons_only():
    assert "R-ACTION-SOURCE" in rules_of(check("action", "jump", JUMP, replace(JUMP_D, buttons=("turbo",))))
    assert "R-ACTION-SOURCE" in rules_of(check("action", "jump", JUMP, replace(JUMP_D, buttons=())))


def test_an_action_may_use_only_declared_game_facts_and_must_explain_them():
    assert "R-ACTION-SOURCE" in rules_of(check("action", "jump", JUMP, replace(JUMP_D, game_reads=("mario_x",))))
    assert "R-ACTION-SOURCE" in rules_of(check("action", "jump", JUMP, replace(JUMP_D, what="short")))


# ---- D4: dials ---------------------------------------------------------------------------------------------------

class _Dials:
    def __init__(self, *knobs):
        self.knobs = list(knobs)


def test_a_dial_cannot_claim_to_be_real_wiring():
    k = KnobSpec("x.gain", "Gain", "lo", "hi", 1.0, 0.1, 10.0, origin="fly", evolvable=False)
    assert "R-DIALS" in rules_of(V.check_knobs("sense", "x", _Dials(k)))


def test_only_sense_action_and_shape_dials_are_evolvable():
    k = KnobSpec("x.gain", "Gain", "lo", "hi", 1.0, 0.1, 10.0, origin="invented", evolvable=True)
    assert V.check_knobs("sense", "x", _Dials(k)) == []
    assert "R-DIALS" in rules_of(V.check_knobs("object", "x", _Dials(k)))
    assert "R-DIALS" in rules_of(V.check_knobs("mechanism", "x", _Dials(k)))


# ---- N1 / N2 (static): nothing writes the weights, nothing but the runner drives the brain ---------------------------

def scan(tmp_path, area, code, name="bad.py"):
    f = tmp_path / area / name
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(textwrap.dedent(code), encoding="utf-8")
    return V.scan_source([f], root=tmp_path)


@pytest.mark.parametrize("code", [
    "def f(brain):\n    brain.W[0, 0] = 1.0\n",
    "def f(brain):\n    brain.W = None\n",
    "def f(brain):\n    brain._Ws.data[:] = 0\n",
    "def f(brain):\n    brain.W *= 2\n",
    "def f(brain):\n    del brain.W[0]\n",
], ids=["item", "attribute", "sparse data", "augmented", "delete"])
def test_writing_the_weights_anywhere_is_rejected(tmp_path, code):
    assert rules_of(scan(tmp_path, "evolve", code)) == {"R-NO-WEIGHT-WRITES"}


def test_only_brain_init_may_set_the_weights():
    brain = V.SRC / "fly" / "brain.py"
    assert V.scan_source([brain]) == []
    tree = ast.parse(brain.read_text())
    assert any(isinstance(n, ast.FunctionDef) and n.name == "__init__" for n in ast.walk(tree))


def test_driving_the_brain_outside_fly_and_runner_is_rejected(tmp_path):
    assert rules_of(scan(tmp_path, "senses", "def f(brain):\n    brain.drive({'DNp01': 1.0})\n")) == {"R-NO-DIRECT-DRIVE"}
    assert rules_of(scan(tmp_path, "api", "def f(b, h, I):\n    b.advance(h, I)\n")) == {"R-NO-DIRECT-DRIVE"}
    assert scan(tmp_path, "runner", "def f(b, h, I):\n    b.advance(h, I)\n    b.drive({})\n", "ok.py") == []
    assert scan(tmp_path, "render", "def f(lane):\n    while lane.advance():\n        pass\n", "ok2.py") == []


@pytest.mark.parametrize("area", ["senses", "actions"])
def test_senses_and_actions_never_import_the_brain(tmp_path, area):
    for imp in ("from fly_mario_fly.fly.brain import Brain", "import fly_mario_fly.fly.connectome",
                "from fly_mario_fly.fly import brain"):
        assert "R-NO-DIRECT-DRIVE" in rules_of(scan(tmp_path, area, imp + "\n")), imp


# ---- the schema and guards stay light and neutral ------------------------------------------------------------------

@pytest.mark.parametrize("name", ["schema.py", "guards.py"])
def test_schema_and_guards_import_nothing_from_the_project(name):
    tree = ast.parse((V.SRC / "rules" / name).read_text())
    for n in ast.walk(tree):
        mods = [a.name for a in n.names] if isinstance(n, ast.Import) else [n.module or ""] if isinstance(n, ast.ImportFrom) else []
        assert not any(m.startswith("fly_mario_fly") for m in mods), (name, mods)


def test_declare_builds_a_declaration():
    d = declare("object", "invented", "x")
    assert d == Declaration(kind="object", origin="invented", what="x")
