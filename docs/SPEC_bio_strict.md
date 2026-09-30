# SPEC: bio_strict -- an honest fly (audit fixes)

From `docs/AUDIT_biological_validity.md`. Rule: perception may compute what a fly could sense; nothing may inject
control. Phase 1 is pure bookkeeping (no behaviour change). Phases 2-3 sit behind one new flag,
`ProjectConfig.bio_strict` (default False, so every golden and every existing project is unchanged). Values below are
**choices with cited qualitative support, not measurements**: every one is an invented scalar in
`BioStrictParams` (`config/params.py`, counted in `docs/SCALARS.md`) and is marked with a confidence.
Citations are to the literature as I know it; none was re-checked online in this sprint (confidence noted).

## Phase 1 -- bookkeeping
1. **Run spec snapshots everything.** `RunSpec.snapshot`: the *merged* entity profiles (default + project override,
   full JSON, not `enabled: true`), the start state (name, sha256, frame, and the compressed action log itself so the
   spec is self-contained), the brain-weights file name + sha256 (verified at replay; mismatch = error). Character
   settings, modules, rules and every scalar were already in `tool_settings`/`config`. `run_one` prefers the snapshot
   over live project files; old specs without one behave as before. Test: re-run a recorded spec after editing the
   project's profile file and start state, compare action logs bit for bit.
