# fly_mario
Attach MaleCNS fly senses to Super Mario objects, watch a run, rewind and retry, so the fly can win 1-2.
Evolution runs in the background. Small on purpose: hard boundaries, one plug-in per file.
Rules and lanes: see CLAUDE.md.

## Setup
Python 3.12. Everything below runs from the repo root (the folder holding `pyproject.toml`); nothing outside it is needed except `$FLY_MARIO_DATA`.

```
python -m venv .venv
.venv\Scripts\activate                 # POSIX: source .venv/bin/activate
pip install -e ".[test]"
set FLY_MARIO_DATA=D:\fly_mario_data   # POSIX: export FLY_MARIO_DATA=~/fly_mario_data; any empty folder outside the repo
python -m fly_mario.fly build-brains   # downloads MaleCNS v1.0 (about 1.2 GB), builds and caches every brain
python -m pytest tests -q
```

- numpy must stay `<1.27` (nes-py breaks under numpy 2), which is why `pyarrow` and `pandas` are capped in `pyproject.toml`.
- `build-brains` fetches three public files (CC-BY 4.0) from Janelia's `flyem-male-cns` bucket into `$FLY_MARIO_DATA/malecns_v1.0/`
  (resumable if interrupted), then builds the brains into `$FLY_MARIO_DATA/brains/`. Measured on a home connection:
  about 5.5 minutes, 1.2 GB on disk. Without `FLY_MARIO_DATA` the fly tests are skipped.
- The tests compare the code to answers recorded once from the old code (`tests/data/golden/`, checked by `tests/golden/`).
  `tools/freeze_golden.py` records how those fixtures were made; it needs the old code (git tag `pre-cleanup`) and cannot run on this tree.

## Run the tool
```
python -m fly_mario.api                # the API, http://127.0.0.1:8000 (needs FLY_MARIO_DATA set)
cd web && npm ci && npm run dev        # the web app, http://localhost:5173  (first time: npm ci)
python tools/e2e_stack.py              # end-to-end check on its own ports and a temp flies folder (web/e2e/*.mjs)
```
