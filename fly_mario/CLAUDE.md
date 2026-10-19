# fly_mario (new tool)

GOAL: a new, simple tool in `fly_mario/` that lets a user attach fly senses to Super Mario objects, watch a run, rewind and retry, so the MaleCNS fly can win 1-2. Evolution runs in the background. The old tool got complicated and messy; this one stays small, with hard boundaries.

## Rules
- Never import or edit the old code in this repo (it is a frozen read-only reference).
- `fly/` never imports `mario/`, and `mario/` never imports `fly/`. Only `senses/`, `actions/`, `runner/` import both.
- `evolve/`, `api/`, `render/` go through `runner/` and never name a specific object or sense.
- Attachments are config (`configs/flies/*.yaml`), not code.
- One plug-in per file, exposing one object named `PLUGIN`.
- `contracts.py` and this file change only in the lead session.

## Folder owners (a lane writes only in its own folders; needing a contract change = stop and ask)
lead = contracts.py, registry.py, CLAUDE.md, pyproject, tests/golden | fly = fly/ | mario = mario/ |
runner = senses/ actions/ runner/ configs/ | render = render/ | api = api/ | evolve = evolve/ | web = web/

## Data
MaleCNS data and brain caches live outside the repo at the path in env var `FLY_MARIO_DATA`. Never committed.
Parity tests live in tests/parity/; only they may import old repo code (they are deleted at cleanup). Lanes commit on their own branch only; never push or merge; the lead merges.

## Report format (every step, max 15 lines)
Files changed; the check and its result; one screenshot/clip if visual.

## Tests
`python -m pytest fly_mario/tests -q`