2. **Training = Play.** Both build their `run_from_config` kwargs from one function (`runner.run_kwargs`): entity
   profiles, hunger override, forced power-up, start state, frame skip, reward flags. The 60-frame warm-up is removed
   (`WARMUP_FRAMES = 0`: the emulator backup is taken at power-on, identical to Play's first frame). Test: training
   baseline telemetry == `run_one` telemetry for the same spec.
3. `audit/` in `.gitignore`; the audit report is committed.
4. **Eval.** `tool/core/evaluation.py` + `scripts/eval_connectome.py`: N held-out seeds (default 20, seeds 1000+),
   real connectome vs degree-preserving shuffle (a different shuffle seed per run), win rate with Wilson 95 % CI,
   mean (bootstrap 95 % CI) and median `max_x`; saved to `projects/<name>/eval.json`; shown on the Learning tab and in
   the batch summary (win rate + CI).

## Phase 2 -- honest senses (`bio_strict`)
Looming enters only through what the eye could see. *Mapping of the side-view game to a visual field:* Mario's eye looks
along +x; an object is at azimuth 0 (frontal) if it is ahead (dx >= 0), behind otherwise; its elevation is
`atan(|dy| / max(|dx|, 1))`.
5. **Field of view.** An enemy contributes looming only if (a) it is on screen (drawn x = absolute x - ScreenLeft,
   RAM 0x071A/0x071C, within [0, 256): the camera is what a fly's eye sees), (b) it is ahead (dx >= 0: enemies behind
   are outside the frontal field; the ~30 deg rear blind spot of the real eye is ignored, the game has no rear view),
   (c) weight `max(0, 1 - elevation/elevation_limit_deg)`, `elevation_limit_deg = 60`. Both hemispheres get the same
   looming: a frontal object falls in the binocular overlap, so the arbitrary "ahead = right" convention (audit S5:
   swapping it removed both wins) disappears. *Support:* LC4/LPLC2 are lobula columnar neurons whose populations tile
   the visual field and drive the Giant Fiber / DNp02 (Wu et al. 2016 eLife 5:e21022, high; von Reyn et al. 2014
   Nat Neurosci 17:1, high; Klapoetke et al. 2017 Nature 551:237, LPLC2 radial-motion opponency, medium; Ache et al.
   2019 Curr Biol 29:1073, LC4/GF looming encoding, medium). The 60 deg limit is a choice (low confidence).
6. **Page-corrected distance always on** (audit S1: the default was wrong in 43 % of enemy-frames).
7. **Walls.** The current injected onto DNp01 (`wall_takeoff`) is removed. A wall (pipe/stair) may enter only as an
   expanding object through the same LC4/LPLC2 looming route (`wall_ahead.looming_gain`), symmetric in both
   hemispheres, only inside the drawn screen; there is no synapse in the data that carries tile height onto the GF
   (the circuit manifest says so for gaps, `Takeoff.gap_gain` provenance).
8. **Privileged-input audit under bio_strict** (each removed or justified):
   - pit width / `gap_ahead` current onto DNp01 (`gap_gain`), `gap_w` into the mushroom body: *removed* -- no
     connectome route; pits are unperceived (the fly can fall in).
   - `question_block_odor`, `mushroom_odor`, `goomba_odor`: the game has no odour; these are invented channels that
     read the tile map and every enemy slot. *Kept only for sources on screen* (a visual-olfactory proxy, documented as
     invented) so the fly cannot be attracted to what is off screen.
   - `mb_spatial_inputs` (enemy closeness), `qblock_ahead`: restricted to on-screen sources.
   - hunger (Mario's size) = internal state, kept. Speed (RAM 0x0057) = self-motion, kept.
   - hand-coded control rules (`ControlRules`), `graded_pit_response`: forced off (they decide actions).
   - reward events (`?` hit, stomp, death, power-up, cleared gap) are RAM facts used only as dopamine -- allowed.

## Phase 3 -- honest dynamics (`bio_strict`)
9. **Units.** Rate units are read as Hz. `clip = 200` (sustained peak rates of *Drosophila* central neurons are of order
   10^2 Hz; Bhandawat et al. 2007 Nat Neurosci 10:1474 for olfactory projection neurons, medium). `spike_amp = 60`
   = one spike per 16.7 ms frame = 1000/16.67 (derived, high). Both latches are re-tested (`audit/latch.py` logic,
   now `tests/test_bio_strict_latch.py`): the jump network must not sustain activity at zero input; `jump.g` under
   bio_strict is the largest value <= the default that passes (a supercritical loop saturated by a clip is an artefact,
   audit D1); the DNp02 loop is checked with the new spike amplitude.
10. **Motor model.** `adapt_frames = 30` (0.5 s): a press needs a phasic rise of the muscle neuron above a slow
    baseline, for TTMn *and* DLMn, so a tonic level cannot hold A (audit M2). Documented as spike-frequency adaptation
    (time constants of 10^2-10^3 ms are typical for insect motor neurons; Burrows 1996 *The Neurobiology of an Insect
    Brain*, low-medium). `release_on_landing` stays: the NES needs a fresh press, it is an interface constraint.
11. **Walking.** Forward walking is no longer a constant Right press. `walk_drive` (DNp09 current) and `home_bias`
    are kept as documented *spontaneous locomotion / heading drive* (flies walk in spontaneous bouts: Mendes et al. 2013
    eLife 2:e00231, medium; heading-to-goal steering via DNa01/02: Rayshubskiy et al., medium-low); they stand in for
    central-complex drive and are **invented currents** (Steering.home_bias, Speed.walk_drive). Right/Left are pressed
    only while DNp09 >= `walk_threshold` (0.2; DNp09 is the walking DN: Bidaye et al. 2020 Neuron 108:469, medium),
    direction from the steering teams. Suppressing DNp09 stops walking.

## Reporting
After phase 3: `scripts/eval_connectome.py` on honest_1 (#36 settings) with `bio_strict` on, 20 held-out seeds, real vs
shuffled. Expect fewer wins; reported as found.

## Results (2026-09-30): honest_1 #36 settings, 20 held-out seeds (1000-1019), frame cap 3000
Real connectome vs degree-preserving shuffle (a different shuffle per seed). Win = flag. 95 % CIs: Wilson (win rate),
bootstrap (mean max_x). Raw per-seed values in `audit/final_eval.json` (untracked).

| condition | arm | wins | win rate (CI) | max_x mean (CI) | median |
|---|---|---|---|---|---|
| **bio_strict** (walls unperceived, as #36 has `wall_ahead.looming_gain` 0) | real | 0/20 | 0 % (0-16) | 331 (303-359) | 298 |
| | shuffled | 0/20 | 0 % (0-16) | 328 (310-347) | 310 |
| **bio_strict + wall looming route** (`looming_gain` 1.0) | real | 0/20 | 0 % (0-16) | 505 (338-674) | 298 |
| | shuffled | 0/20 | 0 % (0-16) | 355 (310-409) | 310 |
| non-strict, same settings (contrast) | real | 1/20 | 5 % (1-24) | 970 (635-1355) | 770 |
| | shuffled | 0/20 | 0 % (0-16) | 400 (308-583) | 310 |

Reading, truthfully: the honest fly does not win, and under strict the real and shuffled connectomes are
indistinguishable (intervals overlap almost entirely; 15/20 real runs die at x 293-300, the first Goomba; 5/20 reach the
first pipe at x 435). With the wall visible as an expanding object, 5/20 real runs get past it (x ~1130) while the
shuffle mostly does not (2/20 past 435) -- a hint of a connectome effect, not a significant one at n = 20. The
non-strict fly (same settings, held-out seeds) wins 1/20 and is clearly ahead of its shuffle on distance, so the drop from
"wins" to 0/20 is what the injected currents, privileged senses and tonic press were buying; the audit's single-seed win
of #36 (seed 10) was a 5 % event, not a competence. Not done: re-tuning anything under bio_strict (thresholds were
calibrated with the old units), a pit route, a trained (MB) strict fly.
