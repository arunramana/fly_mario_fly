# 029 — C8a validation: real vs. shuffled, default vs. modified profile (`029a_c8a_validation_real.mp4`, `029b_c8a_validation_shuffled.mp4`)

**Setup.** `docs/SPEC_entity_perception.md` section 5's 2×2 batch:
{real, shuffled (`shuffle_seed=1`)} × {default profile, modified profile},
8 seeds (0–7) per cell, level 1-1, 600 frames, `sigma=0.05`. Modified
profile: GOOMBA `danger_weight=2.0`, `intensity=1.4` (SPEC section 3's own
example). The two videos are both under the modified profile at seed 0
(`029a` real, `029b` shuffled) — the condition where a viewer can
actually see something different from a stock run. Full per-cell stats
in `029_c8a_validation_batch.json`.

**Prediction, stated before running anything (SPEC section 5).** C8a is
a gains-only change — no new wiring, the same DNa01/DNa02/LC4/LPLC2
populations as today just driven by different numbers. A gains-only
change shouldn't give the network anything new to discriminate with, so
the (modified − default) gap was predicted to be about the same size
under the real connectome and the shuffled one.

**What happened.** Batch fitness (`=max_x_abs`) means, survival rate, and
mean escape-jump-spike / odour-avoid counts per cell (n=8 seeds each):

| cell | fitness | survival | escape jumps | odour avoids |
|---|---|---|---|---|
| real / default | 876.0 (std 238.6) | 62.5% | 39.25 | 12.9 |
| real / modified | 519.0 (std 59.4) | 100% | 47.1 | 24.0 |
| shuffled / default | 285.0 (std 0.0) | **0%** | **0.0** | **0.0** |
| shuffled / modified | 660.5 (std 16.1) | 75% | 16.6 | 18.4 |

(modified − default) fitness gap: real = **−357.0**, shuffled =
**+375.5** — opposite sign, not just different magnitude.

**What we learned.** The prediction did **not** hold, and the reason is
visible directly in the table, not just in the fitness numbers:
**shuffled/default is a degenerate baseline, not a working-but-different
one.** All 8 seeds die at exactly the same x=285 (std=0.0) with zero
escape-jump spikes and zero odour avoids across every seed —
`shuffle_seed=1`'s jump/escape circuit appears non-functional for this
Goomba encounter, and `sigma=0.05`'s noise never perturbs the outcome at
all. Boosting GOOMBA's `danger_weight`/`intensity` doesn't compete with a
working escape response here; it rescues survival from a circuit that
wasn't escaping at all, by making the (separately-wired) steering
circuit's aversive odour strong enough to route Mario around the
encounter before the jump circuit would ever need to fire — hence
spikes/avoids both go from 0 to a real, non-zero mean, and survival jumps
from 0% to 75%.

Under the real connectome, by contrast, default is already a working,
escape-capable baseline (62.5% survival, real jump activity) — there,
the same profile change trades distance for caution (more avoidance,
lower mean fitness, but 100% survival), the ordinary caution/speed
tradeoff one would expect from a stronger threat signal.

So the honest finding isn't "the connectome amplifies the gain
non-linearly" in general — it's narrower and more mundane: **the two
connectomes started this comparison in qualitatively different regimes**
(one with a working escape reflex, one without, at this specific
`shuffle_seed`), so the same absolute gain change produces different,
even oppositely-signed, absolute effects on fitness. This is still a
real result C8a's own design didn't anticipate (section 5 assumed
comparable baselines), and it's a useful caution against using a single
arbitrary `shuffle_seed` as "the" shuffled control: a different
`shuffle_seed` might land on a functioning escape circuit and tell a
different story. A follow-up sweeping several shuffle seeds, not just
one, would separate "shuffled connectomes generically respond
differently to gains" from "this particular rewiring happened to break
one pathway."

---

## 029, follow-up -- sweeping 8 shuffled networks instead of 1

**Setup.** Same design as the section above, but `{real, shuffled shuffle_seed=1..8} x {default, modified profile}`, still 8 run seeds per cell, level 1-1, 600 frames, sigma=0.05, same modified profile (GOOMBA danger_weight=2.0, intensity=1.4). Answers the question the first section's finding raised: was `shuffle_seed=1`'s non-engaging jump circuit a one-off draw, or the common case? No new videos -- the original two already show what a viewer can see. Full per-network stats in `029_c8a_validation_sweep.json`.

**"Never engages" defined.** Under the default profile, zero escape-jump spikes across all 8 run seeds for that network (the same signature `shuffle_seed=1` showed originally: 0% survival, 0 spikes, 0 variance).

**What happened.**

**7/8 shuffled networks never engaged their jump circuit under the default profile (fraction=0.88) by the strict "any spike at all" criterion -- and the 8th (`shuffle_seed=6`) is a boundary case, not a real counterexample** (see below).

