# fly_mario — redesign plan (draft 1, 2026-10-01)

Author: Claude, for Arun. Status: **draft for review; no code changed.**
Repo state when written: `bb2ceb6` (bio_strict + calibration to 40°, obstacle investigation).

---

## 1. Goal and the one rule

**Goal.** A fruit-fly brain (MaleCNS v1.0) plays Super Mario Bros. Arun adds one mechanism at a time through the tool, sees it work in a small test scene, and builds up until the fly learns to win 1-1. The learned fly is then tested on other levels.

**The rule (Arun, 2026-10-01).**

- Allowed: changing the characteristics of objects, enemies and surroundings, and how the fly perceives them.
- Never: making the fly fire a neuron. Stimuli enter only at sensory neurons.
- Everything after the senses is the fly's: its wiring decides the action, and learning changes it only through experience.

**Arun's design choices.** Strict only (biologically supported mechanisms); a mechanism library plus a guarded builder; small test scenes first; one brain that grows across experiments.

---

## 2. Why redesign (what the audit taught us)

| Finding | Consequence for the design |
|---|---|
| 8 separate circuits, each with its own gain, threshold and clip, gave 107 scalars and knife-edge results. | One brain, one neuron model, one parameter set, calibrated once. |
| Wins came from seed luck, injected drives (`home_bias`, `walk_drive`, the wall cue onto the Giant Fiber) and perception leaks. | No injection API at all; stimuli only at the sensory tier. |
| We fitted the fly to Mario (pits, pipes, run-up). | Fit Mario to the fly: each game object is a natural stimulus, and the behaviour is whatever comes out. |
| We tuned on game outcomes. | Calibrate on synthetic stimuli against physiology; evaluate on held-out seeds against a shuffled connectome. |
| After honest calibration the real brain beats shuffled (16/20 past the Goomba vs 0/20; median x 712 vs 310). | This result is the baseline the redesign must reproduce before anything else is added. |

---

## 3. Architecture

### 3.1 Layers

```
Game (NES emulator, RAM)
   │  scene description: what is on screen, where, what kind   [mario/, reuse]
   ▼
World model  ── per-object characteristics set in the tool (what each thing is to the fly)
   │
   ▼
Senses       ── mechanisms: cue → activity of real sensory neurons      [new, small]
   │            (the only place the outside world touches the brain)
   ▼
Brain        ── ONE network from the connectome, one neuron model,
   │            plasticity in the mushroom body                          [reuse core]
   ▼
Motor readout── fixed map: descending / motor neurons → NES buttons      [reuse, frozen]
   │
   ▼
Game
```

Each layer talks only to the next one. The brain has no method that accepts a current except from the Senses layer.

### 3.2 One brain

- **One unified network, built by one rule.** A manifest lists the sensory populations (entry points) and the output neurons (the motor map). The network is every neuron on a path between them within *k* hops, keeping connections of at least *N* synapses. The rule, *k*, *N* and the resulting neuron and edge counts are saved with the brain.
- **Why not the whole CNS.** MaleCNS has 211,577 bodies and 151.9M connection rows. Simulating all of it per game frame is too slow for training on this machine. The unified subgraph keeps the "one model" property; a whole-CNS run stays possible offline as a check.
- **Weights.** Signed synapse count divided by the target's total input, with the sign from the predicted neurotransmitter. This is the recipe already verified against the raw data (`fly/connectome/circuit.py`).
- **One neuron model, one parameter set.** Rates in Hz (clip 200), one spike model for neurons known to spike singly (Giant Fiber), one time constant.
- **One gain, from stability.** A single recurrent gain set by the spectral-radius criterion already used in calibration (gain = min(g, 0.85/ρ)), so nothing latches at rest.
- **Shuffled twin.** A degree-preserving shuffle of the same network, using the same fixed numbers, is built alongside for every evaluation.

### 3.3 Mechanisms (the Senses layer)

A **mechanism** is three things:

1. **Cue:** something visible or touchable in the scene (an approaching enemy, a smell source, contact with a mushroom, light from one side).
2. **Sense channel:** the real sensory neurons it activates.
3. **Encoding:** how cue strength becomes neuron activity, taken from published recordings and validated on a synthetic stimulus.

