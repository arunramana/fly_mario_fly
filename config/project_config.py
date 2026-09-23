"""config/project_config.py -- ProjectConfig composes every component's
params and serialises them (REFACTOR_PLAN.md section 5.3). It exists only
for the loader and the GUI; components receive their own params, never
the whole config.

`ScenarioParams` is what to run (level, duration, per-episode knobs that
aren't tuned scalars); `OutputParams` is where outputs go. A project saved
as JSON (e.g. `projects/legacy/config.json`) reproduces its run's telemetry
byte-for-byte through `sim/project_runner.run_from_config`.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import get_type_hints

from config.params import (
    Dnp02Params, DemoParams, EntityParams, HabituationParams, JumpParams,
    MdnParams, MushroomBodyParams, NetworkParams, NoiseParams, OdourParams,
    RetinotopyParams, SpeedParams, SteeringParams, TakeoffParams, TerrainParams,
)


@dataclass(frozen=True)
class ScenarioParams:
    """What to run. No `sigma`: it is a tuned scalar on `NoiseParams`, so a
    scenario's sigma is `config.noise.sigma`."""
    level: str = "1-1"
    max_frames: int = 1200
    seed: int | None = None
    inject_gap_frame: int | None = None
    retinotopic: bool = False


@dataclass(frozen=True)
class OutputParams:
    """`project_name` has no default: `config/output_routing.py` rejects
    None, so a run without a named project fails loudly."""
    project_name: str | None = None


@dataclass(frozen=True)
class ProjectConfig:
    network: NetworkParams = field(default_factory=NetworkParams)
    noise: NoiseParams = field(default_factory=NoiseParams)
    jump: JumpParams = field(default_factory=JumpParams)
    dnp02: Dnp02Params = field(default_factory=Dnp02Params)
    takeoff: TakeoffParams = field(default_factory=TakeoffParams)
    speed: SpeedParams = field(default_factory=SpeedParams)
    steering: SteeringParams = field(default_factory=SteeringParams)
    mdn: MdnParams = field(default_factory=MdnParams)
    mushroom_body: MushroomBodyParams = field(default_factory=MushroomBodyParams)
    habituation: HabituationParams = field(default_factory=HabituationParams)
    odour: OdourParams = field(default_factory=OdourParams)
    terrain: TerrainParams = field(default_factory=TerrainParams)
    entity: EntityParams = field(default_factory=EntityParams)
    retinotopy: RetinotopyParams = field(default_factory=RetinotopyParams)
    demo: DemoParams = field(default_factory=DemoParams)
    scenario: ScenarioParams = field(default_factory=ScenarioParams)
    output: OutputParams = field(default_factory=OutputParams)

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
    """Inverse of `dataclasses.asdict()` for nested frozen dataclasses.
    Uses `get_type_hints` because `from __future__ import annotations`
    makes `field.type` a string, which `is_dataclass()` never matches."""
    hints = get_type_hints(cls)
    kwargs = {}
    for f in fields(cls):
        field_type = hints[f.name]
        raw = data.get(f.name)
        if is_dataclass(field_type) and isinstance(raw, dict):
            kwargs[f.name] = _from_dict(field_type, raw)
        else:
            kwargs[f.name] = raw
    return cls(**kwargs)


def from_dict(data: dict) -> ProjectConfig:
    return _from_dict(ProjectConfig, data)


def from_json(text: str) -> ProjectConfig:
    return from_dict(json.loads(text))


def load(path) -> ProjectConfig:
    return from_json(Path(path).read_text(encoding="utf-8"))
