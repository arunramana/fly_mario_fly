"""evolve: the genome follows what is ON in the fly, respects bounds/scale/floors, and the lane stays generic."""
import ast
from pathlib import Path

import pytest

from fly_mario.contracts import KnobSpec
from fly_mario.evolve import fitness as F
from fly_mario.evolve import genome as G
from fly_mario.runner import load_fly

EVOLVE = Path(__file__).resolve().parents[1] / "src" / "fly_mario" / "evolve"


def test_genome_is_only_what_is_on():
    full, blank = load_fly("champion_e1s"), load_fly("blank")
    keys = {g.key for g in G.build_genome(full)}
    assert {"home.drive", "jump.ttmn_thresh"} <= keys
    blank_keys = {g.key for g in G.build_genome(blank)}
    assert blank_keys and not blank_keys & {"home.drive", "hearing.gain"}      # actions only: no sense is on
    looming_only = {g.key for g in G.build_genome(load_fly("looming_only"))}
    assert looming_only < keys | looming_only and "sweet_smell.gain" not in looming_only


def test_non_evolvable_knobs_are_left_out():
    fly = load_fly("champion_e1s")
    off = {k.key for k in G.on_specs(fly) if not k.evolvable}
    assert off.isdisjoint(g.key for g in G.build_genome(fly))


@pytest.mark.parametrize("scale", ["linear", "log"])
def test_value_unit_roundtrip_and_bounds(scale):
    g = G.Gene(KnobSpec("x", "x", "lo", "hi", 2.0, 0.5, 8.0, scale=scale), 0.5, 8.0, 2.0)
    assert g.value(0) == pytest.approx(0.5) and g.value(1) == pytest.approx(8.0)
    assert g.value(-3) == pytest.approx(0.5) and g.value(9) == pytest.approx(8.0)
    assert g.value(g.unit(2.0)) == pytest.approx(2.0)
    if scale == "log":
        assert g.value(0.5) == pytest.approx(2.0)          # geometric midpoint


def test_floor_raises_the_lower_bound():
    fly = load_fly("champion_e1s")
    for g in G.build_genome(fly):
        if g.spec.floor is not None:
            assert g.lo == max(g.spec.lo, g.spec.floor)
        assert g.lo <= g.start <= g.hi


def test_start_vector_reproduces_the_fly():
    fly = load_fly("champion_e1s")
    genes = G.build_genome(fly)
    vals = G.decode(genes, G.encode(genes))
    for k, v in vals.items():
        assert v == pytest.approx(fly.knobs.get(k, v), rel=1e-6)


def test_candidate_fitness_rejects_blind_a():
    ok = {"violations": 0, "fitness": 1.0}
    assert F.candidate_fitness([ok, ok]) == 1.0
    assert F.candidate_fitness([ok, {"violations": 1, "fitness": 9.0}]) == F.WORST


def test_episode_fitness_formula():
    assert F.episode_fitness(1580.5, 2000, 3161.0) == pytest.approx(0.5 + 0.2)


def test_train_and_dev_sets_are_the_old_ones_and_disjoint():
    tr, dv = F.train_scenes("1-1"), F.dev_scenes("1-1")
    assert [s.noop for s in tr[:6]] == [0, 7, 15, 19, 29, 37] and {s.sigma for s in tr} == {0.0, 0.05}
    assert len(tr) == 12 and len(dv) == 10
    assert not {s.seed for s in tr} & {s.seed for s in dv}


def test_evolve_imports_only_runner_contracts_registry():
    """evolve/ goes through runner, contracts and registry; it never names a sense, object or action."""
    allowed = {"fly_mario.runner", "fly_mario.contracts", "fly_mario.registry", "fly_mario.evolve"}
    for path in EVOLVE.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.ImportFrom) and node.module:
                mods = [node.module] if node.module != "fly_mario" else [f"fly_mario.{a.name}" for a in node.names]
            else:
                mods = [a.name for a in node.names] if isinstance(node, ast.Import) else []
            for m in mods:
                if m.startswith("fly_mario"):
                    assert any(m == a or m.startswith(a + ".") for a in allowed), f"{path.name} imports {m}"
        for name in ("looming", "goomba", "jump", "sweet_smell", "hearing", "koopa", "qblock", "pipe"):
            assert f'"{name}' not in text and f"'{name}" not in text, f"{path.name} names {name}"
