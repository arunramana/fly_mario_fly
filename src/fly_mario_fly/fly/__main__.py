"""python -m fly_mario_fly.fly build-brains [--force]  -- build every brain from a clean state."""
from __future__ import annotations

import argparse
import time

from fly_mario_fly.fly import brain as fb
from fly_mario_fly.fly import connectome as cn


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="python -m fly_mario_fly.fly")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build-brains", help="download MaleCNS if missing and build every brain")
    b.add_argument("--force", action="store_true", help="rebuild even when a cached brain exists")
    args = ap.parse_args(argv)
    if args.cmd == "build-brains":
        t0 = time.time()
        conn = cn.Connectome()
        for spec in fb.all_specs():
            brain = fb.build_brain(spec, conn, force=args.force)
            print(f"{fb.brain_name(spec):45s} {brain.n:4d} neurons  {fb.brain_path(spec).name}")
        print(f"done in {time.time() - t0:.0f} s -> {cn.data_dir() / 'brains'}")


if __name__ == "__main__":
    main()
