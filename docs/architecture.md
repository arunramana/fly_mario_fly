# Architecture

```
                 configs/flies/*.yaml  (a fly: attachments + dials)
                          |
 game (NES emulator) -> mario/ ->  senses/  ->  fly/  ->  actions/ -> buttons -> game
   RAM                 objects     invented     real      invented
                       (find)      cues         brain     readouts
                          \_____________ runner/ ______________/
                          (the only place that joins the two sides, one frame at a time)

        evolve/  (CMA-ES over dials)     render/ (mp4)     api/ + web/ (the tool)     mcp_server/ (AI clients)
              \__________________ all go through runner/ and never name a specific object or sense ________/
```

## Packages (`src/fly_mario_fly/`)

| package | job | may import |
|---|---|---|
| `contracts.py` | shared types only (`Box`, `MarioState`, `KnobSpec`, `Sense`, `Action`, `Scene`, `FlyConfig`...) | nothing from the project |
| `registry.py` | finds plug-ins by folder (`list_plugins`, `list_modules`) | nothing else |
| `rules/` | the project's rules as code: declaration schema, catalogue, validator, runtime guards, CLI | schema and guards import nothing; the validator reads the registry |
| `fly/` | the brain: MaleCNS loading (`connectome.py`), groups, mechanisms, the leaky rate update (`brain.py`) | never `mario/` |
| `mario/` | the game: emulator wrapper, RAM readers, objects, scenes, ROM-derived level data, facts (YAML) | never `fly/` |
| `senses/`, `actions/` | the two bridges | both sides, but never the brain object or the connectome |
| `runner/` | `Run` (the frame loop), recording, moments (rewind), level catalogue, fly YAML loading | everything below |
| `evolve/` | CMA-ES over the evolvable dials; dev-set judging | `runner/` |
| `render/` | mp4 export of a run | `runner/` |
| `api/` | FastAPI server for the web app | `runner/`, `render/` |
| `mcp_server/` | MCP tools (read, add plug-ins from fixed recipes, set dials, run) | `runner/`, `rules/`, `render/` |

The rules are enforced by `tests/test_boundaries.py` (imports) and `python -m fly_mario_fly.rules validate` (declarations, static scans).

## Data flow of a run

```
RAM --read_mario / find()--> MarioState + [ObjectInstance]            (mario/)
 --> each sense.cue() --> SenseOutput(inputs per neuron group, overlay, steps)   (senses/)
 --> sum per group --> brain.drive() --> brain.advance(): h <- (1-a) h + a clip(g W h + I)   (fly/; W real, constants invented)
 --> rates per group --> each action.decide() --> ButtonIntent                   (actions/)
 --> resolved buttons --> emulator step --> FrameRecord                          (runner/)
```

## The brain

Built once from the three MaleCNS files and cached by a content hash under `$FLY_MARIO_FLY_DATA/brains/` (`python scripts/download_data.py --build-brains`). The base is 636 neurons (the escape circuit, forward walking, steering and 40 relays);
the hearing, attraction and aversion mechanisms append neurons, so every earlier brain behaves exactly as before. `W[i, j]` = the share of neuron *i*'s input that comes from *j*, signed by *j*'s transmitter (Dale's law). `brain.W` is read-only.

## The tool

`python -m fly_mario_fly.api` serves a local API (no auth, 127.0.0.1) and `web/` is a React app on top of it: pick a level, attach senses to objects on the Fly screen, run, jump to saved **moments** to rewind and retry,
and start background **evolution** jobs (from the command line: `python -m fly_mario_fly.evolve run champion_e1s --level 1-1 --gens 15 --seed 1`; judge flies with `python scripts/evaluate.py`). `web/src/api/types.ts` is generated from `api/openapi.json`, which a test keeps current.

## Tests and CI

`tests/` runs without the data (data-dependent tests skip); `tests/golden/` compares the code to answers recorded once from the old code (`tests/data/golden/`). CI has three jobs with stable names:
`python` (pinned install, full suite without data), `web` (lint and build) and `rules` (validate every plug-in). Reproducibility files: `requirements.txt` (exact pins, Python 3.12), `scripts/demo.py` (hash `3111e33d1b22`),
`scripts/download_data.py`, `scripts/evaluate.py`.

## Licences of what is bundled

Code: MIT. MaleCNS data: CC BY 4.0 (not in the repo). Super Mario Bros. is Nintendo's: `assets/sprites/` and the ROM-derived level data are included for research and education.
