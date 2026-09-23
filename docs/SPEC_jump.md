# SPEC: fly_mario step 1 — the jump

Goal: a Goomba approaches, the **real fly escape circuit** fires, Mario jumps.
NES emulator, visible on screen. **Nothing is trained.** The jump is the real
cascade reaching the muscle.

Scope of this step: **jump only.** No steering, no learning, no other circuits.
Mario runs right on a hardcoded button hold. The only thing the fly decides is
*when to press A*.

---

## 1. The circuit

All counts and connection weights below are **verified** against MaleCNS v1.0 —
do not re-derive them, but do assert them at load time.

| Type | Count | Role |
|---|---|---|
| LC4 | 126 (71 L / 55 R) | looming detector, angular velocity |
| LPLC2 | 185 (94 L / 91 R) | looming detector, expansion |
| ~~LPLC1~~ | 134 | **excluded — verified not to drive the Giant Fiber** |
| DNp01 | 2 (1 per hemisphere) | **Giant Fiber** — the escape command neuron |
| TTMn | 2 | **tergotrochanteral motor neuron — the jump muscle** |
| STTMm | 4 | accessory, optional |

Verified connectivity (synapses / connected neuron pairs):

```
LC4    -> DNp01     6,362 /   126     every LC4 connects, exactly one GF each
LPLC2  -> DNp01     4,862 /   185     every LPLC2 connects, exactly one GF each
LC4    -> LC4      18,392 / 5,334     lateral, ~3x its own output drive
LPLC2  -> LPLC2    46,178 /13,434     lateral, ~9.5x its own output drive
LPLC2  -> LC4       2,902 / 1,180
LC4    -> LPLC2       361 /   306
DNp01  -> LC4          45 /    32     feedback
DNp01  -> DNp01         2 /     2
```

**On LPLC1 (resolved).** flyproject.io describes the escape circuit as "three
visual cell types, LC4, LPLC1 and LPLC2." MaleCNS does contain LPLC1 — 134
neurons, 68 L / 66 R, `visual_projection` — but its drive onto DNp01 is **1
synapse over 1 connected pair**, against LC4's 6,362/126 and LPLC2's 4,862/185
where *every* neuron connects. That is noise, not a pathway. LPLC1 does have
dense self-recurrence (20,774 synapses / 6,761 pairs) and cross-talk with the
other two, so it is doing something — just not driving escape. Excluded from
this circuit. Note it in the README: flyproject's grouping is looser than the
GF-specific wiring supports.

Two consequences that must shape the implementation:

1. **Strict lateralisation.** 126 LC4 over 126 pairs means each detector drives
   exactly *one* Giant Fiber — left eye to left GF. Keep the two hemispheres
   as separate channels.
2. **Recurrence dominates.** Lateral connection within each detector population
   is 3–9.5x the feedforward drive onto the Giant Fiber. This is not a
   feedforward threshold detector. It needs **real dynamics**.

   ~~The lateral competition is what makes the circuit commit decisively.~~
   **CORRECTION.** This was wrong, and the data disproved it. LC4, LPLC2 and
   DNp01 are 100% cholinergic, so that lateral recurrence is *excitatory* —
   positive feedback, an amplifier, not competition. Competition requires
   inhibition, and there is none among these 313 neurons. With rows normalised
   to 1 and all signs positive, ReLU never engages and the system is linear
   across its whole range: it decays for g<1 and diverges for g>1, with no
   third behaviour. That is algebraic, not a tuning failure. See section 1b.

## 1b. The missing inhibition — expand the subgraph

The first 313-neuron build failed for a real reason: we picked neurons **by name**,
from flyproject.io's framing, rather than asking the connectome who actually
drives the Giant Fiber. Measured input coverage was DNp01 26%, LPLC2 13%,
**LC4 7%** — we amputated 74–93% of the circuit and then asked why it didn't
behave like the circuit.

What the data says is missing:

**Onto DNp01** — 36,617 total input synapses, of which **30.6% GABA + 5.3%
glutamate = 35.8% inhibitory**, all of it excluded. The source is fragmented:
no partner exceeds 2.2% of input, and the inhibition arrives from a broad
population of small local neurons (SAD073/091/096/109, CL367, AN12B001,
GNG300, LHAD1g1, PVLP010).

**Onto LPLC2** — 22.6% inhibitory, and structurally far more interesting. A
handful of individually-identified GABA/Glu neurons, **exactly one per
hemisphere**, each synapsing onto ~100% of their own hemisphere's LPLC2
population and zero on the other side:

