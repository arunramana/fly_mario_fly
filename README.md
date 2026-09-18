# fly_mario — the jump

A Goomba approaches Mario, the real fruit-fly escape circuit (Janelia
MaleCNS v1.0) fires, and TTMn's threshold-crossing presses A. See
`SPEC_jump.md` for the full design; this file states what came from the
connectome versus what was hand-set, per section 5.

`mario_jump.mp4` is the recorded deliverable: 582 frames (~9.7s), 9 jumps
triggered by the circuit while Mario runs SMB 1-1.

## What's hand-set

SPEC originally allowed exactly two: global gain `g` and a TTMn press
threshold. **There are now three**, and CLAUDE.md invariant 3 says to flag
that plainly rather than bury it:

| Scalar | Value | Why |
|---|---|---|
| `g` | 3.5 | Global recurrent gain. Chosen from the section-3 re-sweep: the largest g that still passes "decays to zero" and "no ringing" on the expanded, E/I-balanced network (stable up to ~g=3.8-4.0, unstable/oscillatory beyond). |
| `dnp01_spike_threshold` | 0.5 | **The DNp01 spiking fallback.** Section 3's third diagnostic ("sharp, late DNp01 rise") failed at every g we tried, in both the original 315-neuron network and the expanded 1255-neuron one — see below. Per your instruction, DNp01's two bodies are modeled as leaky integrate-and-fire units instead of plain ReLU rate units: accumulate, and once membrane potential crosses this threshold, fire one frame at fixed amplitude and reset. Chosen so the first spike lands late in a synthetic approach (frame 68 of 73, ~93% through) rather than firing on distant/background activity. |
| `ttmn_press_threshold` | 3.0 | TTMn activation to press A. Comfortably below the ~5-50 TTMn reaches after a DNp01 spike, comfortably above its ~0 baseline. |

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

## Video behavior, stated openly

Section 2 routes enemies **ahead of Mario to one hemisphere, behind to the
other**, symmetrically — SPEC doesn't say only "ahead" threats should be
able to trigger a jump, and the fly's compound eyes and bilateral GF circuit
have no such restriction either. In the recorded run, most jumps are
triggered by a Goomba genuinely visible and closing from ahead (e.g. frame
248 — a Goomba at d_px=117, clearly on screen), but a few (frames 53, 118,
313, 378) are triggered by enemies already passed / off the left edge,
because that side's hemisphere is wired identically. This is a faithful
consequence of the symmetric routing rule as specified, not a bug I patched
around — flagging it rather than quietly narrowing the routing to only
"ahead" threats, which would have been an unstated design change.

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

## Outstanding from SPEC section 5

**Shuffled-connectome control not yet built.** SPEC says to write it now,
not later; per your explicit priority this sprint ("don't let step 2 block
step 3... I want to see it jump"), it was deferred behind the recorded
video. Still owed: same neurons, same in/out degree distribution, same
signs, edges rewired at random, run through the same synthetic-ramp and
Mario harness, to check whether the real connectome's specific wiring
(beyond just being a sparse E/I-balanced RNN of the right size) is doing
anything the shuffle can't.

## Files

- `circuit.py` — body-level extraction, signs, weight matrix (`build()` for
  the original 315-neuron core, `build_expanded(N)` for section 1b).
- `expand_subgraph.py` — the sign-agnostic threshold expansion.
- `query_input_pools.py` — the investigative full-presynaptic-population
  queries (DNp01/LPLC2/LC4) that motivated section 1b.
- `dynamics.py` — the leaky-integrator rate model, plus `HybridState` (the
  DNp01 spiking fallback).
- `sensory.py` — synthetic-looming stimulus + hemisphere masks, no
  matplotlib dependency (used by both `tune.py` and `run_mario.py`).
- `tune.py` — the three section-3 diagnostics, g-sweep, plotting.
- `run_mario.py` — RAM reading, sensory drive, hybrid dynamics, overlay,
  video recording. Run under `.venv`.
- `load_cached.py` — quiet re-load of the cached expanded circuit.
