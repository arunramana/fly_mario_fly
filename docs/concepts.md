# Concepts

A short vocabulary for the project. Every term is something you can find in the code.

## The idea in one paragraph

A fruit fly's brain, wired exactly as measured in the **MaleCNS v1.0** connectome, plays Super Mario Bros. We never touch the wiring. Between the game and the brain sit **senses**
that we invented: each reads the game's memory, works out what a fly eye or antenna might perceive, and feeds that as input into **real sensory neurons** on a real circuit. Between the brain
and the controller sit **actions**: a button is pressed when a real motor or descending neuron is active enough. In the middle the brain simply runs.

**teal = real wiring, orange = invented by us.** Every plug-in says which parts are which ([rules of the fly](rules-of-the-fly.md)).

## Terms

| term | what it is | where |
|---|---|---|
| **neuron group** | a named set of MaleCNS neurons picked by cell type (and side): `LC4_R`, `LPLC2_L`, `DNp01` (the Giant Fiber), `TTMn` (jump muscle), `DNp09` (forward walking), `DNa_L/R` (steering), `MDN` (walk backwards)... | `fly/groups.yaml` |
| **brain** | the 636-neuron base plus the neurons a mechanism adds. A weight matrix **W** built from the connectome (read-only) and a leaky rate update (invented constants) | `fly/brain.py` |
| **mechanism** | a real circuit: which groups are its inputs, which its outputs, which extra neurons it adds (`escape`, `walking`, `hearing`, `attraction`, `aversion`) | `fly/mechanisms/` |
| **object** | something in the game the fly can be attached to: a creature (`goomba`, `buzzy_beetle`...), terrain (`pipe`, `brick`, `pit`...), a pickup (`mushroom`, `coin`). Found by reading RAM | `mario/objects/` |
| **sense** | a bridge *in*: objects + Mario -> input levels for input groups of one mechanism. Per-object (attached to object types) or whole-fly | `senses/` |
| **action** | a bridge *out*: rates of its declared motor/descending groups -> a button press | `actions/` |
| **shape** | how an object is turned into the box the looming sense measures (own box, wall, pit tower, custom) | `senses/shapes/` |
| **fly** | a YAML file: which senses attach to which objects, which whole-fly senses and actions are on, the dial values. Config, not code | `configs/flies/` |
| **dial** (`KnobSpec`) | one number with a range and an `origin`: how strong a cue is, where a threshold sits. The only thing evolution tunes | `contracts.py` |
| **scene** | a reproducible situation: level, start point, idle frames (`noop`), sensor noise (`sigma`), **seed**, stop rules; plus optional edits ("no enemies", "keep only pits") | `contracts.Scene`, `mario/scenes/` |
| **run** | one episode: `Run(fly, scene).play()` | `runner/session.py` |
| **moment** | a saved snapshot of a run (emulator + brain + sense memory) to rewind to and retry, possibly with a different fly | `runner/moments.py` |
| **dev set** | the fixed starts used to *judge* a fly (never to train it) | `configs/dev_sets.yaml` |

## One frame

Every game frame the runner does (see `Run.step`):

1. read RAM: Mario's state, and `find()` for every object plug-in;
2. each **sense** gets the objects it is attached to and returns input levels (and what to draw, and its working);
3. the levels are summed per group and the **brain** advances 10 small steps;
4. each **action** reads the rates of its declared groups and returns the buttons to press or release;
5. the buttons go to the emulator.

Nothing in step 3 knows about Mario, nothing in step 1 knows about the fly; the runner is the only place that holds both.

## Reproducible by construction

The emulator is deterministic and every random draw is seeded (`Scene.seed`), so a run is fully determined by (fly, scene). Its **hash** fingerprints the button sequence.
`python scripts/demo.py` always prints hash `3111e33d1b22`.

## Where things live on disk

Never in the repo; all under `$FLY_MARIO_FLY_DATA`: `malecns_v1.0/` (the three public files), `brains/` and `derived/` (caches built from them), `runs/` (recorded runs and their moments,
evolution jobs), `videos/`, `thumbs/`, `icons/`.

## Learn by doing

[tutorials/](../tutorials/README.md) walks through all of this with seven notebooks.
