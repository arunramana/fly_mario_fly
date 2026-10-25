"""The code in the docs is real: the minimal sense in docs/plugin-authoring.md passes the validator and a smoke test,
and the broken variants the doc says would be refused really are."""
import importlib.util
import re
from dataclasses import replace
from pathlib import Path

import pytest

from fly_mario_fly.rules import Route, smoke
from fly_mario_fly.rules import validate as V

DOCS = Path(__file__).resolve().parents[1] / "docs"


def sense_from_doc(tmp_path):
    text = (DOCS / "plugin-authoring.md").read_text(encoding="utf-8")
    block = re.search(r"```python\n(\"\"\"Sweet smell for pipes.*?)```", text, re.S).group(1)
    f = tmp_path / "senses" / "pipe_smell.py"
    f.parent.mkdir()
    f.write_text(block, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("doc_pipe_smell", f)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, f


def test_the_documented_sense_complies_and_runs(tmp_path):
    mod, f = sense_from_doc(tmp_path)
    ctx = V.make_context()
    assert V.check_declaration("sense", "pipe_smell", mod.PLUGIN, mod.DECLARATION, ctx) == []
    assert V.check_knobs("sense", "pipe_smell", mod.PLUGIN) == []
    assert V.scan_source([f], root=tmp_path) == []
    assert smoke.smoke_sense(mod.PLUGIN, mod.DECLARATION) == []


@pytest.mark.parametrize("change,rule", [
    ({"drives": ("ORN_L", "ORN_R", "DNp01")}, "R-SENSE-ROUTE"),
    ({"route": Route("escape", ("LC4", "LPLC2"), "x")}, "R-SENSE-ROUTE"),
    ({"origin": "fly"}, "R-ORIGIN-KIND"),
], ids=["drives a descending neuron", "route is not the circuit it feeds", "claims to be teal"])
def test_the_variants_the_doc_says_are_refused_are_refused(tmp_path, change, rule):
    mod, _ = sense_from_doc(tmp_path)
    bad = replace(mod.DECLARATION, **change)
    assert rule in {v.rule for v in V.check_declaration("sense", "pipe_smell", mod.PLUGIN, bad, V.make_context())}


def test_every_doc_link_to_a_repo_file_exists():
    root = DOCS.parent
    docs = [*DOCS.glob("*.md"), root / "README.md", root / "ROADMAP.md", root / "CONTRIBUTING.md", root / "tutorials" / "README.md"]
    for md in docs:
        text = re.sub(r"<!--.*?-->", "", md.read_text(encoding="utf-8"), flags=re.S)     # a commented-out hero GIF is not a link yet
        for target in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", text):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            assert (md.parent / target).exists(), f"{md.relative_to(root)} links to missing {target}"
