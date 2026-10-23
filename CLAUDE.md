# fly_mario_fly (new tool)

GOAL: a simple tool (this repo) that lets a user attach fly senses to Super Mario objects, watch a run, rewind and retry, so the MaleCNS fly can win 1-2. Evolution runs in the background. The old tool got complicated and messy; this one stays small, with hard boundaries.

## Rules
- The old code is gone from this repo (git tag `pre-cleanup` keeps it); never import it or copy it back.
- `fly/` never imports `mario/`, and `mario/` never imports `fly/`. Only `senses/`, `actions/`, `runner/` import both.
- `evolve/`, `api/`, `render/` go through `runner/` and never name a specific object or sense. `api/` may also import `render/` (presentation).
- Attachments are config (`configs/flies/*.yaml`), not code.
- One plug-in per file, exposing one object named `PLUGIN`.
- Each lane also owns its own new test files under tests/ (`tests/test_<lane>_*.py`).
- `contracts.py` and this file change only in the lead session.
- Only stop processes you started yourself (by PID); never kill all node/python processes.
- Never delete anything in $FLY_MARIO_FLY_DATA or the repo that you did not create in this step. Delete by exact path (recorded when you created it), never by pattern.

## Folder owners (a lane writes only in its own folders; needing a contract change = stop and ask)
lead = contracts.py, registry.py, CLAUDE.md, pyproject, tests/golden | fly = fly/ | mario = mario/ |
runner = senses/ actions/ runner/ configs/ | render = render/ | api = api/ | evolve = evolve/ | web = web/

## Data
MaleCNS data and brain caches live outside the repo at the path in env var `FLY_MARIO_FLY_DATA`. Never committed.
The golden tests (tests/golden/) check the code against answers recorded once from the old code (tests/data/golden/). Lanes commit on their own branch only; never push or merge; the lead merges.

## Report format (every step, max 15 lines)
Files changed; the check and its result; one screenshot/clip if visual.

## Tests
`python -m pytest tests -q`
