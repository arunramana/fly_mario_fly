# Phase 3 investigation: can a sensed cue drive walking and turning, and why does the shuffled arm go Left?

Date 2026-10-04. Read-only: no code, config, calibration or test edited; synthetic stimuli and replay of recorded stimuli only; no game runs.
Scripts (gitignored): `audit/p3_lib.py`, `p3_struct*.py`, `p3_orn.py`, `p3_lc10*.py`, `p3_rest*.py`, `p3_replay.py`, `p3_disc*.py`, `p3_besttypes.py`.
Held fixed: network `brain_k3_N5.npz` (hash 4736dc554136ac98, 15,551 neurons, 568,527 non-zero weights), `brain/calibration.json` (g 0.85, thresholds walk 0.01709, steer 0.01093, back 0.01389 Hz), shuffle seeds 1-5, noise sigma 0.015. Noise seeds 9300-9304 (Q1) and 9310-9329 (Q2); E1's 3000-3019 untouched.
Tags: **[M]** measured here; **[A]** assumed; **[L-v]** literature verified (abstract/snippet level only); **[L-m]** from memory.
Units: a stimulus value is added to a sensory neuron's input every substep, like the looming mechanism (LPLC2 gets theta in rad, 0.70 at 40 deg; LC4 gets |dtheta| rad/frame). The code treats rad as Hz one-to-one, an unregistered factor of 1.

## 1. Answer

1. **Smell (a): no honest route.** Attractive ORNs (DM1, VA2, DM4; 179 left/right-assigned in the network) never drive walking on the real wiring, and drive steering at under 0.3 x threshold even at the 200 Hz clip. Their net effect on DNp09 and MDN is inhibitory. Only the cVA-type channel ORN_DA1 produces any press at all, and it is Left/back, not walk. **Vision (b): LC10a works, in the right direction, but it is not in the network** (5 of 275 are). With LC10a added as a sensory population (a probe network, +913 neurons) a left cue gives a Left press, a right cue gives Right plus walk (B), a central cue gives walk, and 5 of 5 shuffles do not reproduce this.
2. **Shuffled Left is not noise.** The same exact replay of E1 seed 9200 reproduces all 91 Left frames to 1e-16, and with no stimulus the same brain presses Left 0 times. The cause is the looming input (LPLC2) reaching MDN through random wiring; Left comes from the MDN "back" rule, not from DNa01/DNa02. At rest no arm, real or shuffled, ever crossed a threshold in 180,000 frames (max/threshold 0.90 real, 0.98 shuffled).
3. **Goal cue:** a persistent right-LC10a target can carry "right" through wiring, but only as an invented world-level attractor (flagged, counted), not a visible object. Smell cannot carry it.

## 2. Evidence

