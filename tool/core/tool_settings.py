"""tool/core/tool_settings.py -- frozen dataclasses for what ProjectConfig
doesn't hold: character choice, fitness weights, batch/learning knobs, and
render/output settings (tool/PLAN.md section 3). Saved as a project's own
tool.json, alongside config.json (ProjectConfig).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import get_type_hints


@dataclass(frozen=True)
class CharacterSettings:
    """Tab 1. `player` only ever changes the DISPLAYED sprite colour
    (tool/core/palette.py) -- never RAM, never the circuit (tool/PLAN.md's
    Luigi note: the RAM poke this used to mean, C6, froze movement and was
    dropped). Hunger override / starting power-up are C7, not built here
    (tool/PLAN.md P5)."""
    player: str = "mario"

    def __post_init__(self):
        if self.player not in ("mario", "luigi"):
            raise ValueError(f"player must be 'mario' or 'luigi', got {self.player!r}")


@dataclass(frozen=True)
class FitnessSettings:
    """Tab 5. Mirrors sim.fitness.FitnessWeights's own fields exactly (kept
    as its own dataclass, not a re-export, so tool.json's schema doesn't
    reach into sim/ directly) -- tool/core/fitness.py converts one to the
    other for a finished run."""
    points: float = 0.0
    distance: float = 1.0
    time: float = 0.0


@dataclass(frozen=True)
class ExperimentSettings:
    """Tab 5/6. `seeds`: which seeds a batch runs (tool/core/batch.py).
    `learning_enabled` is FullPolicy's own event_proximal_dopamine flag,
    named for what the Goal tab's own control reads, not the internal
    argument name."""
    seeds: tuple[int, ...] = (0,)
    learning_enabled: bool = False


@dataclass(frozen=True)
class RenderSettings:
    """Tab 6. `parallel_workers`: how many warm worker processes
    tool/core/batch.py starts (tool/PLAN.md P0's timing spike: a fresh
    process per run pays a ~7-8s circuit-load cost every time; a pool
    pays it once per worker)."""
    parallel_workers: int = 1
    frame_skip: int = 1
    record_video: bool = False
    brain_panel: bool = True  # only meaningful when record_video is True
    live_preview_fps: int = 30


@dataclass(frozen=True)
class ToolSettings:
    character: CharacterSettings = field(default_factory=CharacterSettings)
    fitness: FitnessSettings = field(default_factory=FitnessSettings)
    experiment: ExperimentSettings = field(default_factory=ExperimentSettings)
    render: RenderSettings = field(default_factory=RenderSettings)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    def save(self, path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")
        return path


def _from_dict(cls, data: dict):
    """Same pattern as config.project_config's own _from_dict: needs
    get_type_hints, not field.type, because `from __future__ import
    annotations` stringifies every annotation."""
    hints = get_type_hints(cls)
    kwargs = {}
    for f in fields(cls):
        field_type = hints[f.name]
        raw = data.get(f.name)
        if is_dataclass(field_type) and isinstance(raw, dict):
            kwargs[f.name] = _from_dict(field_type, raw)
        elif f.name == "seeds" and raw is not None:
            kwargs[f.name] = tuple(raw)
        else:
            kwargs[f.name] = raw
    return cls(**kwargs)


def from_dict(data: dict) -> ToolSettings:
    return _from_dict(ToolSettings, data)


def from_json(text: str) -> ToolSettings:
    return from_dict(json.loads(text))


def load(path) -> ToolSettings:
    return from_json(Path(path).read_text(encoding="utf-8"))
