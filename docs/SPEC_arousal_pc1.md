# SPEC: arousal slider (pC1) -- a steady drive from the courtship/arousal-state population

**Status: decisions made on review (section 8); implemented opt-in, arousal 0 = goldens
unchanged.** Numbers below come
from scratch connectome queries and an isolated-network probe (scripts kept
outside the repo); nothing was run through the game. The decisions taken
are in section 8.

## 1. What and why

pC1 is a male-specific cluster of central-brain neurons (annotated `fruDsx`: dsx_high 56,
coexpress_high 49, coexpress_low 39, dsx_low 6, none 6) that carries the fly's arousal /
courtship state (the role is from the literature, not something this project measured). The slider adds a
*state* to the fly, like `hunger_override`: a steady drive into the real pC1
population, which reaches the circuits through the real wiring. It never
decides or forces an action (CLAUDE.md invariant 8): it changes what the
circuits are being pushed by, and the circuits' own thresholds decide what
happens. Like every other placed current it is a flagged scalar (invariant 3);
the connectome sets *where* the drive goes and *how it is divided*, the one
scalar sets *how hard*.

## 2. Which neurons (MaleCNS v1.0, `type` starts with `pC1`)

- **156 neurons, 49 types, 78 per hemisphere** (`superclass` = `cb_intrinsic`,
  `class` empty). 126 `male-specific`, 22 `potentially male-specific`, 8
  `sexually dimorphic`.
- **All 156 are cholinergic** (`predicted_nt` and `consensus_nt` =
  acetylcholine), so under the circuit code's Dale's-law map
  (`fly/connectome/circuit.py: NT_SIGN`) every pC1 output is excitatory
  (sign +1).
- Families (neurons): pC1_1 9, pC1_2 9, pC1_3 8, pC1_4 8, pC1_5 6, pC1_6 8,
  pC1_7 8, pC1_8 6, pC1_9 6, pC1_10 13, pC1_11 4, pC1_12 6, pC1_13 8,
  pC1_14 8, pC1_15 7, pC1_16 13, pC1_17 8, pC1_18 6, pC1_19 7, pC1x_ 8.
  Sub-letters (a, b, c, d) and the two ambiguous labels (`pC1_2a/2b`) are
  separate `type` values; all 49 are listed with body IDs in the appendix.
- Nothing in this project's circuits contains a pC1 neuron today.

## 3. Downstream targets (streamed from the weights file, min-confidence 0.5)

- pC1 makes **367,170 edges = 793,019 synapses onto 287,123 distinct neurons.**
- **66.9% of those synapses (530,215) land on untyped neurons** -- 281,220 of
  the 287,123 targets (98% of them), with no `type` (and, in aggregate, no `superclass`;
  most are small unproofread fragments). Only **33.1% (262,804 synapses)** land
  on ~5,900 typed neurons. Consequence: any spec built on "typed" targets sees
  a third of pC1's output; the rest is invisible to us and its function is
  unknown. Onto the circuits we actually simulate the loss is small (below),
  because every neuron in our circuits is typed by construction.
- Typed targets by superclass (synapses): cb_intrinsic 245,686; descending
  16,301 (2.1% of all pC1 output); visual_centrifugal 1,060; ascending 602;
  visual_projection 288; ol_intrinsic 15; cb_endocrine 6.
- Largest typed targets (synapses / neurons): pC1_18b 4,516 / 4 (recurrent
  within pC1); AVLP749m 3,752 / 12; SIP104m 3,722 / 8; SIP106m 3,541 / 2;
  mAL_m8 3,523 / 16; SIP122m 3,173 / 8; AVLP717m 3,118 / 2; SIP121m 3,068 / 6;
  aIPg5 2,909 / 6; SIP141m 2,825 / 6; ... pIP10 1,941 / 2 (the descending
  courtship neuron), oviIN 1,881 / 2.

### 3.1 Direct pC1 -> the neurons in our circuits

