"""REFACTOR_PLAN.md section 2: "fly/ never imports mario/... Enforced by an
import-guard test, not by discipline." This is that test.

Static (reads source, parses the AST) rather than dynamic (importing fly.*
and inspecting sys.modules) on purpose: a dynamic check only catches an
import that actually executes on this run, and would miss one guarded by an
`if` branch never taken. Parsing every `import`/`from` statement in every
fly/ module catches the rule being violated in the source at all, not just
on one code path.
"""
from __future__ import annotations

import ast
from pathlib import Path

FLY_DIR = Path(__file__).parent.parent / "fly"
FORBIDDEN_PREFIXES = ("mario", "bridge")


def _imported_top_level_names(py_file: Path) -> set[str]:
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:  # ignore relative imports (level > 0)
                names.add(node.module.split(".")[0])
    return names


def test_fly_never_imports_mario_or_bridge():
    violations = []
    for py_file in FLY_DIR.rglob("*.py"):
        imported = _imported_top_level_names(py_file)
        hit = imported & set(FORBIDDEN_PREFIXES)
        if hit:
            violations.append(f"{py_file.relative_to(FLY_DIR.parent)} imports {sorted(hit)}")
    assert not violations, (
        "fly/ must not import mario/ or bridge/ (REFACTOR_PLAN.md section 2) "
        "-- violations:\n" + "\n".join(violations)
    )


def test_fly_directory_is_not_empty():
    """A guard that silently passes because FLY_DIR.rglob found nothing is
    worse than no guard -- catches the path itself breaking (e.g. a future
    rename of fly/ that forgets this test)."""
    assert list(FLY_DIR.rglob("*.py")), f"no .py files found under {FLY_DIR}"