| # | Claim | Data / source | Conf. |
|---|---|---|---|
| 1 | ORN in network: 2,638 of 2,639, all sign + (ACh). Attractive DM1 74 (L35/R39), VA2 83 (L33/R41/U9), DM4 32 (L16/R15/U1): left 84, right 95, 10 side-unknown get no current. Aversive DA2 48. | `audit/p3_a.py` on the saved network | [M] |
| 2 | ORN to DNp09/DNa/MDN: 3 hops, included by the k/N cut (not excluded). Strongest chain: ORN -> uniglomerular PN (VA2_adPN, M_l2PNl20, DM1_lPN) -> SIP022, LAL030_a/b, CB0356, AVLP299_c -> DNa02. Linear mass is 3e-5 (sum over 84 left ORNs) at hop 3; hop 4-5 is net negative onto DNp09 (-2.8e-5, -1.4e-5). Best single ORN type needs about 160 units/neuron to reach the walk threshold in the linear estimate. | `p3_struct.py`, `p3_struct2.py` (linear, ignores the clip) | [M] |
| 3 | Sweep, real, attractive ORN, 7 strengths 0.3-200 x 5 conditions x 5 seeds: walk/thr falls 0.37 -> 0.14-0.26 (never > 0.6 max). Steer/thr: Lonly -0.25, Ronly -0.02, both -0.30 at 200 (sign Left for every condition; Lonly minus Ronly = -0.23, correct sign, sd over seeds 0.006). Max steer 0.79. Press rate 0 (Left 0.7% of frames at 200). Single glomeruli VA1v, VA1d, DA2, DM1, VA2, DM4: no press at 200. DA1 only: Left 100% (back 3.2 x thr), walk 0.05 x thr. | `p3_orn.py`, `p3_besttypes.py` | [M] |
| 4 | Laterality of ORN: ipsilateral bias onto DNa02 is 2.9x for left ORN, 1.3x for right ORN at hop 3. Literature wants strong lateralisation (ipsilateral central neurons fire 30-50% more; a 5% L/R asymmetry is detectable, Gaudry 2013). | [M]; Gaudry et al. 2013 Nature 493:424, snippet | [M] / [L-v] |
| 5 | LC10a: 275 (L135/R140), ACh, sign +. In network only 5 (L1/R4); LC10b 1, LC10d 6. Manifest has no LC10a population or segment, so `Brain.stimulate` raised `StimulusError: 275 of 275 ids are not in the manifest's sensory tier`. | `p3_lc10run.py` first run | [M] |
| 6 | Probe network: manifest + LC10a population + segment LC10a -> outputs, same k=3, N=5: 16,464 neurons (+913, of which 275 LC10a, AOTU* 77 -> 199), 612,566 non-zero weights, rho(W) unchanged (g 0.85). Disc with the unchanged calibration numbers: real GF fires at 47.2/47.2/47.2/40.6 deg for l/v 10/20/40/80 (spread 6.6, inside the 38-48 and 8 deg gate), shuffle 1 does not fire; rest max/thr 0.82-0.83. Shuffles 2-5 of the probe not disc-checked. | `p3_lc10.py`, `p3_disc.py` | [M] |
| 7 | LC10a wiring (probe): right LC10a -> DNp09R at 1 hop (6.2e-3); left LC10a has no 1-hop edge to DNp09L. Both sides -> AOTU001/025/015/016/012 -> LAL028 -> DNa02 at 2 hops, ipsilateral about 10:1 (1.6e-2 vs 1.5e-3). DNa01 and MDN barely move. | `p3_struct4.py` | [M] |
| 8 | LC10a sweep, real, steady state: s=1 max steer 0.95 x thr (no press); s=3 Lonly steer -1.83 x thr, Left 100%, DNa02L 0.048 Hz vs rest 0.007; Ronly +1.82, Right 100%, walk 0.87, B 17%; both: steer -0.03, walk 0.79 (B 6%). s=10 Ronly and both: walk 2.4 / 2.1 x thr, B and Right 100%; Lonly walk 0.23 (no walk). Window 3 <= s <~ 25; at s=30 Ronly MDN reaches 0.86-1.08 x thr and at 100 Left wins (pL 1.0), because Left beats Right. Response is 8 sigma of the rest steer sd (0.0024 Hz) at s=3. Rest max 0.47 x thr. | `p3_lc10run.py` | [M] |
| 9 | Shuffles (both cues): response is 5-100x threshold in every shuffle, always with Left (MDN back) on. Lateralisation sign: LC10a s=10, steer(Lonly)-steer(Ronly) has the correct (negative) sign in 1 of 5 shuffles; ORN attractive s=10 has the wrong sign in 5 of 5 (+1.3 to +11 x thr; real -0.009). In shuffles LPLC2 reaches MDN/DNa01/DNa02 at 1 hop (linear mass 3.5e-3 to 1.5e-2 per unit input) where the real wiring has 0 there (real: GF 0.117, DNp09 4.1e-3 only), because random edges land on output cells with few inputs and so large normalised weights. | `p3_orn.py`, `p3_lc10run.py`, `p3_struct3.py` | [M] |
| 10 | Q2 replay of `211b` (shuffle 1, noise seed 9200, recorded theta) reproduces telemetry exactly (max diff 1e-16): Left 91, Right 12, B 48 of 308. Ablations: LPLC2 only 85 Left; LC4 only 0; no stimulus 0. Of the 91 Left frames, 91 are MDN > 0.01389 and 0 are steer < -thr. `211a` real: 0 presses, matches. | `p3_replay.py` | [M] |
| 11 | Synthetic approach (Goomba 0.6 px/frame from dx 89, Mario still, first 200 frames), 20 seeds: Left on 43-55% of frames in each of 5 shuffles (real 0); MDN > thr in 20/20 seeds (back ratio 1.9-2.7); steer rule contributes 0-23%. Real: Left 0, walk (B+Right) 4.4% of frames (DNp09 is driven at 1 hop, 4.1e-3). | `p3_rest.py` | [M] |
| 12 | Rest, no stimulus, 20 seeds x 1500 frames x (real + 5 shuffles): 0 presses in 180,000 frames. Max/threshold: steer real 0.72-0.90 (median 0.78), shuffled 0.73-0.98 (median 0.84); walk and back up to 1.0 (pooled max, shuffle 1 walk 0.998). Per-frame rest signal is Gaussian (excess kurtosis 0-0.13, lag-1 autocorr 0.16-0.19), steer threshold = 4.5 sigma real, 4.2-4.5 shuffled. Gaussian-tail estimate of a false steer press: 7.7e-6/frame real (0.5% per 600-frame episode); 2-4e-5/frame shuffled (1.3-2.2% per episode); walk and back 1e-9..1e-7. | `p3_rest2.py` (extrapolation beyond the data) | [M] data / [A] tail |
| 13 | LC10 neurons respond to small moving objects; unilateral LC10 activation gives orienting and ipsilateral wing extension (direction of orienting not stated in the snippet). | Ribeiro et al. 2018 Cell 174:607 (snippet) | [L-v] |
| 14 | DNa01/DNa02 activity predicts ipsilateral turning; right-minus-left DNa02 difference predicts turn velocity. Matches the motor map (DNa-R minus DNa-L, Right for positive). | Rayshubskiy et al., eLife 102230 (snippet) | [L-v] |
| 15 | ORN spike rates in vivo reach order 1e2 /s. Not used as a target. | memory | [L-m] |
| 16 | Persistent right-LC10a (s 3, 10, 30) leaves the real GF firing angles unchanged (47.2/47.2/47.2/40.6). In shuffle 1 the same cue makes the GF fire at 116-157 deg at s=10 and at 2 deg at s=30. | `p3_discgoal.py` | [M] |

