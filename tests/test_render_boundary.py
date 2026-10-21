"""render/ may import only runner, contracts and registry from fly_mario (also covered by test_boundaries)."""
import ast
from pathlib import Path

RENDER = Path(__file__).resolve().parents[1] / "src" / "fly_mario" / "render"
ALLOWED = ("fly_mario.runner", "fly_mario.contracts", "fly_mario.registry", "fly_mario.render")


def test_render_imports_only_runner_contracts_registry():
    for f in RENDER.glob("*.py"):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                [node.module or ""] if isinstance(node, ast.ImportFrom) and not node.level else []
            for n in names:
                if n.split(".")[0] == "fly_mario":
                    assert n == "fly_mario" or n.startswith(ALLOWED), f"{f.name} imports {n}"
