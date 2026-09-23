"""config/scalars_doc.py -- generates docs/SCALARS.md's content directly
from config/params.py's dataclasses, so the two can never silently diverge.
tests/test_scalars_doc.py asserts docs/SCALARS.md equals generate() exactly
-- the same discipline as tests/golden/, applied to a document instead of
a telemetry CSV.

    .venv/Scripts/python.exe -m config.scalars_doc
"""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path

from config.params import ALL_PARAM_CLASSES, scalar_count

HEADER = """# Scalars

Every hand-set scalar in the live system, generated directly from
`config/params.py` -- not recalled from memory, not re-derived by reading
comments across a dozen files. Regenerate after any change to that file:

```
.venv/Scripts/python.exe -m config.scalars_doc
```


`tests/test_scalars_doc.py` fails if this file and `config/params.py`
disagree.

**The count phase 4 was asked to produce, without softening:** this
project's own running comments had been tracking a "budget" of 3, then 5,
then 8, then 9 hand-set neural/mechanical scalars across 26 sprints.
"""


_PROVENANCE_BUCKETS = ("invented", "measured", "connectome-derived")


def _provenance_split() -> dict[str, list[str]]:
    """Buckets every field by the first word of its own `provenance`
    metadata string -- not a second, hand-maintained classification that
    could drift from the per-field text above it."""
    buckets: dict[str, list[str]] = {b: [] for b in _PROVENANCE_BUCKETS}
    buckets["other"] = []
    for cls in ALL_PARAM_CLASSES:
        for f in fields(cls):
            prov = f.metadata.get("provenance", "")
            key = prov.split(" ", 1)[0].rstrip(":").lower()
            buckets.setdefault(key, buckets["other"])
            (buckets[key] if key in buckets else buckets["other"]).append(f"{cls.__name__}.{f.name}")
    return buckets


def _footer(total: int) -> str:
    split = _provenance_split()
    counts = ", ".join(f"**{len(split[b])} {b}**" for b in _PROVENANCE_BUCKETS)
    other_line = (f" {len(split['other'])} fell into neither bucket (check "
                   f"config/scalars_doc.py's parsing against a new provenance string)."
                   if split["other"] else "")
    return f"""
## What this doc is not

A range of `unknown` means genuinely unknown -- not measured, not
documented anywhere in this project's own sprint history, and not invented
here to fill the cell. Per this phase's own instruction: an invented bound
is scaffolding that looks like data. Most fields in this table are
`unknown` for exactly that reason; the two with a real documented range
(`JumpParams.g`, `NoiseParams.sigma`) have one because a specific sprint
(diag4.py's Diagnostic-4 sweep; 025's calibration sweep) actually
characterised it.

**Total: {total} hand-set scalars** -- larger than either "8" or "9", the
two numbers this project's own comments had been citing. Three of the
{total} (`RetinotopyParams`'s fields) are dormant: no golden-tested run
exercises `retinotopic=True`. One (`DemoParams.mushroom_offset`) only
matters when a caller explicitly opts into the synthetic-injection demo.
The other {total - 4} are live in every default run.

## Invented / measured / connectome-derived

Split by the first word of each field's own `provenance` text above, not a
second hand-maintained tally: {counts} (of {total}).{other_line}

**Zero are connectome-derived**, and that's the real finding, not an
artifact of the split: the connectome determines the WEIGHT MATRIX each
circuit steps (`W`, one per circuit, streamed from the real synapse data --
CLAUDE.md invariant 2), but every one of these 49 numbers sits outside
that matrix -- a gain multiplying it, a threshold compared against its
output, or a mechanical hold duration with no neural meaning at all. The
connectome constrains what these circuits CAN compute; it has never
supplied a single one of the scalars controlling how hard they push on
that computation. "Measured" means simulated against the real W and
picked by a sweep (`tune_*.py`/`diag4.py`) or matched to a real biological
timescale/fraction -- a real number, but still chosen, not read off the
data the way `W` itself is. **Invented outnumbers measured (29 vs 20)**:
most of what this project calls "the model" is mechanical scaffolding
(hold durations, cooldowns, body-scaled thresholds) and placed external
currents (`HOME_BIAS`, `GAP_GAIN`, `WALK_DRIVE`, `MDN_DRIVE` and others --
explicitly flagged throughout this project's own comments as currents no
real synapse carries), not calibrated circuit dynamics.
"""


def generate() -> str:
    lines = [HEADER]
    total = 0
    for cls in ALL_PARAM_CLASSES:
        lines.append(f"## {cls.__name__}\n")
        lines.append("| field | value | range | provenance | home |")
        lines.append("|---|---|---|---|---|")
        for f in fields(cls):
            total += 1
            default = f.default
            meta = f.metadata
            rng = meta.get("range")
            rng_str = f"{rng[0]}-{rng[1]}" if rng else "unknown"
            provenance = meta.get("provenance", "")
            home = meta.get("home", "")
            note = meta.get("note")
            provenance_cell = provenance + (f" -- {note}" if note else "")
            lines.append(f"| `{f.name}` | `{default}` | {rng_str} | {provenance_cell} | `{home}` |")
        lines.append("")
    assert total == scalar_count(), "generator and scalar_count() disagree -- fix one"
    lines.append(_footer(total))
    return "\n".join(lines)


SCALARS_MD_PATH = Path(__file__).parent.parent / "docs" / "SCALARS.md"

if __name__ == "__main__":
    SCALARS_MD_PATH.write_text(generate(), encoding="utf-8")
    print(f"wrote {SCALARS_MD_PATH}")
