# SPEC: fly_mario step 6 — the mushroom body

The only learning in this project. Three-factor plasticity (eligibility ×
dopamine × depression), no backprop anywhere, on real KC→MBON connectome
weights.

## 0. Numbers verified, not assumed — and they don't match the "Still open" note

The project's own running log has repeated "4,554 KC → 104 MBON" since
sprint 006's "Still open" list, evidently a remembered figure never
actually checked against this connectome file. Checked now: **4,064 real
Kenyon cells** (class=`Kenyon_Cell`; 15 subtypes, KCg-m/KCab-s/KCab-m
dominate), **97 real MBONs** (class=`MBON`, 37 numbered types), **354 real
dopaminergic neurons** (types prefixed `PAM`/`PPL`/`PPM`, the standard
real Drosophila DAN clusters — PAM canonically reward-associated, PPL1
canonically punishment/aversive-associated in the literature). These are
the numbers this build uses and asserts at load time. The discrepancy is
stated plainly, not quietly corrected away.

Connectivity, all real, all dense: **KC→MBON** 61,210 synapses, 4,063/4,064
KCs connect, all 97 MBONs receive input. **PAM/PPL/PPM→MBON** 3,195
synapses (348 DANs → all 97 MBONs) — dopamine reaching MBON dendrites
directly, the real tripartite-synapse site. **PAM/PPL/PPM→KC** 129,132
synapses (341 DANs → 4,063 KCs) — real, not used by this build's plasticity
rule (see section 4), noted for completeness.

**Checked whether MBONs connect to anything already in this project, so
"modulate the choices we already have" could use real wiring rather than
fabricated ones**: MBON→DNa02 (steering) is real — 250 synapses, 9 (pre,
post) pairs. MBON→MDN (backward-walking fallback) is real — 88 synapses,
21 pairs. **MBON→DNp01 and MBON→DNp02 (the escape arbitration) do not
exist** in this connectome. Same situation DNp04 was in for TTMn (008):
real, dense input on one side, nothing on the intended output. Handled the
same way — don't fabricate a synapse; use a hand-injected external current
where the real wiring doesn't reach, same category as `HOME_BIAS`/
`GAP_GAIN`/`WALK_DRIVE`/`MDN_DRIVE`, and say so.

## 1. KC layer — real recurrence, fabricated input, both stated plainly

**Input is fabricated, not real, and that's fine — the RANDOMNESS is the
biologically correct part, not the specific weights.** Real KCs sample a
small, effectively random combination of ~6 of ~150 real PN types; nothing
in this project's sensory abstractions (theta, odour, gap width, DNp09,
hunger) corresponds to a real PN identity, so there's no synapse table to
look up here regardless. A fixed (seeded, not a tunable scalar — no more a
"hand-set constant" than `shuffle_edges`'s seed is elsewhere in this
project), sparse random projection from a small sensory-state vector
(`theta` per side, `odor_l`/`odor_r`, `gap_width`, `dnp09_val`, hunger) onto
the 4,064 KCs, ~3 random sensory features per KC (mirroring real KCs' small
claw count), unweighted (binary claws, matching KCs' real role as
coincidence detectors, not weighted integrators).

**Sparsity is real and enforced structurally, not learned**: global
feedback inhibition (the real APL neuron) keeps ~5% of KCs active at once
in real flies. Not modeling APL as its own population — directly enforcing
the *result* (top-`KC_SPARSITY` by raw drive, rest zeroed) is the stated
simplification, same spirit as skipping the EPG ring in SPEC_steering.md.
`KC_SPARSITY` is one of this sprint's three new scalars.

## 2. KC→MBON — the one weight matrix that learns

