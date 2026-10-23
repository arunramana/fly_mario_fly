"""python -m fly_mario_fly.runner run <fly.yaml> --level 1-1 --noop N --sigma S --seed K

Plays one episode and writes it to $FLY_MARIO_FLY_DATA/runs/<id>/ (see record.py). Prints the summary.

    --scene keep_only:pit            keep only these object types (comma list: keep_only:pit,pipe); every other enemy and pickup is off
    --scene no_enemies               switch every enemy off
    --from-moment <id>               resume from a saved moment (the fly may be "-" for the moment's own fly, or another fly)

python -m fly_mario_fly.runner moments <run id>   lists a run's saved moments; `tries <moment id>` lists what was tried from one.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import replace

from fly_mario_fly.contracts import Scene
from fly_mario_fly.runner import config as C
from fly_mario_fly.runner import moments as M
from fly_mario_fly.runner import record
from fly_mario_fly.runner.session import Options, Run


def parse_scene_modifier(text: str) -> tuple:
    """"keep_only:pit,pipe" -> ("keep_only", {"types": ["pit", "pipe"]}); "no_enemies" -> ("no_enemies", {})."""
    name, _, arg = text.partition(":")
    if name == "keep_only":
        if not arg:
            raise SystemExit("--scene keep_only needs the types to keep, e.g. keep_only:pit")
        return name, {"types": [t for t in arg.split(",") if t]}
    if arg:
        raise SystemExit(f"--scene {name} takes no argument")
    return name, {}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m fly_mario_fly.runner")
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
    r.add_argument("--scene", action="append", default=[], metavar="MOD[:ARG]", help="a test scene modifier (repeatable)")
    r.add_argument("--from-moment", default=None, metavar="ID", help="resume from a saved moment")
    r.add_argument("--moment-every", type=float, default=2.0, help="auto-save a moment every N seconds (0 = off); default 2")
    ml = sub.add_parser("moments", help="list a run's saved moments")
    ml.add_argument("run_id")
    tr = sub.add_parser("tries", help="list the runs resumed from a moment")
    tr.add_argument("moment_id")
    a = ap.parse_args(argv)
    if a.cmd == "moments":
        for i in M.list_moments(a.run_id):
            print(json.dumps({"id": i.id, "name": i.name, "frame": i.frame, "x": i.x, "kind": i.kind}))
        return 0
    if a.cmd == "tries":
        for t in M.tries_from(a.moment_id):
            print(json.dumps({"run": t.run_id, "change": t.change or "same fly", "outcome": t.outcome, "max_x": t.max_x}))
        return 0

    mods = tuple(parse_scene_modifier(t) for t in a.scene)
    opts = Options(legacy=a.legacy, record_ram=a.record_ram, moment_every_s=a.moment_every)
    if a.from_moment:
        m = M.get_moment(a.from_moment)
        fly = m.fly if a.fly == "-" else C.load_fly(a.fly)
        scene = replace(m.scene, **{k: v for k, v in (("max_frames", a.max_frames), ("stuck_frames", a.stuck_frames)) if v},
                        **({"modifiers": mods} if mods else {}))
    else:
        fly = C.load_fly(a.fly)
        scene = Scene(a.level, rom=a.rom, modifiers=mods, noop=a.noop, sigma=a.sigma, seed=a.seed,
                      max_frames=a.max_frames or (3000 if a.legacy else 6000),
                      stuck_frames=a.stuck_frames or (150 if a.legacy else 300))
    rid = a.run_id or record.new_run_id(fly.name, scene.level_id, scene.seed)
    run = Run(fly, scene, opts, run_id=rid, from_moment=a.from_moment, moments=not a.no_save)
    result = run.play()
    out = {"id": rid, "outcome": result.outcome, "max_x": result.max_x, "score": result.score, "blocks": result.blocks,
           "mushroom": result.mushroom, "frames": result.counts["frames"], "hash": result.hash[:12]}
    if a.from_moment:
        out["from_moment"] = a.from_moment
    if not a.no_save:
        out["moments"] = len(result.moments)
    if not a.no_save:
        out["folder"] = str(record.save_run(run, result))
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
