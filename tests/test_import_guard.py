# What this file does, in plain English:
# Checks, by reading the source files without running them, that the fly
# brain code in fly/ never pulls in game (mario/) or bridge code, and that
# sim/episode.py and sim/protocols.py pull in none of fly/, mario/ or
# bridge/. This keeps the parts separate. It also checks fly/ is not empty,
# so the check cannot pass by finding nothing.
"""
fly/ never imports mario/ or bridge/, and sim/episode.py imports none of
them. Static (parses the AST) on purpose: a dynamic check would miss an
import behind a branch not taken on this run.
"""
from __future__ import annotations

import ast
from pathlib import Path

FLY_DIR = Path(__file__).parent.parent / "fly"
FORBIDDEN_PREFIXES = ("mario", "bridge")

# REFACTOR_PLAN.md phase 5, section 5.2: "Episode composes a Policy and an
# Environment and knows nothing else... bridge supplies the concrete
# fly-backed policy; mario/ supplies the environment." Episode must not
# import any of fly/mario/bridge -- it receives concrete implementations
# by dependency injection (the constructor), never by import. Scoped to
# these two files specifically, not all of sim/: sim/project_runner.py
# legitimately imports run_steering.py (which imports fly/mario/bridge
# everywhere) to drive the full system from a ProjectConfig -- a
# different, glue-layer module, not Episode itself.
SIM_GENERIC_FILES = ("sim/episode.py", "sim/protocols.py")
SIM_FORBIDDEN_PREFIXES = ("fly", "mario", "bridge")


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


def test_episode_never_imports_fly_mario_or_bridge():
    root = FLY_DIR.parent
    violations = []
    for rel_path in SIM_GENERIC_FILES:
        py_file = root / rel_path
        assert py_file.exists(), f"expected {rel_path} to exist -- a rename broke this guard"
        imported = _imported_top_level_names(py_file)
        hit = imported & set(SIM_FORBIDDEN_PREFIXES)
        if hit:
            violations.append(f"{rel_path} imports {sorted(hit)}")
    assert not violations, (
        "sim/episode.py (and sim/protocols.py, the contract it depends on) "
        "must not import fly/, mario/, or bridge/ (REFACTOR_PLAN.md section "
        "5.2) -- violations:\n" + "\n".join(violations)
    )
