# Diagnosis: why the bio_strict fly fails at the first Goomba, and why real ≈ shuffled

Diagnosis only (2026-09-30): no code, config, test or project was changed; scripts and raw traces are in `audit/`
(`diag_trace.py`, `diag_loom.py`, `diag_*.pkl`, untracked). Settings = honest_1 run #36's config with `bio_strict=True`
(so `jump.g` **2.6**, `dnp01_spike_threshold` 0.3, noise σ 0.015, entity profiles on: Goomba `looming_salience` 2.5,
MotorDirect `a_threshold` 4 / `decay` 0.7 / `dlmn_gain` 1), held-out seeds from the 20-seed eval (1000-1019). Traced
seeds: 1000, 1001, 1003, 1004, 1005 (real) and 1000-1002 with shuffles 1-3; counterfactuals at σ = 0 and g = 2.0.

## Executive summary
The escape signal does **not** die at one stage; three independent faults stack, and the "max_x 293-300" bucket is
mislabelled as "dies at the first Goomba": of the five traced real seeds, **two survive the Goomba and then walk
back left and sit at the screen edge (x≈298 never exceeded), two pass it and sit at the pipe (x 435), and only one
dies**. (1) The Giant-Fiber pathway fires almost as soon as anything is ahead (DNp01 spikes at an *effective*
angular size of ~15°, 130-140 px = ~2 s before contact) and keeps firing; it is a size detector, not a looming
timer. (2) The TTMn pool is **ignited by noise into a latched level** (TTMn 19-56 at rest with no stimulus, DNp01
silent) because `jump.g` 2.6 makes the loop supercritical; the strict motor stage then measures a press as a *rise
above a 30-frame adapted baseline*, and the GF event never rises above the latched baseline (TTMn ratio 7 against a
baseline of 17), so **A is not pressed until the last moments**, and then only as a 1-frame stutter because the
MotorDirect drive hovers just under `a_threshold` (3.1-3.7 vs 4.0). (3) The units changed under it: TTMn now swings
0-60 instead of 0-17, so `ttmn_press_threshold` 3, `a_threshold` 4 and `ttmn_gain` 1, calibrated at clip 50,
are 3.5× too low in relative terms and `dnp02` (LC4 input ~1e-3 rad/frame vs threshold 0.1) is silent. Real and
shuffled circuits do differ at the stage before the motor (real TTMn latched at 11-42, peak 62; shuffled TTMn 0.02 at
rest, peak 4.5) but **both fail at the same motor gate** with the same outcome, so max_x, which saturates at the
Goomba, cannot see the difference (real survives 3000 frames, shuffled dies at frame 108; both end at x≈300).

## 1. Stage-by-stage (seed 1005 = death; 1000 = survives, then goes left; 1001 = reaches the pipe)
Numbers from the per-frame traces. "Ahead/on-screen/elev" is the strict field-of-view gate.

