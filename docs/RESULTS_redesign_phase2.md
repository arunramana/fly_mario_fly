# Phase 2 results (experimenter, 2026-10-02)

Scene check (audit/p2_scene.py): scene e1_goomba_approach, hash 15d214a2d20eb35d, 110 log frames. At takeover: Goomba on screen YES, ahead YES (dx = +90 px), Mario x speed 0, Mario x 226. Replayed twice: RAM state hash 880dd438187319e2 both times (deterministic).

E1 eval (once): `-m brain.e1 --n 20 --seed0 3000 --workers 8 --out audit/p2_e1_eval.json`, network 4736dc554136ac98, calibration cddee55ba0a629ee.

| | real | shuffled | criterion | result |
|---|---|---|---|---|
| survived | 18/20 (Wilson 95% 70-97%) | 0/20 (0-16%) | real >= 16, shuffled <= 2 | PASS / PASS |
| deaths / timeouts | 2 / 0 | 20 / 0 | | |
| GF before contact | 20/20 | 0/20 (GF never fired) | | |
| A pressed (runs) | 20/20 | 0/20 | | |
| theta at first GF spike | mean 40.7, min 38.4, max 43.6 deg | none | | |
| distance at first GF | mean 21.6, min 20, max 23 px | none | | |

Real deaths: seeds 3018 and 3019 (GF fired at frame 110, A pressed only 3-4 frames, died at frame 130 right after contact at 126/124; the 18 others stomped, A 12-26 frames). Per-run theta at GF (real, seeds 3000-3019): 41.7 40.0 41.7 40.0 43.6 40.0 40.0 38.4 40.0 40.0 41.7 41.7 41.7 40.0 40.0 41.7 40.0 41.7 40.0 40.0. Per-run distance: 21 22 21 22 20 22 22 23 22 22 21 21 21 22 22 21 22 21 22 22. Contact frames 120-138 in real runs; shuffled contact 116-299, all died, shuffled GF fired 0/20. Per-episode data: audit/p2_e1_eval.json.
Gate: PASS on the plan criterion (real 18 >= 16, shuffled 0 <= 2).

Phase 1 re-run (audit/p1_disc.py, once): real GF at l/v 10/20/40/80 = 47.2/47.2/40.6/43.6 deg (unchanged); real rest max/threshold walk 0.73, back 0.77, steer 0.85, 0 GF spikes; shuffled 1-5 never fire the GF (all four l/v), rest ratios 0.78-0.91.

Tests (.venv, one run each): tests/test_e1.py + test_brain_core.py + test_scalars_doc.py + tool/tests test_brain_tool/test_tab_registry/test_ui_smoke: 46 passed. Full root tests/ in 4 chunks (alphabetical, includes test_golden.py): 68 + 64 + 50 + 50 = 232 passed, 0 failed; tests/golden unchanged in git status.

Tool path headless (audit/p2_tool_run.py, tool/core/brain_runner.run_brain_one, seed 9200, project projects/redesign_e1): both arms produced frames (raw.npz), telemetry CSV (21 columns), actions.npy, summary, run_spec kind brain_e1, no error. Real: stomped, 218 frames, GF frame 113 (theta 43.6 deg, 20 px), contact 130, A 12 frames, survived. Shuffled (shuffle seed 1): died, 308 frames, GF never fired, no A.
Seed 9100 re-run via CLI (--n 1): real survived, GF before contact, theta 41.7 at 21 px; shuffled died, GF none. Consistent with the implementer's smoke.

Videos: projects/redesign_e1/runs/211a_e1_real_seed9200.mp4 and 211b_e1_shuffled_seed9200.mp4 (+ .md, telemetry CSVs); docs/RUNS.md entry 211 appended. The tool renders no mp4 itself; rendered via render.brain_panel.render_run with the imageio_ffmpeg binary copied to a scratch ffmpeg.exe on PATH (no system ffmpeg).

Surprises: none in the gate. Note for the reader: shuffled arm GF never fires at all, so there is no jump; shuffled Mario retreats Left, looming-driven (corrected in Phase 3: the Left is the MDN back rule driven by looming through random wiring, not noise; see docs/NOTE_e1_shuffled_contact_spread.md) and still dies; the real arm's 2 deaths pressed A only 3-4 frames.

## Round notes (approved-with-fixes, implementer, 2026-10-04)

