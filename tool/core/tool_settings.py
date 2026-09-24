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
    dropped). `hunger_override`/`starting_powerup` are C7
    (tool/CODEBASE_CHANGES.md) -- science changes when actually used
    (CLAUDE.md rule 3), not display choices."""
    player: str = "mario"
    hunger_override: bool | None = None  # None: read Mario's real size, as always
    starting_powerup: bool = False       # True: force_mario_size=1 from frame 0

    def __post_init__(self):
        if self.player not in ("mario", "luigi"):
            raise ValueError(f"player must be 'mario' or 'luigi', got {self.player!r}")


@dataclass(frozen=True)
class CircuitSettings:
    """Tab 4. `shuffle_seed` is CLAUDE.md invariant 6's control -- None
    (default) is the real connectome; an int rebuilds every circuit's
    weight matrix with edges rewired at random (C5)."""
    shuffle_seed: int | None = None


@dataclass(frozen=True)
class EntityProfileSettings:
    """Tabs 2/3. `enabled=False` (default): FullPolicy gets
    entity_profiles=None, byte-identical to before C8a existed
    (docs/SPEC_entity_perception.md). True: runner.py loads
    projects/<name>/entity_profiles.json (bridge/entity_profiles.py),
    merged over bridge/profiles/default.json -- the file existing is not
    itself what turns the feature on, this flag is (ground rule 4)."""
    enabled: bool = False


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
    circuits: CircuitSettings = field(default_factory=CircuitSettings)
    entity_profile: EntityProfileSettings = field(default_factory=EntityProfileSettings)
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
    annotations` stringifies every annotation.

    A field name ABSENT from `data` is left out of `kwargs` entirely, so
    the dataclass's own default applies (same real bug config.
    project_config._from_dict had: an older saved tool.json missing e.g.
    `entity_profile` used to pass an explicit `None`, overriding
    `EntityProfileSettings`'s own default instead of forward-compatibly
    falling back to it)."""
    hints = get_type_hints(cls)
    kwargs = {}
    for f in fields(cls):
        if f.name not in data:
            continue
        field_type = hints[f.name]
        raw = data[f.name]
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
