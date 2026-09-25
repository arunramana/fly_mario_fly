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
