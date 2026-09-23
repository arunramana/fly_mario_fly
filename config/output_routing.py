"""config/output_routing.py -- turns a ProjectConfig into a run's output
paths, projects/<name>/runs/ and projects/<name>/telemetry/. A config with
no project name fails loudly instead of writing to a stray folder.
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
