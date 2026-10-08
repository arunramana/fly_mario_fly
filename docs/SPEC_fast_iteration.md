# SPEC: fast iteration, sprint part 1

Goal: make the routine experiment loop cheaper without changing any number it reports. Three steps, each timed on the same batch.

## The fixed batch ("240-episode revalidation")
Seeds 9600-9619 (n = 20 per arm, not an eval seed range), `--workers 8` (brain/workers.py WorkerPool), idle machine, timed once per step,
run by `scripts/bench_batch.py` (one `run_eval` per experiment, sequential, each with its own pool):

| experiment | arms | episodes |
|---|---|---|
| E1 (brain.e1) | real, shuffled, shuffled_class, lesion_gf | 80 |
| E2a (brain.e2a) | real, shuffled, shuffled_class, real_no_obstacle | 80 |
| B11 (brain.baseline) | real, shuffled, shuffled_class | 60 |
| E0 (brain.goal_eval) | real | 20 |

Total 240. When a step removes arms, only the remaining arms are run (measured). The 240-equivalent time is then an ESTIMATE:
per experiment, measured wall seconds per simulated frame (wall / sum of episode frames) times the frames of the removed arms taken
from the baseline run, added to the measured wall. Measured vs estimated is labelled in every table. The script also stores a
digest of every episode result so a later step can be checked to give identical results on the arms it still runs.

## Step 1: degree-shuffle arm out of routine runs
`shuffled` (degree-preserving) has been 0/20 on every experiment: a settled control. Routine default arms exclude it in every
harness CLI (e1, e2a, baseline, goal_eval, dose_response, brain.evaluation). `--with-degree-shuffle` (alias of intent `--release`)
puts it back; an explicit `--arms` is always honoured. It must be re-run: at the release boundary, and after any change to the
stimulus layer (brain/perception.py, brain/obstacles.py, the mechanisms' encoding), the network hash, or the calibration.
The class-preserving `shuffled_class` arm stays in the routine defaults. Saved evals that contain `shuffled` still display
(tool/ui/tabs/results.py tolerates its absence in the criterion line).

## Step 2: end episodes when the verdict is final
Audit of the existing stops (no frame cap adopted anywhere):
* E1: stops at death or at resolved + E1_GRACE_FRAMES (60). That is exactly the verdict definition (survived = alive 60 frames
  after resolved; death earlier = not survived), so it is already a decided-state stop. No earlier exact stop exists: a death inside
  the 60 grace frames flips the verdict, and the reported fields (frames, max_x, ttmn_max_hz) include them.
* E2a: stops at clear (x > 479), death, or stuck (300 frames without a new max x). Decided-state already.
* B11: stops at flag, death, stuck (declared invented convention) or timeout 3000. A stuck Mario can still change goombas_jumped or
  collect a power-up, so there is no further exact stop; the declared stuck rule is the stop.
Test: tests/test_fast_iteration.py checks an E1 episode ends at death or resolved + 60, and that the same episode run with a larger
max_frames is identical (the stop is the harness's, not the cap's).

## Step 3: prune populations that cannot matter
Exactness argument: neurons with no directed path to any neuron the run reads or stimulates (the outputs, LC4, LPLC2, LC10a) cannot
influence it. Dropping them changes nothing if (a) the kept rows hold no non-zeros in dropped columns (true by the ancestor
definition, asserted in tests) and (b) the noise is drawn for the full population and sliced (fallback (a) of the brief: a smaller draw
would shift the generator). Opt-in `--pruned` on e1 / e2a / baseline (`pruned=True`, `BrainPolicy(pruned=True)`, brain/pruned.py);
E0/E3 and every other path are unchanged; the full network stays the default. The pruned network is a VIEW: its `build_hash()` is
the full network's hash, the committed network and calibration hashes are unchanged.

Result: ORN, GRN_head, THERMO, KC, MBON, DAN are NOT inert. At rest under membrane noise they sit at 0.006-0.0075 Hz (phi(noise) > 0, not
zero), and 81,986 of their edges land on kept rows (they feed the outputs through KC -> MBON -> DN and the path-union construction
kept every neuron because it lies on a path to an output). Force-dropping those six populations (7,433 neurons, noise still drawn
full) changes the output rates and GF membrane (max abs diff 0.0047 on a 40-frame synthetic stimulus): not allowed, not adopted.
What IS exactly prunable is only the neurons with no path to a read population: 444 of 16,464 neurons (2.7%), W non-zeros
612,566 -> 588,933 (-3.9%). That prune is bit-identical: 120/120 episodes (E1, E2a, B11 x real, shuffled_class x 20 seeds
9600-9619), every frame's telemetry row and the final result hashed, full vs pruned (`scripts/verify_pruned.py`); and the 180-episode timed
batch digests equal the unpruned ones. It buys nothing measurable: 0.855 vs 0.871 ms per network step (best of 8 interleaved blocks),
batch wall 1147 s (unpruned) vs 1207 s (pruned), inside the run-to-run noise; the full-population noise draw (RNG 14%) is still paid.
So `--pruned` stays opt-in and off; routine runs do not use it.

## Timing (docs/SPEC_fast_iteration.md batch, 8 workers, seeds 9600-9619)
Machine caveat: the box throttles under sustained 8-worker load (single-process matvec probe 0.47 ms before a batch, 2.1-2.8 ms right after it;
the first baseline also ran on battery). Wall times therefore wander +-20% between identical runs (same code, same arms: 2178 s then 1796 s),
and per-frame cost is the only fair unit. Digests of all episodes were identical across every run for every arm they share.

| stage | episodes run | measured wall | 240-eq (estimated) | frames | wall*8/frames |
|---|---|---|---|---|---|
| baseline, run 1 (battery) | 240 | 2178 s | - | 73,136 | 0.238 |
| baseline, run 2 (AC) | 240 | 1796 s | - | 73,136 | 0.196 |
| after step 1 (no degree shuffle) | 180 | 1147 s | 1672 s | 50,130 | 0.183 |
| after step 2 (no change, stops already exact) | 180 | = step 1 | 1672 s | 50,130 | - |
| after step 3 (`--pruned`, not adopted) | 180 | 1207 s | 1768 s | 50,130 | 0.193 |
240-eq = measured wall + (the removed arm's frames from the baseline) x (this stage's wall per frame, per experiment). Step 1 removes
23,006 of 73,136 simulated frames (31.5%) by construction.

## Read-only side note: substeps 3 and 5 vs the disc calibration (scratch, committed calibration untouched, gf_threshold unchanged)
GF first-spike angle (deg) at l/v 10 / 20 / 40 / 80 ms, noise seeds 7000-7002 (3 seeds), rest = 1500 frames no stimulus.
* substeps 10 (committed): 47.2 / 47.2 / 40.6-47.2 / 40.6-43.6; rest 0 GF spikes.
* substeps 5: 116.1 / 68.9 / 47.2-56.2 / 47.2; rest 0 GF spikes (the fast discs fire much later: alpha=0.3 per substep integrates less per frame).
* substeps 3: 116.1 / 68.9 / 56.2 / 47.2-56.2; rest 0 GF spikes, max TTMn 0.0186 vs 0.0157. Fewer substeps means a recalibration of g / thresholds, not a free speed-up.
