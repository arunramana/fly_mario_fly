"""One command to see the fly play: the champion fly on World 1-1 with a fixed seed.

    python scripts/demo.py                  # play it, print the summary (about 1-2 minutes after the data is in place)
    python scripts/demo.py --video          # also render an mp4 of the run (game + brain + senses)

Needs $FLY_MARIO_FLY_DATA (run scripts/download_data.py first; the first run also builds the brain cache).
The run is deterministic: seed 101 prints the same `hash` every time on the same pinned install.
"""
import argparse

from fly_mario_fly.runner.__main__ import main as run_main

ARGS = ["run", "champion_e1s", "--level", "1-1", "--noop", "3", "--sigma", "0.05", "--seed", "101", "--run-id", "demo"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--video", action="store_true", help="also render an mp4 under $FLY_MARIO_FLY_DATA/videos/")
    args = ap.parse_args(argv)
    code = run_main(ARGS)
    if args.video:
        from fly_mario_fly.render.__main__ import main as render_main
        render_main(["run", "demo"])
    return code


if __name__ == "__main__":
    raise SystemExit(main())
