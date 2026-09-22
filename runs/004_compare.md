# 004 — three controllers compared

`004a_real.mp4` (A, g=1.5), `004b_shuffled_best.mp4` (B, best-of-20 shuffle,
g=3.0), `004c_theta.mp4` (C, theta>c=1.125). All level 1-1, seed 0.

**Numbers (this seed):** A dies at frame 20 (1 jump). C — tuned to A's jump
rate — dies at frame 20 too (1 jump): identical press trace, not just
matched count. B survives the full 4000 frames (2 jumps, 31 unsticks).

**Not a clean "B beats A" result yet.** The seed mechanism (a random blind
run-up before recording starts) looks like it drops Mario already on top of
a Goomba on this seed — A's own un-warmed-up run (no run-up) survives all
4000 frames with 2 jumps, identical to B. Recorded as-is per instructions;
see chat/README discussion before drawing conclusions from survival time
here. `compare_controllers_battery.csv` and `shuffle_sweep_results.json`
have the full 3-level x 3-seed x 21-network data.
