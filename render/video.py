# What this file does, in plain English:
# Makes the ffmpeg video tool findable so brain_panel.py can call it to
# build videos. It copies the ffmpeg program bundled with the imageio-ffmpeg
# package to a plain "ffmpeg.exe" name and adds its folder to the system
# search path. Used by run_steering.py and scripts/compare_controllers.py.
"""render/video.py -- video-output plumbing shared by run_steering.py and
scripts/compare_controllers.py."""

from __future__ import annotations

from pathlib import Path


def _ensure_ffmpeg_on_path():
    """brain_panel.render_run shells out to a bare `ffmpeg`; there's no
    system install here. imageio-ffmpeg bundles a static binary under a
    version-suffixed name -- copy it to a plain `ffmpeg.exe` once and put
    that directory on PATH, rather than editing brain_panel.py."""
    import os
    import shutil
    import imageio_ffmpeg
    src = imageio_ffmpeg.get_ffmpeg_exe()
    d = Path(src).parent
    dst = d / "ffmpeg.exe"
    if not dst.exists():
        shutil.copy(src, dst)
    os.environ["PATH"] = str(d) + os.pathsep + os.environ["PATH"]
