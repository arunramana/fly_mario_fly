"""sim/project_runner.py -- REFACTOR_PLAN.md phase 5: "Prove the config
round-trip: load projects/legacy/config.json, run the 017 scenario from it
alone, and assert byte-identical telemetry. That is the first moment a
project is reproducible from one file -- and the thing the GUI's Play
button will eventually do."

Deliberately NOT part of sim/episode.py's generic Episode -- Episode must
never import fly/mario/bridge (tests/test_import_guard.py). This module is
different: it's the glue that ties a ProjectConfig to run_steering.main(),
today's actual full-system entry point (jump/steering/terrain/mushroom-
body/habituation/MDN). Migrating that whole system onto Episode/Policy/
Environment is real, separate future work (docs/RUNS.md's phase 5 note has
the scoping reasoning) -- this proves config-drivenness works for the
system as it actually exists today, not for a smaller stand-in.
"""

from __future__ import annotations

from pathlib import Path

import run_steering
from config.output_routing import resolve_run_path, resolve_telemetry_path
from config.project_config import ProjectConfig, load as load_project_config

__all__ = ["load_project_config", "run_from_config"]


def run_from_config(config: ProjectConfig, out_filename: str, **overrides):
    """Runs `run_steering.main()` with every scenario/output value taken
    from `config`, unless explicitly overridden by a keyword argument
    (e.g. `record_video=True` for a caller that actually wants a video --
    the round-trip proof itself uses `record_video=False`, since only the
    telemetry needs to be byte-identical). Component circuit scalars
    (`config.jump.g` and the other 14 dataclasses) are NOT threaded through
    here -- REFACTOR_PLAN.md phase 4 already made each live module source
    its own scalar from its own dataclass at IMPORT time (`G = JumpParams().g`
    in run_mario.py, etc.), so `run_steering.main()` already runs with
    whatever `config/params.py` currently holds; this function's job is
    narrower, just the scenario (level/frames/sigma/seed) and the output
    paths.
    """
    sc = config.scenario
    kwargs = dict(
        level=sc.level,
        max_frames=sc.max_frames,
        sigma=config.noise.sigma,
        seed=sc.seed,
        inject_gap_frame=sc.inject_gap_frame,
        retinotopic=sc.retinotopic,
        out_mp4=str(resolve_run_path(config, out_filename)),
        telemetry_path=str(resolve_telemetry_path(config, Path(out_filename).stem + "_telemetry.csv")),
        record_video=False,
        write_telemetry=True,
    )
    kwargs.update(overrides)
    return run_steering.main(**kwargs)
