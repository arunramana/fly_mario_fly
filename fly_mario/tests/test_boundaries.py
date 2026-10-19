"""AST scan of src/fly_mario: enforce the import boundaries in CLAUDE.md."""
import ast
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "fly_mario"
FILES = sorted(SRC.rglob("*.py"))
STDLIB = set(sys.stdlib_module_names)
# Old-repo top-level modules, forbidden even if they happen to be importable.
OLD_REPO = {"brain", "bridge", "config", "fly", "mario", "render", "sim", "tool",
            "mcns", "escape_circuit", "mechanisms", "projects", "scripts"}


def _imports(path: Path) -> list[str]:
    """Absolute dotted module names imported by a file (relative imports resolved)."""
    pkg = ["fly_mario"] + list(path.relative_to(SRC).parent.parts)
    out = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            out += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = pkg[: len(pkg) - (node.level - 1)]
                mod = ".".join(base + ([node.module] if node.module else []))
                out.append(mod)
                out += [f"{mod}.{a.name}" for a in node.names]
            else:
                out.append(node.module or "")
                out += [f"{node.module}.{a.name}" for a in node.names]
    return out


def _area(path: Path) -> str:
    rel = path.relative_to(SRC).parts
    return rel[0] if len(rel) > 1 else rel[0].removesuffix(".py")


def test_files_found():
    assert any(f.name == "contracts.py" for f in FILES)


@pytest.mark.parametrize("path", FILES, ids=lambda p: str(p.relative_to(SRC)))
def test_no_foreign_imports(path):
    for name in _imports(path):
        top = name.split(".")[0]
        if top == "fly_mario" or top in STDLIB or not top:
            continue
        assert top not in OLD_REPO, f"{path.name} imports old-repo module {name}"


def _violations(area: str, forbidden: str):
    for f in FILES:
        if _area(f) == area:
            for n in _imports(f):
                if n == forbidden or n.startswith(forbidden + "."):
                    yield f"{f.relative_to(SRC)} imports {n}"


def test_fly_does_not_import_mario():
    assert not list(_violations("fly", "fly_mario.mario"))


def test_mario_does_not_import_fly():
    assert not list(_violations("mario", "fly_mario.fly"))


def test_contracts_imports_nothing_from_fly_mario():
    for n in _imports(SRC / "contracts.py"):
        assert n.split(".")[0] != "fly_mario", n


@pytest.mark.parametrize("area", ["evolve", "api", "render"])
def test_outer_lanes_only_runner(area):
    allowed = {"fly_mario.runner", "fly_mario.contracts", "fly_mario.registry"}
    for f in FILES:
        if _area(f) != area:
            continue
        for n in _imports(f):
            if n.split(".")[0] != "fly_mario" or n == "fly_mario":
                continue
            assert any(n == a or n.startswith(a + ".") for a in allowed) or n.startswith(f"fly_mario.{area}"), \
                f"{f.relative_to(SRC)} imports {n}"
