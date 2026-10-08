# SPEC: E1d, E1 under a scene distribution (written 2026-10-08, before any E1d episode ran)

Problem: E1 uses one fixed scene (brain/scenes/e1_goomba_approach.json, Goomba 90 px ahead of a stationary Mario), so the real arm
has 16 distinct trajectories in 50 episodes (docs/RESULTS_e1_n50.md; the episodes differ only by noise seed). Fisher treats them as
50 independent samples. E1d makes the samples independent by drawing a different scene per seed. It tests the same question
(real vs class-shuffled connectome, survival) over a distribution of scenes instead of one scene.

Nothing about the brain, the stimulus layer or the calibration changes. The default E1 (fixed scene) is untouched and byte-identical.

## 1. What varies, and why only this
Everything below is produced by the game itself from a different replay prefix. No RAM byte is written (no clear_enemies-style edit
is needed here: E1 already has none).

The E1 log is two segments: hold Right+B for `walk_frames`, then release all for `settle_frames`. E1d draws both lengths.

| parameter | range | what it moves (game-produced) |
|---|---|---|
| `walk_frames` W | integers 50..65 | Mario's start x (197..241 px at settle 50) and, because the Goomba walks left meanwhile, the Goomba's distance |
| `settle_frames` S | integers 40..70 | how long the Goomba keeps walking toward a stationary Mario: distance falls 0.625 px per frame; also its sub-pixel walking phase (RAM 0x0401+slot) |

Measured on the fixed log's geometry (scene geometry only, no fly involved; probe before this spec, nothing to do with outcomes):
- W = 45 leaves the Goomba off screen, W = 50 puts it on screen: 50 is the lower bound.
- S = 30 leaves Mario's x speed non-zero (still sliding), S = 40 is the first settle length with speed 0: 40 is the lower bound.
- Distance at W,S = (125, 107, 90, 72, 53, 17 px at W = 50, 55, 60, 65, 70, 80 and S = 50); each extra settle frame subtracts
  0.625 px. The upper bounds W = 65 and S = 70 keep the Goomba at least three sprite widths (48 px) ahead in the worst corner
  (72 - 19 = 53 px), so it is "approaching" and not already in contact. The fixed E1 scene (W = 60, S = 50, 90 px) lies inside the ranges.
- Resulting distance range about 53..125 px ahead (a priori from the above), Mario x offset up to 44 px; the first Goomba of 1-1 on
  flat ground; no other enemy; nothing cleared (E1 has no rules).
- The ranges are experiment conventions, chosen from these game facts. They are not chosen, checked or edited against any outcome.

What is NOT varied, and why:
- Goomba speed: the game's walking speed byte (Enemy_X_Speed, RAM 0x58+slot) reads 246 (-10/16 px per frame) for this Goomba. I
  have no evidence of a second value the game produces for the first Goomba of 1-1 (the fixed value in every probe), so I do not
  invent one.
- Moving direction (0x46+slot = 2, left): the Goomba always walks left toward Mario; the other value would make it walk away.
- Mario stationary at takeover is required (as in E1); the settle lower bound guarantees it and `check_scene` verifies it.

## 2. Sampling rule
`brain.scenes.draw_scene_params(seed)`: `rng = np.random.default_rng([E1D_STREAM_TAG, seed])`, then `walk_frames =
rng.integers(50, 66)`, `settle_frames = rng.integers(40, 71)`, in that order (uniform, integers). E1D_STREAM_TAG = 0x53434E45.
The brain's noise stream is `default_rng(seed)`-derived (policy.reset(seed)); a SeedSequence with entropy `[tag, seed]` is a
different stream, so the scene RNG is independent of the brain noise RNG and uses no brain draw. The draw depends on the
episode seed only, so both arms of the same seed play the SAME scene (paired). The scene is outcome-neutral: it is a fixed
function of the seed and never depends on the fly. After the replay `check_scene` is run; if it fails the episode raises (no
redraw, no skipping). Expected: 0 failures (verified over all 16 x 31 = 496 possible draws in the geometry survey, tests/test_e1_scene_dist.py).

Geometry survey of all 496 possible draws (run after the ranges were fixed, scene geometry only, no brain): 0 check_scene failures; Goomba dx 59..131 px (73 distinct values, the a-priori estimate above was 53..125: the 6 px difference is the worst-corner arithmetic being approximate); Mario x takes 16 values; all 496 draws give a distinct (Mario x, Goomba dx, sub-pixel phase, speed) state. Expected distinct scenes among 50 uniform draws = 496 (1 - (1 - 1/496)^50) = 47.6.

## 3. Unchanged definitions
Survival, contact, resolved, E1_GRACE_FRAMES, E1_MAX_FRAMES, the 16 px Goomba box, the arms, the calibration: exactly docs/SPEC_tool_phase2.md
section 3. The per-episode JSON records `scene_draw` (walk_frames, settle_frames) and `a_trace` (per-frame A press string, needed for the trajectory).

## 4. Pre-registered run and analysis (run once)
- Command: `python -m brain.e1 --scene-dist --n 50 --seed0 3800 --workers 8 --arms real shuffled_class --out <json>`.
- Seeds 3800-3849 (fresh: never used by any earlier set). `shuffled_class` uses a DISTINCT class rewiring per seed (shuffle seed 1 + i, as before).
  Same noise seed and same scene draw in both arms for a given i. The degree shuffle is not run (docs/SPEC_fast_iteration.md).
- Reported: survived count per arm; Fisher exact p (two-sided, and one-sided real > class); Wilson 95% CI per arm; Newcombe
  95% CI of the difference; distinct trajectories per arm (tuple of SPEC_e1_n50 section 3: outcome, first GF frame, first A frame,
  A-run lengths, contact frame, death frame); Kish effective n; the TRAJECTORY-LEVEL permutation test (100,000 permutations,
  rng seed 20261007, two-sided) and cluster bootstrap (10,000 resamples, seed 20261007, percentile 95% CI of episode-level
  survival(real) - survival(class)), exactly the logic of audit/p24_stats.py section 1 (implemented as functions in audit/e1d_stats.py);
  distinct scenes drawn among the 50 and survival by scene tercile of Goomba distance (descriptive only).
- Reading, fixed now (verbatim): "p < 0.05 AND the CI of the difference excluding 0 at the trajectory level -> fine wiring matters
  for the jump in this scene distribution; otherwise not shown (unresolved)". p is the Fisher episode-level p; the CI is the
  cluster-bootstrap CI (and the trajectory permutation p must also be < 0.05 for the trajectory-level statement). "Real beats class"
  means real survived more; class beating real is reported as such and the sentence is not applied.

## 5. Validation (no outcomes)
tests/test_e1_scene_dist.py: draws deterministic per seed; within ranges; independent of the brain noise stream; `check_scene`
passes for 50 draws; default E1 unchanged (same scene hash, same stamp keys, same result fields). Smoke: one episode per arm at seed 9100 (not an eval).

## 6. Files
- brain/scenes.py (adapted): `draw_scene_params`, `draw_scene`, `scene_ok`, `distribution_dict`, constants; `SceneSpec.draw` (default None).
- brain/e1.py (adapted): `--scene-dist`, `scene_dist` flag through `run_eval`/`_job`/`run_e1_episode`, `E1dResult` (E1Result + `scene_draw`, `a_trace`).
- brain/scalars.py (adapted): four invented scalars E1D_WALK_MIN/MAX, E1D_SETTLE_MIN/MAX; docs/SCALARS_BRAIN.md regenerated.
- audit/e1d_stats.py (new): the pre-registered analysis.
- tests/test_e1_scene_dist.py (new).
