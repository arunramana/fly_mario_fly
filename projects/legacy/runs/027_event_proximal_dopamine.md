# 027 — event-proximal dopamine

REFACTOR_PLAN.md phase 6, step 3 demonstration: `event_proximal_dopamine=
True`, same baseline scenario as every other σ=0/seed=0 run (1-1, 689
frames, dies at the same point, max_x=1432 -- identical trajectory to the
legacy trigger, since the WTA/escape/steering decisions never read
mushroom-body output strongly enough on this single episode to diverge
visibly). What differs is invisible on screen and visible in the CSV:
PAM dopamine now fires only at the 7 `?` block hits and 5 stomps this run
produces, not on every one of ~650 frames of forward progress. See
docs/RUNS.md's phase 6 entry for the full four-field writeup, including
why a single-episode video can't show the class-imbalance finding this
sprint's real result actually is.
