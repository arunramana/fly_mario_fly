# fly_mario — restructure plan

Plan only. **Revision 3** — `fly/` ÷ `mario/` split, entity model, and a SOLID
pass that removed two inheritance hierarchies.

**Goal:** a modular, reusable, object-oriented codebase that can back the GUI
tool (see `docs/TOOL_VISION.md` if present, otherwise §4 and §6 here), with docs
and run artifacts organised by experiment line. The eligibility trace lands
*after* the restructure, so it is written once, in the new shape.

**Decisions settled:**

- A "project" is an **experiment line** — `projects/escape_baseline/`,
  `projects/learning_trace/` — spanning many sprints. Sprint numbers stay as
  filename prefixes inside.
- All 26 existing runs **migrate into `projects/legacy/`**, with `docs/RUNS.md`
  paths rewritten.
- The package splits into **`fly/`** and **`mario/`**, which do not import each
  other.
- **Composition over inheritance throughout.** See §5 — this reversed two
  earlier designs.

---

## 1. Why this is safe to attempt now

One asset makes a refactor of this size tractable: **`sigma = 0.0` reproduces
every pre-025 run byte-for-byte** (verified in 025). That is a complete
behavioural specification of the current system, available for free.

Everything below is built on it. Nothing else in the repo is tested.

---

## 2. The central rule: `fly/` never imports `mario/`

- **`fly/`** is a fruit fly. It consumes abstract stimuli and emits abstract
  motor commands. It has no idea what a Goomba is, what a button is, or that a
  game exists.
- **`mario/`** is Super Mario Bros. It decodes RAM into entity records and
  accepts controller input. It has no idea what a neuron is.
- **`bridge/`** is the only place both are imported. It answers exactly two
  questions: *what does this entity smell and look like to the fly?* and *what
  button does this motor command press?*

The payoff is concrete: the fly becomes reusable for another game — Luigi,
Flappy Bird, anything with decodable state — by writing a new `mario/`-shaped
package and a new bridge, touching no circuit code. **Enforced by an import-
guard test, not by discipline.**

---

## 3. Directory layout

```
fly_mario/
  docs/
    RUNS.md                 # already here before this plan -- phase 1 found
                             # this diagram wrong; only paths rewritten
    MECHANISMS.md           # already here before this plan, same correction
    SPEC_jump.md            # actually moved in phase 1 (from repo root)
    REFACTOR_PLAN.md        # this file, also moved from repo root, phase 1
    ARCHITECTURE.md         # new — the map, and the import rule
    SCALARS.md              # new — the parameter registry
    ENTITIES.md             # new — every entity and its default profile

  fly/                      # knows nothing about Mario
    connectome/             # streaming load, caching, subgraph extraction
    network/                # Network, Population, Integrator
    circuits/               # named configurations, NOT subclasses
    sensing/                # channel interfaces, abstract stimuli
    state/                  # hunger, arousal, satiety
    learning/               # eligibility trace, dopamine, plasticity

  mario/                    # knows nothing about the fly
    emulator/               # nes-py wrapper, frame stepping, seeding
    ram/                    # address maps, tile decoding, entity extraction
    entities/               # entity records + kind registry
    level/                  # level identity, geometry, progress
    actions/                # button set, MOVES, action encoding

  bridge/                   # the ONLY module importing both
    perception.py           # entity record -> stimulus, via PerceptionProfile
    motor.py                # motor command -> button press
    policy.py               # assembles a Policy from fly + bridge
    profiles/               # shipped default profiles (JSON)

  sim/                      # Episode, protocols, fitness, telemetry observers
  render/                   # panel, layout, video
  config/                   # per-component params + composition

  projects/
    legacy/
      config.json
      runs/                 # 001-026 videos
      telemetry/            # their CSVs
    escape_baseline/
    learning_trace/

  tests/
    golden/                 # frozen telemetry from phase 0
  scripts/                  # thin CLI entry points only
```

---

## 4. The entity model

The surface the GUI's enemy-attribute panel binds to.

### The separation that makes it work

**Intrinsic game facts** — `mario/entities/`. Width, height, RAM type byte,
solidity, whether contact is lethal. These come from the ROM and are **not
user-editable**; changing them makes the game wrong rather than the experiment
different.

**Perceptual attributes** — `bridge/profiles/`, loaded from config. What the fly
*makes of* the entity: odour channels, looming salience, danger weighting,
whether it reads as food. **Fully user-editable; this is what the tool exposes.**

So you never edit what a Goomba *is*. You edit what the fly *perceives*. A
profile file is then a complete description of one experimental condition.

### Entities are records, not a class tree

**Revised from an earlier draft, which had a `Character → Goomba/Koopa/Piranha`
hierarchy. That was wrong.** We do not simulate these things — nes-py does, and
we only read RAM. Giving a Goomba methods implies we own behaviour we do not
own, and the taxonomy fractures on contact with reality: Koopa has shell state,
Piranha is not stompable, Pit has no RAM slot at all.

