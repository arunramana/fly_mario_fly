# fly_mario

Super Mario Bros (NES) played by a real fruit-fly brain. The circuits come
from the Janelia FlyEM MaleCNS v1.0 connectome. A Goomba approaches, the
looming detectors (LC4/LPLC2) fire, the Giant Fiber (DNp01) commits, the jump
muscle (TTMn) contracts, and Mario jumps. Nothing is trained: the weight
matrices are the connectome's, and every hand-set scalar is logged in
[`docs/SCALARS.md`](docs/SCALARS.md).

The project rules and invariants are in [`CLAUDE.md`](CLAUDE.md). Read
[`docs/SPEC_jump.md`](docs/SPEC_jump.md) before changing circuit code.

## Layout

```
fly/        the fly: connectome loading, circuits, network/integrator,
            sensing, internal state, plasticity. Never imports mario/.
mario/      the game: emulator, RAM addresses, entity records, actions.
            Never imports fly/.
bridge/     the only place both meet: perception (RAM -> stimuli),
            motor (command -> button), and the policies.
sim/        Episode loop, protocols, fitness, telemetry, reports.
config/     per-component params (the 49 scalars) and ProjectConfig.
render/     the live-brain panel and video output.
scripts/    diagnostics, calibration sweeps, the shuffled-connectome
            control, and benchmarks.
projects/   run artifacts per experiment line (videos, telemetry CSVs).
tests/      unit tests plus the golden-telemetry characterisation tests.
docs/       specs, the run log, audits.
```

Every `.py` file opens with a short `# What this file does, in plain
English:` comment, so you can skim a file's purpose before reading its code.

## Setup

Windows, Python 3.12. The pins in `requirements.txt` are load-bearing
(nes-py needs `numpy<2` and `gym==0.23.1`; the reasons are in that file).

```
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
```

The connectome data is not in this repo. It lives one level up, in
`../data/malecns_v1.0/`, and is read through `../mcns.py` (both belong to
the parent `fly_brain/` workspace).

## Running

Full system (jump, steering, terrain, mushroom body, habituation, MDN):

```
.venv/Scripts/python.exe -c "import run_steering; run_steering.main(out_mp4='projects/<name>/runs/NNN_slug.mp4')"
```

Or from a project config (for example `projects/legacy/config.json`):
`sim.project_runner.run_from_config(config, "NNN_slug.mp4")`.

The original jump-only demo:

```
.venv/Scripts/python.exe run_mario.py
```

Diagnostics and sweeps run from the repo root as modules:

```
.venv/Scripts/python.exe -m scripts.diag4 --sweep
.venv/Scripts/python.exe -m scripts.compare_controllers
```

## Tests

```
.venv/Scripts/python.exe -m pytest tests/
```

`tests/test_golden.py` replays three frozen scenarios and requires their
telemetry CSVs to be byte-identical. That is the project's specification of
correct behaviour: if a golden fails, diff it before re-baselining.

## Docs

- [`docs/RUNS.md`](docs/RUNS.md): the running log of every run, append-only.
- [`docs/SPEC_jump.md`](docs/SPEC_jump.md) and the other `docs/SPEC_*.md`
  files: the design spec for each circuit.
- [`docs/SCALARS.md`](docs/SCALARS.md): every hand-set scalar, generated
  from `config/params.py`.
- [`docs/REFACTOR_PLAN.md`](docs/REFACTOR_PLAN.md): the package split and
  the SOLID decisions.
- [`docs/CODE_AUDIT.md`](docs/CODE_AUDIT.md): open code-audit findings (structure, hard-coded values).
- [`docs/MECHANISMS.md`](docs/MECHANISMS.md),
  [`docs/ENTITIES.md`](docs/ENTITIES.md),
  [`docs/TRACE_BIOLOGY.md`](docs/TRACE_BIOLOGY.md): mechanism notes, the
  entity model, and the eligibility-trace biology.
- [`docs/JUMP_WRITEUP.md`](docs/JUMP_WRITEUP.md): the original sprint-1 jump
  writeup (measurements, diagnostics, controller comparison).