| target | direct synapses | neurons | which pC1 types (synapses) | side |
|---|---|---|---|---|
| DNp09 (speed) | 104 | 2 | pC1_7a 40, pC1_7b 33, pC1_11b 13, pC1_16b 6 | R 102, L 2 |
| DNa01 (steering) | 115 | 2 | pC1_16a 70, pC1_15b 15, pC1_16b 12, pC1_15c 10 | L 47, R 68 |
| DNa02 (steering) | 64 | 2 | pC1_15c 27, pC1_17a 16, pC1_10c 6, pC1_14a 6 | L 18, R 46 |
| pIP1 (in the DNp02 subgraph) | 32 | 2 | pC1_11a 8, pC1_13b 4, pC1_2a 4 | L 20, R 12 |
| MDN (backing up) | 13 | 4 | pC1_13b 5, pC1_13a 3, pC1_14b 2 | L 7, R 6 |
| DNp01 (Giant Fiber), DNp02, TTMn, DLMn, LC4, LPLC2 | **0** | 0 | - | - |

11,235 direct synapses reach 212 neurons across the six simulated subgraphs
(jump 58, steering 122, speed 16, MDN 28, DNp02 4, takeoff 0); **0 of them are
untyped.** The DNp09 wiring is strongly lateralised (right side), so the two
hemispheres must stay separate (invariant 5).

### 3.2 Two hops (pC1 -> X -> circuit neuron), untyped share

Magnitude, in fraction-of-total-input units, unsigned: DNp01 0.0017, DNp02
0.0006, TTMn 0.0000, DLMn 0.0059 (via DNa08), DNp09 0.024, DNa01 0.0067, DNa02
0.0079, MDN 0.028, pIP1 0.017. **Only 2.0% of the two-hop flow into our
circuits passes through untyped intermediates** (DNp09 1.0%, DNa01 2.8%, MDN
0.8%, pIP1 0.0%, DNp01 0.0%). The strongest DNp01 route is PVLP010 (0.0008).
The Giant Fiber gets pC1 input only indirectly and weakly; the two-hop analysis
above used unsigned magnitudes, the probe below uses Dale-signed ones.

## 4. How the slider injects a steady drive

- **Slider** `arousal` in [0, 1] (Character tab, next to hunger; see section 7).
  The pC1 population's activity is `h_pC1 = arousal * arousal_max_h`, with
  `arousal_max_h` a flagged scalar (invented, **default 10**, range 0-50,
  editable in the Circuits tab). `two_hop` (default off) and `arousal` itself are
  the other two typed fields of `ArousalParams`.
- **Injection.** Each simulated circuit `N` gets, on every substep, an extra
  input `I_N += g_N * w_pC1(N) * h_pC1`, where `w_pC1(N)` is a fixed vector over
  that circuit's neurons: the direct pC1 -> j synapse count plus the two-hop
  paths `sum_X (pC1->X share) * (X->j)`, the latter multiplied by the sign of X
  (Dale's law, from `consensus_nt`), divided by a normaliser (below). It is
  computed once in a single streaming pass over the weights file (~80 s) and
  cached under `../data/derived/`, exactly like
  `fly/circuits/mbon_pathway_weights.py`. It is a constant current between
  slider changes; all dynamics (recurrence, thresholds, spikes) stay in the
  existing `Network.step`.
- **Normaliser -- decided: the target's total input.** Two conventions were probed:
  1. *Fraction of the target's total input synapses* (recommended): the
     physiological share of that neuron's input coming from pC1.
  2. *The circuit's own in-subgraph normaliser* (what `W` uses:
     `circuit.build_weight_matrix` divides by input from within the subgraph).
     This inflates neurons with little in-subgraph input: direct weights reach
     28 (MDN), 5.1 (DNp09), 4.4 (steering), so the slider saturates the circuits
     and even *silences* DNp09 (section 5).
- **Two-hop is a separate toggle, default off** (`ArousalParams.two_hop`): the
  default is direct synapses only. Both weight vectors are computed and cached
  in the same pass, so flipping the toggle needs no recompute.
- pC1 -> the mushroom body, the retina, and everything outside the six
  subgraphs is out of scope; so is pC1 -> untyped neurons (nothing to project onto).
- **Not** a per-frame decision: the slider is a project/Character setting. It is
  live: while a run is playing, moving the slider updates a shared value the
  policy reads each frame (the per-frame level is recorded in the `arousal`
  telemetry column, so a run with live changes is still fully described by its
  telemetry).

## 5. Expected and measured effects (isolated-network probe, not full runs)

