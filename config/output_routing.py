"""config/output_routing.py -- REFACTOR_PLAN.md phase 5: "Route all
outputs through ProjectConfig into projects/<name>/runs/ and
projects/<name>/telemetry/, and make a run without a named project fail
loudly rather than silently writing to a stray top-level folder."

`run_steering.main()`'s own `out_mp4` default was exactly that stray
top-level folder (`"runs/008_run.mp4"`) until this phase -- `out_mp4` now
has no default at all (a bare `main()` call raises). This module is the
one place that turns a `ProjectConfig` into the two paths a run actually
needs; `sim/project_runner.py` is the one place that calls it.
"""

from __future__ import annotations

from pathlib import Path

from config.project_config import ProjectConfig

PROJECTS_ROOT = Path(__file__).parent.parent / "projects"


def _require_project_name(config: ProjectConfig) -> str:
    name = config.output.project_name
    if not name:
        raise ValueError(
            "ProjectConfig.output.project_name is required to resolve an "
            "output path -- REFACTOR_PLAN.md phase 5: no silent stray "
            "top-level runs/. Set output=OutputParams(project_name=\"...\") "
            "on the config before running."
        )
    return name


def resolve_run_path(config: ProjectConfig, filename: str) -> Path:
    return PROJECTS_ROOT / _require_project_name(config) / "runs" / filename


def resolve_telemetry_path(config: ProjectConfig, filename: str) -> Path:
    return PROJECTS_ROOT / _require_project_name(config) / "telemetry" / filename
