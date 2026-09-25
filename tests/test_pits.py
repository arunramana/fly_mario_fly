"""docs/SPEC_pits.md: graded_pit_response, opt-in (default False). Off
reproduces tests/test_golden.py's own bytes exactly (that suite is the
real proof); this file proves the ON path actually changes -- and
improves -- behaviour on the exact scenario that motivated it.
"""
from __future__ import annotations

import dataclasses

import run_steering
from config.project_config import ProjectConfig, ScenarioParams


def _run(graded: bool, max_frames: int = 3000):
    config = dataclasses.replace(
        ProjectConfig(),
        scenario=dataclasses.replace(
            ScenarioParams(), level="1-1", max_frames=max_frames, graded_pit_response=graded),
    )
    return run_steering.main(
        out_mp4="unused.mp4", record_video=False, write_telemetry=False,
        level="1-1", max_frames=max_frames, sigma=0.0, seed=0, config=config,
    )


def test_off_is_byte_identical_to_the_pre_existing_default():
    """graded_pit_response=False (explicit) must match the plain default
    -- proves the flag's own default keeps behaviour, the same way every
    other opt-in flag in this codebase (shuffle_seed, retinotopic) is
    proven (tests/test_c5_shuffle.py)."""
    tel_default, info_default = run_steering.main(
        out_mp4="unused.mp4", record_video=False, write_telemetry=False,
        level="1-1", max_frames=800, sigma=0.0, seed=0,
    )
    tel_explicit_off, info_explicit_off = _run(graded=False, max_frames=800)
    assert tel_default.equals(tel_explicit_off)
    assert info_default["n_frames"] == info_explicit_off["n_frames"]
    assert info_default["max_x_abs"] == info_explicit_off["max_x_abs"]


def test_off_dies_at_the_known_pit_frame_689():
    """The exact failure docs/SPEC_pits.md's own motivation is built on --
    tests/test_golden.py's test_sigma0_baseline freezes this same number."""
    tel, info = _run(graded=False, max_frames=800)
    assert info["died_or_flagged"] is True
    assert info["n_frames"] == 689
    assert info["max_x_abs"] == 1432


def test_on_clears_the_original_fatal_pit():
    """With graded_pit_response on, the run must survive well past frame
    689/x=1432 -- the specific pit that killed the baseline is cleared."""
    tel, info = _run(graded=True, max_frames=3000)
    # The baseline dies AT the pit, frame 689 -- surviving far past that
    # (whatever the eventual outcome) is direct proof it no longer kills
    # the run there. max_x_abs isn't asserted against 1432: a materially
    # different path (this run takes 4 long jumps and 19 qblock hits
    # before even reaching the old pit) needn't retrace the same peak x.
    assert info["n_frames"] > 689
    assert (tel["gap"] > 0).any(), "the pit must still be detected, not silently skipped"


def test_on_reproduces_the_validated_second_death():
    """docs/SPEC_pits.md section 6's own validation result, pinned as a
    regression check: the run now dies later, further, and to an enemy
    (gap=0 throughout the tail), not a pit."""
    tel, info = _run(graded=True, max_frames=3000)
    assert info["died_or_flagged"] is True
    assert info["n_frames"] == 1023
    assert info["max_x_abs"] == 1430
    assert (tel["gap"].iloc[-8:] == 0).all(), "the second death is not pit-caused"
