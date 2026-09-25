"""tool/core/raw_frame_recorder.py -- ease-of-use redesign, Run tab video
player: a cheap, no-brain-panel recording of a run's raw emulator frames,
piped straight to ffmpeg (`-preset ultrafast`) as they're produced --
distinct from render/brain_panel.render_run's own composited video, which
is expensive (measured ~5.1ms/frame, docs/RUNS.md 026) and only ever
built after a run finishes. This one is cheap enough to run on EVERY
Play, live: the output file uses a fragmented-mp4 layout
(`frag_keyframe+empty_moov`) specifically so it's a valid, seekable file
while still being written, not just after `close()` -- the same trick
live-streaming tools use to make an mp4 playable mid-write. That's what
lets the Run tab's player show a run "live" during Play and become
scrubbable afterwards from the exact same file, no second encode.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np

FFMPEG_NOT_FOUND_MESSAGE = (
    "ffmpeg not found on PATH -- raw frame recording is skipped, not a hard failure "
    "(RenderSettings.raw_frames stays requested, tool_settings isn't changed)."
)


def ffmpeg_available() -> bool:
    """There is no system ffmpeg install here -- render/video.py's own
    `_ensure_ffmpeg_on_path()` (already relied on by run_steering.py's
    brain-panel video path) copies imageio-ffmpeg's bundled static binary
    to a plain `ffmpeg.exe` and puts it on PATH. Found live: without
    calling this first, `shutil.which("ffmpeg")` returns None here and
    every raw-frame recording silently produced no file at all."""
    from render.video import _ensure_ffmpeg_on_path
    _ensure_ffmpeg_on_path()
    return shutil.which("ffmpeg") is not None


class RawFrameRecorder:
    """`write_frame(obs)` once per real emulator frame, `close()` once at
    the end of the episode (normal end OR cancel -- both call it, a half
    -written file is still a valid, playable one thanks to the fragmented
    layout). Raises nothing on ffmpeg failure after construction --
    `write_frame`/`close` degrade to a no-op if the pipe ever breaks, so a
    recording problem can never take an actual simulation run down with
    it (the same "never crash the app over a missing/broken asset"
    convention tool/ui/widgets/asset_image.py already follows)."""

    def __init__(self, out_path: str | Path, width: int = 256, height: int = 240, fps: int = 60):
        self.out_path = Path(out_path)
        self.width = width
        self.height = height
        self._broken = False
        self._process: subprocess.Popen | None = None
        if not ffmpeg_available():
            self._broken = True
            return
        self.out_path.parent.mkdir(parents=True, exist_ok=True)
        self._process = subprocess.Popen(
            ["ffmpeg", "-v", "error", "-y",
             "-f", "rawvideo", "-pixel_format", "rgb24",
             "-video_size", f"{width}x{height}", "-framerate", str(fps),
             "-i", "-",
             "-an", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
             "-movflags", "frag_keyframe+empty_moov+default_base_moof",
             str(self.out_path)],
            stdin=subprocess.PIPE,
            # Explicit DEVNULL, not inherited: this Popen runs INSIDE a
            # multiprocessing worker (tool/core/runner.py) -- found live,
            # intermittently (~1/3 of runs under test), the worker process
            # never sent its "done" message at all, consistent with a
            # rare Windows handle-inheritance stall on a subprocess-of-a-
            # subprocess sharing stdout/stderr. Cheap insurance either way.
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

    def write_frame(self, obs: np.ndarray) -> None:
        if self._broken or self._process is None or self._process.stdin is None:
            return
        try:
            self._process.stdin.write(np.ascontiguousarray(obs).tobytes())
        except (BrokenPipeError, OSError):
            self._broken = True

    def close(self) -> Path | None:
        """Deliberately does NOT wait for ffmpeg to exit. Found live: on
        this machine, waiting on the process -- with a plain timeout, and
        even with a watchdog thread force-killing it after a hard
        deadline -- still hung the whole simulation worker intermittently
        (roughly half of runs, under test). ffmpeg is a genuinely separate
        process, not killed when this one exits on Windows, so it simply
        keeps encoding/flushing in the background after this call returns
        -- the fragmented-mp4 layout (`frag_keyframe+empty_moov`) is
        exactly what makes that safe to read from mid-flush, which is the
        whole reason that layout was chosen over a plain mp4. The
        remaining risk -- the player opens the file in the brief window
        before ffmpeg finishes flushing the last fragment -- is a smaller
        and more honest one than a guaranteed intermittent hang."""
        if self._broken or self._process is None:
            return None
        try:
            self._process.stdin.close()
        except Exception:
            self._broken = True
            return None
        return self.out_path
