Sprint 017. Three steps ordered; only step 1 shipped code. Step 2
(mutual inhibition) and step 3 (pC1 attack) were both investigated and
both declined, on evidence, not skipped for lack of trying — see
docs/RUNS.md for the numbers. Slug says "step1_fixes" rather than
"arbitration" because arbitration is exactly what didn't get built.

Step 1: the "steering bug" wasn't one — dna01/dna02 (by TYPE) are
mathematically guaranteed to look balanced regardless of real steering,
since both types get the identical per-side current. r_team/l_team (by
HEMISPHERE) is the actual decision axis and was never exposed. Added it
to telemetry and the overlay. Separately, the DNp09 odour-brake shipped
in 016 reused ODOUR_GAIN's long-range steering-calibrated magnitude for
braking, crushing WALK_DRIVE across most of a `?`-block-dense stretch
instead of just on final approach — confirmed by A/B (median dnp09
0.0→0.94, B-press 9.3%→67.7% with the brake forced off). Fixed by only
braking on the excess over HOME_BIAS. No new scalars either fix.

Step 2 (skipped): counted real contradictory-command frames across three
levels, ~5000 frames total — escape+steering(L)+climb same frame: 0
everywhere; climb-and-escape both wanting A: ≤1 per level; aversive-vs-
home near-tie (|r_team-l_team|<0.1): ≤1 per level. Building arbitration
for conflicts this rare would be scaffolding for a problem that doesn't
occur.

Step 3 (skipped): pC1 is real (156 bodies, not the ~85 MECHANISMS.md
guessed) but DNp37 doesn't exist anywhere in this connectome (DNp36→
DNp38, no DNp37), and pC1→TTMn is zero synapses — a stronger negative
than DNp02's 012 case, which at least had a real (if modest) direct
TTMn link to justify building on. pC1's largest real link to anything
already built is DNa01 (115 syn/20 pairs) — steering, not an attack
effector. "Fiery Mario attacks" has no real connectome path to stand on.
