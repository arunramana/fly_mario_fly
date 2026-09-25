# SPEC: pits — cooldown override, distance-triggered long jump, run-up

Motivated by `projects/win_attempt/runs/031_cooldown_sweep.md`'s
`jump_cooldown_frames` sweep: the deterministic baseline (1-1, sigma=0,
seed=0) dies at frame 689, x=1432, to a real pit it had already detected
6 frames earlier — the escape circuit's own shared cooldown/hold timer
just hadn't reopened yet. Sweeping the cooldown down didn't fix it; it
only traded one failure mode for another (an earlier enemy death, or a
permanent stall against a much wider gap). This spec targets the actual
mechanism, not the cooldown knob.

**Opt-in, default off.** Everything below is gated behind
`config.scenario.graded_pit_response: bool = False`. Off reproduces
today's behaviour byte-for-byte (`tests/test_golden.py`, unaffected) —
this is a new decision path, not a retune of an existing one.

## 0. First: verify the measurement, don't trust the sweep's own number

Before touching any circuit logic, checked directly whether `gap_width`
was actually miscounting. **It wasn't.** The sweep's "stuck refusing a
7-tile gap" result was `win_attempt`'s own config carrying over
`legacy`'s `inject_gap_frame=600` — the sprint-016 synthetic wide-gap
test injection (`refusal_gap_tiles(5) + refusal_gap_margin_tiles(2) =
7`, `run_steering.py`'s own `poke_wide_gap`), not a real pit. It came
along for free when `win_attempt` was duplicated from `legacy` and was
never cleared before the sweep ran.

With `inject_gap_frame` cleared, `gap_width` against 1-1's own real
terrain (sigma=0, seed=0, logged via `FullPolicy.act`'s new rising-edge
`log.debug` — see section 1) finds exactly two real pits before the
first death, both visually cross-checked against the rendered frame:

| frame | mario_x_abs | measured gap_width |
|---:|---:|---:|
| 568 | 1089 | 2 tiles |
| 664 | 1360 | 3 tiles (the fatal one) |

No miscount found. `win_attempt`'s config has been corrected
(`inject_gap_frame=None`) for this spec's own validation run.

## 1. Diagnostic logging (always on, not gated)

`FullPolicy.act` now logs once per pit encounter (`gap_width`'s own
rising edge, 0 -> >0): `mario_x`, `gap_width`, and the new
`distance_to_gap` reading (section 2). Pure `log.debug` output, no
telemetry column added, no golden affected — this is what section 0's
own verification used.

## 2. `distance_to_gap`: how far, not just how wide

`tile_ram.gap_width` only ever reads offset 1 — it's 0 for every frame
until Mario's own column is already at the pit's edge, which is exactly
why the escape trigger (gated on the SAME frame gap_width first reads
nonzero, in practice gated on jump_cooldown/jump_hold reopening at all)
had no earlier signal to act on. New `tile_ram.distance_to_gap(ram,
max_tiles)`: reuses the same `ground_ahead` scan, returns the tile-offset
of the nearest non-ground tile (1-indexed, matching `ground_ahead`'s own
convention), or `None` if the whole lookahead window is solid ground.
Always computed (cheap, pure RAM read); only *used* when
`graded_pit_response` is on.

## 3. A strong gap signal overrides the jump cooldown

`FullPolicy.act`'s escape-trigger block gates ALL commits — pit or enemy
— behind one shared `jump_cooldown`/`jump_hold` timer, on a roughly
65-frame cycle set by `jump_cooldown_frames + {jump_hold_frames,
long_jump_hold_frames}`. This is what actually killed the baseline: the
real, growing pit signal (DLMn already past `dlmn_recruit_threshold` six
frames before the fatal jump) had no way to preempt a timer mid-cycle
from an earlier, unrelated commit.

`gap_override = graded_pit_response and distance_to_edge is not None and
distance_to_edge <= long_jump_trigger_distance_tiles` (new scalar,
`TakeoffParams.long_jump_trigger_distance_tiles = 2`) now bypasses the
cooldown decrement (`if self.jump_cooldown > 0 and not gap_override:
...`), and forces `dnp01_ready` regardless of whether `ttmn_val` has
independently crossed its own press threshold — DNp01 is the pathway
that actually receives the gap's own placed current
(`gap_gain * gap_w`), so a gap override always commits through DNp01,
never DNp02.

> **Scaffolding, not circuit behaviour.** The direct DNp01 commit in
> sections 3-5 (`dnp01_ready = ... or gap_override`, forced `long_jump`,
> forced `press_b`) is a hand-placed controller rule keyed on a RAM tile
> read, exactly like `gap_gain`/`HOME_BIAS`: nothing in the connectome
> produces it, and it bypasses DNp01's own TTMn threshold. It exists to
> test whether the pit failure is a timing problem; it is not a claim about
> what the fly's circuit does. Do not cite it as evidence for the wiring.

## 4. Trigger the long jump by distance, not by whichever check happens to run

`long_jump = gap_override or dlmn_val >= dlmn_recruit_threshold` — once a
gap_override has fired, it always launches long, since it's already known
to be a deliberate pit response rather than a graded read of whatever
DLMn happens to be at an unrelated commit's own timing.

**Known limitation, stated plainly**: `gap_override`'s distance check
doesn't know how *wide* the upcoming gap will turn out to be (`gap_width`
itself only becomes readable at the edge) — the refusal rule
(`refusing = gap_width > refusal_gap_tiles`) still applies once Mario
actually reaches it, but a gap_override commit is not itself refusal-
aware in advance. Fine for 1-1's own real pits (2-3 tiles, well inside
the validated 0-4 tile range); a wider one could still get an attempted
jump it shouldn't. Not fixed here — would need a width prediction this
sprint doesn't build.

