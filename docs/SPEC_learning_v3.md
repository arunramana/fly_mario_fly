# SPEC: learning v3 -- recovery, more MB inputs, cleared-gap reward, TTMn plateau fix, curriculum, all buttons

**Status: decisions made before implementation.** Everything is opt-in / default off; goldens stay
byte-identical. Rule (CLAUDE.md invariant 8): perception and reward are allowed, hand-coded control is
not -- every button press comes from neuron activity through MotorDirect "muscles".

## A1. Potentiation (recovery) -- `MushroomBodyParams.recovery_rate` (0 = off, range 0-1)
Real flies: dopamine without KC coincidence lets a depressed KC->MBON synapse recover. Rule, applied on
every dopamine pulse (reward or punishment) after the depression step, per MBON j with dopamine `d_j`:
`W[i,j] += min(1, recovery_rate * d_j * (1 - elig_i)) * (W0[i,j] - W[i,j])`, `W0` = the connectome's
untrained weight. Recovery is toward `W0` only (never above it, so no new potentiation beyond baseline),
only where a real synapse exists, and only for KCs that were NOT recently active (`1 - elig`). Editable
as a slider in Circuits -> Mushroom body (ParamForm ranged field). **Sign test** re-run
(`tests/test_mb_recovery.py`): a pulse now moves eligible synapses down and non-eligible depressed ones up.

## A2. MB inputs: gap width and own speed -- module `mb_gap_speed_inputs` (`N_INPUTS = 2`)
Two more Kenyon-cell inputs, perception only: width of the first pit within `perceive_tiles` (tiles /
range, 0..1; `tile_ram.upcoming_gap_width`) and Mario's own horizontal speed (RAM `0x0057`
Player_X_Speed, |v| / 40, the game's max, 0..1). Appended in module order like `mb_spatial_inputs`.

## A3. Cleared-gap reward
Event: Mario was approaching a pit (its far edge column recorded when it first entered the lookahead)
and is now on the ground (RAM `0x001D` = 0) at or past that column. One-shot PAM pulse of `dynamics.CLIP`
(same as `?` hit / stomp / power-up, no new scalar), `event_dopamine(..., gap_cleared=True)`. Switched on
by `FitnessSettings.gap` > 0 (the fitness weight of one cleared gap; its value never scales the dopamine,
as for the power-up). Needs event-proximal mode. `info["n_gaps_cleared"]` always reported.

## A4. TTMn plateau -- diagnosis and opt-in fix
Evidence (`projects/learn_1` telemetry, 209 runs, 94 with long plateaus; `learn_1` play run 1, frames
195-231): TTMn is not "exactly 17" but a 3-frame limit cycle 4.1 -> 8.3 -> 17.0 -> 4.1, sustained while
looming is *quiet* (lc4 0.2, lplc2 0.3-2.4, no spike, d_px -41...-155, i.e. the enemy is **behind**
Mario). Causes, each verified by isolating the jump network:
1. **Tonic input from receding enemies.** `enemy_thetas` uses `|d|`, so an enemy behind Mario keeps a
   non-zero theta (0.13 at 127 px) and routes it to the left hemisphere for as long as it stays on screen.
2. **Recurrent latch.** With `jump.g` 2.6 the network stays at TTMn 2.9-11.9 with *zero* input after one
   looming pulse; at g 2.0 it decays to 0 with no input but any tonic lplc2 >= 0.4 holds TTMn at 5-17.
   Not the clip (50), refractory, or MBON readout: removing each leaves the plateau.
3. **MotorDirect turns it into a held A.** The drive sums `ttmn_gain` x TTMn *rise* (a 4->8->17 cycle is a
   rise every 3 frames) and `dlmn_gain` x DLMn level; `learn_1` has `dlmn_gain` 1.0 and DLMn sits at 1.5-2.9
   while the jump circuit is latched, so drive is 5-14 > `a_threshold` 4 and A stays down for hundreds of
   frames (no fresh press, no jump). Measured, learn_1 seed 0, 450 frames: A held 338 frames, 288 of them with
   looming quiet.
