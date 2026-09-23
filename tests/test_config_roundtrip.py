"""REFACTOR_PLAN.md phase 5: "Prove the config round-trip: load
projects/legacy/config.json, run the 017 scenario from it alone, and
assert byte-identical telemetry. That is the first moment a project is
reproducible from one file."

Deliberately writes to the REAL projects/legacy/telemetry/ (resolved via
config.output.project_name="legacy", not a pytest tmp_path) -- the whole
point is proving output routing lands in the right place, not just that
main() itself is byte-identical (tests/test_golden.py already covers
that). Re-running this test overwrites the same bytes each time (the
scenario is byte-identical by construction), which is idempotent, not the
"lost a video to a blanket delete" hazard CLAUDE.md warns about (different
content silently replacing different content) -- distinctly named
(`017_reprise_config_roundtrip`) so it's never confused with an actual
sprint run.
"""
from __future__ import annotations

import filecmp
from pathlib import Path

from sim.project_runner import load_project_config, run_from_config
from config.output_routing import resolve_run_path, resolve_telemetry_path

CONFIG_PATH = Path(__file__).parent.parent / "projects" / "legacy" / "config.json"
GOLDEN = Path(__file__).parent / "golden" / "017_reprise_telemetry.csv"
OUT_FILENAME = "017_reprise_config_roundtrip.mp4"


def test_projects_legacy_config_json_exists():
    assert CONFIG_PATH.exists(), (
        f"{CONFIG_PATH} is missing -- the config round-trip proof needs a "
        "real, committed config file, not one built inline in the test"
    )


def test_config_round_trip_reproduces_017_byte_identical():
    config = load_project_config(CONFIG_PATH)
    assert config.output.project_name == "legacy"
    assert config.scenario.level == "1-1"
    assert config.scenario.max_frames == 1500
    assert config.scenario.inject_gap_frame == 600

    run_from_config(config, OUT_FILENAME)

    produced = resolve_telemetry_path(config, Path(OUT_FILENAME).stem + "_telemetry.csv")
    assert produced.exists(), f"{produced} was not written"
    assert filecmp.cmp(produced, GOLDEN, shallow=False), (
        f"{produced} (driven entirely by {CONFIG_PATH}) no longer matches "
        f"the frozen golden {GOLDEN} -- diff the two files before "
        "re-baselining, per this project's own rule for a golden failure."
    )


def test_run_without_a_named_project_fails_loudly():
    """The other half of REFACTOR_PLAN.md phase 5's output-routing ask:
    resolving a path without a project name raises, rather than silently
    falling back to a stray top-level folder."""
    from config.project_config import ProjectConfig
    import pytest

    unnamed = ProjectConfig()  # output.project_name defaults to None
    with pytest.raises(ValueError, match="project_name is required"):
        resolve_run_path(unnamed, "whatever.mp4")
    with pytest.raises(ValueError, match="project_name is required"):
        resolve_telemetry_path(unnamed, "whatever_telemetry.csv")

    import run_steering
    with pytest.raises(ValueError, match="out_mp4"):
        run_steering.main()  # no out_mp4 given at all -- the same failure, one level up