| Type | Coverage |
|---|---|
| PVLP011 | 91/91 R, 94/94 L |
| LPi21 | 91/91 R, 93/94 L |
| LPi2b, Li39, LPT59 | similarly lateralised |

Only ~3.8% of LPLC2's synapse count, but a single neuron pooling over an entire
hemisphere's detector population **is** the wiring diagram for divisive
normalisation. LPi — lobula plate intrinsic — is precisely the cell class known
for inhibitory pooling in the fly optic lobe. Weight understates its role;
topology is the point.

### The expansion rule

Add these neurons. **But do not add only the inhibitory ones** — selecting
partners by sign would be hand-tuning the model toward the answer we want, and
would invalidate the claim that the behaviour comes from the connectome.

Use a **sign-agnostic threshold**: include every neuron with ≥ N synapses onto
any member of {LC4, LPLC2, DNp01}, whatever its neurotransmitter. Choose N so
the network lands somewhere around 600–1,500 neurons — still trivial to
simulate. Report the resulting size, the new input-coverage percentages, and
the new excitatory/inhibitory balance.

Exception, stated openly: PVLP011, LPi21, LPi2b, Li39 and LPT59 are included
regardless of whether they clear N, justified by **hemisphere coverage** rather
than sign — a neuron touching 100% of a population is structurally load-bearing
even when its synapse count is small. Note this in the README as a judgement
call, not a data-driven one.

Then re-run the section 3 sweep. The hypothesis is that inhibition opens a band
where the network is both stable and sharp. It may not. Either result is worth
having.

---

### Data

This repo lives at `fly_brain/fly_mario/`, so everything below is one level up
(`../`). Do not copy the data in — reference it.

| What | Path (relative to repo root) |
|---|---|
| Annotations (212k neurons, 36 cols) | `../data/malecns_v1.0/body-annotations-male-cns-v1.0-minconf-0.5.feather` |
| Weights — 152M edges, 1 GB | `../data/malecns_v1.0/connectome-weights-male-cns-v1.0-minconf-0.5.feather` |
| Neurotransmitters | `../data/malecns_v1.0/body-neurotransmitters-male-cns-v1.0.feather` |
| **Escape subgraph, already extracted** | `../data/derived/edges_escape_circuit.parquet` |
| Streaming loader — reuse it | `../mcns.py` |
| The extraction that produced it | `../escape_circuit.py` |

`mcns.py` already has the streaming aggregator, Dale's-law-ready annotation
loader and the neurotransmitter deduplication. Reuse it rather than writing a
new one. **Never `pd.read_feather` the weights file whole** — it is 3.6 GB
uncompressed. `mcns.aggregate_edges(level, keep=...)` streams it in Arrow
record batches and caches to `../data/derived/`.

For body-level (not type-level) wiring, which this step needs, you will have to
extend `mcns.py` with a body-id-level extraction restricted to the ~313 neurons
of interest. Follow the same streaming pattern.

### Signs

Dale's law. Take `consensus_nt` per presynaptic neuron from the
neurotransmitter file (deduplicate to one row per body, keeping the highest
`predicted_nt_confidence`):

- acetylcholine, dopamine → **+1**
- GABA, glutamate → **−1**
- everything else → 0 (or drop the edge; log how many)

A neuron's sign applies to *all* its outgoing edges.

### Weight normalisation

`w_ij = sign_i * (synapses_ij / input_synapses_of_j)`, then a single global gain
scalar `g`.

**Careful with the denominator.** We are modelling 313 neurons out of 211,577.
Most of each neuron's real synaptic input comes from outside this subgraph. If
you normalise by each neuron's *total* input in the whole connectome, the
in-subgraph weights come out tiny and the network is dead until `g` is enormous.
Normalise by **in-subgraph input** instead, so each row sums to roughly 1 and
the spectral radius starts near 1. Log both denominators so we can see how much
of each neuron's input we are ignoring — for the detector populations that
fraction is the honest measure of how much of the real circuit we've cut away.

---

## 2. Input — read RAM, not pixels

**Do not feed the NES frame to the looming detectors.** The NES view is
third-person side-scrolling: a Goomba walking toward Mario does *not* expand on
screen, it translates horizontally. There is no looming stimulus in those pixels.
Feeding the raw frame in would give the detectors an optomotor signal, not a
threat, and the whole premise breaks.