Real edges (61,210), Dale's-law signs from `consensus_nt`, row-normalised
by each MBON's real total input — identical pipeline to every other
circuit in this project. This weight matrix, and only this one, is
modified by the plasticity rule. MBON activity is `W_kc_mbon.T @
kc_active` through the shared, unmodified leaky dynamics (`dynamics.step`,
no new gain — MBONs are a readout layer, not a recurrent amplifier, so
there's nothing here that needs its own calibrated `g`).

## 3. Reward and punishment — real DAN routing, no invented gain

Reward: `max(0, Δx)` per step — raw pixels of forward progress, unscaled.
No reward-scaling constant; that would be a fourth new scalar the budget
doesn't allow, and forward progress in pixels is already the honest,
natural unit. Punishment: a single fixed pulse on death, reusing
`dynamics.CLIP` (=50, already a defined project constant — not new)
rather than inventing a punishment magnitude.

**Both route through real anatomy, not a single undifferentiated
scalar**: reward broadcasts through real PAM→MBON weights (PAM is the
literature's reward cluster), punishment through real PPL(+PPM)→MBON
weights (PPL1 is the literature's punishment cluster; PPM's role is mixed
in the literature — lumped with PPL here as a stated judgement call, not a
verified split). Each MBON's actual dopamine exposure is therefore real
and MBON-specific, weighted by its own real DAN input pattern, with zero
extra hand-set parameters — the *spatial* structure comes entirely from
the connectome; only the *timing* (when a pulse fires, and its raw
magnitude) is computed from game state.

## 4. The rule — three-factor, depression-only, on real synapses only

Eligibility, per KC (not per synapse pair — the sparse KC code IS the
identity-carrying signal; gating by presynaptic activity alone matches the
standard real-MB coincidence-detection model, Aso/Rubin-style):

```
elig_i(t+1) = (1 - 1/TRACE_DECAY) * elig_i(t) + (1/TRACE_DECAY) * kc_active_i(t)
```

`TRACE_DECAY` (~60 frames, ~1s at 60Hz) is this sprint's second new
scalar. On any step with nonzero dopamine at MBON `j` (reward or
punishment, routed per section 3):

```
ΔW_kc_mbon[i,j] = -LEARNING_RATE * dopamine_j(t) * elig_i(t) * W_kc_mbon[i,j]
```

Multiplicative (proportional to the synapse's own current weight, so it
decays toward zero, never below, and never needs clipping) — applied ONLY
to (i,j) pairs where a real synapse exists, never creating new connectivity.
**Depression only, both directions**: `dopamine_j(t)` is a non-negative
magnitude regardless of whether it came from the reward or punishment
channel — this matches the real fly mechanism directly, where both
appetitive and aversive learning work by *depressing* the relevant
KC→MBON synapse, with the behavioural difference coming from *which*
MBON (approach-promoting or avoidance-promoting) gets depressed, not from
the synaptic sign of the change. `LEARNING_RATE` is the third new scalar.
**No backprop, no gradient, no target output — a local, causal, three-
factor rule at each real synapse.**

## 5. MBON → existing choices, real where real exists

- **Odour vs. home bias (steering)**: real MBON→DNa02 weights (250
  synapses) feed the aggregate MBON output directly into DNa02's existing
  R-hemisphere input, alongside `HOME_BIAS` and odour — a genuine learned
  modulation of an existing real pathway, no fabrication needed.
- **DNp01 vs. DNp02 (escape arbitration)**: no real MBON→DNp01/DNp02
  synapse exists. A small aggregate-MBON-derived external current is
  injected onto DNp02's own circuit instead (same category as
  `GAP_GAIN`/`HOME_BIAS` — a hand-placed bias standing in for a connection
  the connectome doesn't have), stated openly as a judgement call, not
  discovered wiring.

Nothing new to control in either case — both are additive terms on inputs
that already exist; the WTA/threshold-crossing decision logic itself is
untouched.

## 6. Training

500 episodes from an identical savestate (sprint 013's `_backup`/
`_restore` mechanism — no warm-up replay cost, every episode starts
identically). Reuse sprint 013's memoized circuit loading and headless
mode for throughput; frame_skip is available but not required — given
013's own finding that it changes behaviour chaotically, default to
frame_skip=1 for training unless throughput makes 500 episodes
impractical, and say which was used. Plot x-progress per episode as the
learning curve. **If it's flat, report it flat** — this project has three
sprints of precedent (odour never quite winning without hunger; DNp02
never reliably out-committing DNp01; frame-skip's chaotic sensitivity) for
treating a clean negative as a real result, not a bug to hide.

Record a before video (an untrained/early episode) and an after video (a
late, trained episode) — only worth two videos if there's something to
show; if the curve is flat, one representative video plus the flat curve
plot may say more than two near-identical videos would.

## 7. Scalar budget

Was 5 (`g`, `dnp01_spike_threshold`, `ttmn_press_threshold`,
`G_DNP02`, `DNP02_SPIKE_THRESHOLD`/`DNP02_ALPHA` counted as the pair from
SPEC_second_escape.md — see that spec's own accounting; that spec is not
in this repo, and `docs/RUNS.md` entry 012 is the surviving record of the
DNp02 work). This sprint adds
exactly three: `KC_SPARSITY`, `TRACE_DECAY`, `LEARNING_RATE`. **8 total.**
Flagged in the README, same as every prior addition — the budget is a
standing invariant, and it costs something every time it grows.

## 8. Explicitly out of scope

Compartment-specific eligibility (real MB has ~15 anatomically distinct
compartments with separate DAN input; this build uses one global
per-MBON dopamine level via section 3's PAM/PPL routing, not per-
compartment traces). Potentiation of any kind. Any change to circuit.py,
dynamics.py, run_mario.py, or the existing jump/steering/takeoff/speed/
MDN/DNp02 circuits' own internal wiring — the mushroom body reads from and
adds bias onto them, it does not rewire them.
