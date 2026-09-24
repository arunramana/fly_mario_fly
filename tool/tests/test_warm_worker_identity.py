"""tool/PLAN.md P2's hard prerequisite for persistent warm workers: a
reused worker's telemetry must be byte-for-byte identical to the same
RunSpec run in a fresh process. Not assumed safe -- this is exactly the
scenario C10 fixed (tool/CODEBASE_CHANGES.md): a warm worker running
episode 2 right after episode 1 in the same process used to inherit
FullPolicy._last_x from episode 1's last frame.
"""
from __future__ import annotations

import dataclasses
import filecmp
import multiprocessing as mp
import shutil
from pathlib import Path

import pytest

from config.output_routing import PROJECTS_ROOT
from config.project_config import ProjectConfig
from tool.core.run_spec import RunSpec
from tool.core.runner import run_one
from tool.core.tool_settings import ToolSettings

PROJECT_NAME = "_warm_worker_identity_test"
SCENARIO_KW = dict(level="1-1", max_frames=300, seed=0)


def _spec(out_filename: str) -> RunSpec:
    cfg = ProjectConfig(
        scenario=dataclasses.replace(ProjectConfig().scenario,
                                      level=SCENARIO_KW["level"], max_frames=SCENARIO_KW["max_frames"]),
        output=dataclasses.replace(ProjectConfig().output, project_name=PROJECT_NAME),
    )
    return RunSpec(project_name=PROJECT_NAME, config=cfg, tool_settings=ToolSettings(),
                    seed=SCENARIO_KW["seed"], out_filename=out_filename)


def _telemetry_path(out_filename: str) -> Path:
    stem = out_filename.rsplit(".", 1)[0]
    return PROJECTS_ROOT / PROJECT_NAME / "telemetry" / f"{stem}_telemetry.csv"


@pytest.fixture
def clean_project():
    root = PROJECTS_ROOT / PROJECT_NAME
    shutil.rmtree(root, ignore_errors=True)
    yield
    shutil.rmtree(root, ignore_errors=True)


def _run_two_specs_in_worker(specs):
    """Runs both specs through ONE multiprocessing.Pool worker (a real
    process, reused for the second task the same way a batch's warm pool
    would) -- Pool with processes=1 guarantees the same worker handles
    both, sequentially, matching "episode 2 right after episode 1"."""
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=1) as pool:
        pool.map(_run_for_pool, specs)


def _run_for_pool(spec):
    run_one(spec)
    return None


def test_warm_worker_second_run_matches_a_fresh_process(clean_project):
    spec_a = _spec("a.mp4")
    spec_b = _spec("b.mp4")

    # B run alone, in THIS process, which has never run any FullPolicy
    # instance yet for this test -- the "fresh process" baseline.
    run_one(spec_b)
    fresh_csv = _telemetry_path("b.mp4")
    assert fresh_csv.exists()
    fresh_bytes = fresh_csv.read_bytes()
    fresh_csv.unlink()  # so the warm-pool run below can't accidentally compare against itself

    # A then B, through the SAME single-worker pool -- B here is "episode
    # 2 right after episode 1" in one reused process.
    _run_two_specs_in_worker([spec_a, spec_b])
    warm_csv = _telemetry_path("b.mp4")
    assert warm_csv.exists()

    assert warm_csv.read_bytes() == fresh_bytes, (
        "B's telemetry differs depending on whether it ran alone or as "
        "the second task on a reused worker -- a warm worker pool would "
        "silently change training/batch results depending on run order, "
        "exactly the failure mode C10 fixed for FullPolicy's own "
        "_prev_avoid_odor/_last_x"
    )
