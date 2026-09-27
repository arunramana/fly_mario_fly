# CONTROL AUDIT: rules that decide when or how to act

Rule (CLAUDE.md invariant 8): the fly controls, the code only perceives. This lists every rule in the controller, outside the *motor thresholds* (`ttmn_press_threshold`, `dnp09_speed_threshold`, the R/L team comparison that picks the direction), that decides when or how long to act. **Nothing here has been removed.** Line numbers are `bridge/full_policy.py` at commit `9e9ba2b` unless another file is named.

"Needed today" is judged from the 1-1 runs of this project (baseline 689 frames; the 1023- and 2148-frame win_attempt runs).

| # | Rule | Where | What it does | Needed today? | What could replace it |
|---|---|---|---|---|---|
| 1 | Fixed A-hold after a jump commit | 603, 658-662 (`jump_hold_frames`=25) | Once TTMn crosses threshold, A is held for a fixed count regardless of what the neurons do afterwards | **Yes** -- it is the jump's duration | A held while the motor output stays above threshold (TTMn/DLMn activity sets the duration); or duration learned through the MB |
| 2 | Jump cooldown | 590-591, 662 (`jump_cooldown_frames`=40) | After a jump's hold ends, no new escape commit for 40 frames | **It is the cause of the frame-689 pit death** and of the Goomba deaths in win_attempt iters 1-2 | Refractory dynamics of the Giant Fiber pathway itself (short, activity-dependent); the code gate can go |
| 3 | Binary long-jump selection | 601-604 (`dlmn >= dlmn_recruit_threshold` -> 35-frame hold) | Picks long vs short hold at the instant of commit, from one DLMn sample | Yes for pits | Hold duration proportional to sustained DLMn activity (graded), or learned |
| 4 | Escape habituation give-up | 601, `fly/state/reflex_habituation.py` (3 checks with <16 px progress) | Suppresses the escape reflex, then hands over to MDN | Fires in stalled runs (1023-frame run logs it); not in the first 689 baseline frames | Synaptic depression on the GF pathway (a real GF property); or MB-learned suppression of a failing reflex |
| 5 | MDN backup hold | 637-655 (`mdn_backup_frames`) | When MDN crosses threshold, forces direction L for a fixed count, then resets habituation | Occasionally | Direction = L while MDN activity is high (graded, no counter); reset by circuit recovery |
| 6 | Climb stall detector | 543-551 (`stall_count`, `climb_stall_frames`) | Infers "blocked" from mario_x unchanged for N frames | **Yes** (1 hop in the baseline; pipes/stairs) | A wall-contact / proprioceptive stimulus (perception, RAM `solid_ahead`) onto a climb pathway |
| 7 | Climb hop/jump hold, cooldown, attempt counter | 553-570, 663-668, `climb_hop_small/big_frames`, `climb_jump_frames`, `climb_cooldown_frames`, `climb_clear_distance` | Fixed hop, escalating to a full jump, with its own cooldown and attempt count | Yes | Same as #1/#2 for a climb motor pathway; escalation by learning (MB) rather than a counter |
| 8 | Climb habituation | 555 (`hab_climb`) | Gives up on repeated futile climbs | Rare | Same as #4 |
| 9 | Shared-A conflict resolution | 630-635, 658 | `press_a = jump_hold>0 or climb_hold>0`; counts conflicts | Yes (one A button) | Motor-neuron competition for the A output (WTA) |
| 10 | Refusal rule | 341, 423, 514, 673 (`refusal_gap_tiles`=5) | For a gap wider than validated: drops the gap current, pushes steering away, zeroes DNp09 | **No** in 1-1 (0 refusal frames in real terrain; only the injected 7-tile test gap triggers it) | Learned aversion to wide gaps (MB) or inhibition through real gap->DNa/DNp09 pathways |
| 11 | Walk suppression while busy | 672-675 (`walk_suppression`, `busy = press_a or stall_count>0`) | Cuts DNp09 drive during a jump/stall | Yes (Mario slows in jumps) | An efference-copy / inhibitory connection from the jump pathway onto DNp09 |
| 12 | Odour brake | 675 | Subtracts odour from the walk drive | Minor | Odour -> DNp09 inhibitory path through the MB |
| 13 | Always-on placed currents | `HOME_BIAS` (steering), `WALK_DRIVE`, `gap_gain`, `MDN_DRIVE` | Constant/placed drive onto DNa01/02, DNp09, DNp01, MDN | Yes | These are *stimuli* (allowed by invariant 8) but not learned; the MB could set their effective size |
| 14 | Direction latch | ~523-527 | Direction only changes when one team strictly wins | Yes | Motor readout (kept) |
| 15 | Frame-skip repeat | `run_steering.py` ~382 | Repeats the last action between decisions | No (default 1) | Remove |
| 16 | Test-harness injections | `run_steering.py` (`inject_gap_frame`, `force_mario_size`, mushroom injection) | Poke RAM for demos | Test only | Keep out of real configs |
| 17 | **GradedPitModule** (legacy) | `bridge/controller_modules.py`, `scenario.graded_pit_response` | Forces cooldown bypass, DNp01 commit, long jump, B hold near a pit | No (research scaffolding; pinned by tests/test_pits.py) | **Remove** with its Goal-tab toggle once a circuit route reaches the same behaviour |
| 18 | Death-triggered MB punishment / reward-for-progress | `policy.on_step`, MB block | Teaching signal, not an action | n/a | Stimulus-side; allowed |