## 3. Results table, real vs 5 shuffles (mean of 5 noise seeds; x = multiples of the derived threshold)

| Stimulus | net | walk x | steer x (+ = Right) | back x | DNa02 L/R Hz | presses L / R / B |
|---|---|---|---|---|---|---|
| ORN attr, Lonly, 200 | real | 0.26 | -0.25 | 0.38 | 0.013/0.007 | 0.01/0/0 |
| | shuf 1..5 | 22, 46, 32, 56, 27 | +37, +35, +41, +47, -7 | 32-73 | 0.18-0.43 / 0.35-1.2 | 1 / 0 / 1 |
| ORN attr, Ronly, 200 | real | 0.21 | -0.02 | 0.36 | 0.011/0.010 | 0/0/0 |
| | shuf 1..5 | 25-138 | -192, -37, -8, -36, -30 | 63-120 | 0.58-1.7 / 0.30-0.99 | 1 / 0 / 1 |
| LC10a, Lonly, s=3 | real | 0.33 | **-1.83** | 0.41 | 0.048/0.009 | 1/0/0 |
| | shuf 1..5 | 1.3-2.4 | +2.6, +0.7, +4.9, -1.4, +2.2 | 1.4-4.1 | 0.02-0.04 / 0.02-0.07 | 1 / 0 / ~1 |
| LC10a, Ronly, s=3 | real | 0.87 | **+1.82** | 0.43 | 0.010/0.049 | 0/1/0.17 |
| | shuf 1..5 | 1.4-3.2 | +0.9, -0.1, +0.1, -0.5, -2.3 | 1.8-6.1 | 0.02-0.05 / 0.04-0.06 | 1 / 0 / 1 |
| LC10a, Lonly, s=10 | real | 0.23 | -6.60 | 0.33 | 0.156/0.016 | 1/0/0 |
| LC10a, Ronly, s=10 | real | 2.41 | +6.56 | 0.48 | 0.018/0.160 | 0/1/1 |
| Rest (no stimulus) | real | 0.38 | 0.00 | 0.47 | 0.0069/0.0066 | 0 |
| | shuf 1..5 | 0.43-0.45 | 0.00 | 0.51-0.55 | 0.0069-0.0079 | 0 |

(Rest means are ratios of the mean, not the max; rest max is in evidence row 12. Rows marked "real" for LC10a use the probe network, not the production one.)

## 4. Verdict per question

**Q1(a) ORN odour: cannot make the fly walk or turn.** What is missing is not a route within the cut (3 hops ORN -> PN -> SIP/LAL -> DNa02 is in the network) but strength and sign: the route is about 4e-7 per ORN, the walk path is net inhibitory beyond hop 3, and the thresholds sit at 0.011-0.017 Hz. Reaching them needs more than the 200 Hz clip, and what is reached is Left. The mushroom-body route (ORN -> KC -> MBON -> DNa02/MDN, 4 hops, MB included whole) carries no learned weights yet; whether Phase 4 plasticity could make smell steer is untested here.
**Q1(b) LC10a: can, with a manifest change.** Receptors: LC10a only (275 = 135 L + 140 R, ACh, sign +), none currently in the network. Left LC10a -> DNa02L -> Left; right LC10a -> DNa02R and DNp09R -> Right + B. The left/right walk asymmetry is a wiring fact (a direct right-only LC10a -> DNp09R edge). The shuffles do not reproduce it (wrong sign in 4 of 5, always Left).
**Q2: not noise; looming through random wiring.** See rows 10-12. Left is the MDN rule (backing up = Left button, Left beats Right).
**Goal cue:** see 5.