| shuffle_seed | escape-jump spikes (mean/8 seeds) | default survival | default fitness | modified fitness | (modified-default) gap |
|---|---|---|---|---|---|
| 1 | 0.0 | 0% | 285.0 | 660.5 | 375.5 |
| 2 | 0.0 | 0% | 285.0 | 285.0 | 0.0 |
| 3 | 0.0 | 0% | 285.0 | 285.0 | 0.0 |
| 4 | 0.0 | 0% | 285.0 | 285.0 | 0.0 |
| 5 | 0.0 | 0% | 285.0 | 285.0 | 0.0 |
| 6 | 0.125 (1 spike, 1 of 8 seeds) | 0% | 285.0 | 285.0 | 0.0 |
| 7 | 0.0 | 0% | 285.0 | 598.6 | 313.6 |
| 8 | 0.0 | 0% | 285.0 | 285.0 | 0.0 |

**The more striking result is in that table, not just the fraction: every one of the 8 shuffled networks -- regardless of which specific rewiring -- dies at the exact same x=285 under the default profile, at 0% survival.** This is not "one bad rewiring" (the original 029 section's `shuffle_seed=1` finding); it looks like the general case for shuffled connectomes at this level/frame-count/sigma setting. `shuffle_seed=6`'s single incidental spike (1 of 64 run-seed-frames' worth of episodes) doesn't change its outcome at all -- same 0% survival, same x=285, same zero profile effect as the networks with literally zero spikes -- so calling it "engaged" by a strict >0 threshold overstates what actually happened; functionally, all 8 tested networks show no working escape response under the default profile.

Profile effect (modified - default fitness), as requested:

- real: -357.0 (within-network seed std: default=238.6, modified=59.4)
- "engaging" shuffled networks by the strict criterion (1/8, `shuffle_seed=6` only): mean=0.0, std-across-networks=0.0 (undefined with n=1 -- **not a meaningful comparison group**, see below)

**What we learned.** The requested real-vs-engaging-shuffled comparison isn't answerable from this sample the way it was posed: with a strict "any spike" criterion exactly one network qualifies, and that one network (`shuffle_seed=6`) is a boundary case whose single spike didn't change its outcome in any way -- it behaves identically to the zero-spike networks. There is no shuffled network in this sample of 8 with a real, functioning escape response to compare against the real connectome's own effect.

That absence is itself the finding, and a bigger one than "engaging vs. non-engaging spread": **a working jump/escape circuit looks like the exception for a shuffled connectome here, not the rule** -- 8/8 sampled networks fail identically (same death point, same 0% survival) regardless of the specific random rewiring, which is a stronger and cleaner result than the original section's single-seed finding suggested (that finding undersold it by leaving open the possibility `shuffle_seed=1` was just an unlucky draw). Second, among these non-functioning networks, the profile boost's rescue-via-steering effect (SPEC section 1's separate odour pathway, no jump circuit needed) is itself inconsistent: 2 of 8 networks (`shuffle_seed=1`, `shuffle_seed=7`) are substantially rescued (+375.5, +313.6 fitness), the other 6 are not moved at all (gap=0.0). So even the "does the odour-only rescue work" question doesn't have a uniform answer across shuffled rewirings -- it depends on the specific network, same as everything else about the shuffled condition in this validation. A real follow-up here isn't sweeping more shuffle seeds (this sample already shows the pattern clearly) -- it's asking why the jump circuit fails so consistently across random rewirings when the same level/encounter is entirely survivable by the real connectome, which is a question about the jump circuit's sensitivity to its specific wiring, not about C8a's own per-kind gains.

---

## 029, addendum -- the shared-gain caveat this section's own conclusion needs

Checked 2026-09-24 (`docs/PROPOSAL_c5_gain_calibration.md`, not built):
`scripts/shuffle_sweep.py`/`scripts/compare_controllers.py` re-tune the
jump circuit's gain per shuffled network via Diagnostic-4 -- using the
real circuit's gain on an untuned shuffle "answers nothing about the
wiring" (that script's own words). The sweep above used `config.jump.g`
(2.0) unchanged for every one of the 8 shuffled networks, exactly the
comparison that warning is about.

Existing (stale, dated 2026-09-19, needs a fresh run) results in
`projects/legacy/telemetry/shuffle_sweep_results.json` show `shuffle_seed`
1, 6, and 7 need `g=3.0`, not the `2.0` used here -- so those three
networks' "died at x=285 with zero jump activity" result may simply be
under-driven, not evidence of a non-functional escape pathway. But
`shuffle_seed` 3, 4, 5, and 8 have **no confirmed g at any tested value**,
and `shuffle_seed=2`'s own confirmed g was already exactly 2.0 (what was
used here) and it still died identically -- so gain mismatch is a real,
partial confound for this section's "8/8 fail identically" conclusion,
not a full explanation of it. See `docs/PROPOSAL_c5_gain_calibration.md`
for the design that would separate the two populations cleanly (not
built).
