# 006 — steering (DNa01/DNa02) + contact-based climbing

First video with Mario **not** holding right unconditionally. New circuit:
DNa01/DNa02 core + N>=60 presynaptic partners (329 neurons total,
`steering_circuit.py`), plain leaky-integrator dynamics (no spiking
fallback), winner-take-all between hemispheres decides left/right every
frame. A separate contact-based reflex (stall-then-hop-then-escalate, no
tile RAM) handles obstacles. The jump circuit (DNp01/TTMn) is untouched.

New hand-set scalars (on top of `g`, `dnp01_spike_threshold`,
`ttmn_press_threshold` from the jump circuit): `G_STEER=1.2` (spectral
radius of `W_steer` at g=1 is 0.79; the linear boundary is near g~1.27, so
1.2 is comfortably under it — see `tune_steering.py`), `HOME_BIAS=1.0`,
`CLIMB_STALL_FRAMES=20`, `CLIMB_HOP_SMALL_FRAMES=10` /
`CLIMB_HOP_BIG_FRAMES=14`, `CLIMB_JUMP_FRAMES=25`.

**Mushroom vs. home bias: the competition is real but home bias wins at
these magnitudes.** A synthetic powerup was injected at frame 220, ~40px
behind Mario (RAM poke, same trick as `tune.py`'s synthetic θ-ramp — no `?`
block was hit). DNa01/DNa02 population means jumped from ~0.498 to ~0.59
that same frame (a real, visible, decaying transient — watch the panel), but
the steering direction never flipped to L across the whole 1138-frame run:
odor concentration at 40px is `1/40 = 0.025`, dwarfed by `HOME_BIAS=1.0`.
The mechanism is wired correctly and shows up in the telemetry; it just
doesn't win this particular race. Worth revisiting with a closer injection
distance or a smaller `HOME_BIAS` if a future sprint wants to see the
winner actually flip.

**Climbing fired 6 times** (1 hop, 5 escalated jumps) — after the very
first hop, the escalation counter mostly went straight to a full jump on
subsequent obstacles, because the 24px "clear distance" that resets the
attempt counter wasn't being reached (Mario was still contesting the same
obstacle). **2 conflicts** logged where the escape jump and a climb jump
both wanted A in the same frame — harmless (A is idempotent) but confirms
the two pathways really are independent, as SPEC required.

**Ended in death at frame 1138**, apparently wedged against an obstacle
next to a Goomba (theta pinned at a constant 0.73 for dozens of frames,
TTMn cycling through repeated spike/reset without Mario's x ever clearing
it) — the kind of case the old mechanical "unstick" kludge in
`compare_controllers.py` used to paper over with a blind left-nudge. The new
contact-based climb reflex tried (visible in the telemetry) but didn't
free him this time. Not patched further this sprint (cut for speed, per
spec) — a legitimate negative result, not a silent bug.

Net: steering and climbing are both real, connectome-driven, and
independently verifiable in the telemetry; survival is worse than the
hold-right jump-only baseline on this particular seed, which is an honest
first-pass result, not a regression to paper over.
