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
