"""Download the MaleCNS v1.0 files this project needs (about 1.2 GB, public, CC-BY 4.0) and stop.

    export FLY_MARIO_FLY_DATA=~/fly_mario_fly_data     # any folder outside the repo
    python scripts/download_data.py [--build-brains]

Resumable: re-run it after an interruption. Files that are already complete are skipped. It does not check hashes (Janelia
publishes none for these files); `Connectome()` checks the body count (N_BODIES) when it loads them.
--build-brains also builds and caches every brain (about 5 more minutes), same as `python -m fly_mario_fly.fly build-brains`.
"""
import argparse
import sys

from fly_mario_fly.fly import connectome as cn


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--build-brains", action="store_true", help="also build and cache every brain")
    args = ap.parse_args(argv)
    try:
        folder = cn.ensure_data()
    except RuntimeError as e:
        print(e, file=sys.stderr)
        return 2
    print(f"MaleCNS v1.0 files are in {folder}")
    if args.build_brains:
        from fly_mario_fly.fly.__main__ import main as fly_main
        fly_main(["build-brains"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