**KNOWN LIMITATION: real-arm deaths, seeds 3018 and 3019.** The GF fired at frame 110 in both, but A was held only 3-4 frames, so
the hop was short: contact at frames 126 / 124 and death at 130. The 18 survivors held A 12-26 frames. Recorded as a limitation of
the circuit and the fixed motor map; no threshold was tuned and no code changed for it (Arun's decision).

**Scene settle frames, 30 -> 50.** With 60 frames of right+B and then N idle frames, Mario's x speed is 34 / 19 / 4 / 0 at
N = 10 / 20 / 30 / 40. At 30 he is still sliding, so `check_scene`'s `mario_stationary` fails; 50 gives margin. The 30-frame draft
was not saved, and from the artefacts alone the order of the smoke run versus the check cannot be verified (the SPEC's statement
that the change came from the check is the implementer's account, not something the files prove).

**Shuffled contact-frame spread (116-299 vs real 120-138).** See `docs/NOTE_e1_shuffled_contact_spread.md` (written separately by
the investigator).

**Control arm added: `lesion_gf`** (real connectome, both GF cells silenced; docs/SPEC_tool_phase2.md section 3b). Not yet run on
seeds 3000-3019. Smoke check on 9100-9101 (CLI, 2 seeds): real survived 2/2, GF fired 2/2, A pressed 2; shuffled 0/2, GF 0/2;
lesion_gf 0/2 (both died), GF still crossed threshold 2/2 (before contact), GF output max 0, A never pressed, TTMn peak about 3% of
the real arm's in this 2-seed smoke check only (residual drive reaching TTMn without the GF; smoke-only, seeds 9100-9101). `gf_output_max_hz` / `ttmn_max_hz` are NOT stored for the real and shuffled arms of the 3000-3019 eval (they pre-date those fields). Two seeds are a smoke check, not a result.

## GF-lesion control arm (seeds 3000-3019)

Run once, no retries: `.venv/Scripts/python.exe -m brain.e1 --arms lesion_gf --n 20 --seed0 3000 --workers 8 --out audit/p2_e1_lesion.json` (scene e1_goomba_approach 15d214a2d20eb35d, network 4736dc554136ac98, calibration cddee55ba0a629ee). Real and shuffled are the earlier run (audit/p2_e1_eval.json), not re-run. Lesion = real connectome, both GF cells silenced (docs/SPEC_tool_phase2.md 3b).

| metric | real | shuffled | lesion_gf |
|---|---|---|---|
| survived (Wilson 95% CI) | 18/20 (70-97%) | 0/20 (0-16%) | 0/20 (0-16%) |
| deaths | 2 | 20 | 20 |
| timeouts | 0 | 0 | 0 |
| GF crossed threshold before contact (membrane, pre-clamp) | 20/20 | 0/20 | 20/20 |
| GF output max Hz | not stored in the earlier json | not stored | 0.00 |
| TTMn max Hz | not stored in the earlier json | not stored | 0.011 (per run 0.008-0.011) |
| A pressed (runs) | 20/20 | 0/20 | 0/20 |

Pairing: seed lists identical across arms (3000-3019), and `run_e1_episode` calls `policy.reset(seed)` with the same seed in every arm. Consistent with this, lesion first-GF frame and theta at GF match the real arm per seed (first GF frames 108-113 in both; e.g. 3000: 112, 3004: 113, 3007: 108). The real-arm Hz fields (gf_output_max_hz, ttmn_max_hz) are absent from p2_e1_eval.json (that json predates them), so those two cells are not available for real/shuffled; not re-run, per instruction.

Lesion per run: every run died, frames 130, contact frame 120, A frames 0, GF output 0.0 Hz. GF-before-contact in all 20, first GF frame 108-113, theta at GF median 40.0 deg (38.4-43.6), distance median 22 px. Seeds 3018 and 3019: GF at frame 110 (theta 40.0), no A, contact 120, death 130, like the other 18. Real-arm comparison for those two: A held 3 and 4 frames, contact 126/124, death 130.

Reading: with the GF still crossing threshold (20/20, same frames and angles as real) but its output cut, survival goes from 18/20 to 0/20 and no jump (A) is issued in any run. Survival depends on the GF output, not just on threshold crossing. Lesion arm survival equals shuffled (0/20) but by a different route (shuffled: GF never fires; lesion: GF fires, no output). Residual TTMn activity is about 0.01 Hz, effectively none.

## Annotation 2026-10-04 (Phase 3 review)

E1 caveat (stated plainly): the Phase 2 result 18/20 belongs to the Phase 2 network (`brain_k3_N5.npz`, hash `4736dc554136ac98`). On the Phase 3 network
(`3848f3e70b2051ef`, LC10a added) the same E1 regression gives real 13/20 (the criterion >= 16 FAILS), shuffled 0/20, lesion 0/20, on the previously used
seeds 3000-3019, so it is not a fresh held-out result. The GF still fires before contact in 20/20; deaths held A for 4-9 frames against 11-20 for survivors.
The cause was not diagnosed (a correlation only).

## Annotation 2026-10-04 (reviewer, append)

On fresh seeds 3100-3119 the Phase 3 network gives E1 real 12/20 (FAILS >= 16), matching 13/20 on replayed seeds (not seed luck), while the class-preserving shuffle survives 13/20: near-equal with overlapping CIs, so E1 survival does not separate the real wiring from class-preserving rewiring. The A-hold diagnosis is correlational (brain-only, not a paired closed-loop test). See docs/RUNS.md entry 217.

## Annotation 2026-10-04 (criteria wording, append)

The degree-preserving shuffle is the pass/fail null (<= 2/20 for survival / reach). The class-preserving shuffle is an informative arm ("does
type-level wiring suffice?") with no pass/fail. E1 shows that type-level wiring matters, not neuron-level wiring: the class-shuffled arm survives about as
often as the real one. See docs/SPEC_phase3.md section 13. Earlier tables are not rewritten.
