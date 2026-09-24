"""tool/core/batch.py -- seeds x episodes, parallel, aggregated
(tool/PLAN.md section 3). `n_workers > 1` uses a persistent warm worker
pool: `multiprocessing.Pool` already keeps its worker processes alive and
reuses them across every submitted task, so N runs on P workers pay the
~7-8s circuit-load cost (tool/PLAN.md's P0 timing spike) P times, not N
times -- the whole reason this phase's own hard prerequisite is
`tests/test_warm_worker_identity.py` (does a reused worker's SECOND run
match a fresh process, byte for byte -- see that test and C10's fix in
tool/CODEBASE_CHANGES.md for why this was not assumed safe).
"""

from __future__ import annotations

import multiprocessing as mp
from dataclasses import dataclass

from tool.core.fitness import fitness_of
from tool.core.run_spec import RunSpec
from tool.core.run_store import next_run_number, record_run
from tool.core.runner import run_one


def _run_one_for_pool(spec: RunSpec):
    """Module-level (not a closure) so multiprocessing can pickle it --
    on_frame/should_stop are never passed to a pool worker: a live-preview
    callback into the GUI process, or a cancel flag checked in it, has no
    meaning run inside a different, already-parallel worker process."""
    tel, info = run_one(spec)
    return info


@dataclass
class BatchResult:
    numbers: list[int]
    infos: list[dict]
    fitnesses: list[float]


def run_batch(project, seeds, fitness_settings=None, n_workers: int = 1) -> BatchResult:
    """Runs one RunSpec per seed, from `project`'s own config/tool_settings
    (only `seed` and `out_filename` vary), recording each in the project's
    run history exactly like a single CLI run would."""
    fitness_settings = fitness_settings or project.tool_settings.fitness
    start = next_run_number(project.name)
    numbers = list(range(start, start + len(seeds)))
    specs = [
        RunSpec(project_name=project.name, config=project.config,
                tool_settings=project.tool_settings, seed=seed,
                out_filename=f"{number:03d}_batch_seed{seed}.mp4")
        for number, seed in zip(numbers, seeds)
    ]

    if n_workers <= 1:
        infos = [run_one(s)[1] for s in specs]
    else:
        ctx = mp.get_context("spawn")
        with ctx.Pool(processes=n_workers) as pool:
            infos = pool.map(_run_one_for_pool, specs)

    fitnesses = [fitness_of(fitness_settings, info) for info in infos]
    for number, spec, info in zip(numbers, specs, infos):
        record_run(project.name, number, spec.out_filename.rsplit(".", 1)[0],
                   spec.seed, info, spec.to_dict())
    return BatchResult(numbers=numbers, infos=infos, fitnesses=fitnesses)
