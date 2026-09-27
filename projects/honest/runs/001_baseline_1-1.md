# 001 -- 001_baseline_1-1

**Setup.** Level 1-1, seed 0, sigma=0, max_frames=5000. Project `honest` (test3's settings; every `config.rules` switch off; MotorDirect with fresh press; DNp01 + DNp02 refractory 8 steps; page, gap and wall perception on; arousal 0; graded pit off).

**What happened.** Died at frame 108, max_x_abs=311, on the first Goomba (enemy contact, 7 px ahead; no pit, no wall). The fly committed three times (frames 89, 92, 105, all DNp01, DNp02 silent); only the third drove MotorDirect above `a_threshold` (6.19 vs 5.0), pressing A for one frame, 14 px from the Goomba. The first two commits (motor drive 3.68 and 2.45) pressed nothing. Wall stimulus: 0 frames (no wall ahead).

**What we learned.** With the code's hold/cooldown/habituation rules removed, the circuit's own response to a Goomba is too weak and too late through MotorDirect: the ~65 px commit never reaches the A threshold, and a 1-frame press is a minimal hop. Full numbers in `001_baseline_1-1_report.json`; save state `001_baseline_1-1_pre_death` (frame 48, 60 frames before the end).
