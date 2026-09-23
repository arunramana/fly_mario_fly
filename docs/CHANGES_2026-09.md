# Changes — September 2026 cleanup

Five commits, all on `main`. None changes game behaviour: after each one,
57 tests pass and the three golden telemetry CSVs are byte-identical.
No new videos or `docs/RUNS.md` entries, since nothing on screen changed.

## 1. `2263059` — Code audit and behaviour-preserving cleanup

- Added `docs/CODE_AUDIT.md`: structure/coupling findings, plus live
  hard-coded values missing from `docs/SCALARS.md` (noted, not moved).
- `run_steering.py`: removed unused imports and dead copies of
  `_memo_load` / `_circuit_cache` / `make_steering_masks` (live copies are
  in `bridge/full_policy.py`).
- `ReflexHabituation.check`: argument `mario_x` renamed `x`, so `fly/`
  stays game-agnostic.
- `JumpPolicy` / `FullPolicy` import `action_index` via `bridge.motor`.

## 2. `fb3437a` — Project clean up (layout)

- Root now holds only `README.md`, `CLAUDE.md`, `requirements.txt`,
  `.gitignore`, `run_steering.py`, `run_mario.py`.
- `brain_panel` → `render/`, ffmpeg helper → `render/video.py`,
  `pit_report` / `commitment_report` → `sim/`.
- 7 one-off scripts deleted; the other 18 moved to `scripts/`
  (run as `python -m scripts.<name>`).
- Data artifacts → `projects/legacy/telemetry/` and `projects/legacy/runs/`.
- `SPEC_*.md` → `docs/`; old README → `docs/JUMP_WRITEUP.md`; new root README.
- `/runs/` gitignored.

## 3. `58dade4` — Comment cleanup and dead code

- Comments/docstrings keep constraints (biology, RAM facts, golden-parity
  quirks) and drop sprint narration already in `docs/RUNS.md`
  (comment lines 2811 → 1586).
- Removed dead code: `theta_multi_approach`, `ProjectConfig.default()`,
  the ignored `hex2_mid` argument, unused locals/imports.
- Fixed comments that contradicted the code (stomp radius is 20px).
- `CLAUDE.md`: every rule kept; scope now deferred to `docs/SPEC_*.md`.

## 4. `5c206ad` — Plain-English headers and docs refresh

- Every `.py` file in `fly/`, `sim/`, `scripts/`, `tests/`, `run_mario.py`,
  `run_steering.py` (75 files), plus `requirements.txt` and `.gitignore`,
  opens with `# What this file does, in plain English:`.
- Docs brought in line with the code: `MECHANISMS.md` (what was built or
  declined), `TRACE_BIOLOGY.md` (how run 027 differs from the plan),
  `REFACTOR_PLAN.md` (phases 0–6 done), `ENTITIES.md` (post-refactor
  paths), `CODE_AUDIT.md` (new section D: scripts out of step with the
  layout), small fixes to `JUMP_WRITEUP.md`, `SPEC_mushroom_body.md`, `README.md`.
- Dangling `SPEC_second_escape.md` references → `docs/RUNS.md` entry 012.

## 5. `c122dc3` — Logging instead of printing

- New `config/logging_setup.py`: `setup_logging(run_name)` writes one file
  per run to `logs/` (DEBUG and up, timestamped); the console gets INFO and
  up. Third-party loggers are held to WARNING.
- `run_steering.main()` / `run_mario.main()` call `ensure_logging()`, which
  does nothing if a caller already configured logging.
- Levels: run summary, noise seed and "wrote <file>" → INFO; circuit build
  reports, circuit loading and per-frame events (jumps, climbs, `?`-block
  hits, habituation, MDN) → DEBUG.
- Unchanged: the circuit builders, when run on their own, and `scripts/`
  still print.
- `logs/` gitignored.

## Using the code from a tool

```python
from config.logging_setup import setup_logging
from sim.project_runner import load_project_config, run_from_config

setup_logging("my_tool")   # optional; picks the log file name
cfg = load_project_config("projects/legacy/config.json")
tel, info = run_from_config(cfg, "028_slug.mp4", record_video=True)
# tel: per-frame telemetry DataFrame (54 columns)
# info: summary dict (jumps, stomps, n_frames, died_or_flagged, ...)
```

- Video → `projects/<name>/runs/`, CSV → `projects/<name>/telemetry/`.
- Any `run_steering.main()` argument can be passed as an override
  (`max_frames`, `level`, `sigma`, `seed`, ...).
- `record_video` defaults to False in `run_from_config`.

## Still open

- `mario/`, `bridge/`, `render/`, `config/` (27 files) have no plain-English
  header yet; `config/logging_setup.py` does.
- `config/params.py` (`Dnp02Params` docstring) still references the
  missing `SPEC_second_escape.md`.
- `run_steering.py 008|016|023|024`, `scripts/compare_controllers.py` and
  `scripts/bench_episodes.py` write to the old top-level `runs/` (see
  `docs/CODE_AUDIT.md`).
- Structural findings S1–S3 in `docs/CODE_AUDIT.md`, notably that
  `FullPolicy` is one very large class.
