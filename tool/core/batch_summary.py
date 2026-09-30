"""tool/core/batch_summary.py -- one line summarising a finished batch
(ease-of-use redesign: "show the result line once" -- the Run tab's
former dedicated Batch sub-tab/label is gone, batch results go through
the same single result_label every other run outcome does). Cancelled
runs are excluded from the stats -- ground rule 4's "no control lies"
extends to the aggregate, not just the single run it came from.
"""

from __future__ import annotations


def format_batch_result(result) -> str:
    from tool.core.evaluation import wilson_ci
    kept = [fit for fit, info in zip(result.fitnesses, result.infos) if not info.get("cancelled")]
    n_cancelled = len(result.fitnesses) - len(kept)
    if kept:
        mean = sum(kept) / len(kept)
        stats = f"mean fitness={mean:.1f}  min={min(kept):.1f}  max={max(kept):.1f}"
    else:
        stats = "no completed runs to summarise"
    cancelled_note = f"  ({n_cancelled} cancelled excluded)" if n_cancelled else ""
    done = [i for i in result.infos if not i.get("cancelled")]
    wins = sum(1 for i in done if i.get("flag_get"))
    lo, hi = wilson_ci(wins, len(done))
    rate = f"  wins {wins}/{len(done)} (95% CI {100 * lo:.0f}-{100 * hi:.0f}%)" if done else ""
    return f"Batch: {len(result.fitnesses)} runs, {stats}{rate}{cancelled_note}"


BATCH_COLUMNS = ("seed", "max_x", "flag", "frames", "stomps", "escape jumps")


def entries_in_batch(entries: list[dict], batch_id: str | None) -> list[dict]:
    """The recorded runs sharing one batch_id, in seed order (none for a plain run)."""
    if not batch_id:
        return []
    return sorted((e for e in entries if e.get("batch_id") == batch_id), key=lambda e: (e.get("seed", 0), e["number"]))


def batch_rows(batch_entries: list[dict]) -> list[tuple]:
    """One (seed, max_x, flag, frames, stomps, escape jumps) row per run."""
    rows = []
    for e in batch_entries:
        s = e.get("summary", {})
        rows.append((e.get("seed"), s.get("max_x_abs"), bool(s.get("flag_get")), s.get("n_frames"),
                     s.get("n_stomps"), s.get("n_escape_jumps")))
    return rows


def batch_stats(rows: list[tuple]) -> tuple[int, int, float | None]:
    """(wins, runs, mean max_x): a win is reaching the flag."""
    xs = [r[1] for r in rows if isinstance(r[1], (int, float))]
    return sum(1 for r in rows if r[2]), len(rows), (sum(xs) / len(xs) if xs else None)
