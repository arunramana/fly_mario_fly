"""Phase 0 of REFACTOR_PLAN.md: characterisation tests.

Freezes telemetry from three runs and asserts a fresh `run_steering.main()`
call reproduces each one byte-for-byte. This is the only thing that makes
the restructure in REFACTOR_PLAN.md safe to attempt: if the system is not
this deterministic, every later phase's "goldens still pass" check is
worthless.

Comparison is against the on-disk CSV bytes (CRLF, as `DataFrame.to_csv`
writes them on Windows in text mode), not an in-memory DataFrame diff --
"byte-identical" is the literal claim being tested.
"""
from __future__ import annotations

import filecmp
from pathlib import Path

import run_steering

GOLDEN_DIR = Path(__file__).parent / "golden"


def _run_and_compare(tmp_path, golden_name, **kwargs):
    out_mp4 = tmp_path / "run.mp4"
    run_steering.main(out_mp4=str(out_mp4), record_video=False,
                       write_telemetry=True, **kwargs)
    produced = out_mp4.with_name(out_mp4.stem + "_telemetry.csv")
    golden = GOLDEN_DIR / golden_name
    assert filecmp.cmp(produced, golden, shallow=False), (
        f"{produced} no longer matches frozen golden {golden}. "
        "Diff the two files before re-baselining -- this is the "
        "regression the golden exists to catch (CLAUDE.md, sprint 9's "
        "risk list: 'if one fails, stop and diff rather than "
        "re-baselining')."
    )


def test_017_reprise(tmp_path):
    """026's re-run of 017's exact scenario: 1-1, the sprint-016 synthetic
    wide-gap injection at frame 600, sigma=0.0 (017 predates noise)."""
    _run_and_compare(tmp_path, "017_reprise_telemetry.csv",
                      level="1-1", max_frames=1500, inject_gap_frame=600,
                      retinotopic=False, sigma=0.0)


def test_025b_noise_bad(tmp_path):
    """025's calibrated sigma=0.04, seed=5 -- the "later commitment cost a
    life" case: commits one frame later than the sigma=0 baseline and dies
    at frame 406 instead of 689. Same config as 025's calibration sweep:
    1-1, max_frames=800, no gap injection."""
    _run_and_compare(tmp_path, "025b_telemetry.csv",
                      level="1-1", max_frames=800, sigma=0.04, seed=5)


def test_sigma0_baseline(tmp_path):
    """sigma=0.0 baseline at the same config as 025's sweep (1-1,
    max_frames=800, no gap injection). Matches 025's own reference point
    exactly: DNp01 commits at frame 148, dies at frame 689, max_x=1432.
    No golden existed for this exact config before this sprint -- frozen
    here, not carried over from an earlier run."""
    _run_and_compare(tmp_path, "sigma0_baseline_telemetry.csv",
                      level="1-1", max_frames=800, sigma=0.0, seed=0)