Initial library (status column is honest about what exists today):

| Mechanism | Cue in Mario | Entry neurons | Evidence | Status |
|---|---|---|---|---|
| Looming threat | Enemy approaching on screen | LPLC2 (size), LC4 (speed) | Ache et al. 2019 (verified) | Built and calibrated (GF fires at 41–47°) |
| Expanding obstacle | Wall or pipe ahead | Same looming entry | Same | Built (opt-in), gives a jump on approach only |
| Food smell | Mushroom, "?" block | Attractive olfactory receptor neurons, left and right antenna | To verify | Exists but enters mid-pathway; move to receptor neurons |
| Aversive smell | Enemy | Aversive olfactory receptor neurons | To verify | Same |
| Sweet taste (reward) | Touching the mushroom, hitting "?" | Sugar taste neurons → dopamine neurons through real wiring | To verify | **New.** Today reward is injected as dopamine |
| Pain or heat (punishment) | Getting hit, dying | Nociceptive neurons → dopamine neurons through real wiring | To verify | **New.** Today punishment is injected |
| Goal direction | "Right is the way" | A light or attractive cue to the right, through phototaxis | To verify | **New.** Replaces `home_bias` and `walk_drive` |
| Gap width | Pit ahead | C2/C3 (parallax) → central complex | Pick & Strauss 2005, Triphan 2010/2016, Krause 2019 (verified) | **Investigation.** Route in MaleCNS not yet traced |
| Hunger | Fly state | Internal state, set in the tool | — | Exists |

**Vision entry tier (open decision D1).** The strict reading of the rule is "photoreceptors only". Simulating the retina and medulla for every frame is a large project of its own. The pragmatic reading is to enter vision at early feature neurons whose tuning is published (LPLC2, LC4, C2/C3), which is what the calibrated model does now. The plan assumes the pragmatic tier and labels it in the tool.

### 3.4 Motor readout

- A fixed table from output neurons to buttons: Giant Fiber/TTMn → A; DNp09 → walk and B; DNa01/DNa02 → left/right; MDN → back up.
- Reading neurons fires nothing, so it is within the rule.
- Thresholds are set once from synthetic-stimulus tests and are never an experiment input.
- Down and Up stay unassigned until a justified neuron is found.

### 3.5 Learning

- Mushroom-body three-factor rule with recovery (already built).
- Dopamine comes only from sensed reward and punishment through real pathways (see 3.3). No dopamine injection.
- **One brain grows:** each experiment continues from the previous stage's weights. A stage checkpoint is saved after every experiment, and any stage can be reloaded.

### 3.6 Guard rails (enforced in code, not by discipline)

- The stimulus API accepts only neuron ids in the manifest's sensory tier.
- There is no function that adds current to any other neuron.
- A mechanism cannot read RAM facts that are not visible on screen.
- Every result is stamped with the brain's build rule, calibration file hash and mechanism list, and is always reported next to its shuffled twin.

---

## 4. Experiment ladder

An **experiment** = a test scene + the mechanisms switched on + a pass criterion + controls. Controls are the same for all: 20 held-out seeds, real vs shuffled connectome.

| # | Experiment | Scene | Mechanisms on | Pass criterion |
|---|---|---|---|---|
| E0 | Walk to the goal | Flat ground | Goal direction | Reaches the right edge in ≥ 18/20; shuffled does not |
| E1 | Jump the Goomba | Flat ground, one Goomba | + Looming threat | Clears it in ≥ 16/20; shuffled ≤ 2/20 |
| E2a | Obstacle | One pipe | + Expanding obstacle | Gets past in ≥ 14/20 |
| E2b | Gap | One pit | + Gap width (if the route exists) | Crosses crossable gaps, refuses wide ones |
| E3 | Find food | Mushroom released from a block | + Food smell | Touches the mushroom in ≥ 14/20 |
| E4 | Learn from reward | E3 repeated | + Sweet taste | Touch rate rises with training; shuffled does not |
| E5 | Learn from mistakes | E1 repeated with hits | + Pain | Hit rate falls with training |
| E6 | 1-1 in segments | 1-1 split at savestates | All passed mechanisms | Each segment passes |
| E7 | Win 1-1 | Full level, training | All | Win rate on held-out seeds rises and beats shuffled |
| E8 | Transfer | 1-2, 1-3, 1-4 | Frozen learned brain | Distance vs shuffled, no retraining |

