"""Judge flies on the level's fixed dev set (configs/dev_sets.yaml: 10 starts, never used for training). Reproduces the README's results table.

    python scripts/evaluate.py champion_e1s looming_only blank [--level 1-1] [--workers 4]

Needs the MaleCNS brain cache ($FLY_MARIO_FLY_DATA, see the README). Same stop rules as the evolution (3000 frames, 150 stuck frames).
"""
import argparse
import sys

from fly_mario_fly.evolve import devset
from fly_mario_fly.runner import load_fly


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("flies", nargs="+", help="fly names in configs/flies/ (or yaml paths)")
    ap.add_argument("--level", default="1-1")
    ap.add_argument("--workers", type=int, default=0, help="processes (0 = this process)")
    args = ap.parse_args(argv)
    print(f"{'fly':16s} {'level':5s} {'flags':>7s} {'mean max x':>11s}   outcomes by start (noop/sigma/seed)")
    for name in args.flies:
        try:
            res = devset.evaluate(load_fly(name), args.level, "tuned", workers=args.workers)
        except RuntimeError as e:                    # $FLY_MARIO_FLY_DATA not set
            print(e, file=sys.stderr)
            return 2
        s = res["summary"]
        outs = " ".join(f"{e['outcome'][:4]}" for e in res["episodes"])
        print(f"{name:16s} {args.level:5s} {s['flags']:>3d}/{s['n']:<3d} {s['mean_max_x']:>11.0f}   {outs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