Fixes (both opt-in): `PagePerceptionParams.ignore_behind` (perception: an enemy behind produces no
looming -- it is out of the frontal visual field) and `MotorDirectParams.adapt_frames` (muscle
adaptation: the TTMn rise and the DLMn level are measured above slow baselines, tau = adapt_frames, so a
sustained cycle or tonic DLMn adapts away while a fresh onset -- a pit takeoff -- still drives fully; 0 = off).
Result (learn_1, seeds 0/1): A-held frames 338/318 -> 60/77 with `adapt_frames` 30 (`ignore_behind` alone:
289/225, since the latch persists without input). The circuit-level latch itself (TTMn >= 8 with quiet
looming, ~170 frames) is *not* removed by either fix -- only `jump.g` <= ~2.0 does that, at the price of
tonic looming holding TTMn up; the fix is at the muscle, where the held A was made. Side effect to expect:
without the accidental permanent hop the fly gets less far on these projects (max_x 708 -> 323 seed 0).

## A5. Training curriculum -- `TrainingSettings.start_states`
A tuple of savestate names (`"power-on"` allowed); each episode samples one with the episode's own
seeded rng (`default_rng(episode seed)`), empty = today's behaviour. A saved state replays its action
log on its own env (the power-on env keeps its warm-up backup). `learn_1` gets `before_mushroom_block`.

## A6. MBON readout cap 1.0
`MbonReadoutParams.*_frac` range `(0.0, 1.0)` in params and the Circuits editor.

## A7. All moves -- action space and muscles
Action space = every combination of `{right, left, down, up} x {A} x {B}` (64, NOOP included), the
existing 8 first in their old order (so old indices, action logs and goldens are unchanged).
`MotorDirectParams.buttons` (default False) turns on the new muscles; each is a leaky integrator of its
neurons' activity, `drive = decay*drive + gain*activity`, pressed while `drive >= threshold`
(`down_/up_/left_` `gain` and `threshold`, shared `button_decay`, all in the Circuits tab). Right stays the
default walk unless the Left muscle is active.

| Button | Neurons (MaleCNS v1.0) | Evidence | Confidence |
|---|---|---|---|
| A (jump) | TTMn / DLMn (existing) | SPEC_jump | high |
| B (run) | DNp09 (existing) | SPEC_speed | high |
| Right (walk) | default drive, DNp09 | existing | high |
| Left (walk/turn) | DNa01 + DNa02 (existing), L minus R team | steering DNs, SPEC_steering | high |
| Back-up | MDN (existing) | SPEC_habituation | high |
| Down (crouch/duck) | DNp03, DNp06, DNp11 | strongest non-escape looming-driven DNs, LPLC1-dominant: DNp03 3602/6110 looming-neuron synapses from LPLC1, DNp06 2773/5654, DNp11 1041/5936 (+LC4 3666) | hypothesis: role is a modelling choice |
| Up (reach/climb) | DNg40, DNp05 | looming-driven, LPLC2/LC4-dominant: DNg40 2998 LPLC2 + 980 LC4, DNp05 1303 LC4 | hypothesis: role is a modelling choice |

Honest limit: the annotations carry no behavioural labels, so Down/Up are *not* established
crouch/climb neurons; the choice is "distinct, connectome-verified looming-driven descending pathways
other than the escape ones", assigned to the two free buttons. They are driven through their real
inputs (a small circuit, `posture_circuit`: LC4/LPLC2/LPLC1 bodies with >= 60 synapses onto the core +
the core DNs, real weights, same pipeline as MDN; looming enters like the jump network's). Their
thresholds must be raised or trained for a behaviour to emerge; nothing is forced.

## B8. Luigi palette
Choosing Luigi recolours only Mario's sprite (not the level) in the live preview and in replay.

## Results (2026-09-30)
Posture circuit: 10 core neurons (2 each of DNp03/06/11, DNg40, DNp05) + 142 inputs (85 LC4, 53 LPLC1, 4
LPLC2 with >= 60 synapses onto the core), spectral radius 0.9993 at g=1 (posture_g 0.8). Coverage of the
core's real input is 5-20% (DNp03 20%, DNg40 7%). Sign test, TTMn numbers and the fix results:
`docs/RUNS.md` (`learning-v3-001`). Skipped: drawing Up/Down on the controller-pad overlay; no
behaviour was trained or verified for the new buttons; the second-level (VNC) function of the chosen DNs.
