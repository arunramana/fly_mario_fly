"""tool/core/project.py -- ToolProject: create/open/duplicate/save a
project's projects/<name>/ folder (tool/PLAN.md section 3). Extends the
existing on-disk layout (config.json, runs/, telemetry/) with tool.json;
nothing already there is replaced.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

from config.output_routing import PROJECTS_ROOT
from config.project_config import OutputParams, ProjectConfig
from config.project_config import load as load_project_config
from tool.core.tool_settings import ToolSettings
from tool.core.tool_settings import load as load_tool_settings


# "legacy" is the shared reference project every other project is
# duplicated from (gate.py's own "Duplicate legacy" button,
# scripts/validate_entity_profiles.py's own PROJECT_NAME) -- editing it
# in place through the GUI silently drifted a scalar (habituation.
# hab_give_up, 3 -> -2) invisibly enough that nobody noticed until the
# golden gate's own config-roundtrip test caught it days later. Read-only
# in the GUI now; "Duplicate to edit" is the one way to change anything
# derived from it.
READ_ONLY_PROJECT_NAMES = frozenset({"legacy"})


@dataclass
class ToolProject:
    name: str
    config: ProjectConfig
    tool_settings: ToolSettings = field(default_factory=ToolSettings)

    @property
    def root(self):
        return PROJECTS_ROOT / self.name

    @property
    def is_read_only(self) -> bool:
        return self.name in READ_ONLY_PROJECT_NAMES

    @classmethod
    def create(cls, name: str, config: ProjectConfig | None = None,
               tool_settings: ToolSettings | None = None) -> ToolProject:
        root = PROJECTS_ROOT / name
        if root.exists():
            raise FileExistsError(
                f"project {name!r} already exists at {root} -- use open() or duplicate() instead"
            )
        config = config or ProjectConfig()
        # config.output.project_name must match the project's own name for
        # config.output_routing's resolve_run_path/resolve_telemetry_path
        # to land in the right folder -- set it here so a caller never has
        # to remember to.
        config = dataclasses.replace(config, output=OutputParams(project_name=name))
        project = cls(name=name, config=config, tool_settings=tool_settings or ToolSettings())
        project.save()
        return project

    @classmethod
    def open(cls, name: str) -> ToolProject:
        root = PROJECTS_ROOT / name
        config_path = root / "config.json"
        if not config_path.exists():
            raise FileNotFoundError(f"no project named {name!r} -- {config_path} does not exist")
        config = load_project_config(config_path)
        tool_path = root / "tool.json"
        settings = load_tool_settings(tool_path) if tool_path.exists() else ToolSettings()
        return cls(name=name, config=config, tool_settings=settings)

    def duplicate(self, new_name: str) -> ToolProject:
        return ToolProject.create(new_name, config=self.config, tool_settings=self.tool_settings)

    def save(self) -> None:
        # A hard backstop, not the only guard -- tool/ui/main_window.py
        # disables every editing control for a read-only project so this
        # should never actually be reached in normal use, but a script or
        # a missed UI path must not be able to silently overwrite the
        # shared reference project either.
        if self.is_read_only:
            raise PermissionError(
                f"project {self.name!r} is read-only -- duplicate it first (ToolProject.duplicate)"
            )
        self.root.mkdir(parents=True, exist_ok=True)
        self.config.save(self.root / "config.json")
        self.tool_settings.save(self.root / "tool.json")

    @staticmethod
    def list_recent() -> list[str]:
        if not PROJECTS_ROOT.exists():
            return []
        return sorted(p.name for p in PROJECTS_ROOT.iterdir()
                      if p.is_dir() and (p / "config.json").exists())
