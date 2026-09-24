# fly_mario tool

Status: P2 done (tool core, headless -- no GUI yet). See `PLAN.md` for the
full plan and phase history, `CODEBASE_CHANGES.md` for every change made
outside `tool/` to support it.

## Install

```
pip install -r requirements.txt          # from the repo root
pip install -r tool/requirements.txt     # PySide6 + pyqtgraph, on top
```

## Command line

No GUI exists yet (P3+). Everything tool/core can do, it can do from the
command line:

```
# create a project (projects/<name>/, holding config.json + tool.json)
python -c "from tool.core.project import ToolProject; ToolProject.create('my_project')"

# run one seed
python -m tool.core.cli run my_project --seed 3

# run several seeds, in parallel (a warm worker pool -- see PLAN.md P2)
python -m tool.core.cli batch my_project --seeds 0 1 2 3 --workers 4
```

Each run is recorded in `projects/<name>/tool_runs/index.json` (number,
seed, git commit, fitness, and the full `RunSpec` needed to reproduce it
-- `tool/core/run_spec.py`'s `to_dict`/`from_dict`).

## Layout

See `PLAN.md` section 3 for the intended full layout. As of P2:

```
tool/
  core/
    project.py       ToolProject: create/open/duplicate/save
    tool_settings.py CharacterSettings, FitnessSettings, ExperimentSettings,
                      RenderSettings -- everything ProjectConfig doesn't hold
    schema.py         all_controls(): every one of config/params.py's 49
                      scalars as a ControlSpec (range, provenance, wiring)
    wiring.py         live/partial/not_wired status for non-scalar controls
    run_spec.py       RunSpec: one frozen object, one run, reproducible
    runner.py         RunSpec -> run_steering.main(), via
                      sim.project_runner.run_from_config
    run_store.py      NNN numbering (never reused), tool_runs/index.json
    batch.py          seeds x episodes, a warm multiprocessing.Pool
    fitness.py        thin wrapper over sim.fitness for a finished run
    cli.py            python -m tool.core.cli run|batch
  tests/              tool/core's own tests, separate from the repo's own
                      golden gate (`pytest tests/`) -- `pytest tool/tests/`
```

No Qt import anywhere under `tool/core/` -- every module here is plain,
testable Python, proven by `tool/tests/` before any UI is built on top
of it (P3+).
