# SPEC: E1 real vs class-shuffled connectome at n = 50 (written 2026-10-07, before any episode ran)

## 1. Design
- Scene E1 ("jump the Goomba"), the current gated build (expansion gate, Step 7). Metric: survived the encounter (brain/e1.py).
- 50 fresh held-out seeds 3700-3749. No earlier set used them (searched docs/ and brain/: 3700-3749 appear only inside citation numbers).
- Arms: `real` and `shuffled_class` ONLY. The degree-preserving shuffle is a settled control (0/20 on every set, it never fires the GF) and is routinely dropped (docs/SPEC_fast_iteration.md); it is not run here.
- Class-shuffle rewirings: brain/e1.py `run_eval` derives the shuffle seed as `1 + i` for seed index i, and `BuiltNetwork.shuffled(seed, "class")` permutes the post column with `np.random.default_rng(seed)`. So there is a DIFFERENT class shuffle per seed: 50 distinct rewirings (shuffle seeds 1..50). Verified by hashing the 50 shuffled networks (audit/p23_hash.py, audit/p23_hash.json): 50 distinct hashes of 50. Seeds 1..20 are the same rewirings earlier E1 sets used; the noise seeds are new, and earlier sets are not pooled, so this does not matter for this test.
- Same noise seed (3700 + i) in both arms, as in the standard eval.
- Run executed once, 8 workers, by `audit/p23_run.py`. It builds exactly the jobs of `brain.e1.run_eval` (same `run_e1_episode`, same WorkerPool, same shuffle seeds) and differs only in `record_rows=True`, because the `python -m brain.e1` JSON carries no per-frame A presses and the trajectory definition below needs them. `record_rows` only reads state. Per-episode E1Result rows and the per-frame A trace are saved in audit/p23_e1_n50.json.
- Not pooled: the pre-gate sets (3200, 3300, 3400, 3500) are a different system (the expansion gate changed the input encoding). The single gated set 3600-3619 (real 19/20, class 12/20) is reported only as context, never added to these 50.

## 2. Pre-registered reading (verbatim)
"If real beats class with p < 0.05 (Fisher exact, two-sided, on survived counts), the fine wiring matters for the jump and the type-level-wiring-suffices conclusion is overturned for this experiment. If p >= 0.05, the result is no difference shown at n = 50, reported with the CI of the difference; claim type-level wiring does the work only if that interval is tight around zero."

"Tight around zero", defined now: the 95% Newcombe hybrid-score CI of (real - class) survival proportion lies entirely within +-0.20.
Justification: +-0.20 means a difference of up to 10 episodes in 50 is excluded. At n = 50 per arm and survival near 0.7 the CI half-width is about 0.18 whatever the true difference, so a bound of +-0.15 could be met only if survival were above about 0.8 and would make "tight" unreachable by construction. +-0.20 is a judgment, not a derived value; it is fixed here and will not be moved. If survival is below 0.5 or the interval is wider than +-0.20, the answer is "not tight", i.e. type-level wiring is not claimed to suffice.
"Real beats class" is read as real survived > class survived with two-sided p < 0.05. If class beats real with p < 0.05 it is reported as such and the sentence for p < 0.05 is not applied (it states real beats class).

## 3. Reported quantities
- Survived count per arm (of 50); Fisher exact p, two-sided and one-sided (real > class).
- Wilson 95% CI per arm; 95% CI of the difference in proportions by the Newcombe hybrid-score method (method 10, built from the two Wilson intervals).
- Distinct trajectories per arm: number of distinct values of the tuple (outcome, first GF frame, first A frame, tuple of A-run lengths, contact frame, death frame), where an A-run is a maximal run of consecutive frames with the A button pressed, outcome is the E1Result outcome, death frame is the final frame if the outcome is "died" else None, and missing values are None.
- Context only: A-run/tap split (see bins below), spike-to-contact lead (contact frame minus first GF frame) per arm.
  A-run lengths are reported in bins 1, 2, 3-5, 6-10, 11+ (the bins RUNS.md uses). "Tap" = run of length <= 2.

## 4. Scripts
- audit/p23_hash.py (distinctness), audit/p23_run.py (the run), audit/p23_stats.py (all quantities above; no tuning).
