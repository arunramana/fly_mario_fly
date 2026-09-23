"""config/project_config.py -- REFACTOR_PLAN.md section 5.3: "A single
composed ProjectConfig handed to every component violates interface
segregation... ProjectConfig exists ONLY to compose and serialise, and is
touched by the loader and the GUI, nowhere else."

Phase 5 adds `ScenarioParams` (what to run -- level, duration, the per-
episode knobs main() exposes that aren't one of the 49 tuned scalars) and
`OutputParams` (where outputs go -- REFACTOR_PLAN.md phase 5's "make a run
without a named project fail loudly": `project_name` has no default, and
`config/output_routing.py` rejects a `None` one rather than silently
falling back to a stray top-level path). `sigma` is NOT duplicated here --
it already lives on `NoiseParams`; a scenario's sigma is `config.noise.
sigma`.

No component's own numerical constant is threaded through a `ProjectConfig`
instance yet (phase 4 already sources each live module's own scalar from
its own dataclass -- see config/params.py). What phase 5 adds is the
config-round-trip proof itself: `sim/project_runner.py`'s `run_from_config`
takes one `ProjectConfig`, loaded from one JSON file
(`projects/legacy/config.json`), and reproduces a full scenario's
telemetry byte-for-byte -- the first moment a project is reproducible from
one file, per this phase's own instruction.
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
    """What to run. `sigma` is deliberately absent -- it already lives on
    `NoiseParams` (config/params.py), one of the 49 tuned scalars; a
    scenario's sigma is `config.noise.sigma`, not a second copy here."""
    level: str = "1-1"
    max_frames: int = 1200
    seed: int | None = None
    inject_gap_frame: int | None = None
    retinotopic: bool = False


@dataclass(frozen=True)
class OutputParams:
    """`project_name` has no default. REFACTOR_PLAN.md phase 5: a run
    without a named project must fail loudly, not silently write to a
    stray top-level `runs/` -- `None` here is a real, intentional "not
    set" that `config/output_routing.py` rejects rather than papers over."""
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
    """Reconstructs a (possibly nested) frozen dataclass from a plain
    dict, the inverse of `dataclasses.asdict()`. Needs `get_type_hints`
    rather than reading `field.type` directly because every dataclass in
    this module uses `from __future__ import annotations`, which turns
    annotations into strings -- `field.type` would give the string
    `"NetworkParams"`, not the class, and `is_dataclass()` on a string is
    always False."""
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


def default() -> ProjectConfig:
    """The values every golden run in tests/golden/ was recorded against.
    Not a claim that these are optimal -- see config/params.py's per-field
    provenance for what's measured, what's invented, and what's unknown."""
    return ProjectConfig()
