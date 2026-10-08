# Status (2026-10-06, after Phase 5c step 4)

Short current-state summary of the redesigned brain (`brain/`, plan in docs/REDESIGN_PLAN.md). Numbers are copied from docs/RESULTS_5c_step4.md, docs/RESULTS_baseline_1-1.md and the step 2/3 results; each is on the seeds named. Scalar count: docs/SCALARS_BRAIN.md (50 active + 1 inert).

## Routine runs omit the degree-shuffle arm (docs/SPEC_fast_iteration.md)
The degree-preserving shuffle (`shuffled`) has been 0/20 on every experiment (it never fires the GF or never walks): a settled control. Routine
E1/E2a/B11/E0/E3/dose-response/evaluation runs no longer include it; `--with-degree-shuffle` (alias `--release`) restores it, an explicit `--arms`
is always honoured. The class shuffle (`shuffled_class`) stays in the routine defaults. Re-run the degree shuffle after a change to the stimulus
layer (brain/perception.py, brain/obstacles.py, the mechanisms' encoding), the network hash, or the calibration, and at the release boundary.
Saved evals that contain `shuffled` still display; the Results tab criterion line judges real alone when the arm is absent and says so.

## Phase 5c results (two findings, equal weight)

### (a) Level run B11 improved
- Mean max_x 357 -> 698 (step 4 seeds 6500-6519; 653-756 CI). The 357 baseline is from earlier seeds and PRE-CORRECTION geometry (centre-to-centre distance, sprite-width enemy); the step 3 run on 6400-6419 gave 385. Different seeds, so a before/after on the same seeds does not exist.
- First-Goomba deaths 15/20 (step 3, seeds 6400-6419) -> 0/20 (step 4, 6500-6519).
- Pipe 1 cleared 20/20, pipe 2 12/20, pipe 3 2/20. Stalls now at pipe 2 (x 596, 8 runs) and pipe 3 (x 722, 9 runs). None reached the goal.
- B11 real is near-deterministic (GF first spike at frame 102 in all 20, a few distinct trajectories), so 20 seeds are closer to a handful of independent trajectories than 20 samples.

### (b) Class-preserving shuffle BEAT real on E1
- E1 seeds 3300-3319: class shuffle 15/20 (Wilson 53-89%) vs real 10/20 (30-70%). Degree shuffle 0/20, lesion_gf 0/20.
- Previous seeds 3200-3219 (step 3): real 16/20, class 16/20, degree 0/20. Real missed the >= 16 criterion at step 4.
- Real deaths are all short A presses (2-6 frames); survivors are long holds (14-21).

## What the controls support about the connectome

Fine wiring (neuron-level; degree-preserving or class-preserving shuffle vs real) matters for:
- Pursuit (E3, seeds 5300-5319): real 20/20 vs class-shuffled 2/20, degree shuffle 0/20.
- The level run (B11): both shuffles stay at x = 40 while real reaches mean 698. And E2a (real 20/20 vs degree 0/20).

SUPERSEDED (2026-10-08, E1 n = 50, gate on): the earlier reading "it does NOT matter for the escape jump (E1); type-level wiring suffices" was drawn from pre-gate sets (class 15 vs real 10; 16 vs 16) and does not hold for the gated system. On seeds 3700-3749 real survives 46/50 vs class shuffle 31/50 (Fisher p = 0.00064; difference +0.30, Newcombe 95% CI +0.14 to +0.45), so fine wiring DOES matter for the jump with the expansion gate on (docs/RESULTS_e1_n50.md). The degree shuffle fails because it never fires the GF. Which wiring feature matters is not shown.

Caveats, stated plainly:
- Under the landmark drive the shuffled brains saturate or do not walk. Some 0/20 results (B11 shuffles at x = 40, E2a degree and class shuffle) mean "does not walk / no GF", not a failure specific to the obstacle or the Goomba. They show the shuffled brain is not a working walker, not which wiring feature is needed.
- B11 real is near-deterministic (few trajectories), and the CIs on E1 (10/20 vs 15/20) overlap.
- E2a class shuffle 0/20 is uninformative (no GF).
- Baselines before step 4 used pre-correction geometry; cross-seed, cross-step comparisons are indicative only.

The headline "the fly's wiring does the work" is therefore NOT claimed for escape, and for pursuit and walking it is claimed only at the level the shuffles above test. README.md and CLAUDE.md state no result of this kind (invariants unchanged), so they were not edited.

Standing practice: re-run the human shadow reference after every stimulus-layer change, and shadow data diagnoses, never scores (CLAUDE.md "Shadow reference runs").

## Update 2026-10-07: expansion gate and the fourth "the fly doesn't have this"
- The expansion gate (Step 7) exposed a FOURTH thing the fly does not have: a wall-jump. Pick & Strauss 2005 (flies climb obstacles); no source supports jumping at static obstacles. Listed with: no brake, no sustained jump, no pit sense.
- The pipe-clearing drop after the gate (pipe 2: 8 -> 5, pipe 3: 2 -> 0) is the gate removing a false alarm (the cue was a size-only alarm at the wall), not a regression.
- E1 at n = 50 on the gated system (seeds 3700-3749): real 46/50 vs class shuffle 31/50, Fisher p = 0.00064. The earlier "type-level wiring suffices for the jump" (above) does not hold for the gated system; see docs/RESULTS_e1_n50.md.