Method: each circuit alone, from rest, 600 substeps (60 frames), `h_pC1` from 0 to
50 in steps of 12.5 (`arousal` 0, 0.25, ..., 1), mean over the last 100
substeps; steering has `home_bias` on the R team, speed has `walk_drive` on
DNp09, the jump circuit is shown with no stimulus and with a constant
sub-threshold looming input of 0.15 on the R detectors. Thresholds: DNp09 press
B 0.5, MDN backup 1.0, TTMn press 3.0, DNp01 spike 0.5.

**Expected** from the wiring: direct pC1 input goes only to DNp09 (R), DNa01/02
(both sides), MDN and pIP1, so steering and speed should move, backing up
should barely move, and the Giant Fiber (no direct pC1 input) should be
unaffected or weakly changed via two-hop paths.

**Measured, total-input units (recommended), real connectome, direct only /
direct + signed two-hop:**

| quantity (arousal 0 -> 0.5 -> 1) | direct only | direct + two-hop |
|---|---|---|
| steering R team | 0.995 -> 1.139 -> 1.284 | 0.995 -> 1.198 -> 1.402 |
| steering L team | 0.000 -> 0.098 -> 0.201 | 0.000 -> 0.158 -> 0.320 |
| DNa01 / DNa02 mean | 0.497/0.498 -> 0.749/0.736 | -> 0.799/0.922 |
| DNp09 (walk drive 1.0, B threshold 0.5) | 0.943 -> 1.209 -> 1.501 | 0.943 -> 1.088 -> 1.252 |
| MDN (backup threshold 1.0) | 0 -> 0.011 -> 0.022 | 0 -> 0.002 -> 0.003 |
| DNp02 spikes, its TTMn (no looming) | 0, 0 (no latch triggered) | 0, 0 |
| Giant Fiber, no stimulus: spikes / TTMn | 0 / 0 | 0 / 0 |
| Giant Fiber membrane, looming 0.15 | 0.195 -> 0.100 -> 0.015 | 0.195 -> 0.020 -> 0.000 |

Reading: arousal raises both steering teams and DNp09 modestly and never
approaches the MDN threshold; it **lowers** the Giant Fiber's response to a
sub-threshold looming input (0.195 -> 0.000, spikes stay 0 in both), i.e. an
aroused fly is *harder* to startle -- the direction expected for a
courtship state, and it comes out of the wiring rather than being put in.
DNp02 is not pushed into its pIP1 latch (see the DNp02 investigation), because
pC1's input onto pIP1 is small.

**Measured, circuit-normaliser units (not recommended):** steering R/L
0.995/0.000 -> 2.242/1.099 (direct) and 2.821/1.853 (direct+two-hop); DNp09 is
driven to **0.000** at arousal >= 0.5 (below the B threshold, walk stops); MDN
reaches 1.222 (over its 1.0 threshold) with direct input alone; the GF
membrane under looming goes to 0.000 at arousal 0.5. These are the saturating
effects the normaliser choice causes.

## 6. Shuffled control (invariant 6)

Control = the same probe with (a) the circuits' weight matrices rewired
(`build_shuffled`, seeds 1 and 2: same neurons, degrees and signs) and (b)
the pC1 weight vector dealt to random neurons of that circuit (same values,
random targets, same seed). The connectome-specific pattern must not appear.

| total-input units, arousal 1 | real | shuffled 1 | shuffled 2 |
|---|---|---|---|
| steering R / L team | 1.402 / 0.320 | 1.338 / 0.038 | 2.181 / 1.080 |
| DNa01 / DNa02 | 0.799 / 0.922 | 0.793 / 0.583 | 0.681 / 2.580 |
| DNp09 | 1.252 | 1.049 | 1.538 |
| MDN (thr 1.0) | 0.003 | **2.583** | 0.093 |
| GF membrane, looming 0.15 | 0.000 (suppressed) | 0.172 (raised) | 0.042 (lower) |
| DNp02 TTMn | 0 | 0.034 | 0.035 |

The shuffled networks disagree with each other and with the real one (MDN
over threshold in one, GF membrane *raised* in one, L team blowing up in
another): the real wiring's signature is a consistent, modest steering/speed
rise with GF suppression and MDN silent; shuffling produces different,
arbitrary effects. In circuit-normaliser units the shuffles go much further
(MDN 21.8 and the GF spiking with no stimulus in shuffled 1; DNp09 25.0, its ceiling, in shuffled 2).

## 7. Tabs, telemetry, files

