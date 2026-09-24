"""tool/core/schema.py -- introspects config/params.py's 49 scalars into
ControlSpecs (name, type, default, range, provenance, group, wiring),
tool/PLAN.md section 3. Ranges/provenance are read from config/params.py,
never duplicated here (tool/PLAN.md's own risk-table entry).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any, get_type_hints

from config.params import ALL_PARAM_CLASSES
from config.project_config import ProjectConfig
from tool.core.wiring import LIVE, status_of


@dataclass(frozen=True)
class ControlSpec:
    group: str          # ProjectConfig's own attribute name, e.g. "jump"
    name: str           # the scalar's field name, e.g. "g"
    path: str           # "jump.g" -- what dataclasses.replace nesting needs
    type: type
    default: Any
    range: tuple[float, float] | None
    provenance: str
    home: str
    wiring: str


_GROUP_BY_CLASS: dict[type, str] | None = None


def _group_by_class() -> dict[type, str]:
    """ALL_PARAM_CLASSES lists the 15 scalar-holding dataclasses;
    ProjectConfig's own field names ARE the group names a GUI tab or a
    RunSpec path needs -- derived once, not hand-duplicated, so the two
    can never drift apart."""
    global _GROUP_BY_CLASS
    if _GROUP_BY_CLASS is None:
        hints = get_type_hints(ProjectConfig)
        by_class = {}
        for f in dataclasses.fields(ProjectConfig):
            if hints[f.name] in ALL_PARAM_CLASSES:
                by_class[hints[f.name]] = f.name
        missing = set(ALL_PARAM_CLASSES) - set(by_class)
        assert not missing, f"ALL_PARAM_CLASSES has a class with no ProjectConfig field: {missing}"
        _GROUP_BY_CLASS = by_class
    return _GROUP_BY_CLASS


def all_controls() -> list[ControlSpec]:
    """One ControlSpec per scalar, in ALL_PARAM_CLASSES's own order --
    all 49 are `live` (C1 threads a passed config through, C2 wired the
    four groups that used to be documentation-only), so schema.py doesn't
    consult wiring.py's per-control overrides for these; wiring.py is for
    controls schema.py doesn't cover (character, entity smell, ...)."""
    group_by_class = _group_by_class()
    specs = []
    for cls in ALL_PARAM_CLASSES:
        group = group_by_class[cls]
        hints = get_type_hints(cls)
        for f in dataclasses.fields(cls):
            path = f"{group}.{f.name}"
            specs.append(ControlSpec(
                group=group, name=f.name, path=path,
                type=hints[f.name], default=f.default,
                range=f.metadata.get("range"), provenance=f.metadata.get("provenance"),
                home=f.metadata.get("home"),
                wiring=status_of(path, default=LIVE),
            ))
    return specs


def get_value(config: ProjectConfig, path: str):
    group, name = path.split(".", 1)
    return getattr(getattr(config, group), name)


def with_value(config: ProjectConfig, path: str, value) -> ProjectConfig:
    """Returns a NEW ProjectConfig with one scalar replaced -- config is
    frozen, so this is how the GUI's param_form (tool/PLAN.md P3) or a
    script edits one control without touching the other 48."""
    group, name = path.split(".", 1)
    group_obj = getattr(config, group)
    new_group = dataclasses.replace(group_obj, **{name: value})
    return dataclasses.replace(config, **{group: new_group})
