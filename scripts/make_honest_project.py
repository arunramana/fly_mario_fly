# What this file does, in plain English:
# Builds projects/honest, the honest-play reference project: test3's settings
# with every hand-coded control rule switched off, so the fly (the circuit)
# makes every decision and the code only computes stimuli or maps neuron
# activity to buttons. The project is read-only in the tool (like legacy);
# every experiment happens in a duplicate of it.
"""scripts/make_honest_project.py -- one-off seeding of projects/honest from
projects/test3 (docs/CONTROL_AUDIT.md, invariant 8):

  * every ControlRules switch off, graded_pit_response off (no forced module);
  * MotorDirect on with release_on_landing (fresh press);
  * both refractory periods on (DNp01 and DNp02);
  * perception modules page, gap and wall on;
  * arousal 0 (module absent = no injection), noise sigma 0.

Written straight to disk: ToolProject.create()/save() refuse a read-only name,
which is exactly the guard this project is meant to have afterwards.

    .venv/Scripts/python.exe -m scripts.make_honest_project
"""

from __future__ import annotations

import dataclasses
import shutil

from config.output_routing import PROJECTS_ROOT
from config.params import (
    ControlRules, Dnp01RefractoryParams, Dnp02RefractoryParams, GapAheadParams,
    MotorDirectParams, PagePerceptionParams, WallAheadParams,
)
from config.project_config import OutputParams, load as load_config
from tool.core.tool_settings import load as load_settings

SOURCE, NAME = "test3", "honest"
MAX_FRAMES = 5000   # long enough for a whole 1-1; the run ends at death or the flag


def build():
    src = PROJECTS_ROOT / SOURCE
    dst = PROJECTS_ROOT / NAME
    if dst.exists():
        raise FileExistsError(f"{dst} exists -- honest is read-only; delete it by hand to rebuild")
    config = load_config(src / "config.json")
    settings = load_settings(src / "tool.json")

    src_motor = config.modules.motor_direct or MotorDirectParams()
    modules = dataclasses.replace(
        config.modules,
        page_perception=PagePerceptionParams(),
        gap_ahead=config.modules.gap_ahead or GapAheadParams(),
        wall_ahead=WallAheadParams(),
        motor_direct=dataclasses.replace(src_motor, release_on_landing=True),
        dnp01_refractory=Dnp01RefractoryParams(),
        dnp02_refractory=config.modules.dnp02_refractory or Dnp02RefractoryParams(),
        arousal=None,
    )
    config = dataclasses.replace(
        config,
        modules=modules,
        rules=ControlRules(**{f.name: False for f in dataclasses.fields(ControlRules)}),
        noise=dataclasses.replace(config.noise, sigma=0.0),
        scenario=dataclasses.replace(config.scenario, graded_pit_response=False, level="1-1",
                                      max_frames=MAX_FRAMES),
        output=OutputParams(project_name=NAME),
    )
    dst.mkdir(parents=True)
    config.save(dst / "config.json")
    settings.save(dst / "tool.json")
    if (src / "entity_profiles.json").exists():
        shutil.copyfile(src / "entity_profiles.json", dst / "entity_profiles.json")
    return dst


if __name__ == "__main__":
    print(f"wrote {build()}")
