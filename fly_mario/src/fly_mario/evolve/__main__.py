"""python -m fly_mario.evolve run <fly.yaml> --level 1-1 --gens 15 --seed K [--workers N] [--from-moments id,id]

    --pop N          population (default 12, the old E1s run)
    --train-n N      use only N of the training episodes (smoke runs)
    --flag-x X       the level's flag x, when the level scan never reached it
    --id ID          name of the run folder, evo_<id> (default: time, fly, level, seed)
python -m fly_mario.evolve resume <id> [--gens N] [--workers N]    continue an interrupted run
"""
from __future__ import annotations

import argparse
import json
import os
import time

from fly_mario.evolve import search
from fly_mario.runner import record


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m fly_mario.evolve")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="evolve a fly")
    r.add_argument("fly", help="a fly yaml, or the name of a file in configs/flies/")
    r.add_argument("--level", default="1-1")
    r.add_argument("--gens", type=int, default=15)
    r.add_argument("--seed", type=int, default=1)
    r.add_argument("--pop", type=int, default=search.POP)
    r.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 1), help="0 = in this process")
    r.add_argument("--from-moments", default="", metavar="ID,ID", help="start every episode from these saved moments")
    r.add_argument("--train-n", type=int, default=0)
    r.add_argument("--flag-x", type=float, default=None)
    r.add_argument("--id", default="")
    c = sub.add_parser("resume", help="continue an interrupted run")
    c.add_argument("id")
    c.add_argument("--gens", type=int, default=None)
    c.add_argument("--workers", type=int, default=None)
    j = sub.add_parser("job", help="run one background job folder (what the API starts)")
    j.add_argument("folder")
    a = ap.parse_args(argv)
    if a.cmd == "job":
        from fly_mario.evolve import jobs
        return jobs.run_job(a.folder)

    if a.cmd == "resume":
        folder = record.runs_dir() / (a.id if a.id.startswith("evo_") else f"evo_{a.id}")
        cfg = json.loads((folder / "config.json").read_text(encoding="utf-8"))
        if a.gens is not None:
            cfg["gens"] = a.gens
        if a.workers is not None:
            cfg["workers"] = a.workers
    else:
        name = os.path.splitext(os.path.basename(a.fly))[0]
        eid = a.id or f"{time.strftime('%Y%m%d-%H%M%S')}_{name}_{a.level}_k{a.seed}"
        cfg = {"id": f"evo_{eid}", "fly": a.fly, "level": a.level, "gens": a.gens, "seed": a.seed, "pop": a.pop,
               "workers": a.workers, "moments": [m for m in a.from_moments.split(",") if m], "train_n": a.train_n,
               "flag_x": a.flag_x}
    out = search.run(cfg, log=lambda s: print(s, flush=True))
    d = out["dev"]
    print(json.dumps({"folder": out["folder"], "best_fitness": out["best"]["fitness"], "best_gen": out["best"]["gen"],
                      "dev_flags": f"{d['best']['flags']}/{d['best']['n']}", "start_dev_flags": f"{d['start']['flags']}/{d['start']['n']}"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
