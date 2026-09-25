"""tool/core/frame_store.py -- Run tab video player: a cheap, no-subprocess
per-run frame recording. Replaces tool/core/raw_frame_recorder.py's ffmpeg
pipe (removed -- that subprocess intermittently raced with worker teardown
on Windows and hung a run even after close() was made non-blocking).

The NES emulator only ever draws a fixed, exact palette -- an emulated NES
has no anti-aliasing or blending, and checked directly (tool/core/
frame_store.py's own probe, a real 1-1 run): a run samples well under 64
distinct RGB colours. So each frame is stored as a uint8 palette INDEX
array instead of RGB, with the small per-run discovered palette saved
alongside it in one compressed .npz. No subprocess, no codec, no format to
get wrong: write_frame() is pure numpy, close() is one np.savez_compressed
call. See tool/CODEBASE_CHANGES.md / RUNS.md for the measured time and
disk cost per run.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

MAX_PALETTE_SIZE = 256


class FrameStore:
    """write_frame(obs) once per emulator frame that should be recorded
    (the caller decides which -- run_steering.py's frame-skip repeats and
    death-animation extension frames all go through the same on_frame
    hook, so they're all recorded the same way). close(out_path) once at
    the end; returns the written path, or None if nothing was ever
    written (an empty recording is not a file worth having)."""

    def __init__(self):
        self._palette: dict[int, int] = {}  # packed 24-bit RGB -> index
        self._palette_rgb: list[tuple[int, int, int]] = []
        self._frames: list[np.ndarray] = []

    def write_frame(self, obs: np.ndarray) -> None:
        frame = np.asarray(obs)
        packed = (frame[..., 0].astype(np.uint32) << 16
                  | frame[..., 1].astype(np.uint32) << 8
                  | frame[..., 2].astype(np.uint32))
        uniq, inverse = np.unique(packed.reshape(-1), return_inverse=True)
        local_to_global = np.empty(len(uniq), dtype=np.uint8)
        for i, key in enumerate(uniq.tolist()):
            idx = self._palette.get(key)
            if idx is None:
                if len(self._palette_rgb) < MAX_PALETTE_SIZE:
                    idx = len(self._palette_rgb)
                    self._palette[key] = idx
                    self._palette_rgb.append(((key >> 16) & 0xFF, (key >> 8) & 0xFF, key & 0xFF))
                else:
                    # Never observed on a real NES frame (~54-colour master
                    # palette) -- clamp rather than crash a run over a
                    # display feature.
                    idx = MAX_PALETTE_SIZE - 1
            local_to_global[i] = idx
        self._frames.append(local_to_global[inverse].reshape(frame.shape[:2]).astype(np.uint8))

    def close(self, out_path) -> Path | None:
        if not self._frames:
            return None
        out_path = Path(out_path)
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(
                out_path,
                frames=np.stack(self._frames, axis=0),
                palette=np.array(self._palette_rgb, dtype=np.uint8),
            )
        except OSError:
            return None
        return out_path


def load_frames(path) -> tuple[np.ndarray, np.ndarray] | None:
    """A run's recording, loaded back for the player: (frames, palette) --
    frames is (N, H, W) uint8 indices into palette, a (K, 3) uint8 RGB
    table. None if the file is missing or unreadable (an older run, or one
    played with raw_frames off) -- "no recording", not a crash."""
    path = Path(path)
    if not path.exists():
        return None
    try:
        with np.load(path) as data:
            return data["frames"], data["palette"]
    except (OSError, ValueError, KeyError):
        return None


def frames_to_rgb(frames: np.ndarray, palette: np.ndarray) -> np.ndarray:
    """Palette indices -> RGB, vectorised; `frames` may be a single (H, W)
    frame or a whole (N, H, W) stack."""
    return palette[frames]