Instead, synthesise Mario's-eye view from RAM. `nes-py` exposes `env.ram`.

SMB RAM addresses:

| What | Address |
|---|---|
| Mario x on screen | `0x0086` |
| Mario level x page | `0x006D` |
| Mario y | `0x00B5` |
| Enemy x on screen | `0x0087`–`0x008B` (5 slots) |
| Enemy y | `0x00B6`–`0x00BA` |
| Enemy type | `0x0016`–`0x001A` |
| Enemy active flag | `0x000F`–`0x0013` |

For each **active** enemy slot, compute angular size as seen from Mario:

```
d      = enemy_x - mario_x          # signed; positive = ahead
theta  = 2 * arctan(w / (2 * |d|))  # w ~ 16 px, one tile
```

θ grows non-linearly as d shrinks — slow, then a sharp blow-up in the final
frames. That expansion is the real stimulus LPLC2 is tuned to. Also track
`dtheta/dt` across frames; LC4 responds to angular velocity, LPLC2 to expansion,
so drive them with slightly different functions of (θ, θ̇).

**Retinotopy: skip it in v1.** `assignedOlHex1/2` is 0% populated for LC4 and
LPLC2 in MaleCNS (those coordinates exist only for columnar optic lobe cells),
so we cannot place receptive fields without deriving them from upstream
partners. For now drive all detectors in a hemisphere with the same θ(t) —
route enemies ahead of Mario to one hemisphere, behind to the other. Jump
*timing* still emerges from the real circuit.

---

## 3. Dynamics

Leaky integrator over the ~313 neurons:

```
h(t+1) = (1 - alpha) * h(t) + alpha * phi( g * W @ h(t) + I_sensory(t) + b )
```

**Use ReLU for `phi`, not tanh.** These are firing-rate units; a rate cannot go
negative. tanh would let a neuron have negative output, which is meaningless
here — inhibition already enters through the sign of `w_ij`. Add an upper clip
to stop runaway.

**Starting values** (these are guesses, not verified — expect to move them):

- `alpha = 0.3`
- `substeps = 10` network steps per emulator frame

At 60 fps one frame is 16.7 ms, so 10 substeps puts each at ~1.7 ms, and
`alpha = 0.3` gives a time constant of ~3 substeps ≈ 5 ms. That lands in the
range of the real Giant Fiber escape latency (5–10 ms from looming threshold to
spike), which is the only anchor we have.

`g` has no principled starting value. Sweep it.

### Tune the circuit before it ever sees Mario

**This is the first thing to build, ahead of any emulator integration.** Drive
the circuit with a *synthetic* looming stimulus — an object of fixed width
approaching at constant velocity, so θ(t) = 2·arctan(w / 2(d₀ − vt)) — and plot
LC4 mean, LPLC2 mean, DNp01 and TTMn against time. No game, no RAM, no
rendering. If the circuit doesn't behave here it will never behave in Mario, and
debugging it through an emulator is miserable.

What you are looking for, sweeping `g` over a few orders of magnitude:

1. **With zero input, activity decays to zero.** If it self-sustains, `g` is too
   high — the recurrence is running away.
2. **A brief input pulse produces a transient that dies.** No ringing.
3. **A looming ramp produces a sharp, late DNp01 rise** — not a slow ramp that
   tracks θ. The Giant Fiber should stay quiet and then commit. That sharpness
   is the winner-take-all signature, and it's the thing to verify: it should
   come out of the lateral recurrence, not out of a threshold we imposed.

Report the spectral radius of `g·W` at the chosen `g`, and save the diagnostic
plot. If no value of `g` gives all three, say so rather than picking the least
bad — that would be a real finding about the model, and we'd revisit the
normalisation or the leak rather than paper over it.

### Diagnostic 4 — sustained input (added after the first video)

**A single ramp from rest is not enough, and trusting it cost us a run.** In the
game the circuit receives input continuously for thousands of frames: enemies
approach, pass, reappear, with no reset between them. An amplifying network that
looks stable on one transient will integrate that sustained drive and pin itself
against the clip ceiling, after which every unit is a constant and the circuit
has stopped computing — while still "working" in the sense that the numbers are
finite and a threshold is still being crossed.

So before any emulator run, replay a **long input trace** — at minimum 2,000
steps containing several approaches separated by gaps — and assert:

1. `LC4_mean` and `LPLC2_mean` **vary with θ** across the whole trace. Report
   their correlation with θ. If it is near zero, the circuit is saturated.
2. No unit sits at the clip ceiling for more than a brief transient. Report the
   fraction of steps any unit spends clipped.
3. Activity **returns toward baseline in the gaps** between approaches.
4. `TTMn` crosses its press threshold on approaches and **not** in the gaps.

Fail the run loudly if any of these break. A jump that happens while the
detectors are pinned at a constant is not caused by looming, whatever the video
looks like.

### The press must be caused by the circuit

Assert the causal chain every frame, and log violations: A is pressed **iff**
TTMn is over threshold, and TTMn is over threshold only when DNp01 has spiked
within the last few steps. If A fires while DNp01 is silent, or DNp01 spikes
with no press, that is a broken chain — report it, do not render it.

---

## 4. Output — the jump muscle

Do **not** map a DNp01 spike straight to the A button. Go one more hop:

```
looming -> LC4/LPLC2 -> DNp01 (Giant Fiber) -> TTMn -> press A
```

Press A when TTMn activation crosses threshold. That threshold and the global
gain `g` are the only two hand-set scalars in the system; everything else comes
from the connectome. Say so clearly in the README.

---

## 5. Deliverable for this step

A script that runs SMB level 1-1 with Mario holding right, and per frame prints
or logs:

```
frame  d_px  theta  dtheta  LC4_mean  LPLC2_mean  DNp01  TTMn  A?
```

Plus:

- An assertion at load that the neuron counts and the four main connection
  weights match the table above — fail loudly if the data changed.
- A **shuffled-connectome control**: same neurons, same in/out degree
  distribution, same signs, edges rewired at random. If the real fly doesn't
  jump better than the shuffle, we've built a sparse RNN with fly-shaped
  decoration. Write this now, not later.
- A short README stating exactly what was hand-set (two scalars) and what came
  from the connectome.

## 6. Emulator — resolved

`gym-super-mario-bros` + `nes-py` 8.2.1 works on Windows / Python 3.12. No C
compiler needed, but three version pins are required (all documented upstream
incompatibilities, recorded in `requirements.txt`):

- `numpy<2` — numpy ≥2.0 overflows in nes-py's ROM-size arithmetic
- `gym==0.23.1` — gym ≥0.26 expects a 5-tuple from `step()`; nes-py returns the
  old 4-tuple
- `setuptools<70` — gym 0.23.1 imports stdlib `distutils`, removed in 3.12;
  setuptools provides the shim, but **only if imported before gym**

Verified end to end in `fly_mario/.venv`: reset, RAM read, 60 steps holding
right moved Mario x 40 → 121. `stable-retro` not needed.

## 7b. The visual — this sprint must end with Mario jumping

**This is the sprint's definition of done.** Not a plot: Mario, on screen,
launching and jumping because the circuit fired.

Deliver a recorded run (MP4 or GIF, committed) of SMB 1-1 with Mario holding
right, jumping Goombas under circuit control, with a live overlay panel beside
or below the game frame showing:

- θ and dθ/dt, the looming signal
- LC4 mean, LPLC2 mean — the detector populations
- **DNp01** — the Giant Fiber, its own trace
- **TTMn** — the jump muscle, with the press threshold drawn as a line
- a visible flash on the frame where A is pressed

Rolling traces, last ~2 seconds. Keep it plain — this is a diagnostic readout
we will be staring at for hours, not a showpiece. The 3D brain render comes
later.

### Ship the visual even if the dynamics are imperfect

If the expanded subgraph gives a stable-and-sharp band for `g`, use it and say
so. **If it does not**, do not stall — fall back to giving **DNp01 itself**
spike-threshold-and-refractory dynamics while the detector populations stay
rate-based, and ship the video anyway with that stated plainly in the README.

That fallback is defensible: the Giant Fiber's all-or-none spiking with a
refractory period is a documented property of that specific neuron, and a rate
model of a two-neuron command stage cannot represent it. It is modelling real
biophysics, not papering over a gap. What would *not* be acceptable is a
saturating sigmoid chosen because it produces the answer we want — that
attributes the decision to a nonlinearity we picked rather than to the fly.

Whichever path it takes, the README states in one sentence which one, and how
many hand-set constants the final system has.

## 7. Explicitly out of scope

Steering, terrain, learning, the brain overlay, training of any kind. Later
steps. Build the jump.