| stage | seed 1005 (dies, frame 161) | verdict |
|---|---|---|
| Enemy in field | Goomba on screen from dx 157 (frame 96); elevation 2.9°→9° (w 0.95→0.85) while Mario walks on the ground; at frame 144 Mario is in the air (elev 33°, w 0.46) and **looming is down-weighted exactly when a jump starts**, at 155 w=0.06 | gate works as designed; elevation weight reduces the signal during the jump |
| Stimulus θ | 0 until dx 143, then 0.28 → 0.68 rad (16°→39°) at dx 134→49. Real angular size at dx 134 is 6.8°; the **2.5× profile salience** multiplies it | θ is a *size*, fed straight in as current; LC4 gets |dθ|≈1e-3 rad/frame |
| LC4 / LPLC2 | telemetry `lc4` 0.2-0.5, `lplc2` 0.3-2 (units are radians, not Hz) | fine, tiny |
| DNp01 (GF) | `spiked` True from frame 104 (dx 134, θ 0.28) and then **every frame**; `dnp01_h` = 30 (= spike 60 × 50 %) | fires ~2 s before contact, sustained: no angular-size or rate selectivity |
| TTMn / DLMn | TTMn **56 at rest before the enemy** (latched), *drops* to 21 when DNp01 starts firing; DLMn 2.2-2.8 | GF spike does not produce a TTMn rise; it lowers it from the latch |
| Motor ratio/baseline | ratio 7.05 vs 30-frame baseline **17.2** → rise = max(0, ratio − max(prev, baseline)) = 0 | **adaptation erases the escape signal** (baseline sits on the latch) |
| MotorDirect drive | 0.6-3.6 over frames 96-150 vs `a_threshold` 4.0 | never reaches threshold |
| press_a | pressed 21-43 (start-up transient), then **0 until frame 139**, then 139,141,143,… every other frame (drive flickers across 4.0) | too late, 1-frame taps: Mario rises 26 px and lands on the Goomba |
| DNp02 path | 0 spikes all run, TTMn_dnp02 ≤ 0.03 | silent (input 1e-3 rad/frame vs `spike_threshold` 0.1) |
| DNp09 / B / MDN | DNp09 0.46-0.49 (walk_drive tonic), walking 100 % of frames, B 4 frames, MDN 0.01 | walking and B irrelevant to the failure |
| Seed 1000 (survives) | A pressed 110-125 (dx 127→102, θ 0.24): a jump **~100 px early**; second press at 180 (dx 5). Survives by timing, then `direction` flips L: aversive odour from the Goomba, then the **food odour of the `?` block behind (visible, `odour_l` 1.3-1.5 ≫ `home_bias` 1.0)** holds Mario at the screen's left edge for 2800 frames | outcome set by odour/timing, not by the escape circuit |
| Seed 1001 (pipe) | TTMn flips 19 → 61 at dx 143 (θ 0.26) with **DNp01 silent**: ratio 20.4 vs baseline 6 → rise → A 102-120 (a jump at 143 px); survives by luck of the early jump | the jump is triggered by a TTMn bistable flip, not by the GF spike |

**Where the signal dies, exactly:** (a) upstream it never had angular-size selectivity (GF spikes at ~15° regardless of
approach speed, then continuously); (b) the TTMn pool is noise-latched, so the GF spike cannot raise it; (c) the phasic
motor gate compares against a baseline that has adapted to the latch, and `a_threshold` is a knife-edge for the
remaining drive. Not gated out by field of view or elevation (except the jump-phase down-weighting), not blocked by
refractory, not a missing path (DNp02 *is* silent, but the GF path reaches the motor).

Counterfactuals (diagnostic only): σ = 0 → resting TTMn **0.00**, outcomes unchanged (1000 and 1005 both end at x 298,
stuck left); `jump.g` 2.0 → resting TTMn 0.01, seed 1000 reaches the pipe (435), seed 1005 still dies (293). So the latch is
noise-ignited supercriticality (g·ρ = 2.13), it is one of the causes, and removing it alone does not fix the escape.

## 2. Units: what was calibrated at clip 50 / spike 50 and what it is now (clip 200 / spike 60)
Measured with the same looming disc in both unit systems (`diag_loom.py`): peak TTMn 16-17 (old) vs 53-62 (strict),
i.e. **×3.5**; DNp01/GF output 50 → 60 (×1.2); DLMn ≈ unchanged (2.2-2.8); spike *thresholds* act on drive (current),
not rate, so they did not move.

