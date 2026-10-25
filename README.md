# fly_mario_fly

[![CI](https://github.com/arunramana/fly_mario_fly/actions/workflows/ci.yml/badge.svg)](https://github.com/arunramana/fly_mario_fly/actions/workflows/ci.yml)

**A real fruit-fly brain plays Super Mario Bros.**

<!-- HERO GIF: put a short clip of the fly clearing World 1-1 at docs/media/demo.gif, then replace this comment with:
     ![The fly clearing World 1-1](docs/media/demo.gif)
     Render one with `python scripts/demo.py --video` (mp4 under $FLY_MARIO_FLY_DATA/videos/), then convert it to a GIF under ~5 MB. -->

## What is this? (30 seconds)

The wiring of the fly's brain comes from **MaleCNS v1.0**, the connectome of an adult male *Drosophila* central nervous system (Janelia FlyEM and Google). We run that wiring as it was measured: a 636-neuron circuit with its real synapses and signs.
It cannot see Mario, so we invent **senses**: small cues computed from the game's memory (how big a Goomba looks, how close a mushroom smells, a hum from a ? block) that feed **real sensory neurons**. Real motor and descending neurons
(the jump muscle, the forward-walking neuron, the steering neurons) decide the buttons.

```
Mario's memory --> invented cues (orange) --> real neurons and wiring (teal) --> real motor neurons --> buttons (orange thresholds)
```

You attach senses to Mario objects (goombas, pipes, pits, ? blocks...), watch a run with the brain's activity drawn beside the game, **rewind to any moment and retry**, and let evolution tune a few dials in the background.

**teal = real wiring, orange = invented by us.** Everything is labelled one or the other. **The wiring is untouched; a few dials are evolved.**

## Quick start

Python 3.12 (Linux, macOS or Windows). Node 22 is only needed for the web app.

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

Tests: `python -m pytest tests -q`. Without `FLY_MARIO_FLY_DATA` the tests that need the connectome skip, so the suite runs on a bare checkout in a couple of minutes using small synthetic data.
**Do not point the variable at an empty folder to run the tests:** the first test that needs the weights will download the 1 GB file.

## How it works

Every game frame: read the game's RAM -> objects -> each **sense** turns the objects it is attached to into input levels for sensory neurons -> the **brain** advances (`h <- (1-a) h + a clip(g W h + I)`, W = the real weights) -> each **action** reads the rates of its own motor or descending neurons and presses a button.
The runner is the only code that holds both the game and the fly. See [docs/concepts.md](docs/concepts.md) and [docs/architecture.md](docs/architecture.md).

| sense | the cue we invented (orange) | the real circuit it feeds (teal) |
|---|---|---|
| `looming` | the visual angle of the nearest threat, and its growth | LC4 / LPLC2 -> Giant Fiber (DNp01) -> jump muscle (TTMn) |
| `hearing` | a ? block that hums louder as Mario nears | Johnston's organ (JO) -> Giant Fiber |
| `sweet_smell` | a mushroom smells good on the antenna on its side | ORN -> relays -> steering (DNa) |
| `sour_smell` | an enemy smells of acid | acid receptors (ORN_DC4) -> relays -> moonwalker (MDN) |
| `home` | a constant pull to the right | LC10a -> forward walking (DNp09) and steering |
| `headroom`, `rear_eye` | modulate the looming cue (a low ceiling, a threat behind) | no neuron of their own |

Actions are thresholds on real neurons: `walk` (DNp09), `steer` (DNa), `jump` (TTMn), `back_up` (MDN). Dials set how strong each cue is and where each threshold sits; they are the only thing evolution may tune.

### The rules of the fly

- **Do:** the fly makes every decision; read the game's memory to work out what it senses; invent cues the fly can react to; add dials that set how strong each sense and cue is.
- **Don't:** edit the fly's wiring (no neuroevolution: weights are read-only); fire its neurons directly; let our code decide an action for the fly.

These are code, not just words: every plug-in **declares** its origin and the real route it rides, a validator checks them (`python -m fly_mario_fly.rules validate`; CI runs it), and runtime guards stop a run that tries to write weights,
drive a motor neuron or read the wrong neurons. Details: [docs/rules-of-the-fly.md](docs/rules-of-the-fly.md).

### Work with it from an AI client (MCP)

An MCP server (`python -m fly_mario_fly.mcp_server`) lets Claude or any MCP client explore the rules and plug-ins, add senses, creatures and objects from fixed recipes, set dials, and run a fly headlessly.
Every write goes through the same validator and is refused, with the reason, if it breaks a rule; there is no tool that edits weights or fires neurons. Setup: [docs/mcp.md](docs/mcp.md).

## Results

`python scripts/evaluate.py champion_e1s looming_only blank --level 1-1` plays each fly on the level's fixed **dev set**: ten starts (5 idle-frame counts x sensor noise 0 and 5 %), used only to judge, never to train.

| fly | what it has | World 1-1 flags | mean furthest x |
|---|---|---|---|
| `champion_e1s` | looming + hearing + sweet and sour smell + headroom, 8 evolved dials | **10 / 10** | 3161 (the flag) |
| `looming_only` | looming only (plus `home`), with the champion's evolved motor and home values | **10 / 10** | 3161 |
| `blank` | nothing attached | 0 / 10 | 40 (never moves) |

On **World 1-2** the same two flies reach 0 / 10 (all die around x = 890): **1-2 is not solved**, and nothing is tuned for it yet.

What this shows and does not show: an invented cue driving a real circuit is enough to clear World 1-1 on these starts. It does *not* show that a fly would do this, and the champion's dials were evolved on 1-1 (on separate training starts),
so `looming_only` borrows evolved values too. Runs are reproducible: the same fly, scene and seed always give the same hash.

## Getting the MaleCNS data

The connectome is **not** in this repo. `scripts/download_data.py` (or `python -m fly_mario_fly.fly build-brains`) fetches three public files from Janelia's open bucket (`gs://flyem-male-cns/v1.0/`) into `$FLY_MARIO_FLY_DATA/malecns_v1.0/`:

| file | size |
|---|---|
| `connectome-weights-male-cns-v1.0-minconf-0.5.feather` | ~1.0 GB |
| `body-annotations-male-cns-v1.0-minconf-0.5.feather` | small |
| `body-neurotransmitters-male-cns-v1.0.feather` | small |

The data is licensed **CC BY 4.0**. If you use it (or anything derived from it, such as brain caches or figures from this tool), credit the creators (see [Credits](#credits)).
Derived caches are written to `$FLY_MARIO_FLY_DATA/brains/` and `derived/` and are never committed.

## Learn and contribute

- **Tutorials:** [tutorials/](tutorials/README.md): seven Jupyter notebooks, from loading the connectome to one whole run.
- **Docs:** [concepts](docs/concepts.md) · [rules of the fly](docs/rules-of-the-fly.md) · [writing a plug-in](docs/plugin-authoring.md) · [adding a creature or object](docs/adding_creatures.md) · [MCP server](docs/mcp.md) · [architecture](docs/architecture.md) · [maintainers](docs/maintainers.md).
- **Contributing:** [CONTRIBUTING.md](CONTRIBUTING.md); starter ideas in [docs/issues.md](docs/issues.md). Security issues: [SECURITY.md](SECURITY.md). Please follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Project layout

```
src/fly_mario_fly/
  contracts.py   shared types only; imports nothing from the package
  registry.py    finds plug-ins; every plug-in file exposes one object named PLUGIN (and a DECLARATION)
  rules/         the rules as code: declarations, validator, runtime guards
  fly/           the brain: MaleCNS loading, groups, mechanisms, the leaky rate update.  Never imports mario/
  mario/         the game: emulator wrapper, RAM reading, objects, scenes, level data.   Never imports fly/
  senses/        game state -> neuron input (looming, hearing, smells, ...).  Imports both sides
  actions/       neuron output -> controller buttons (walk, steer, jump, back_up).  Imports both sides
  runner/        plays one episode, records it, saves "moments" to rewind to.  Imports both sides
  evolve/        CMA-ES over the evolvable dials, in the background; goes through runner/
  render/        mp4 export of a run; goes through runner/
  api/           FastAPI server for the web app; goes through runner/
  mcp_server/    MCP tools for AI clients; goes through runner/ and rules/
configs/flies/   a fly = a YAML file: which senses attach to which objects, which dials. Config, not code
configs/*.yaml   levels, icons, dev sets (fixed starts used to judge a fly)
web/             React + TypeScript front end
tutorials/       seven notebooks            docs/   the guides above
tests/           pytest; tests/golden/ checks the code against answers recorded once from the old code
scripts/         for users: demo, data download, evaluate     tools/   one-off maintenance scripts
```

The import rules are enforced by `tests/test_boundaries.py`. [CLAUDE.md](CLAUDE.md) has the full rules and the folder owners.

## Limitations

- **World 1-1 only is solved** (the next goal is 1-2). The level data for all 32 stages is read from the ROM, but the flies are only tuned and judged on 1-1.
- **The wiring is untouched; a few dials are evolved** (the champion tunes 8: home drive, three sense gains, four action thresholds). Senses and their attachments are hand-chosen.
- The cues, action thresholds and rate-update constants are invented (orange); a win shows the *combination* works, not that a fly would do this.
- The game runs on an emulator through `gym-super-mario-bros`, which bundles the game ROM; see [Licensing](#licensing).

## Roadmap

See [ROADMAP.md](ROADMAP.md): **evolution across all levels**, and **a lightweight browser version** (pick a level and fly settings, watch the run; no downloads, no evolution).

## Credits

- **MaleCNS v1.0**, the connectome, released under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) by a collaboration of **FlyEM (HHMI Janelia Research Campus)**, the **University of Cambridge (Department of Zoology)**, the **MRC Laboratory of Molecular Biology** and **Google Research**. See the [release notes](https://male-cns.janelia.org/release/). The release page gives no citation string; if you use the data, cite the dataset's paper.
- **[The Fly Project](https://flyproject.io/)**: a fly connectome brain in the browser, with a Minecraft mod where the fly responds to looming shapes, food smells and more. **Ro0oney** has shown a fly-connectome brain playing Minecraft ([TweakTown](https://www.tweaktown.com/news/113507/googles-mapped-fruit-fly-brain-has-played-doom-more-than-6000-times-and-still-hasnt-beaten-it/index.html)). Inspiration for wiring a real fly connectome to a game.
- **SethBling's MarI/O** (2015): the well-known demonstration of a neural network learning a Mario level. There the network is *trained* (NEAT neuroevolution); here the fly's wiring is real and left untouched.
- **Super Mario Bros.** is a Nintendo game; the emulator stack is [`nes-py`](https://github.com/Kautenja/nes-py) and [`gym-super-mario-bros`](https://github.com/Kautenja/gym-super-mario-bros) by Christian Kauten.

## Licensing

The code is under the [MIT License](LICENSE). That does **not** cover:

- the **MaleCNS** data (CC BY 4.0, see Credits);
- **Super Mario Bros.**, a Nintendo property: the ROM is not in this repo (it comes with the `gym-super-mario-bros` dependency), and `assets/sprites/` and the level data in `mario/facts/level_db.json` are derived from the game. They are included for research and education.
