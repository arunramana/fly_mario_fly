# Tutorials

Seven notebooks that walk through how this repository works, from the raw fly data to one whole run. They are meant to be **played with**: change a number, re-run a cell, see what happens. Each notebook starts with its goal, explains in markdown, and ends with a recap and things to try.

| # | notebook | you will see | needs the MaleCNS data? |
|---|---|---|---|
| 01 | `01_load_and_view_malecns` | the connectome: neurons, types, soma positions, transmitters, the synapse file | yes |
| 02 | `02_malecns_data_preparation` | how raw tables become groups and the weight matrix **W**; the repo's brain | yes |
| 03 | `03_senses_looming` | what a sense is; the looming angle; shapes, knobs, noise | no |
| 04 | `04_see_the_reaction_of_malecns` | the brain's response over time; from a neuron's rate to a button; removing the recurrence | yes |
| 05 | `05_load_and_view_mario` | the emulator: reset, step, save and rewind | no |
| 06 | `06_reading_memory_and_preparation` | NES RAM → Mario, objects and tiles → a distance | no |
| 07 | `07_fly_plus_mario_one_run` | the looming-only fly plays World 1-1; reproducibility; rewind | yes |

A good order is 05 → 06 → 03 (the game side and the sense, no data needed), then 01 → 02 → 04 (the fly side), then 07 (everything together). Reading them in number order also works.

The notebooks are saved **without outputs**: run them to see the figures.

## Setup

From the repository root, in a virtual environment (see the main [README](../README.md) for the full install):

```bash
pip install -r requirements.txt && pip install -e . --no-deps     # the project, exact versions
pip install -r tutorials/requirements.txt                          # Jupyter and plotting
jupyter lab tutorials/
```

If you installed the project with `pip install -e ".[test]"` instead, the second line is the same.

> Keep numpy below 1.27 (the project needs it). `tutorials/requirements.txt` pins versions that are compatible; if you install `matplotlib` or `pandas` yourself, check that pip did not upgrade numpy.

## Getting the data (notebooks 01, 02, 04, 07)

The notebooks **never download anything**. Get the MaleCNS v1.0 data once, then tell each notebook where it is.

1. Pick a folder **outside the repository**, for example `~/fly_mario_fly_data`.
2. Download the three public files (about 1.2 GB, CC BY 4.0, Janelia FlyEM / Google). The easiest way, from the repo root:
   ```bash
   export FLY_MARIO_FLY_DATA=~/fly_mario_fly_data        # Windows: set FLY_MARIO_FLY_DATA=C:\fly_mario_fly_data
   python scripts/download_data.py --build-brains
   ```
   This puts the files in `~/fly_mario_fly_data/malecns_v1.0/` and builds the brain caches in `~/fly_mario_fly_data/brains/` (a few minutes). Or download the files yourself from the `flyem-male-cns` bucket (`v1.0/connectome-data/flat-connectome/`) and place them in a folder called `malecns_v1.0`.
3. In the **first code cell** of each of those notebooks, set:
   ```python
   DATA_DIR = "~/fly_mario_fly_data"      # the folder that CONTAINS malecns_v1.0/
   ```
   If the files are not found you get a clear message that lists the missing ones.

Notebook 02 builds the 636-neuron brain from the data if it is not cached yet, which streams the big file once and takes a couple of minutes. Notebooks 03, 05 and 06 need no data at all.

If you use the data, credit the MaleCNS dataset from the FlyEM project at HHMI Janelia Research Campus in collaboration with Google (CC BY 4.0).

## The honesty rule

Every dial and number in this project is either **teal** (read off the real connectome) or **orange** (invented by us). The notebooks say which is which wherever it matters; keep that habit when you extend them.

## Troubleshooting

- *"Could not find MaleCNS files"*: `DATA_DIR` must be the folder containing `malecns_v1.0/`, not the `malecns_v1.0` folder itself.
- *Gym deprecation warnings*: harmless; the project pins the older `gym` on purpose.
- *A notebook is slow the first time*: some steps build caches in `$FLY_MARIO_FLY_DATA/derived/` once (notebook 02, section 2).
- Restart the kernel if you change `DATA_DIR` after a notebook has already loaded the data.
