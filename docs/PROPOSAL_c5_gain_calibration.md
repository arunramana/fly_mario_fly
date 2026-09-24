# Proposal: per-network gain calibration for C5's shuffled control

**Status: proposal only, not built, per explicit instruction.** This
document answers "how do `scripts/shuffle_sweep.py` and `scripts/
compare_controllers.py` set the gain for a shuffled network" and, since
the answer is "they re-tune it per network," proposes what C5's own
`shuffle_seed` control would need to do the same. Nothing here has been
implemented; `bridge/full_policy.py`'s `shuffle_seed` still uses the
real circuit's own gains for every shuffle, unchanged.

## 1. What the existing scripts actually do

**`scripts/shuffle_sweep.py`'s own docstring states the principle
directly**: "n=20 shuffles, each tuned with the SAME Diagnostic-4
procedure the real circuit got. Matched procedure, not matched
parameter -- g=2.0 was selected FOR the real circuit; handing it to a
shuffle would compare a tuned network to an untuned one, which answers
nothing about the wiring."

Procedure (`find_g`/`screen`/`confirm` in that file): for the real
circuit and each of 20 shuffled rewirings (`circuit.build_shuffled(...,
seed=0..19)`), search a coarse grid of `g` values
(`[0.05, 0.1, 0.2, 0.4, 0.7, 1.0, 1.5, 2.0, 3.0, 4.5, 7.0, 11.0, 17.0,
25.0]`) with a short Diagnostic-4 trace (`screen`), then confirm the
smallest passing candidate against the full-length trace (`confirm`,
`>=2000` frames, SPEC's own minimum). A network with no confirmed `g` at
any grid value is recorded as `null` -- an explicitly anticipated,
informative outcome, not an error.

**`scripts/compare_controllers.py`** reads `shuffle_sweep.py`'s own
output (`projects/legacy/telemetry/shuffle_sweep_results.json`) and
picks the best-*performing* confirmed shuffle by live play
(`pick_best_shuffle`), using **that network's own confirmed `g`**, never
the real circuit's. Its docstring: "same g/thresholds as A -- only the
wiring changes" describes controller A (real) vs. C (a hand-tuned
baseline), not the shuffle -- the shuffle explicitly gets its own tuned
value.

**Scope note**: both scripts tune only the jump circuit's `g`, via
`fly.connectome.load_cached.load` -- the exact same loader
`bridge/full_policy.py` uses for its own jump circuit
(`from fly.connectome.load_cached import load as load_jump`). So a
shuffled `W` built by `circuit.build_shuffled(..., seed=N)` is identical
between the two pathways, and `shuffle_sweep.py`'s existing confirmed-`g`
values are directly meaningful for `FullPolicy`'s jump circuit at the
same seed -- they don't need re-deriving from scratch, only re-running
fresh (see section 4's caveat) and extending to `FullPolicy`'s other five
circuits if those turn out to matter too (section 2).

## 2. Why this matters now, not hypothetically

`projects/legacy/telemetry/shuffle_sweep_results.json` (committed
2026-09-23, generated earlier -- see section 4's staleness caveat) already
has confirmed-`g` results for shuffle seeds 0-8, which line up directly
with the `shuffle_seed=1..8` used in `029_c8a_validation.md`'s sweep:

| seed | confirmed `g` | `029`'s finding at `jump.g=2.0` (the real circuit's value) |
|---|---|---|
| 1 | **3.0** | died at x=285, 0% survival, 0 escape-jump spikes |
| 2 | 2.0 | died at x=285, 0% survival, 0 escape-jump spikes |
| 3 | **None (no `g` passes at all)** | died at x=285, 0% survival, 0 escape-jump spikes |
| 4 | **None** | died at x=285, 0% survival, 0 escape-jump spikes |
| 5 | **None** | died at x=285, 0% survival, 0 escape-jump spikes |
| 6 | **3.0** | died at x=285, 0% survival, 1 spike in 1/8 seeds |
| 7 | **3.0** | died at x=285, 0% survival, 0 escape-jump spikes |
| 8 | **None** | died at x=285, 0% survival, 0 escape-jump spikes |

This directly and partially explains `029`'s finding: three of the eight
networks (1, 6, 7) needed **twice** the real circuit's gain
(`g=3.0` vs. `2.0`) to pass Diagnostic-4 at all, so testing them at
`g=2.0` (what C5's `shuffle_seed` actually does today) under-drives their
jump circuit -- consistent with, though not proof of, why they never
escape. But it does **not** fully explain it: seed 2 was already at its
own confirmed `g=2.0`, identical to what `029` used, and it *still* died
identically at x=285 with zero jump activity. And four of the eight (3,
4, 5, 8) have **no confirmed `g` at any tested value** -- for those, no
amount of jump-circuit gain retuning would help; Diagnostic-4 itself says
the rewiring can't pass regardless of drive strength, a different and
deeper claim than "wrong gain."

So the honest updated picture is: **gain mismatch explains some but not
all of `029`'s degenerate networks.** Re-running the comparison with each
shuffle at its own properly confirmed gain (or its own confirmed
non-existence of one) would separate these two populations cleanly,
which the current, single-shared-gain C5 cannot do.

## 3. Proposed design (not built)

1. **Scope to the jump circuit first**, not all six of `FullPolicy`'s
   circuits at once. It's the one this project already has a proven
   Diagnostic-4-based tuning procedure for (`scripts/diag4.py`,
   `scripts/shuffle_sweep.py`), it's the pathway `029`'s finding
   implicates directly (zero escape-jump spikes), and re-tuning all six
   circuits' own gain scalars (`steering`, `speed`/`dnp09`, `mdn`,
   `dnp02`, `mushroom_body`) per shuffled network -- each of which has its
   own hand-set gain in `config/params.py` -- is a substantially larger
   effort with no existing procedure or pass/fail criterion analogous to
   Diagnostic-4 for any of them. Extend to the others only if a
   jump-circuit-only calibration still leaves a shuffled network
   behaving suspiciously (e.g. it escapes fine but never steers).
2. **Reuse, don't reinvent, the screen/confirm procedure.**
   `scripts/shuffle_sweep.py`'s `find_g` already does exactly the search
   needed; it would run against `_load_maybe_shuffled("jump", load_jump,
   shuffle_seed, N=60)`'s own `W` (confirmed identical to
   `shuffle_sweep.py`'s own loader in section 1) rather than being
   re-derived. Concretely: a new script (e.g.
   `scripts/calibrate_shuffle_gains.py`) that, for a list of
   `shuffle_seed` values, runs `find_g` and writes a
   `{shuffle_seed: confirmed_g_or_null}` cache -- structurally the same
   output shape `shuffle_sweep_results.json` already has, just keyed to
   match `FullPolicy`'s own `shuffle_seed` parameter directly (an int)
   rather than a `"shuffleNN"` string.
3. **Cache, never compute live.** `shuffle_sweep.py`'s own profiling:
   one full Diagnostic-4 confirm call costs ~20s; screening 14 grid
   values with a shorter trace first keeps the *total* per-network cost
   well under that naively-multiplied worst case, but it's still on the
   order of tens of seconds to a couple of minutes per network -- clearly
   a precompute-and-cache step, not something `FullPolicy.__init__` (or
   the GUI's Play button) can do per run. A `shuffle_seed` with no cached
   entry should either fail loudly (this project's own stated preference
   for "fail loudly rather than silently default") or trigger an
   explicit, separate calibration step -- not a silent, unfair fallback
   to the real circuit's gain.
4. **A `None`/unconfirmed result is a valid, load-bearing outcome, not a
   failure to work around.** Per section 2, several shuffled networks
   may have no jump-circuit gain that passes Diagnostic-4 at all. Those
   networks are genuinely, structurally incapable at the jump circuit
   regardless of drive strength -- a real finding about that specific
   rewiring, and any run using such a `shuffle_seed` should say so
   plainly (matching `shuffle_sweep.py`'s own convention of recording
   `g: null` rather than silently falling back).
5. **Wire it into `FullPolicy` as an override, same shape as everything
   else in this project**: `FullPolicy(shuffle_seed=N, shuffle_jump_g=
   <looked up or explicit>)`, defaulting to `None` -- meaning "use
   `config.jump.g` unchanged," today's exact behavior -- so this stays
   additive and opt-in, the same bar every other C-numbered control here
   has cleared. `tool/core/tool_settings.py`'s `CircuitSettings` would
   gain a parallel `shuffle_jump_g: float | None` (or a lookup keyed by
   `shuffle_seed`, read from a small cache file) for the GUI's Circuits
   tab.

## 4. A caveat before trusting the section 2 numbers operationally

`shuffle_sweep_results.json`'s own `real` entry reports a confirmed
`g=1.5`, not `2.0` -- the value `config/params.py`'s own `jump.g` field
currently ships and cites as "measured (scripts/diag4.py Diagnostic-4
sweep against the real 1255-neuron subgraph...)". Both numbers fall
inside `jump.g`'s own documented robust range (`1.12-3.35`), so they
aren't necessarily contradictory (the smallest-passing-value-on-a-coarse-
grid `shuffle_sweep.py` reports isn't the same question as whatever
specific, later diag4.py run picked `2.0`), but it does mean this
specific results file predates the currently-shipped `jump.g` and should
be **re-run fresh** (`.venv/Scripts/python.exe -m scripts.shuffle_sweep`,
~cheap relative to a full 21-network x full-grid sweep per its own
docstring) before any of section 2's specific `g` values are used to
build a calibration cache -- the *qualitative* finding (heterogeneous
per-network gains, several confirmed-nonexistent) is solid regardless;
the *exact* numbers are not guaranteed current.

## 5. Recommendation

Worth doing, and before drawing further conclusions from any C5
comparison, including `029`'s own: right now, every shuffled-connectome
run this project has recorded (C5's tests, C8a's validation) compares a
tuned real circuit against an untuned shuffled one, which is exactly the
comparison `shuffle_sweep.py`'s own docstring says "answers nothing about
the wiring." A jump-circuit-only calibration (section 3, items 1-2) is a
small, scoped, reusable-procedure effort that would let `029`'s
conclusion ("a working escape circuit looks like the exception, not the
rule, for a shuffled connectome here") be re-tested on a level footing --
possibly confirming it, possibly revealing it was mostly an artifact of
the shared gain. Either outcome is more informative than the current
uncalibrated state, and it directly answers the "is the C5 control fair"
question `tool/PLAN.md`'s status header now flags as open.
