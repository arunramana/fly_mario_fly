# fly_mario (new tool)
Attach MaleCNS fly senses to Super Mario objects, watch a run, rewind and retry, so the fly can win 1-2.
Evolution runs in the background. Small on purpose: hard boundaries, one plug-in per file.
Rules and lanes: see CLAUDE.md.

## Setup
Python 3.12. Everything below runs from inside this folder (the one holding `pyproject.toml`); nothing outside it is needed.

```
python -m venv .venv
.venv\Scripts\activate                 # POSIX: source .venv/bin/activate
pip install -e ".[test]"
pip install "setuptools<70" "gym==0.23.1" nes-py gym-super-mario-bros "opencv-python-headless<4.10" pillow cma "pyarrow<23" "pandas<3"
set FLY_MARIO_DATA=D:\fly_mario_data   # POSIX: export FLY_MARIO_DATA=~/fly_mario_data; any empty folder outside the repo
python -m fly_mario.fly build-brains   # downloads MaleCNS v1.0 (about 1.2 GB), builds and caches every brain
python -m pytest tests -q
```

- The second `pip install` line is needed until `pyproject.toml` lists these dependencies (it does not yet). numpy must stay `<1.27`
  (nes-py breaks under numpy 2), which is why `pyarrow` and `pandas` are capped: their newest releases need numpy 2.
- `build-brains` fetches three public files (CC-BY 4.0) from Janelia's `flyem-male-cns` bucket into `$FLY_MARIO_DATA/malecns_v1.0/`
  (resumable if interrupted), then builds the brains into `$FLY_MARIO_DATA/brains/`. Measured on a home connection:
  about 5.5 minutes, 1.2 GB on disk. Without `FLY_MARIO_DATA` the fly tests are skipped.
- The tests compare the new code to answers recorded once from the old code (`tests/data/golden/`, checked by `tests/golden/`).
  `tests/parity/` (marked `parity_old`) re-derives those answers from the old repo and is skipped when the old code is absent.
  `tools/freeze_golden.py` shows how the fixtures were made; it only runs where the old repo exists.
