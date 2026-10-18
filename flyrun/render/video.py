"""Replay the emulator from the logged actions (frames only), draw the three panels, write PNG stills or an mp4 (60 fps)."""
from pathlib import Path

import cv2
import numpy as np

from .. import env as E
from ..run import _get_env
from .panels import Log, Renderer

ROOT = Path(__file__).resolve().parents[1]


def replay(log, upto=None):
    """Yield (k, NES frame BEFORE action k). Checks every step against the logged x (the emulator is deterministic)."""
    env = _get_env()
    state = env.reset()
    acts = log.df.action.to_numpy()
    xs = log.df.x.to_numpy()
    for k in range(len(acts) if upto is None else upto + 1):
        yield k, np.asarray(state).copy()
        state, _, done, info = env.step(int(acts[k]))
        assert int(info.get("x_pos", xs[k])) == xs[k], f"replay diverged at frame {k}"


def stills(base, frames, outdir, label=None):
    log = Log(base)
    rd = Renderer(log, label)
    want = set(frames.values())
    done = {}
    hi = max(want)
    # the renderer keeps ring-flash state, so feed it every frame in order (no PNG for the others)
    for k, nes in replay(log, hi):
        if k in want or k >= hi - 0:
            img = rd.frame(nes, k)
            done[k] = img
        else:
            rd.brain.draw(k)      # advance the ring state
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    for name, k in frames.items():
        cv2.imwrite(str(outdir / f"{name}.png"), cv2.cvtColor(done[k], cv2.COLOR_RGB2BGR))
    return {n: (outdir / f"{n}.png") for n in frames}


def video(base, path, label=None, fps=60):
    log = Log(base)
    rd = Renderer(log, label)
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (1920, 1080))
    for k, nes in replay(log):
        vw.write(cv2.cvtColor(rd.frame(nes, k), cv2.COLOR_RGB2BGR))
        if k % 300 == 0:
            print("frame", k, "/", len(log), flush=True)
    vw.release()
    print(path, len(log), "frames = %.1f s" % (len(log) / fps))