| parameter (value) | calibrated as | now | mis-scaled? |
|---|---|---|---|
| `network.clip` 50 → 200 | rate ceiling | TTMn pool range 0-60+ | scale changed ×4 |
| `jump.spike_amp` 50 → 60 | full-scale spike | ×1.2 | ok in itself |
| `jump.ttmn_press_threshold` 3.0 | ~18 % of TTMn peak (17) | ~5 % of peak (60); a latched pool is 6-19× over it | **yes**: "ready" is permanently true once latched |
| `motor_direct.a_threshold` 4.0, `ttmn_gain` 1.0 | rise of TTMn/3 (peak ≈ 5.7) | rises up to 20 from a flip, 0 from an adapted GF event | **yes** (÷3.5 in relative terms; knife-edge 3.1-3.7 vs 4.0) |
| `motor_direct.dlmn_gain` 1.0 × DLMn | DLMn 2.2 | same | scale ok, but tonic (adaptation now removes it) |
| `motor_direct.adapt_frames` 30 (new) | - | baseline tracks the latch | **yes**, interacts with the latch |
| `jump.g` 2.6 (#36) / 2.0 default | "measured" by sweeps | ρ·g 2.13 / 1.64, noise-ignited latch | **yes** (supercritical at either) |
| `jump.dnp01_spike_threshold` 0.3 / 0.5 | GF fires at a size | θ_eff ≈ 15-25° | mis-set vs ~50-60° (below) |
| `dnp02.spike_threshold` 0.1, `dnp02.alpha` 0.1 | fast looms | LC4 EMA ≈ 1e-3 | **yes**: DNp02 never fires |
| `bio.walk_threshold` 0.2 | DNp09 gate | DNp09 tonic 0.47 | inert (always walking) |
| `entity looming_salience` 2.5 (Goomba) | project edit | θ×2.5 | multiplies the size input; not a physiological quantity |
| `steering.home_bias` 1.0 vs food odour (`odour_gain` 16 × hunger 3) | - | odour 1.3-1.5 beats bias | **yes** for seeds stuck left |

## 3. Synthetic looming (no game): standard disc, l/v = 10, 20, 40, 80 ms, θ from 2° to collision
Jump + DNp02 networks only, inputs as in the game (|dθ| → LC4, θ → LPLC2, both hemispheres), σ = 0, per-frame.
"τ" = time before collision; "θ" = angular size. GF = DNp01 spike.

Real connectome, strict units (TTMn ≥ 3 = press-ready):

| l/v | #36 params (g 2.6, thr 0.3): GF spike | TTMn ≥ thr | default params (g 2.0, thr 0.5): GF spike | TTMn ≥ thr |
|---|---|---|---|---|
| 10 ms | τ 6 ms, θ 116° | τ 140 ms, θ 8° | none | τ 40 ms, θ 28° |
| 20 ms | τ 279 ms, θ 8° | **τ 1146 ms, θ 2° (onset)** | τ 96 ms, θ 24° | **onset** |
| 40 ms | τ 358 ms, θ 13° | **onset** | τ 175 ms, θ 26° | **onset** |
| 80 ms | τ 1200 ms, θ 8° | **onset** | τ 367 ms, θ 25° | **onset** |

With the project's default-like parameters the real GF fires at a roughly fixed angular size (24-26°, for l/v 20-80),
the right *form* but about half the literature value; with #36's g 2.6 it fires at 8-13° (far too early). Independently of
the GF, **TTMn exceeds the press threshold at stimulus onset (θ = 2°) for l/v ≥ 20**: the pool integrates any persistent
input, so "TTMn ≥ threshold" carries no timing information.

Shuffled connectome (5 shuffles, default params): TTMn peak 0.9-8.7 against the real 40-47; GF/TTMn fire later and
mostly at 56-157° (l/v 10-80); shuffle 4 never reaches threshold. So the real circuit is ~5× more sensitive and
about 3× earlier in angle, but neither is a timer.

**Literature target (confidence: medium-low, to be checked against the papers before use).** The Drosophila Giant
Fiber responds to looming at a roughly fixed angular size of the order of 50-60° largely independent of l/v over
the tested range (von Reyn et al. 2014 Nat Neurosci 17:1, medium; Card & Dickinson 2008 Curr Biol 18:1300 report
takeoff at comparable angular thresholds, low-medium; LC4/GF looming encoding: Ache et al. 2019 Curr Biol 29:1073,
medium). At θ = 55° that is τ ≈ 1.9 × (l/v): ~19, 38, 77, 154 ms before collision for l/v 10, 20, 40, 80 ms. The
model's GF time-to-collision is 96-367 ms (default params) or 279-1200 ms (#36): 3-8× too early for l/v ≥ 20.

## 4. The five seeds that reach the pipe (x 435)
Nothing kills them: they live to the 3000-frame cap. In seed 1001 Mario reaches x=435 at frame ~93+, and after frame
300 there are **0 A presses in 2700 frames**: TTMn is flat at 19.3, the motor ratio equals its adapted baseline (no
rise), θ = 0 (`wall_ahead.looming_gain` is 0 in #36, and the strict mode removed the takeoff current), so nothing
perceives the pipe and there is no phasic event. They got past the Goomba by an early TTMn flip (1001: jump at dx 143
px) and stall at the first wall. (Eval with the wall looming route on: these five pass to x≈1130.)

## 5. Why real ≈ shuffled
At the Goomba the two circuits produce *different* activity before the motor stage but the same failure:

| | real (1005 / 1000) | shuffled (shuffle 1, seed 1000) |
|---|---|---|
| resting TTMn | 42 / 23 (latched) | 0.02 |
| first GF spike | frame 102 / 103, θ 0.27 (dx ~140) | frame 69, θ 0.27 (dx 138) |
| TTMn near contact | 21 (falls) / 56-61 (flips) | 1.0 → 4.3 (slow ramp), ratio 1.4 |
| MotorDirect drive | 0.6-3.6, stutters at 4.0 | 1.4-3.3, never ≥ 4.0 |
| A presses before contact | 1-frame taps / a lucky early jump | **0** (dies frame 108) |

Stages that erase the difference: the **GF onset** (fires at the same θ≈0.27 frame in both: it is set by
`dnp01_spike_threshold` against the input size, not by the wiring); the **motor threshold** (`a_threshold` 4.0 sits between the
two circuits' drives, so both miss it); and the **metric** (max_x saturates at the Goomba at ~300 for a survivor stuck
left, a death, or a shuffle). Real survives 3000 frames, the shuffle dies in 108, but both report max_x≈300 (note the eval
win criterion = flag is also 0/0). The connectome difference is real in TTMn (×10-1000 at rest, ×5-10 at peak) but it is
not converted into a timed jump.

## 6. Proposed physiology-based calibration plan (not applied)
Target: a **GF/TTMn response that fires at a fixed angular size of ~50-60° independent of l/v (10-80 ms), with take-off
~20-150 ms before collision, silent at rest and to non-looming input**; nothing tuned to win the game.
1. **Remove the latch first (circuit gain).** Choose `jump.g` from a stability criterion (ρ·g < 1, here g ≤ 1.2 for
   ρ = 0.82) or add the missing inhibition, and verify zero TTMn at rest for σ ≥ 0.015 (noise must not ignite it).
   Validate: resting TTMn = 0 over 10⁴ frames at σ 0.015.
2. **Fix the input convention.** Drive LC4/LPLC2 with a physiologically scaled signal (θ and dθ/dt per frame converted with a
   stated gain), not raw radians; drop the 2.5× profile salience from the calibration runs. Validate on the synthetic
   disc, not in-game.
3. **Set `dnp01_spike_threshold` (and LPLC2→GF gain) so the GF spikes at 50-60°** for l/v 10-80 (fixed-θ criterion, per l/v);
   report the error per l/v (target ≤ 10°) for real and for 20 shuffles (the shuffle should miss the target).
4. **Rescale the motor model to the new units** as a relation, not a number: `ttmn_press_threshold` as a fraction of the
   GF-evoked TTMn peak (from step 3), `a_threshold` as a fraction of the phasic rise a spike produces; `adapt_frames`
   longer than a looming event but shorter than tonic drift. Validate: a synthetic disc at each l/v gives one press of
   the right size, tonic input gives none.
5. **DNp02**: scale its input (EMA of |dθ|) so it responds to fast looms (l/v ≤ 20) and not slow ones, as in the
   two-pathway model of the escape (short-mode vs long-mode); validate on the same discs.
6. **Odour vs escape priority**: make the on-screen food odour weak relative to the heading drive (or remove the
   behind-Mario odour channel), so the fly does not stall at the screen's left edge.
7. Only then run the 20-seed eval (real vs 20 shuffles) and report max_x **and** survival time, time-to-first-press and TTMn-rise
   statistics, since max_x alone hid the real/shuffled difference.

## Caveats
Five real seeds and three shuffled were traced in detail (the other 15 eval runs were not; the split between "dies",
"stuck left" and "stuck at pipe" for the 15 max_x≈300 runs is inferred from 5 seeds: 2 stuck-left, 1 death, plus 2 pipe). The synthetic
disc uses the game's input convention (θ and |dθ| as currents) and per-frame (16.7 ms) sampling, which is coarse for l/v = 10 ms.
The literature values are from memory and flagged; they must be verified before they are used as targets.