```python
@dataclass(frozen=True)
class EntityRecord:
    kind: EntityKind          # enum: GOOMBA, KOOPA, PIPE, PIT, MUSHROOM, ...
    x: float
    y: float
    width: int
    height: int
    active: bool
    traits: frozenset[Trait]  # STOMPABLE, SOLID, COLLECTIBLE, LETHAL_ON_CONTACT
```

One immutable value object; `kind` and `traits` carry the variation. Traits are
a composed set, not a position in a tree, so a new entity with an unusual mix
needs no new class. A `KindRegistry` maps RAM type bytes to kinds and their
intrinsic dimensions — the one place ROM facts live.

`Pit` is synthesised from missing tiles rather than read from an entity slot. It
is the only entity defined by what is *not* there, and 004 established a looming
detector structurally cannot see it — which is exactly why it needs a first-class
record and its own profile rather than a special case in a decoder.

### Perceptual profiles

```python
@dataclass
class PerceptionProfile:
    odours: list[OdourEmission]   # channel name, valence, intensity, falloff
    looming_salience: float
    danger_weight: float
    is_food: bool
    body_scale: float             # for the climb / refusal rule
```

Odour is a **list of labelled channels**, not one scalar. That is what makes "a
Goomba smells bad and a Koopa smells bad *differently*" expressible: different
named channels, both aversive, separately learnable. A single intensity could
never represent it, and it is the reason the mushroom body has anything to
discriminate.

Defaults ship in `bridge/profiles/default.json`, documented in
`docs/ENTITIES.md`. A project overrides them in its own `config.json`.

---

## 5. The SOLID pass — what the earlier draft got wrong

Four corrections, recorded with their reasoning so they are not quietly undone.

### 5.1 No `Circuit` base class — composition instead

An earlier draft proposed `Circuit` with `EscapeCircuit`, `SteeringCircuit`,
`MushroomBody`, `RetinotopicMap` as subclasses. **They are not substitutable.**
The mushroom body carries plastic weights and a learning step the others lack;
`RetinotopicMap` is an input transform, not a circuit at all. A shared base would
grow optional methods and force `isinstance` checks at every call site — Liskov
broken immediately.

Instead:

```python
class Network:                    # one concrete class, no subclasses
    populations: dict[str, slice] # named views into the state vector
    weights: sparse matrix
    integrator: Integrator
    def step(self, inputs) -> None
```

A "circuit" becomes a **named configuration** that builds a `Network` — a
function or a small factory, not a type. Plasticity is an injected collaborator
(`PlasticityRule | None`) present only where it applies. `RetinotopicMap` lives
in `sensing/`, where it always belonged.

### 5.2 `Episode` depends on protocols, not on fly or mario

The earlier draft had `Episode` owning the loop *and* telemetry, which is two
responsibilities and would have pulled fly, mario, bridge, config and render
into one import graph.

```python
class Policy(Protocol):
    def act(self, observation) -> Action: ...
    def reset(self, seed: int) -> None: ...

class Environment(Protocol):
    def step(self, action) -> Observation: ...
    def reset(self, seed: int) -> Observation: ...
```

`Episode` composes a `Policy` and an `Environment` and knows nothing else. The
bridge supplies the concrete fly-backed policy; `mario/` supplies the
environment. **Telemetry becomes an observer** the episode notifies, so adding a
recorded field never edits the loop — which matters given how often 017-022
turned on adding one.

### 5.3 Each component gets its own params, not the whole config

A single composed `ProjectConfig` handed to every component violates interface
segregation, and makes everything transitively depend on everything's
parameters. Instead each component takes its own frozen params object;
`ProjectConfig` exists **only** to compose and serialise, and is touched by the
loader and the GUI, nowhere else.

### 5.4 Dropped as YAGNI

The `Subgraph` criterion-strategy objects from the earlier draft. Three call
sites do not need a strategy pattern — a function with an explicit signature is
honest. That was pattern-matching, not problem-solving.

---

## 6. The rest of the object model

### fly/

- **`Connectome`** — streaming loader, aggregation cache, `consensus_nt` signs.
  Never loads weights whole (invariant 2).
- **`Network`**, **`Integrator`** — the integrator is one implementation of the
  leaky update, ReLU, clip, denormal flush and noise. Today this is duplicated
  across six call sites.
- **`SensoryChannel`** → `LoomingChannel` (θ, θ̇), `OdourChannel`,
  `TerrainChannel`, `HomeSignal`, `RetinotopicMap` (dormant). Consume abstract
  stimuli, never entities.
- **`InternalState`** — hunger (NPF), arousal (pC1), satiety. Gates and
  modulates rather than drives.
- **`EligibilityTrace`**, **`DopamineSignal`** (compartment-aware: PAM reward vs
  PPL1 punishment, which one undifferentiated channel cannot express),
  **`PlasticityRule`**. Serialisation of learned weights is a **separate**
  collaborator, not a method on the rule — persistence has never been verified
  and deserves its own test.

