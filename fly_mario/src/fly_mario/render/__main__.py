"""python -m fly_mario.render <run_dir> --still FRAME | --video [--no-senses] [--no-brain] [--out PATH]

<run_dir> is a folder under $FLY_MARIO_DATA/runs/ (or just its name). Output defaults to <run_dir>/render/.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import cv2

from fly_mario.render import source
from fly_mario.render.draw import H, W, Renderer


def _suffix(a) -> str:
    return ("_nosenses" if a.no_senses else "") + ("_nobrain" if a.no_brain else "")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m fly_mario.render")
    ap.add_argument("run_dir")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--still", type=int, metavar="FRAME", help="one PNG of this frame (idle frames counted)")
    g.add_argument("--video", action="store_true", help="the whole run as an mp4")
    ap.add_argument("--no-senses", action="store_true", help="leave the game pixels untouched (no overlay)")
    ap.add_argument("--no-brain", action="store_true", help="game only, centred")
    ap.add_argument("--out", default=None)
    ap.add_argument("--fps", type=int, default=60)
    a = ap.parse_args(argv)

    run_dir = Path(a.run_dir)
    if not run_dir.exists():
        run_dir = Path(os.environ["FLY_MARIO_DATA"]) / "runs" / a.run_dir
    run = source.load_run(run_dir)
    brain = None if a.no_brain else source.brain_data(run, run_dir)
    rd = Renderer(brain, show_senses=not a.no_senses, show_brain=not a.no_brain)

    if a.still is not None:
        out = Path(a.out) if a.out else run_dir / "render" / f"still_{a.still:05d}{_suffix(a)}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        img = rd.frame(source.still_frame(run, a.still))
        cv2.imwrite(str(out), cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
        print(out)
        return 0

    out = Path(a.out) if a.out else run_dir / "render" / f"run{_suffix(a)}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    vw = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*"mp4v"), a.fps, (W, H))
    n = 0
    for fd in source.frames(run):
        vw.write(cv2.cvtColor(rd.frame(fd), cv2.COLOR_RGB2BGR))
        n += 1
        if n % 300 == 0:
            print("frame", n, flush=True)
    vw.release()
    print(out, n, "frames", "(replay matches the recorded hash)" if source.check_hash(run, run_dir) else "(WARNING: replay hash differs from the recording)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