Notes:

- E0 and E1 should already pass with what exists; they are the parity check for the new architecture.
- E2b may fail honestly. Real flies climb across gaps, they do not jump them, and the route from C2/C3 to an action is not yet traced in the data.
- Test scenes are savestates plus a small scene description, so no new emulator work is needed.

---

## 5. Tool redesign

**Four screens instead of seven tabs.**

1. **Experiments.** The ladder as cards: scene preview, mechanisms on, pass criterion, last result (real vs shuffled), Run and Train buttons.
2. **Mechanisms.** The library as cards with an on/off switch per object kind and one strength slider. A **Build** button opens the guarded builder: choose a cue (from on-screen cues), choose a sense channel (from the sensory tier), choose an encoding, preview it on a synthetic stimulus.
3. **Watch.** The existing run player, brain map and controller pad, unchanged.
4. **Results.** Pass/fail per experiment, real vs shuffled with confidence intervals, learning curves, stage checkpoints.

**Inputs the user sets (about 12):** per object kind: which mechanisms and how strong; fly state: hunger, arousal, noise; brain: real or shuffled, learning on/off, learning rate; experiment: scene, seeds, episodes.

**Everything else** (gain, thresholds, unit factors, time constants) is shown read-only in a **Details** drawer with a tag: measured, calibrated or invented.

---

## 6. Reuse analysis

Sizes are lines of Python today. "Keep" means used as is; "adapt" means small edits; "retire" means frozen as legacy, not deleted, so the goldens and old runs still work.

| Area | Lines | Verdict | Reason |
|---|---|---|---|
| `mcns.py` (data access) | 287 | Keep | Streaming loader and subgraph extraction are exactly what the unified builder needs |
| `mario/` (emulator, RAM, entities, actions) | 625 | Keep | Scene description already exists (entity registry, tile queries, visible-only variants) |
| `sim/` (episode loop, telemetry, fitness, protocols) | 419 | Keep | Policy and Environment protocols fit the new layers |
| `fly/network/` (integrator, network, dynamics) | 301 | Keep | One neuron model already; drop per-circuit instances |
| `fly/plasticity/` (three-factor, dopamine events) | 104 | Adapt | Rule kept; dopamine source moves from events to sensed pathways |
| `fly/connectome/circuit.py`, `expand_subgraph.py` | 421 | Adapt | Signs, weight matrix, shuffle, spectral radius are reused; the per-circuit type lists become the manifest |
| `fly/sensing/` (retinotopy, sensory, adaptation) | 277 | Adapt | Looming encoding and odour adaptation move into mechanisms |
| `fly/circuits/` (8 circuit files + loaders) | ~1,100 | Retire | Replaced by one unified builder; their verified neuron lists and edge checks feed the manifest and tests |
| `bridge/loom_disc.py` (synthetic disc harness) | 101 | Keep | The calibration and validation harness |
| `bridge/perception.py`, `entity_profiles.py` | 428 | Adapt | Become the scene description and the mechanism definitions |
| `bridge/controller_modules.py` | 531 | Adapt | Keep the module protocol and MotorDirect; retire control and injection modules |
| `bridge/full_policy.py` | 969 | Retire | The monolith that wires 8 circuits; replaced by a slim brain policy (~250 lines) |
| `run_steering.py` | 821 | Retire | Old runner with demo paths; `sim/` plus the tool runner replace it |
| `config/params.py` + docs generators | 827 | Retire for new path | 107 scalars; new path has ~12 user inputs plus one calibration file |
| `config/bio_strict.py`, `project_config.py` | 181 | Adapt | Strict becomes the only mode of the new path |
| `scripts/` eval and calibration | ~500 of 3,331 | Keep | `eval_connectome.py`, `calibrate_bio.py`; the rest is legacy analysis |
| `tool/core/` run store, run spec, runner, frame store, savestates, project, evaluation, batch, training | ~1,700 of 2,713 | Keep | Reproducible specs, eval and training are solid |
| `tool/core/` schema, display params, circuit manifest, presets, wiring | ~500 | Retire | Serve the 107-scalar forms |
| `tool/ui/` player, video, overlays, learning chart, batch table, gate, duplicate, responsive shell | ~3,000 of 5,357 | Keep | The Watch and Results screens are mostly built |
| `tool/ui/tabs/` circuits, goal, character, enemies, objects, settings + param form | ~1,900 | Replace | Become Experiments and Mechanisms; entity cards and sprites are reused |
| `tests/`, `tool/tests/` | 8,108 | Keep legacy; add new | Goldens stay byte-identical because the legacy path is frozen |

