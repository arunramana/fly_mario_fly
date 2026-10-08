# SPEC: which wiring feature carries the E1 jump advantage (written 2026-10-07, before any episode of the new arms ran)

Context: E1 at n = 50 (docs/SPEC_e1_n50.md, docs/RESULTS_e1_n50.md): real 46/50 vs class shuffle 31/50, seeds 3700-3749, gate on.
This sprint adds two CONTROL arms that rewire only part of the network, and pre-registers a re-analysis of the existing data.
No change to the brain, the stimulus layer or the calibration. Nothing is tuned on outcomes.

## 1. The escape-pathway set P (network hash 3848f3e70b2051ef, 16,464 neurons)
Edge criterion (stated once): "an edge a -> b exists" means a non-zero entry W[b, a] in the built weight matrix (an edge whose
source has unknown transmitter has sign 0 and weight 0, so it is not an edge for this definition).
P = LC4 + LPLC2 + GF (DNp01, both sides) + TTMn + every neuron X with an edge from some LC4/LPLC2 neuron into X AND an edge from X
into some GF/TTMn neuron (one intermediate: LC4/LPLC2 -> X -> GF/TTMn). X may itself be an LC4/LPLC2 neuron (lateral relay);
direct LC4/LPLC2 -> GF/TTMn edges (302 of them) are inside P through their endpoints.
Computed by `BuiltNetwork.path_set()` on the real network (a twin never redefines P). Counts:

| quantity | count |
|---|---|
| LC4 | 126 |
| LPLC2 | 185 |
| GF (DNp01) | 2 |
| TTMn | 2 |
| core (LC4+LPLC2+GF+TTMn) | 315 |
| neurons meeting the X criterion | 431 (of which 304 are core neurons) |
| X outside the core | 127 |
| **|P|** | **442** |
| built edges (rows of the edge list, incl. sign-0 sources) | 637,176 |
| non-zero W entries | 612,566 |
| edges among P (both endpoints in P) | 13,291 (all non-zero) |
| edges not among P | 623,885 (non-zero: 599,275) |

X outside the core by cell type (127 neurons, 59 types): AMMC-A1 6, SAD064 6, PVLP123 6, (no type) 6, PVLP122 5, SAD023 5, PVLP151 4,
CB3513 4, CL323 4, AVLP452 4, PVLP021 3, PVLP024 3; two each: PVLP010, DNpe042, DNp11, DNp02, LHAD1g1, DNp06, GNG300, DNp103, DNg40, DNp70,
AVLP396, CB1280, SAD013, PVLP022, LoVP85, CB2664, CB3544, PVLP100, PVLP026, CB1498, AVLP094, CB1638, SAD049, SAD011; one each: PS306,
WED116, IB114, AVLP542, PLP060, PVLP094, AVLP429, OCG06, CB4179, PVLP011, CB1932, PVLP046, CL128a, WED125, CB4102, CB2940, PVLP027,
PVLP018, WED109, PVLP124, PVLP015.

## 2. Arms (control only; same pattern as lesion_gf)
Both use the class-shuffle machinery (`BuiltNetwork._class_permuted_post`): the post column of the chosen edge subset is permuted only
among subset edges whose post neuron is in the same tier group; pre, synapse count, hence sign and out-degree, are untouched; the
identical normalisation then rebuilds W. With the whole edge list as subset it is exactly `class`.
- `path_kept`: edges among P exactly as real; every other edge class-shuffled. Note: the permuted outside edges can by chance land
  on a pair with both ends in P; measured +268..+297 such extra P-P edges on shuffle seeds 1-3 (about 2% of 13,291). Reported, not removed.
- `path_shuffled`: ONLY the 13,291 edges among P are class-shuffled (among themselves, inside P); everything else exactly as real.
  The P-P edge count is exactly preserved.
- Shuffle seed `1 + i` for seed index i (as `shuffled_class`): 50 distinct rewirings per arm, hash-confirmed by tests (shuffle seeds 1..50).
- Calibration fixed (the existing one); noise seeds 3700-3749, paired with the existing real and class arms, which are NOT re-run.
- Reachable only through `python -m brain.e1 --arms path_kept path_shuffled` / `run_eval`; not selectable from the tool Run/play path.
- Shared-memory pool: both arms' variants are built once in the parent. One variant is 12.06 MB, so 100 fit under the 1536 MB cap
  (1.2 GB); if more variants are requested in one invocation (e.g. together with `shuffled_class`), the ones past the cap are built
  privately per worker (results identical, only slower).

