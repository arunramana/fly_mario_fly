"""tool/PLAN.md C7: `hunger_override` and starting power-up (the latter
reuses the existing `force_mario_size`/`force_size_from_frame`, no new
codebase surface). A science change when actually used (CLAUDE.md rule
3) -- this proves the plumbing works, not that using it is a good idea.
"""
from __future__ import annotations

import run_steering

SCENARIO = dict(level="1-1", max_frames=300, sigma=0.0, seed=0,
                 record_video=False, write_telemetry=False)


def test_hunger_override_changes_odour_telemetry(tmp_path):
    tel_default, _ = run_steering.main(out_mp4=str(tmp_path / "default.mp4"), **SCENARIO)
    tel_sated, _ = run_steering.main(out_mp4=str(tmp_path / "sated.mp4"),
                                      hunger_override=False, **SCENARIO)
    assert not tel_default["hungry"].equals(tel_sated["hungry"]), (
        "hunger_override=False produced identical 'hungry' telemetry to "
        "the RAM-driven default"
    )
    assert not tel_sated["hungry"].any(), "hunger_override=False must force 'hungry' False every frame"

    tel_hungry, _ = run_steering.main(out_mp4=str(tmp_path / "hungry.mp4"),
                                       hunger_override=True, **SCENARIO)
    assert tel_hungry["hungry"].all(), "hunger_override=True must force 'hungry' True every frame"


def test_hunger_override_none_reproduces_default_exactly(tmp_path):
    tel_default, _ = run_steering.main(out_mp4=str(tmp_path / "default.mp4"), **SCENARIO)
    tel_explicit_none, _ = run_steering.main(out_mp4=str(tmp_path / "none.mp4"),
                                              hunger_override=None, **SCENARIO)
    assert tel_default.equals(tel_explicit_none)


def test_starting_powerup_reuses_existing_force_mario_size(tmp_path):
    """No new codebase surface for this half of C7 -- force_mario_size=1,
    force_size_from_frame=0 (already-existing kwargs) IS "start big"."""
    tel_small, info_small = run_steering.main(out_mp4=str(tmp_path / "small.mp4"), **SCENARIO)
    tel_big, info_big = run_steering.main(out_mp4=str(tmp_path / "big.mp4"),
                                           force_mario_size=1, force_size_from_frame=0, **SCENARIO)
    assert (tel_big["mario_size"] == 1).all(), "force_mario_size=1 from frame 0 must hold all episode"
    assert not tel_small["mario_size"].equals(tel_big["mario_size"])
