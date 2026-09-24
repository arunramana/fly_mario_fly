"""tool/core/cli.py -- python -m tool.core.cli: proves tool/core works end
to end before any UI exists (tool/PLAN.md P2).

    python -m tool.core.cli run <project> --seed 3
    python -m tool.core.cli batch <project> --seeds 0 1 2 3 --workers 4
"""

from __future__ import annotations

import argparse
import sys

from tool.core.batch import run_batch
from tool.core.fitness import fitness_of
from tool.core.project import ToolProject
from tool.core.run_spec import RunSpec
from tool.core.run_store import next_run_number, record_run
from tool.core.runner import run_one


def cmd_run(args) -> int:
    project = ToolProject.open(args.project)
    number = next_run_number(project.name)
    slug = f"{number:03d}_cli_run"
    spec = RunSpec(project_name=project.name, config=project.config,
                    tool_settings=project.tool_settings, seed=args.seed,
                    out_filename=f"{slug}.mp4")
    tel, info = run_one(spec)
    fitness = fitness_of(project.tool_settings.fitness, info)
    record_run(project.name, number, slug, args.seed, info, spec.to_dict())
    print(f"run {number}: fitness={fitness:.1f} n_frames={info['n_frames']} "
          f"died={info['died_or_flagged']} max_x={info['max_x_abs']}")
    return 0


def cmd_batch(args) -> int:
    project = ToolProject.open(args.project)
    result = run_batch(project, seeds=args.seeds, n_workers=args.workers)
    for number, fitness, info in zip(result.numbers, result.fitnesses, result.infos):
        print(f"run {number}: fitness={fitness:.1f} n_frames={info['n_frames']} "
              f"died={info['died_or_flagged']} max_x={info['max_x_abs']}")
    n = len(result.fitnesses)
    mean_fitness = sum(result.fitnesses) / n
    print(f"\n{n} runs, mean fitness={mean_fitness:.1f}, "
          f"min={min(result.fitnesses):.1f}, max={max(result.fitnesses):.1f}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m tool.core.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="run one seed")
    run_p.add_argument("project")
    run_p.add_argument("--seed", type=int, default=0)
    run_p.set_defaults(func=cmd_run)

    batch_p = sub.add_parser("batch", help="run several seeds, optionally in parallel")
    batch_p.add_argument("project")
    batch_p.add_argument("--seeds", type=int, nargs="+", required=True)
    batch_p.add_argument("--workers", type=int, default=1)
    batch_p.set_defaults(func=cmd_batch)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