## 3. Reported per arm (path_kept, path_shuffled; real and class for reference)
Survived k/50; Wilson 95% CI; Fisher exact two-sided p vs real and vs class; Newcombe hybrid-score (method 10) 95% CI of the difference
vs real and vs class (as in SPEC_e1_n50); outcome counts (passed/stomped/died/timeout); distinct trajectories (same tuple definition as
SPEC_e1_n50); A-run length histogram (bins 1, 2, 3-5, 6-10, 11+); GF spike-to-contact lead (contact frame minus first GF frame).

## 4. Pre-registered readings (verbatim)
"path-kept ~ real AND path-shuffled ~ class -> the advantage is local to the escape pathway. The reverse -> it lies outside the pathway.
Both in between -> distributed. ~ means the 95% CI of the difference includes 0."

Rule for the cases that sentence does not cover, fixed now. For each new arm A compute D_real = A - real and D_class = A - class (survival
proportions, Newcombe 95% CI). Status of A:
- R ("indistinguishable from real only"): CI(D_real) includes 0, CI(D_class) excludes 0.
- C ("indistinguishable from class only"): CI(D_class) includes 0, CI(D_real) excludes 0.
- B ("both"): both CIs include 0 (A cannot be told from either end; uninformative for that arm).
- N ("neither"): both CIs exclude 0.
Mapping of (status of path_kept, status of path_shuffled):
- (R, C) -> **local to the escape pathway**.
- (C, R) -> **lies outside the pathway**.
- (N or B, N or B) with both point estimates strictly between class and real and at least one status N -> **distributed**.
- (R, R) -> **non-additive/redundant** (shuffling either part alone leaves the advantage, shuffling everything removes it); no location claimed.
- (C, C) -> **conjunctive** (damaging either part alone removes it); no location claimed.
- N with a point estimate outside [class, real] (better than real or worse than class) -> **anomalous**, reported as is, no reading.
- Everything else, including (B, B) and any pattern with one B and the other R, C or N -> **uninformative (CI includes 0 against both
  for at least one arm)**; the observed pattern is reported but no location is claimed.
Supplementary, not used for classification: fraction of the advantage retained, f = (A - class)/(real - class), point estimate only.

## 5. Re-analysis of the existing n = 50 data (no new runs; audit/p23_e1_n50.json)
Unit = TRAJECTORY (the tuple of SPEC_e1_n50, section 3), because identical trajectories are not independent evidence.
- Effective n: number of distinct trajectories per arm, and Kish n_eff = (sum m)^2 / sum m^2 over trajectory multiplicities m.
- Test 1 (primary): trajectory-level permutation test. Collapse each arm to its distinct trajectories, each labelled survived or not (if
  one trajectory carried both outcomes, that is reported and it counts as two units, one per outcome).
  Statistic: proportion of surviving trajectories in real minus class. Pool the distinct trajectories of both arms (a trajectory
  present in both arms stays once per arm), permute arm labels 100,000 times (numpy default_rng seed 20261007), two-sided p.
- Test 2 (CI): cluster bootstrap, clusters = trajectories within arm, resampled with replacement keeping their episode multiplicities,
  10,000 resamples (seed 20261007), statistic = episode-level survival(real) - survival(class), percentile 95% CI; also reported for
  the trajectory-weighted statistic. Compared against the naive episode-level Newcombe CI of SPEC_e1_n50.
- Reading: the conclusion "fine wiring matters" is called robust to non-independence only if the permutation p < 0.05 AND the bootstrap
  CI excludes 0; otherwise the n = 50 result is reported as not robust at the trajectory level.
- Sensory vs motor decomposition (descriptive, no causal claim; Mann-Whitney U two-sided for continuous quantities, Fisher for
  proportions, no multiplicity correction, real vs class):
  - sensory side: fraction with GF fired, first-GF frame, distance and theta at the first GF spike, spike-to-contact lead.
  - motor side: A-run shape (share of runs of 6-10 frames vs taps <= 2 vs 11+), number of A runs, A onset delay (first A frame
    minus first GF frame) when both exist.