## Observations

- Rules 1-3 form one mechanism: *when the jump button is down and for how long* is decided by counters, not by the motor neurons. Replacing them with "A follows motor activity" removes the cooldown entirely and fixes the pit failure mechanism found in `SPEC_pits.md`.
- Only #2, #4, #6, #7 and #9 are exercised by the winning 1-1 route today; #10 and #17 are not.
- Perception repairs (page-corrected enemy distance, upcoming-gap input) are now `PerceptionModule`s and do not appear here.

## Switches (honest-play sprint)

Each rule that decides when or how long to act now has an off switch in `config.rules` (`ControlRules`, `config/params.py`), shown as a checkbox in the Circuits tab. **True (default) = the rule is active, so every golden is byte-identical**; False removes the rule and leaves the decision to the circuit.

| Row | Switch | Effect when off |
|---|---|---|
| 1 | `rules.jump_hold` | A is no longer held by the counter after a commit (a commit only counts; A then comes from MotorDirect, or from nothing) |
| 2 | `rules.jump_cooldown` | No cooldown after a jump; a new commit needs only the circuit's own dynamics |
| 3 | `rules.long_jump_select` | No long-vs-short choice from one DLMn sample (always the short hold; `graded_pit`'s forced long jump is separate) |
| 4 | `rules.escape_habituation` | The escape reflex is never suppressed; `hab_escape` stays 0, so MDN is never driven |
| 5 | `rules.mdn_backup` | MDN is still simulated but never forces the fixed backing-up hold or the habituation reset |
| 6 | `rules.climb_stall` | No "blocked" inference from an unchanged `mario_x` (also removes stall from the walk-suppression `busy`) |
| 7 | `rules.climb_reflex` | No climb hop/jump hold, cooldown or attempt counter |
| 8 | `rules.climb_habituation` | The climb reflex never gives up |
| 10 | `rules.refusal` | A wide gap keeps its gap current; no steering push, DNp09 not zeroed |
| 11 | `rules.walk_suppression` | DNp09 drive is not cut while jumping/stalled |
| 12 | `rules.odour_brake` | Odour is not subtracted from the walk drive |
| 17 | `scenario.graded_pit_response` (already existed) | The forced GradedPitModule (cooldown bypass, forced DNp01 commit, long jump, B hold); mirrored read-only in the Circuits tab, written from the Goal tab |

No switch: **row 9** (shared A button) only merges rows 1 and 7, so it is vacuous with both off; **13, 14** are stimuli and the motor readout, kept by design; **15, 16** are harness settings (frame-skip 1, injections) not present in real configs; **18** is a teaching signal.

The perception replacement for row 6 is `WallAheadPerceptionModule` (`modules.wall_ahead`, off by default): the first ground-attached solid obstacle within `perceive_tiles` (pipe, stair, block stack) as distance and height from the tile RAM, fed only as looming (`theta = 2*arctan(h_px / (2*d_px))` into right-hemisphere LC4/LPLC2 and the DNp02 LC4 input) and/or a takeoff current onto DNp01. Two gains (`looming_gain`, `takeoff_gain`; 0 = that route off).

`projects/honest` is the reference with every switch off; it is read-only (like `legacy`), so every experiment is a duplicate of it.
