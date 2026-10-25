# fly_mario_fly

A fruit-fly brain plays Super Mario Bros. This tool wires the real **MaleCNS v1.0** connectome (Janelia / Google, the adult male fruit-fly central nervous system) into the NES game: you attach fly *senses* (looming, hearing, sweet and sour smell, ...) to Super Mario *objects* (goombas, pipes, pits, question blocks, ...), watch the run with the brain's activity drawn next to the game, rewind to any moment and retry with a change. A few dials are evolved in the background (CMA-ES). The goal is for the MaleCNS fly to win World 1-1 (and then 1-2) without anything being injected past its senses.

<!-- Put a short GIF of a run here: docs/media/demo.gif (render one with `python scripts/demo.py --video`, then convert) -->
<!-- ![The fly clearing World 1-1](docs/media/demo.gif) -->

## Quick start

Python 3.12 and Linux/macOS/Windows. Node 22 (what CI uses) is only needed for the web app.

```bash
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt && pip install -e . --no-deps   # exact tested versions
#   or: pip install -e ".[test]"                                # version ranges from pyproject.toml
export FLY_MARIO_FLY_DATA=~/fly_mario_fly_data            # any folder OUTSIDE the repo (Windows: set ...)
python scripts/download_data.py --build-brains            # ~1.2 GB download, ~5 min; resumable
python scripts/demo.py                                    # the champion fly on World 1-1, seed 101
```

`scripts/demo.py` is deterministic: on the pinned install the champion reaches the flag (`"outcome": "flag"`, `"max_x": 3161.0`, `"hash": "3111e33d1b22"`). Add `--video` to render an mp4 under `$FLY_MARIO_FLY_DATA/videos/`.

The interactive tool:

```bash
python -m fly_mario_fly.api                  # API on http://127.0.0.1:8000 (local only, no auth)
cd web && npm ci && npm run dev              # web app on http://localhost:5173
cd web && npm run dev:mock                   # web app against canned data, no Python needed
```

Tests: `python -m pytest tests -q`. Without `FLY_MARIO_FLY_DATA` the tests that need the connectome skip, so the suite runs on a bare checkout in a couple of minutes using small synthetic data. **Do not point the variable at an empty folder to run the tests:** the first test that needs the weights will download the 1 GB file.

## Getting the MaleCNS data

The connectome is **not** in this repo. `scripts/download_data.py` (or `python -m fly_mario_fly.fly build-brains`) fetches three public files from Janelia's open bucket (`gs://flyem-male-cns/v1.0/`) into `$FLY_MARIO_FLY_DATA/malecns_v1.0/`:

| file | size |
|---|---|
| `connectome-weights-male-cns-v1.0-minconf-0.5.feather` | ~1.0 GB |
| `body-annotations-male-cns-v1.0-minconf-0.5.feather` | small |
| `body-neurotransmitters-male-cns-v1.0.feather` | small |

The data is licensed **CC BY 4.0**. If you use it (or anything derived from it, such as brain caches or figures from this tool), credit the creators: the **MaleCNS** dataset from the **FlyEM project at HHMI Janelia Research Campus in collaboration with Google** (use the citation given in the dataset's release notes, https://www.janelia.org/project-team/flyem). Derived caches are written to `$FLY_MARIO_FLY_DATA/brains/` and `derived/` and are never committed.

## Project layout

```
src/fly_mario_fly/
  contracts.py   shared types only (lead-owned); imports nothing from the package
  registry.py    finds plug-ins; every plug-in file exposes one object named PLUGIN
  fly/           the brain: MaleCNS loading, groups, mechanisms, the leaky rate update.  Never imports mario/
  mario/         the game: emulator wrapper, RAM reading, objects, scenes, level data.   Never imports fly/
  senses/        game state -> neuron input (looming, hearing, smells, ...).  Imports both sides
  actions/       neuron output -> controller buttons (walk, steer, jump, back_up).  Imports both sides
  runner/        plays one episode, records it, saves "moments" to rewind to.  Imports both sides
  evolve/        CMA-ES over the evolvable dials, in the background; goes through runner/
  render/        mp4 export of a run; goes through runner/
  api/           FastAPI server for the web app; goes through runner/
configs/flies/   a fly = a YAML file: which senses attach to which objects, which dials. Config, not code
configs/*.yaml   levels, icons, dev sets (fixed starts used to judge a fly)
web/             React + TypeScript front end
tests/           pytest; tests/golden/ checks the code against answers recorded once from the old code
tools/           one-off maintenance scripts (ROM reading, screenshots); scripts/ is for users
```

The import rules are enforced by `tests/test_boundaries.py`. [CLAUDE.md](CLAUDE.md) has the full rules and the folder owners.

## Honesty rule: teal = real wiring, orange = invented by us

Everything in the UI is coloured by where it comes from:

- **teal**: read off the MaleCNS connectome (which neurons exist, who connects to whom, the sign of each synapse from its transmitter).
- **orange**: invented by us (the cue that turns a Mario object into a neuron input, thresholds that turn neuron output into a button, the leaky-update constants, the shapes an object "looms" with). In code these are `KnobSpec(origin="invented")`; wiring is `origin="fly"`.

If you add a dial, a sense or an action, set `origin` truthfully. A result that depends on an orange choice must not be described as "the fly's".

## Limitations

- **World 1-1 only is solved** (the stated goal is 1-2 next). The level data for all 32 stages is read from the ROM, but the flies are only tuned and judged on 1-1.
- **Only a few dials are evolved** (the champion tunes 8: home drive, three sense gains, four action thresholds). Senses and their attachments are hand-chosen.
- **The wiring is untouched**: the connectome is used as published, with a fixed rule for which extra neurons each mechanism adds. Nothing is rewired or trained.
- The sense cues, action thresholds and rate-update constants are invented (orange); a win shows the *combination* works, not that a fly would do this.
- The game runs on an emulator through `gym-super-mario-bros`, which bundles the game ROM; see [Licensing](#licensing).

## Tutorials

`tutorials/` has seven Jupyter notebooks that explain how the repo works, from loading the connectome to one whole run: see [tutorials/README.md](tutorials/README.md).

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md); starter ideas are in [docs/issues.md](docs/issues.md). Security issues: [SECURITY.md](SECURITY.md). Please follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Licensing

The code is under the [MIT License](LICENSE). That does **not** cover:

- the **MaleCNS** data (CC BY 4.0, see above);
- **Super Mario Bros.** is a Nintendo property: the ROM is not in this repo (it comes with the `gym-super-mario-bros` dependency), and `assets/sprites/` and the level data in `mario/facts/level_db.json` are derived from the game. They are included for research/education and may need to be removed or replaced before any wider redistribution.
