"""Test-suite wiring.

`parity_old` marks the tests that import the old repo's code (tests/parity/). They are skipped unless that code is
present (a folder holding `flyrun/` above this one). The answers they compare against are frozen in tests/data/golden/
and checked by tests/golden/ with no old code at all, so a copy of fly_mario/ on its own passes the whole suite.
"""
from pathlib import Path

import pytest


def old_code_present() -> bool:
    return any((p / "flyrun" / "__init__.py").exists() for p in Path(__file__).resolve().parents)


def pytest_collection_modifyitems(config, items):
    if old_code_present():
        return
    skip = pytest.mark.skip(reason="old repo code (flyrun/) not present; see tests/golden/ for the frozen comparison")
    for item in items:
        if "parity_old" in item.keywords:
            item.add_marker(skip)
