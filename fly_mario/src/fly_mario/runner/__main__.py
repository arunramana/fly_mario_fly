"""python -m fly_mario.runner run <fly.yaml> --level 1-1 --noop N --sigma S --seed K

Plays one episode and writes it to $FLY_MARIO_DATA/runs/<id>/ (see record.py). Prints the summary.
"""
from __future__ import annotations

import argparse
import json

from fly_mario.contracts import Scene
from fly_mario.runner import config as C
from fly_mario.runner import record
from fly_mario.runner.session import Options, Run


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m fly_mario.runner")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="play one episode")
    r.add_argument("fly", help="a fly yaml, or the name of a file in configs/flies/")
    r.add_argument("--level", default="1-1")
    r.add_argument("--rom", default="v0")
    r.add_argument("--noop", type=int, default=0, help="idle frames before the fly takes over")
    r.add_argument("--sigma", type=float, default=0.0, help="sensor noise: fraction of each input")
    r.add_argument("--seed", type=int, default=0)
    r.add_argument("--max-frames", type=int, default=None, help="default 6000 (3000 with --legacy)")
    r.add_argument("--stuck-frames", type=int, default=None,
                   help="frames without progress that end a run, counted after Mario's first move; default 300 (150 with --legacy)")
    r.add_argument("--legacy", action="store_true", help="the old tool's quirks (150-frame stuck rule from frame 0, 3000 frames, no bare A); for parity")
    r.add_argument("--record-ram", action="store_true", help="also save the RAM of every frame")
    r.add_argument("--run-id", default="")
    r.add_argument("--no-save", action="store_true")
    a = ap.parse_args(argv)

    fly = C.load_fly(a.fly)
    scene = Scene(a.level, rom=a.rom, noop=a.noop, sigma=a.sigma, seed=a.seed,
                  max_frames=a.max_frames or (3000 if a.legacy else 6000),
                  stuck_frames=a.stuck_frames or (150 if a.legacy else 300))
    rid = a.run_id or record.new_run_id(fly.name, a.level, a.seed)
    run = Run(fly, scene, Options(legacy=a.legacy, record_ram=a.record_ram), run_id=rid)
    result = run.play()
    out = {"id": rid, "outcome": result.outcome, "max_x": result.max_x, "score": result.score, "blocks": result.blocks,
           "mushroom": result.mushroom, "frames": result.counts["frames"], "hash": result.hash[:12]}
    if not a.no_save:
        out["folder"] = str(record.save_run(run, result))
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