**Summary.**

- Roughly **60%** of non-test code is kept or lightly adapted.
- New code is about **1,800–2,200 lines**: unified network builder (~300), mechanisms and encoders (~400), slim brain policy (~250), experiment and scene runner (~250), Experiments and Mechanisms screens with the builder (~700), tests.
- The expensive work already done carries over in full: data verification, calibration to physiology, the eval harness, reproducible run specs, the player.
- The main thing thrown away is `full_policy.py`, the per-circuit files and the parameter forms, which is where the clutter and the hidden coupling live.

---

## 7. Migration plan

Each phase: a short SPEC first, one Claude Code session, validation on synthetic stimuli, one eval, one commit. The legacy path is never edited.

| Phase | Work | Exit check |
|---|---|---|
| 0. Investigate (no code) | Which sensory neuron types MaleCNS contains for smell, taste, pain, light; size and speed of the unified network for candidate *k* and *N*; whether C2/C3 → central complex → an output can be traced | A short report; decisions D1–D3 settled |
| 1. Brain core | Manifest, unified builder, slim policy, motor map; looming mechanism ported | **Parity:** GF fires at 41–47° on the disc; E1 ≥ 16/20; shuffled 0/20 |
| 2. Tool skeleton | Experiments and Mechanisms screens (library only), Watch and Results wired to the new path | Arun runs E0 and E1 from the tool with no Claude Code change |
| 3. Smell and goal | Odour at receptor neurons with left/right difference; goal-direction cue replaces `home_bias` | E0 and E3 pass; no injected drive left |
| 4. Sensed reward and punishment | Taste and pain through real pathways to dopamine neurons; stage checkpoints | E4 and E5 show learning vs shuffled |
| 5. Builder | Guarded mechanism builder in the tool | Arun builds one new mechanism end to end |
| 6. Obstacles and gaps | Build only what Phase 0 found a route for | E2a, and E2b if a route exists |
| 7. 1-1 and transfer | Segment training, full-level training, transfer runs | E6–E8 reported honestly |

**Keeping cost down.**

- One phase per session, with a prompt that points at this document, so context stays small.
- Tool-only changes run only the affected tool tests; changes outside `tool/` run the full root tests once at the end of the phase.
- No tuning loops on game runs: a value is derived, validated on a synthetic stimulus, and evaluated once.
- Legacy stays frozen, so there is no rework of old tests or goldens.

---

## 8. Risks and open decisions

| # | Item | Options | Recommendation |
|---|---|---|---|
| D1 | Vision entry tier | Photoreceptors only (large project) vs early feature neurons with published tuning | Feature neurons, labelled in the tool |
| D2 | "Go right" | Keep `home_bias` flagged as invented vs a goal cue through phototaxis | Goal cue; it fits the rule exactly |
| D3 | Gaps | Jump (no route found) vs attempt-to-cross (real fly behaviour) vs leave unsolved | Decide after Phase 0 |
| D4 | Buttons the fly cannot justify | Down, Up | Leave unassigned |
| D5 | Winning 1-1 | May not be reachable under the rule | Report distance and win rate vs shuffled honestly at every stage |
| D6 | Speed | Unified network may be larger than today's circuits | Measure in Phase 0; pick *k* and *N* to keep training practical |
| D7 | Sensory types in the data | I could not query the annotations from here to confirm receptor, taste and pain neuron types exist in MaleCNS | First item of Phase 0 |

---

## 9. Done means

- Arun can run and train every experiment from the tool without a code change.
- The tool has about 12 inputs; everything else is read-only with its origin shown.
- No code path can add current to a non-sensory neuron.
- Every reported result has a shuffled twin on held-out seeds.
- E0 and E1 pass at parity with today's calibrated result.
