# fly_mario — the jump

A Goomba approaches Mario, the real fruit-fly escape circuit (Janelia
MaleCNS v1.0) fires, and TTMn's threshold-crossing presses A. See
`SPEC_jump.md` for the full design; this file states what came from the
connectome versus what was hand-set, per section 5.

`mario_jump.mp4` is the recorded deliverable: 300 frames (~5s), 1 jump
triggered by the circuit while Mario runs SMB 1-1 — see "Diagnostic 4" below
for why this replaces an earlier 582-frame/9-jump recording that turned out
to be an artifact, not a real result.

## What's hand-set

SPEC originally allowed exactly two: global gain `g` and a TTMn press
threshold. **There are now three**, and CLAUDE.md invariant 3 says to flag
that plainly rather than bury it:

| Scalar | Value | Why |
|---|---|---|
| `g` | 2.0 | Global recurrent gain. **Not** the value from the original section-3 re-sweep (3.5) — that value passed the single-ramp diagnostics but failed Diagnostic 4 (sustained input); see below. 2.0 is the middle of the band `[1.12, 3.35]` that passes Diagnostic 4, confirmed stable across 5 random trace seeds (`diag4.py`). |
| `dnp01_spike_threshold` | 0.5 | **The DNp01 spiking fallback.** Section 3's third diagnostic ("sharp, late DNp01 rise") failed at every g we tried, in both the original 315-neuron network and the expanded 1255-neuron one — see below. Per your instruction, DNp01's two bodies are modeled as leaky integrate-and-fire units instead of plain ReLU rate units: accumulate, and once membrane potential crosses this threshold, fire one frame at fixed amplitude and reset. Unaffected by the g fix — re-verified against Diagnostic 4 at the new g. |
| `ttmn_press_threshold` | 3.0 | TTMn activation to press A. Unchanged — still comfortably separates baseline from a post-spike TTMn response at the new g. |

Two more are mechanical (button-hold interface, not part of the neural
model): `JUMP_HOLD_FRAMES=25` (how long A stays down once triggered, so the
NES registers a real jump height) and `JUMP_COOLDOWN_FRAMES=40` (no
re-trigger while still airborne from the last one).

## What came from the connectome