### mario/

- **`Emulator`** — nes-py wrapper, deterministic seeding, frame stepping.
- **`RamDecoder`** — every address in one place, producing a `WorldState`.
- **`WorldState`** — decoded frame: player, entity records, tiles, score, time.
  The single boundary between the emulator and everything else.
- **`KindRegistry`**, **`Level`**, **`ActionSet`**.

### sim / render / config

- **`Episode`** — seeded loop over `Policy` × `Environment`; notifies observers.
- **`Fitness`** — weights on points, distance, time. **025 proved survival-only
  is degenerate** (an episode survived 800 frames oscillating at x=658 against a
  baseline 1432), so distance is not optional and the GUI must make a
  survival-only setting visibly degenerate.
- **`TelemetryObserver`** — typed schema, one writer. Hard rule from 017:
  **expose the axis the decision actually runs on** (`r_team`/`l_team`), not the
  one the name suggests (`dna01`/`dna02`).
- **`BrainPanel`**, **`Layout`** (1536x1080), **`VideoWriter`**.
- Per-component params dataclasses; every hand-set scalar becomes a named,
  typed, **bounded** field — bounds are not decoration, since 025 found
  `sigma`'s usable band is only ~0.04-0.06 and a GUI offering 0-1 would lie.

---

## 7. Phases

**Reordered from an earlier draft**, which extracted config from six duplicated
update sites and then unified those sites — doing the same extraction
repeatedly. Config extraction now happens once, against code already in final
shape.

Each phase ends green against the phase-0 goldens. No phase changes behaviour
except the last.

**Phase 0 — characterisation tests. Non-negotiable.**
Freeze golden telemetry for three runs (017 reprise, 025b, a σ=0 baseline).
Assert byte-identical reproduction. Without this the refactor is unverifiable.

**Phase 1 — move, don't change.**
Docs into `docs/`, runs and telemetry into `projects/legacy/`, RUNS.md paths
rewritten, package skeleton created, imports fixed. Zero logic edits. Goldens
must pass — this phase proves the harness works.

**Warning, live until phase 5 lands:** every `out_mp4="runs/..."` default
across `run_steering.py`/`compare_controllers.py`/etc. still points at the
old top-level location — phase 1 deliberately left these untouched (a
default-output redesign is phase 5's job, not a move). Any ad-hoc call to
one of these functions before phase 5 silently recreates a stray top-level
`runs/` directory next to `projects/legacy/runs/`. Not a bug; just don't be
surprised by it.

**Phase 2 — the `fly/` ÷ `mario/` split and the entity records.**
Code to its side, `EntityRecord` + `KindRegistry` + profiles, `bridge/` stood
up. **Add the import-guard test.**

**Phase 3 — unify duplicated logic.**
One `Network` and one `Integrator` replacing six update sites. Highest risk of
silent numerical drift; goldens are the check.

**Phase 4 — config extraction.**
Now that each constant has exactly one home, extract once into per-component
params. Produces `docs/SCALARS.md`, the first honest count we will have had.

**Phase 5 — `Episode`, protocols, fitness, telemetry observers, render.**
`ProjectConfig` drives a run; outputs land in `projects/<name>/`.

**Phase 6 — the eligibility trace.** The only phase that changes behaviour; full
four-field RUNS.md entry and a video.

---

## 8. The trace, and the question to settle first

025 measured the thing that makes this hard: **one frame of difference at
commitment produced death at frame 406 instead of 689** — 283 frames of
divergence from one frame of cause.

So `tau` is the load-bearing choice. Too short and the tag has decayed before
the outcome arrives; too long and every synapse active in the episode receives
equal credit for what one of them caused.

**Settle before building:** what is the real eligibility-trace time constant in
*Drosophila*, and does it span the gap between a decision and its consequence in
Mario? If the fly's trace is ~1 second and our cascade is ~5 seconds of game
time, the mechanism does not reach — and that is a finding, not a tuning
problem. Check the biology before picking a number.

---

## 9. Risks

- **Silent numerical drift in phase 3.** Goldens are the check; if one fails,
  stop and diff rather than re-baselining.
- **Over-abstraction.** The test is whether a GUI could bind to a class.
  Classes that fail it should not exist. This revision already deleted two.
- **The import rule decaying.** Enforced by a test.
- **Scope creep into the GUI.** This plan stops at "the tool could be built on
  this."
- **Migration losing a run.** Media is not in git and we have already lost one
  file to a blanket delete. Copy, verify counts and sizes, then remove — never
  bulk `mv`.

---

## 10. Estimate

Phase 0-1 one sprint. Phase 2 one. Phase 3 one. Phase 4-5 one to two. Phase 6
one. **Five to six sprints**, with a working tree and passing goldens at every
boundary.