## 5. Recommended design (needs Arun's decisions)

- **Receptors:** LC10a, left (135) and right (140) as two sensory populations; azimuth of a target splits the drive between them. Add it to `brain/manifest.py` as a SENSORY population plus an `LC10a -> outputs` segment (same k=3, N=5). This changes the network (+913 neurons) and so its hash, so `brain.calibrate` must be re-run once; the disc gate on the unchanged numbers already holds for the real network [M, row 6].
- **Mechanism:** a `TargetMechanism`: cue = a small moving object at azimuth a; encoding = drive s_L, s_R onto the left and right LC10a. LC10a prefers small moving objects (row 13), so a static or large goal cue is not licensed.
- **Invented scalars (all would go in `brain/scalars.py`):** (1) `LC10A_GAIN`: sensed salience -> input rate. The usable window on the real wiring is about 3 <= s < 25 per neuron (looming reaches only 0.7), so no literature number fixes it and it would be set from this synthetic sweep, never from game outcomes. (2) `LC10A_AZIMUTH_SPLIT`: how azimuth maps to the L/R share (a width in degrees, or a linear split). (3) If a permanent goal cue is used, its salience (`GOAL_CUE_SALIENCE`). Also the implicit rad-to-Hz factor of the looming encoding is not registered; the new mechanism makes that gap visible.
- **Synthetic test and exit check (no game):** drive L-only, R-only, both, graded, 5 strengths, 5 noise seeds, real vs 5 shuffles, as here. Pass if real shows Left for left, Right for right, walk for central/right cue, correct lateralisation in all 5 seeds, a max/threshold at rest <= 0.9, and no press without a cue; shuffles should not reproduce the lateralised pattern. Also re-run the disc gate and confirm a persistent target leaves the GF angle unchanged (real: yes up to s=30; shuffled GF fires spuriously from s=10, row 16, which should be reported as a property of the control).
- **Smell stays in the plan as a Phase 4 learning target**, not an E3 mechanism. E3 ("find the mushroom by smell") cannot pass through unlearned wiring; either re-define it as a visual attractor (LC10a) or report it as an honest fail.
- **Goal cue (D2).** Permitted by the rule in the narrow sense (it enters at sensory neurons and the fly's wiring decides). It is not a visible object: "right is the way" is a world-level fact, so the cue would be an invented permanent attractor at a fixed azimuth, the same information as `home_bias` entering by another door. If Arun accepts it, label it invented and counted; do not describe it as removing the injected drive. Not tested: its interaction with the looming cue in the game (only the disc), and whether the walk persists through a left-LC10a/MDN conflict (Left wins over Right).
- **Q2 options (thresholds untouched):** (i) fix the wording in SPEC/NOTE/scalars: shuffled Left is looming-driven, not noise; (ii) report "frames Left" and min x per arm in E1, and treat `contact_frame` as non-comparable across arms (already in the NOTE); (iii) consider a stricter control that preserves the post-class of each output edge (or a class-preserving rewire), so random wiring cannot hand MDN/DNa a large LPLC2 weight; this is a control-design decision, not a threshold change; (iv) review the MDN -> Left mapping: it is the only reason a threshold crossing becomes a Left press that overrides Right.

## 6. Risks and decisions for Arun

1. Add LC10a to the manifest (new hash, re-calibration, shuffles re-built)? Without it Phase 3 has no cue that works.
2. Accept an invented, permanent goal attractor (D2), or leave "go right" unsolved? Phase 3's "no injected drive left" is true only in the sensory-tier sense.
3. Re-define E3 (visual instead of smell) or keep it as an expected fail.
4. Gain window is narrow (3-25); outside it Right turns into Left (MDN) or does nothing. Knife-edge risk like earlier prototypes; one scalar decides it.
5. LC10a left/right = same-side eye is an assumption [A]; the orienting direction of unilateral LC10a activation was not read [L-v only for "orienting"]. Verify before Mario labels it "attractive".
6. Shuffled control becomes more Left-biased with every sensory drive (rest 0, loom 45%, cue 100%): keep reporting it, but do not read a shuffled "Left" as brain intent.

## 7. Open questions

- Shuffle seeds 2-5 of the probe network were not disc-checked; only shuffle 1.
- Linear-response ORN screen ignores the 0-clip; the sweep confirms it for attractive types and four others, not all 53 types.
- cVA-type (DA1) identification and ORN valence beyond DM1/VA2/DM4/DA2 not verified (Phase 0 section 2.2 applies).
- Steady-state responses over frames 20-50; no adaptation in the model, so a sustained cue is assumed not to habituate [A].