- **Character tab:** the `arousal` slider (0-1) beside hunger override; read-only
  for `legacy`. Moving it above 0 switches the module on. **Circuits tab:** an
  "Arousal (pC1)" module toggle (default off) with `arousal`, `arousal_max_h` and
  `two_hop` editable while on; same toggle/param-editor pattern as MotorDirect. **Goal tab:** unchanged.
  **Player:** Data panel gets an "Arousal (pC1)" group; the Brain overlay lights
  the 156 pC1 somas at `arousal` level (a new population, like MBON); the Config
  panel shows the module via the existing off/on diff. **Learning tab, run
  store, Circuits card grid:** unchanged (the module and slider are in the
  run's config snapshot).
- **Telemetry (columns exist only when the module is on, goldens unchanged when
  off):** `arousal`, `pc1_h`, and per-pathway injected drive
  `pc1_drive_steer_r`, `pc1_drive_steer_l`, `pc1_drive_dnp09`,
  `pc1_drive_gf` (the last should stay ~0 unless two-hop is on).
- **Code (for the implementation sprint, not now):** `config/params.py`
  (`ArousalParams`, +1 scalar), `bridge/controller_modules.py`
  (`ArousalModule`, kind "circuit"), `fly/circuits/pc1_weights.py` (cached
  streaming pass), `bridge/full_policy.py` (inject in the six network steps),
  `docs/SCALARS.md`/`CLAUDE.md` count, tests for off-is-identical, the weights
  loader, the slider, and the shuffled control.

## 8. Decisions (taken on review) and remaining caveats

1. **Normaliser:** the target's total input synapses. (The circuit's own
   in-subgraph normaliser saturates the circuits; not used.)
2. **Two-hop:** off by default, its own toggle (`two_hop`). Direct synapses only
   is the default drive.
3. **One slider**, not per-family.
4. **`arousal_max_h` default 10**, editable (range 0-50). With it at 10 the
   direct-only effects in section 5 (measured at 50) are about one fifth as
   large; section 9 gives the default-scale numbers.
5. **Remaining caveats:** 67% of pC1's output is invisible (untyped targets); the
   probe is isolated networks with constant baselines, no noise, steady state
   only; interactions with MotorDirect, MBON readout, the refractory terms and
   habituation are untested; a full-run check is a separate step, with the
   shuffled control shipping alongside (section 9 is that control at the probe level).

## 9. Implementation and the shuffle spread (probe at the default scale)

Implemented as `ArousalParams` / `ArousalModule` (kind "circuit"),
`fly/circuits/pc1_arousal_weights.py` (cached at `../data/derived/pc1_arousal_weights.npz`)
and the injection in `FullPolicy`. **Arousal 0 injects nothing: a run with the module on and
arousal 0 has telemetry identical to a run without it** (tested). Slider live-wiring: the Character
tab's Arousal slider writes `config.modules.arousal.arousal` (switching the module on above 0) and,
during a run, a shared value the policy reads every frame. Telemetry columns (module on only):
`arousal`, `pc1_h`, `pc1_drive_steer_r`, `pc1_drive_steer_l`, `pc1_drive_dnp09`, `pc1_drive_gf`.

Shuffle spread: the section-5 probe (total-input units, isolated networks, 600 substeps) repeated for
the real connectome and **8 shuffles** (seeds 1-8: rewired circuits, and the pC1 weight vector dealt to
random neurons with the same seed). Values are the change from arousal 0 (`h_pC1` 0 -> 10 is the default
arousal 1; 0 -> 50 is the network clip). "Range" is the min..max over the 8 shuffles.

Direct only (the default), `h_pC1` = 10 / 50:

| change | real | shuffle range | real vs range |
|---|---|---|---|
| DNa01 | +0.047 / +0.252 | +0.002..+0.035 / +0.012..+0.178 | **above all 8** (z +3.4 / +3.6) |
| Giant Fiber membrane (looming 0.15) | -0.040 / -0.180 | -0.005..+0.080 / -0.022..+0.396 | **below all 8** (z -2.0 / -1.9) |
| MDN | +0.004 / +0.022 | +0.005..+0.558 / +0.024..+2.79 | below all 8 (tiny; shuffles are larger) |
| DNp09 | +0.095 / +0.558 | -0.018..+0.546 / -0.024..+2.73 | inside (z -0.1) |
| DNa02 | +0.047 / +0.239 | +0.002..+0.321 / +0.009..+1.61 | inside (z -0.1) |
| steering R - L | +0.021 / +0.088 | -0.035..+0.058 / -0.178..+0.288 | inside (z +0.4) |
| GF spikes | 0 / 0 | 0..0 / 0..0 | - |

