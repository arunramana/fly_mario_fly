"""sim/project_runner.py -- runs a project's scenario from its config file
alone (tests/test_config_roundtrip.py checks the telemetry is
byte-identical). Glue from ProjectConfig to run_steering.main(); kept out
of sim/episode.py, which must not import fly/mario/bridge.
"""

from __future__ import annotations

from pathlib import Path

import run_steering
from config.output_routing import resolve_run_path, resolve_telemetry_path
from config.project_config import ProjectConfig, load as load_project_config

__all__ = ["load_project_config", "run_from_config"]


def run_from_config(config: ProjectConfig, out_filename: str, **overrides):
    """Runs `run_steering.main()` with the scenario (level, frames, sigma,
    seed) and output paths from `config`; keyword arguments override them
    (e.g. `record_video=True`). Circuit scalars are not passed: each module
    reads its own from config/params.py at import time.
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
