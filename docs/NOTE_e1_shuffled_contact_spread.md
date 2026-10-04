# NOTE: why shuffled-arm contact frames spread 116-299 in E1

**Finding.** Mario is not stationary in the shuffled arm. The shuffled brain's steering outputs (DNa01/DNa02) are
noisy and it holds Left for stretches, so Mario walks away from the approaching Goomba. `max_x` (226/228) is a
maximum, so it hides this: it only records the starting x. The Goomba keeps walking toward Mario, so contact is
delayed by however far Mario retreated. Frames 297-299 are Mario hard against x=114, the left edge of the screen
(NES scroll is one-way, he cannot go further left) and the Goomba catching up there.
a_frames=0 is true; the presses are Left (and some B/R), not A.

**Evidence (replay with a non-held-out noise seed, shuffle seeds 101+, audit/probe_spread.py, audit/probe2.py).**
- Seeds 9300-9305 shuffled: contact 121, 124, 121, 299, 299, 299. mario_x range 114..226 in every episode;
  Mario y stays 176 (no jumps). Presses seen: L, L+B, R+B, none; A never.
- Seed 9303 shuffled: 82 Left frames and 2 Right of 308; mario_x sampled every 20 frames:
  226,226,226,226,226,226,224,203,185,182,176,146,137,136,119,114. Real arm same seed: 0 Left, 1 Right, x=226,
  contact 134.
- Goomba approach is identical in both arms until the walk starts: goomba_dx 89,71,52,34 at frames 1,30,60,90.
  Goomba dx at the final contact is 15 (same threshold <16 as the real arm); minimum dx 9-10 at frame ~306.
  So the Goomba is deterministic (same RAM walk, no RNG); only Mario's x differs.
- Recorded eval (audit/p2_e1_eval.json): shuffled contact frames 116-299, 8 of 20 at 297-299; real 120-138
  (two real deaths at 124/126). Early shuffled contacts (116-124, 10 of 20) are runs where Mario stayed or
  barely moved; the 179-212 ones are partial retreats. Not re-run on seeds 3000-3019; per-frame rows for
  those seeds were not stored in the JSON, so the Left-press count is shown on seeds 9300-9305 only.
- Not the cause: contact definition (brain/e1.py is_contact, same for both arms), Goomba RNG, turning or falling
  (dx falls monotonically), vertical sway (mario_y constant).

**Validity of the shuffled control.** It does not affect the verdict. Every shuffled episode dies, with zero GF
spikes and zero A presses, so survival is 0/20 either way. The spread is delayed passive death, because the
shuffled fly's noise-driven Left walking happens to be a bit of accidental retreat. Caveats: (1) "Mario stationary"
is not true for the shuffled arm; describe it as "no jump", not "no movement"; (2) any metric using contact_frame,
or time to death, compared across arms is confounded by this retreat; (3) the retreat means the Goomba can
in principle be outrun in a longer scene, so a max_frames larger than 600 is not an issue here (death at 308) but
a scene with more room to the left could let a noisy shuffled arm survive by walking away, which would be a
fly-driven (not forced) behaviour, still not a jump.

**Open question.** Why the shuffled network drives DNa01/DNa02 into Left so often while the real one does not
(mean pooled DNa01 0.0137, DNa02 0.0133 in seed 9303 shuffled) was not investigated.
