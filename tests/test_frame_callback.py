"""tool/PLAN.md C3: `main(on_frame=None, should_stop=None)` -- the live
preview's frame hook and the Cancel button's stop check. Both default to
None (never called, no cost); each is proven separately, plus that
neither changes recorded behaviour when unused.
"""
from __future__ import annotations

import numpy as np

import run_steering

SCENARIO = dict(level="1-1", max_frames=800, sigma=0.0, seed=0,
                 record_video=False, write_telemetry=False)


def test_on_frame_receives_frame_index_obs_and_row(tmp_path):
    seen = []

    def on_frame(frame, obs, row):
        seen.append((frame, obs.shape, row["frame"]))

    tel, info = run_steering.main(out_mp4=str(tmp_path / "cb.mp4"), on_frame=on_frame, **SCENARIO)

    assert len(seen) == info["n_frames"], (
        "on_frame wasn't called exactly once per emulator frame"
    )
    assert seen[0][0] == 0 and seen[-1][0] == info["n_frames"] - 1
    assert all(shape == seen[0][1] for _, shape, _ in seen), "obs frame shape changed mid-episode"
    assert [s[2] for s in seen] == list(range(info["n_frames"])), (
        "row['frame'] handed to on_frame doesn't match the frame index it was called with"
    )


def test_should_stop_ends_the_episode_early(tmp_path):
    stop_at = 50
    calls = {"n": 0}

    def should_stop():
        calls["n"] += 1
        return calls["n"] >= stop_at

    tel, info = run_steering.main(out_mp4=str(tmp_path / "cancel.mp4"),
                                   should_stop=should_stop, **SCENARIO)

    assert info["n_frames"] == stop_at, (
        f"expected the episode to stop at frame {stop_at}, got {info['n_frames']}"
    )
    assert len(tel) == stop_at


def test_default_none_reproduces_identical_telemetry(tmp_path):
    """The new arguments must be genuinely additive -- unused, they cannot
    change a single byte of what main() already produced."""
    tel_plain, info_plain = run_steering.main(out_mp4=str(tmp_path / "plain.mp4"), **SCENARIO)
    tel_hooked, info_hooked = run_steering.main(
        out_mp4=str(tmp_path / "hooked.mp4"), on_frame=lambda *a: None,
        should_stop=lambda: False, **SCENARIO)

    assert tel_plain.equals(tel_hooked)
    assert info_plain["n_frames"] == info_hooked["n_frames"]
    assert info_plain["died_or_flagged"] == info_hooked["died_or_flagged"]