With `two_hop` on the pattern is the same (DNa01 above all 8 at h=10 and 50, z +1.8/+1.9; GF
membrane below all 8, z -1.3/-3.4; MDN below all 8; DNp09, DNa02 and steering asymmetry inside).

**Does the real effect fall outside the spread?** For three quantities, yes: DNa01 rises more than
in any shuffle, the Giant Fiber's looming response falls more than in any shuffle, and MDN is
essentially unmoved where every shuffle moves it. For DNp09, DNa02 and the R - L steering asymmetry the
real value sits inside the shuffle spread, so **those effects are not evidence of connectome-specific
wiring** -- the same size of push appears with random targets. Caveats: with 8 shuffles a real value
lands outside the range by chance about 2 times in 9 (22%) on any one quantity, so the z-scores and the
fact that the same three quantities are outside at both levels and both weight sets matter more than a
single "outside"; isolated networks, no noise, steady state only.

## Appendix: pC1 body IDs (156 neurons, 49 types)

| subtype | L body IDs | R body IDs |
|---|---|---|
| pC1_10a | 18276 | 517337 |
| pC1_10b | 26153, 517519 | 30699, 515977 |
| pC1_10c | 55136, 518589 | 17434, 17702 |
| pC1_10d | 20580 | 19968, 30546 |
| pC1_11a | 18990 | 13495 |
| pC1_11b | 514077 | 13655 |
| pC1_12a | 513650 | 512011 |
| pC1_12b | 13562, 17851 | 17089, 18554 |
| pC1_13a | 25204 | 19672 |
| pC1_13b | 21538, 23924 | 220200, 555746 |
| pC1_13c | 23787 | 555747 |
| pC1_14a | 23695, 44515, 55986 | 29214, 33553, 516522 |
| pC1_14b | 46570 | 25740 |
| pC1_15a | 108816 | 32437 |
| pC1_15b | 28972 | 25690 |
| pC1_15c | 18934, 180724 | 29388 |
| pC1_16a | 20751, 23789 | 23952, 59527, 67624 |
| pC1_16b | 26833, 32283, 513654, 535835 | 25746, 33041, 58786, 66610 |
| pC1_17a | 70815 | 22818, 23651 |
| pC1_17b | 23661, 31309, 41427 | 35202, 36545 |
| pC1_18a | 12448 | 532011 |
| pC1_18b | 87497, 518253 | 15035, 32788 |
| pC1_19 | 68624, 98113, 127881, 156865 | 79642, 125721, 170209 |
| pC1_1a | 15208, 20255, 519914, 524296 | 19085, 29280, 526918 |
| pC1_1b | 16262 | 26993 |
| pC1_2a | 17564, 524747 | 15329, 519297 |
| pC1_2a/2b | - | 17387 |
| pC1_2b | 18913 | 19705 |
| pC1_2c | 22093 | 20392 |
| pC1_3a | 19650 | 18974 |
| pC1_3b | 13266 | 514925 |
| pC1_3c | 18017, 19136 | 19894, 19948 |
| pC1_4a | 12442, 519518, 522419 | 20117, 20803, 23968 |
| pC1_4b | 17867 | 16719 |
| pC1_5a | 102224 | 32950 |
| pC1_5b | 70011, 557035 | 29143, 29483 |
| pC1_6a | 17098, 26543, 521453 | 20597, 21507, 528986 |
| pC1_6b | 517735 | 24623 |
| pC1_7a | 29043, 53355 | 25542, 71385 |
| pC1_7b | 513651, 513652 | 26746, 43592 |
| pC1_8a | 24727 | 25521 |
| pC1_8b | 513129 | 30391 |
| pC1_8c | 47325 | 41518 |
| pC1_9a | 15876, 555488 | 267996, 555751 |
| pC1_9b | 16364 | 25345 |
| pC1x_a | 521150 | 12366 |
| pC1x_b | 10217 | 512580 |
| pC1x_c | 12257 | 10666 |
| pC1x_d | 12893 | 13449 |
