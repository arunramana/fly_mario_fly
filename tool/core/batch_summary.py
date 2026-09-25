"""tool/core/batch_summary.py -- one line summarising a finished batch
(ease-of-use redesign: "show the result line once" -- the Run tab's
former dedicated Batch sub-tab/label is gone, batch results go through
the same single result_label every other run outcome does). Cancelled
runs are excluded from the stats -- ground rule 4's "no control lies"
extends to the aggregate, not just the single run it came from.
"""

from __future__ import annotations


def format_batch_result(result) -> str:
    kept = [fit for fit, info in zip(result.fitnesses, result.infos) if not info.get("cancelled")]
    n_cancelled = len(result.fitnesses) - len(kept)
    if kept:
        mean = sum(kept) / len(kept)
        stats = f"mean fitness={mean:.1f}  min={min(kept):.1f}  max={max(kept):.1f}"
    else:
        stats = "no completed runs to summarise"
    cancelled_note = f"  ({n_cancelled} cancelled excluded)" if n_cancelled else ""
    return f"Batch: {len(result.fitnesses)} runs, {stats}{cancelled_note}"
