"""config/project_config.py -- REFACTOR_PLAN.md section 5.3: "A single
composed ProjectConfig handed to every component violates interface
segregation... ProjectConfig exists ONLY to compose and serialise, and is
touched by the loader and the GUI, nowhere else."

No component in this codebase takes a ProjectConfig this phase -- that
wiring (a run driven by one ProjectConfig, outputs landing in
projects/<name>/) is phase 5's job (REFACTOR_PLAN.md section 7). This
phase's job is narrower: give every constant one typed, bounded home
(config/params.py) and one object that can compose/serialise all of them
(this file), so phase 5 has something real to hand a loader or a GUI.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields

from config.params import (
    Dnp02Params, DemoParams, EntityParams, HabituationParams, JumpParams,
    MdnParams, MushroomBodyParams, NetworkParams, NoiseParams, OdourParams,
    RetinotopyParams, SpeedParams, SteeringParams, TakeoffParams, TerrainParams,
)


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

    def to_dict(self) -> dict:
        return asdict(self)


def default() -> ProjectConfig:
    """The values every golden run in tests/golden/ was recorded against.
    Not a claim that these are optimal -- see config/params.py's per-field
    provenance for what's measured, what's invented, and what's unknown."""
    return ProjectConfig()
