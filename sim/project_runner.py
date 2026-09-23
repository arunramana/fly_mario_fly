# What this file does, in plain English:
# Runs one game using only the settings in a project's config file (level,
# frame limit, noise level, random seed, a few test options, and where to
# save the output) by passing them to run_steering.py. Extra options given
# by the caller override those settings. Kept apart from episode.py so that
# file stays free of fly and game code.
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
    """Runs `run_steering.main()` with `config` itself (its 49 circuit
    scalars, not just the scenario -- tool/PLAN.md's C1) plus the scenario
    (level, frames, sigma, seed) and output paths derived from it; keyword
    arguments override any of these (e.g. `record_video=True`).
    """
    sc = config.scenario
    kwargs = dict(
        config=config,
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