## 5. Hold B for a run-up

`press_b` was DNp09's own independent decision — found live (test1 run
#1) that it happened to read `False` on the exact frame the fatal jump
launched, so the jump that finally fired was a *standing* long jump, not
a *running* one, in an engine where running clears more horizontal
distance. New scalar `TakeoffParams.run_up_tiles = 4` (wider than the
launch distance, so B is already held by the time the jump itself fires):
`if graded_pit_response and distance_to_edge is not None and
distance_to_edge <= run_up_tiles: press_b = True`, overriding DNp09's own
output for exactly that stretch.

## 6. Validation: `win_attempt`, sigma=0, seed=0, max_frames=3000

`inject_gap_frame` cleared first (section 0). `graded_pit_response=True`:

- **The fatal pit at x=1360 is cleared** — `gap_width` runs 3 -> 2 -> 1 ->
  0 with `long_jump=True` firing well before the edge, matching section
  3-4's own design, not the old late/short-hold pattern.
- The run continues to **frame 1023, max_x_abs=1430** before dying again
  — NOT to a pit (`gap_width=0` for the entire tail) but to enemy contact
  (two active Goombas confirmed via the entity registry at the death
  frame). "Gap=0 for the entire tail" means the last ~8 frames; the
  cleared pit itself sits just before them. max_x_abs is 1430 vs the
  baseline's 1432 -- essentially the same peak reached by a very
  different path (14 escape jumps vs 9, qblock hits 19 vs 7), not
  investigated further here.
- **This is a partial result, reported as such**: the specific pit-
  timing failure this spec targeted is fixed and validated; the run does
  not reach the flag, because a second, unrelated failure mode (enemy
  contact) sits at nearly the same overall distance. Fixing that is out
  of this spec's scope.

## 7. Explicitly out of scope

Width prediction ahead of the refusal check (section 4's own limitation),
the enemy-contact death that now follows the cleared pit, any change to
`jump_cooldown_frames`/`jump_hold_frames`/`long_jump_hold_frames`
themselves (the sweep that motivated this spec already showed retuning
that knob alone doesn't help), and anything not listed above.