- Neuron identities, counts, and every connection weight in the subgraph.
- Signs (Dale's law, from `consensus_nt`).
- Row-normalisation of `W` (in-subgraph input, section "Weight
  normalisation").
- Which neurons are even *in* the subgraph — section 1b's sign-agnostic
  threshold, not name-based selection (see below).
- The fact that DNp01→TTMn exists at all, and which side connects to which
  (both ipsilateral: DNp01[R]→TTMn[R] 70 synapses, DNp01[L]→TTMn[L] 20).

## Section 1b: the expanded subgraph

The original 315-neuron build (LC4/LPLC2/DNp01/TTMn, chosen by name from
flyproject.io's framing) amputated most of its own input: LC4 7%, LPLC2 13%,
DNp01 26% coverage. Expanded per SPEC's sign-agnostic rule — every neuron
with ≥N synapses onto any of {LC4, LPLC2, DNp01}, regardless of
neurotransmitter, plus PVLP011/LPi21/LPi2b/Li39/LPT59 (the lateralised
pooling neurons) unconditionally.

**N=60** was chosen because it lands the threshold-expansion at 940 new
neurons (600-1500 target). Final subgraph: **1255 neurons** (315 core + 940
threshold-expansion; the 5 pooling types all already cleared N=60, so the
"regardless of N" exception added zero extra).

Coverage after expansion:

| Type | Before | After |
|---|---|---|
| LC4 | 7% | 35.1% (21.1-44.6%) |
| LPLC2 | 13% | 24.3% (18.0-31.1%) |
| DNp01 | 26% | 67.3% (66.9-67.8%) |

E/I balance of the final 1255-neuron subgraph:
- By neuron count: 838 excitatory, 404 inhibitory, 13 unsigned (octopamine/
  histamine/unclear — dropped as sources, not mapped to a side).
- By synapse weight flowing into the subgraph: **51.6% excitatory, 45.2%
  inhibitory, 3.2% unsigned** — nearly balanced, a dramatic change from the
  original 315-neuron core's ~100% excitatory internal recurrence.

The largest single new population is **TmY3** (368 neurons) — a broad
medulla transmedullary input, not part of any named "escape circuit" in the
literature, but it clears the same synapse-count bar as everything else. It
is included on the same terms as the rest: the threshold doesn't
distinguish by identity, only by synapse count onto the detector
population, which is the point of section 1b's rule.

**Judgement call, stated openly (not data-driven):** PVLP011, LPi21, LPi2b,
Li39, LPT59 are included regardless of whether they'd clear N=60 on their
own, justified by hemisphere coverage (each synapses onto ~100% of one
side's LPLC2 population) rather than raw synapse count. In this case all
five already clear N=60 anyway, so the exception changed nothing about the
final neuron set — but the exception rule itself, and the reasoning behind
it, is a judgement call, not something the threshold produced on its own.

## Section 3 re-sweep: still no stable-and-sharp band

The hypothesis was that inhibition would open a band where the network is
both stable and produces the sharp, late DNp01 commitment section 3 asks
for. **It didn't.** Swept g from 0.3 to 200 on the expanded network:

- g ≲ 3.8: stable (decays to zero, no ringing), but DNp01 still tracks θ(t)
  almost exactly — same failure mode as the original 315-neuron network.
- g ≈ 4.0-4.6: the E/I balance changes *how* instability appears —
  **damped oscillation (ringing) that grows into runaway**, rather than the
  purely-excitatory network's monotonic blowup. Interesting qualitative
  difference, still fails "no ringing" and "decays to zero" simultaneously
  with the sharp-rise criterion.
- g ≳ 5: unstable, saturates the clip ceiling from noise alone within ~15
  frames, regardless of stimulus timing.

Plots: `tune_summary_no_winner.png` (original 315-neuron network, g=0.3/0.9/
1.05), `tune_summary_expanded_N60.png` (expanded 1255-neuron network,
g=1.0/3.5/4.2 — note the oscillation at g=4.2 vs. the original network's
clean monotonic blowup at high g).

**Conclusion, following your instruction:** used the DNp01 spiking fallback
rather than stall on this. The population dynamics (LC4/LPLC2/recurrence)
still do real work — they're what makes LC4_mean and LPLC2_mean track the
approach shape and what feeds DNp01's membrane — but the actual "commit"
event is a hand-set threshold-crossing on DNp01 itself, not an emergent
network property. That's the honest state of the model, not a claim that
the connectome's recurrence produces winner-take-all dynamics.

**Caveat that mattered later:** this sweep only ever drove the network with
one clean ramp from rest. `g=3.5` looked "stable" here, and passed — it took
a *sustained*, bilateral input trace (Diagnostic 4, below) to show that it
saturates over the timescale of an actual level. Treat "stable" in this
section as "stable under diagnostics 1-3," not stable in general.

## Diagnostic 4 — sustained input (the bug behind the first video)

The first recorded video (582 frames, 9 jumps, `g=3.5`) looked like a
success but wasn't: `LC4_mean`/`LPLC2_mean` were constant to 3 decimals from
around frame 100 on — identical whether a Goomba was at 112px or off screen
entirely — and TTMn was pinned at the 50.0 clip ceiling. The 9 jumps were
not caused by looming; the network had saturated and a saturated threshold
is still "crossed," so nothing in the original 3 diagnostics (tune.py) or
the causal-chain check caught it. Those diagnostics only ever drive the
circuit with **one clean ramp from rest** — never what the game actually
does: enemies on both hemispheres, overlapping, for thousands of frames with
no reset.

**Diagnostic 4** (`diag4.py`, SPEC section 3) replays a long
(3000-frame) input trace of bursts of overlapping approaches on **both**
hemispheres, separated by genuine quiet stretches, through the exact deployed
system (`HybridState` on the expanded N=60 circuit), and checks: (1) LC4/
LPLC2 mean activity correlates with theta across the whole trace, (2) no
unit sits at the clip ceiling beyond a brief transient, (3) activity returns
to baseline in the quiet stretches, (4) TTMn crosses its press threshold on
approaches and not in the quiet stretches.

A gentler version — single hemisphere, cleanly-separated gaps — does **not**
reproduce the bug (everything decays fine). The overlap across both
hemispheres is the missing ingredient: several of the section-1b threshold-
expansion neurons (selected purely by synapse count onto {LC4, LPLC2,
DNp01}, not by hemisphere) integrate drive from both sides at once and never
see a clean reset when only one side is tested in isolation.

**Confirmed failing at g=3.5** (all four numbers reproduce the bug: 3 units
clipped ~99% of the trace, worst end-of-gap/peak ratio 0.112, 4/4 spurious
threshold crossings in quiet periods). **Swept g** and found a band,
`[1.12, 3.35]`, that passes all four checks — well below 3.5, though not by
orders of magnitude, and confirmed stable across 5 random trace seeds.
Chose `g=2.0`, the middle of that band.

**Checked whether a leak/adaptation term was the missing piece instead**
(`dynamics.AdaptiveHybridState`, `adapt_sweep.py`): a slow self-inhibitory
trace subtracted from each rate unit's drive, the standard way to model
firing-rate adaptation. Grid-searched `(g, alpha_a, beta)`. Result: weak
adaptation can rescue the *original* g=3.5, but adaptation never opens up any
g below the band the plain gain fix already found — at moderate g it
actively kills the theta correlation (over-suppresses the signal) before it
helps stability. Since a bare change to `g` already passes Diagnostic 4 with
zero added constants, adaptation was **not adopted** — it would only add two
more hand-set scalars (on top of the three already flagged above) to
reproduce a result the simpler fix already gets, which CLAUDE.md invariant 3
argues against.

**Re-recorded once Diagnostic 4 passed** (`g=2.0`). The new run has exactly
**one** jump in the first 1200+ frames of the level, at frame 102, a Goomba
at `d=18px, theta=0.836` — a genuine, imminent collision. Running the level
further (checked out to 2700 frames) turned up no more jumps, but not
because the circuit went quiet: Mario runs into a pipe just after frame 150
and stays wedged against it (confirmed via RAM: `mario_x` frozen at 178 for
the entire remainder of a 2700-frame run). That's the hardcoded
"hold right, no steering" movement scheme from section 7 of SPEC hitting its
known limit, not a circuit problem — steering and terrain are explicitly out
of scope. The shipped video is trimmed to 300 frames so it shows the real
approach-and-jump event without padding out a frozen Mario.

## Video behavior, stated openly

Section 2 routes enemies **ahead of Mario to one hemisphere, behind to the
other**, symmetrically — SPEC doesn't say only "ahead" threats should be
able to trigger a jump, and the fly's compound eyes and bilateral GF circuit
have no such restriction either. The one jump in the current recording is
triggered by a Goomba genuinely visible and closing from ahead (d_px=18,
clearly on screen and about to collide), so this run doesn't exercise the
behind-Mario routing case — noted for whoever next records a longer run.

## LPLC1 (unchanged from earlier resolution)

134 neurons present in MaleCNS, but only 1 synapse onto DNp01 over 1
connected pair — noise, not a pathway. Excluded. flyproject.io's three-cell-
type framing is looser than the GF-specific wiring in this data supports.

## Emulator

`gym-super-mario-bros` 7.4.0 + `nes-py` 8.2.1, in `fly_mario/.venv`. Three
version pins, all upstream incompatibilities (`requirements.txt`):
`numpy<2`, `gym==0.23.1`, `setuptools<70` (imported before `gym`). Video
recorded via `opencv-python-headless<4.10` — the 5.x line requires
numpy≥2 and will silently break the pin if reinstalled (matplotlib pulls
in numpy≥2 via `contourpy` for the same reason, so it's kept **out** of
the `.venv` entirely; the offline diagnostics in `tune.py` that need it run
under the system Python instead — see `sensory.py`, which factors out the
matplotlib-free helpers `run_mario.py` actually needs).

## Three controllers compared (`compare_controllers.py`)

SPEC section 5's shuffled-connectome control, and a one-line baseline, run
against the real circuit on live SMB 1-1 (not synthetic input), same env,
same button-hold/cooldown mechanics, so only the *decision policy* differs:

- **A — the real circuit**, `g=2.0`.
- **B — shuffled connectome**, SPEC section 5's control: same neurons, same
  in/out degree distribution (exact — see `circuit.shuffle_edges`), same
  signs, edges rewired at random. Same `g` and thresholds as A.
- **C — a one-line baseline**: press A when `theta > c`, `c` bisected to
  fire at the same rate as A.

A minimal, non-neural "unstick" (nudge left if `mario_x` hasn't moved in 90
frames) is shared identically by all three, purely so runs get past the
pipe that ended the single-jump recording above and reach more of the
level — not steering, no circuit involved.

**Result: B dies at frame 106 with zero jumps — the exact same frame a
"never jump" agent dies at.** At the same `g` the real network runs at, the
shuffle never gets DNp01 over threshold in time. This is the section-5
question answered directly: **the real wiring's specific structure is
what's doing the work here, not just "sparse E/I-balanced RNN of the right
size."** (Caveat, checked and worth stating: the shuffle's spectral radius
at g=1 is 0.267 vs. the real network's 0.821 — cranking the shuffle's own g
up to 4+ does let it survive and fire, but at 4 jumps in the first 300
frames versus A's 2, i.e. trigger-happy rather than selective, and it
hasn't been run against Diagnostic 4. The controlled, apples-to-apples
comparison — same g the real circuit actually uses — is the one that
matters here, and it favors the real wiring outright.)

**A vs. C: not the same press trace.** Tuned `c=0.75` to match A's 2 jumps
over 4000 frames. First 404 frames identical (both catch the first,
obvious near-collision the same way), then diverge — 50 of 4000 frames
differ overall. So the circuit is doing something a bare threshold on the
instantaneous stimulus doesn't, at least on the second encounter, though the
two agree completely on the "obvious" case. This is a real but modest
difference, reported plainly rather than rounded up to "clearly different"
or down to "basically the same."

**`corr(LPLC2_mean, theta) = 0.88`** on the live run (below the ~0.95 line
that would mean the population is just a smooth function of the
instantaneous stimulus). `corr(LC4_mean, theta) = 0.50`, weaker still, as
expected for a unit tuned to angular *velocity* rather than angle itself.
Neither is at the ceiling, so the recurrence is contributing something
beyond pass-through, but this is a correlation, not proof of computation —
stated as what it is.

## Files

- `circuit.py` — body-level extraction, signs, weight matrix (`build()` for
  the original 315-neuron core, `build_expanded(N)` for section 1b).
- `expand_subgraph.py` — the sign-agnostic threshold expansion.
- `query_input_pools.py` — the investigative full-presynaptic-population
  queries (DNp01/LPLC2/LC4) that motivated section 1b.
- `dynamics.py` — the leaky-integrator rate model, `HybridState` (the DNp01
  spiking fallback), and `AdaptiveHybridState` (the leak/adaptation
  experiment, not adopted — see Diagnostic 4).
- `sensory.py` — synthetic-looming stimuli + hemisphere masks, no matplotlib
  dependency (used by `tune.py`, `run_mario.py`, and `diag4.py`). Includes
  `theta_multi_approach` (single-hemisphere, clean gaps) and
  `sustained_bilateral_trace` (overlapping, both hemispheres — the one that
  actually reproduces the saturation bug).
- `tune.py` — the three original section-3 diagnostics (single ramp from
  rest), g-sweep, plotting.
- `diag4.py` — Diagnostic 4 (sustained input), run against the deployed
  `HybridState` system. `python diag4.py --g 3.5` reproduces the bug;
  `python diag4.py --sweep` searches for a passing g.
- `adapt_sweep.py` — grid search over `(g, alpha_a, beta)` for
  `AdaptiveHybridState`, checking whether adaptation was the fix instead of
  a lower g. It wasn't — see Diagnostic 4.
- `compare_controllers.py` — the section-5 shuffled-connectome control plus
  a tuned-threshold baseline, run live against SMB 1-1 and compared to the
  real circuit's button-press trace. `circuit.shuffle_edges` /
  `circuit.build_shuffled` live in `circuit.py`.
- `run_mario.py` — RAM reading, sensory drive, hybrid dynamics, overlay,
  video recording. Run under `.venv`.
- `load_cached.py` — quiet re-load of the cached expanded circuit.
