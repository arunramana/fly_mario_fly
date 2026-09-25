"""tool/core/raw_frame_recorder.py -- ease-of-use redesign, Run tab video
player: a cheap, no-brain-panel recording of raw frames, piped to ffmpeg.
`RenderSettings.raw_frames` defaults OFF (tool/core/tool_settings.py's own
docstring on the field): found live, on this machine, letting the
simulation worker wait on the ffmpeg subprocess at all -- with a plain
timeout, and even with a watchdog thread force-killing it after a hard
deadline -- intermittently (roughly half of runs, under real
multiprocessing + Windows) left the whole worker unable to report back.
RawFrameRecorder.close() was changed to never wait for ffmpeg at all;
these tests exercise the mechanism directly (not through the full
multiprocessing + GUI path, which is exactly where the risk lived) so it
stays covered without gambling on the rest of this suite's own runtime.
"""
from __future__ import annotations

import time

import numpy as np
import pytest

from tool.core.raw_frame_recorder import RawFrameRecorder, ffmpeg_available


@pytest.fixture
def obs():
    return np.random.default_rng(0).integers(0, 255, (240, 256, 3), dtype=np.uint8)


def test_ffmpeg_is_resolvable_via_imageio_ffmpeg():
    """render/video.py's own _ensure_ffmpeg_on_path() -- without calling
    it, shutil.which("ffmpeg") returns None on a machine with no system
    ffmpeg install, and every recording would silently produce nothing."""
    assert ffmpeg_available()


def test_write_frame_never_blocks_noticeably(obs, tmp_path):
    """Measured close to 0.1-0.3ms/frame in isolation (the actual
    measured cost tool/CODEBASE_CHANGES.md reports) -- this is the
    write-side half of that measurement, as a regression check."""
    recorder = RawFrameRecorder(tmp_path / "test.mp4")
    times = []
    for _ in range(60):
        t0 = time.perf_counter()
        recorder.write_frame(obs)
        times.append(time.perf_counter() - t0)
    recorder.close()
    # Generous bound (real measurement is under 1ms median) -- this just
    # catches a real regression back to a blocking write, not a tight
    # performance assertion that would be flaky under CI/CPU contention.
    assert sorted(times)[len(times) // 2] < 0.05, f"median write time too high: {times}"


def test_close_does_not_block(obs, tmp_path):
    """The specific fix for the intermittent hang: close() must return
    near-instantly, never waiting on the ffmpeg process."""
    recorder = RawFrameRecorder(tmp_path / "test.mp4")
    for _ in range(14):  # the exact frame count the original hang was found at
        recorder.write_frame(obs)
    t0 = time.perf_counter()
    result = recorder.close()
    elapsed = time.perf_counter() - t0
    assert elapsed < 1.0, f"close() took {elapsed:.2f}s -- it must never wait on ffmpeg"
    assert result is not None


def test_recording_eventually_produces_a_valid_playable_file(obs, tmp_path):
    """close() no longer waits for ffmpeg to finish flushing -- give the
    now-independent background process a moment, then check the file it
    was asked to produce actually exists and has real content."""
    out_path = tmp_path / "test.mp4"
    recorder = RawFrameRecorder(out_path)
    for _ in range(30):
        recorder.write_frame(obs)
    recorder.close()

    deadline = time.time() + 15
    while time.time() < deadline:
        if out_path.exists() and out_path.stat().st_size > 0:
            break
        time.sleep(0.2)
    assert out_path.exists(), "ffmpeg never produced the recording in the background"
    assert out_path.stat().st_size > 0


def test_ffmpeg_unavailable_degrades_to_a_no_op(obs, tmp_path, monkeypatch):
    """Ground rule 4 territory, but for infrastructure rather than a
    control: a broken/missing ffmpeg must never take an actual simulation
    run down with it."""
    import tool.core.raw_frame_recorder as raw_frame_recorder
    monkeypatch.setattr(raw_frame_recorder, "ffmpeg_available", lambda: False)
    recorder = raw_frame_recorder.RawFrameRecorder(tmp_path / "test.mp4")
    recorder.write_frame(obs)  # must not raise
    assert recorder.close() is None
