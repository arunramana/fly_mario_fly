"""tool/CODEBASE_CHANGES.md C13: two additive, display-only extensions to
run_steering.main()'s on_frame contract -- mario_y in every row (for the
Luigi-recolour box) and death_animation_frames (extra frames purely for a
recording, after a real death/flag). Neither touches telemetry or fitness;
tests/test_golden.py already proves default behaviour is unchanged.
"""
from __future__ import annotations

import run_steering


def test_mario_y_is_in_on_frame_rows_but_not_in_telemetry_columns(tmp_path):
    seen_rows = []
    tel, info = run_steering.main(
        out_mp4=str(tmp_path / "run.mp4"), record_video=False, write_telemetry=False,
        level="1-1", max_frames=30, sigma=0.0, seed=0,
        on_frame=lambda frame, obs, row: seen_rows.append(row),
    )
    assert all("mario_y" in row for row in seen_rows), "every on_frame row should carry mario_y"
    assert "mario_y" not in tel.columns, "mario_y must stay a display-only extra, never a CSV column"


def test_death_animation_frames_extends_on_frame_not_telemetry_or_fitness():
    """sigma=0.0 seed=0, 1-1, max_frames=800: the same deterministic death
    tests/test_golden.py's test_sigma0_baseline freezes (dies at frame 689,
    max_x=1432) -- reused here because it's a real, reproducible death, not
    a synthetic one."""
    seen_frames = []

    def on_frame(frame, obs, row):
        seen_frames.append(frame)

    tel0, info0 = run_steering.main(
        out_mp4="unused.mp4", record_video=False, write_telemetry=False,
        level="1-1", max_frames=800, sigma=0.0, seed=0,
        death_animation_frames=0,
    )
    assert info0["died_or_flagged"] is True

    tel90, info90 = run_steering.main(
        out_mp4="unused.mp4", record_video=False, write_telemetry=False,
        level="1-1", max_frames=800, sigma=0.0, seed=0,
        death_animation_frames=90, on_frame=on_frame,
    )

    assert info90["n_frames"] == info0["n_frames"], "the extension must not change the reported frame count"
    assert info90["max_x_abs"] == info0["max_x_abs"]
    assert len(tel90) == len(tel0), "the extension must never reach observer.record()"
    assert tel90.equals(tel0), "telemetry must be byte-for-byte the same with or without the extension"

    last_real_frame = info0["n_frames"] - 1
    extension_frames = [f for f in seen_frames if f > last_real_frame]
    assert len(extension_frames) == 90, "death_animation_frames=90 on a real death must add exactly 90 frames"
    assert extension_frames == list(range(last_real_frame + 1, last_real_frame + 91))


def test_death_animation_frames_does_nothing_on_a_run_that_hits_max_frames():
    """No death, no flag: death_animation_frames must not fire just because
    the episode ended -- only a real done=True triggers it."""
    seen_frames = []
    tel, info = run_steering.main(
        out_mp4="unused.mp4", record_video=False, write_telemetry=False,
        level="1-1", max_frames=50, sigma=0.0, seed=0,
        death_animation_frames=90, on_frame=lambda frame, obs, row: seen_frames.append(frame),
    )
    assert info["died_or_flagged"] is False
    assert max(seen_frames) == info["n_frames"] - 1, "no extra frames beyond the real episode"
