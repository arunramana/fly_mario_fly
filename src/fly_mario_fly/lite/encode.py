"""H.264 mp4 for the web: small, starts playing at once (moov first), plays everywhere (yuv420p)."""
from __future__ import annotations

import numpy as np


class Encoder:
    def __init__(self, path, size: tuple, fps: int, crf: int):
        import imageio_ffmpeg
        self.size = size
        self.gen = imageio_ffmpeg.write_frames(
            str(path), size, fps=fps, codec="libx264", pix_fmt_in="rgb24", pix_fmt_out="yuv420p", quality=None, macro_block_size=1,
            output_params=["-crf", str(crf), "-preset", "veryfast", "-tune", "animation", "-movflags", "+faststart",
                           "-g", str(fps * 2), "-threads", "1"])
        self.gen.send(None)
        self.frames = 0

    def write(self, img: np.ndarray) -> None:
        h, w = img.shape[:2]
        assert (w, h) == self.size, f"frame is {w}x{h}, the video is {self.size[0]}x{self.size[1]}"
        self.gen.send(np.ascontiguousarray(img).tobytes())
        self.frames += 1

    def close(self) -> None:
        self.gen.close()
