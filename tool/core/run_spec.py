"""tool/core/run_spec.py -- RunSpec: everything one run needs, frozen, so
one object reproduces it (tool/PLAN.md section 3 and ground rule 5).
"""

from __future__ import annotations

from dataclasses import dataclass

from config.project_config import ProjectConfig
from config.project_config import from_dict as project_config_from_dict
from tool.core.tool_settings import ToolSettings
from tool.core.tool_settings import from_dict as tool_settings_from_dict


@dataclass(frozen=True)
class RunSpec:
    project_name: str
    config: ProjectConfig
    tool_settings: ToolSettings
    seed: int
    out_filename: str  # e.g. "029_my_run.mp4" -- tool/core/run_store.py assigns the number

    def to_dict(self) -> dict:
        return {
            "project_name": self.project_name,
            "config": self.config.to_dict(),
            "tool_settings": self.tool_settings.to_dict(),
            "seed": self.seed,
            "out_filename": self.out_filename,
        }

    @staticmethod
    def from_dict(data: dict) -> RunSpec:
        return RunSpec(
            project_name=data["project_name"],
            config=project_config_from_dict(data["config"]),
            tool_settings=tool_settings_from_dict(data["tool_settings"]),
            seed=data["seed"],
            out_filename=data["out_filename"],
        )
