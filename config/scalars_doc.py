# What this file does, in plain English:
# Writes docs/SCALARS.md, a table of every hand-picked number listed in
# config/params.py, with counts of how many were invented or measured. Run it
# after changing params.py; a test (tests/test_scalars_doc.py) fails if the
# saved table no longer matches.
"""config/scalars_doc.py -- generates docs/SCALARS.md from config/params.py.
tests/test_scalars_doc.py fails if the committed file differs.

    .venv/Scripts/python.exe -m config.scalars_doc
"""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path

from config.params import ALL_PARAM_CLASSES, scalar_count

HEADER = """# Scalars

Every hand-set scalar in the system, generated from `config/params.py`.
Regenerate after any change to that file:

```
.venv/Scripts/python.exe -m config.scalars_doc
```

`tests/test_scalars_doc.py` fails if this file and `config/params.py`
disagree.
"""


_PROVENANCE_BUCKETS = ("invented", "measured", "connectome-derived")


def _provenance_split() -> dict[str, list[str]]:
    """Buckets every field by the first word of its provenance string, so
    there is no second, hand-maintained classification to drift."""
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
## Totals

**{total} hand-set scalars.** Three (`RetinotopyParams`) are dormant and one
(`DemoParams.mushroom_offset`) only matters in the opt-in injection demo;
the other {total - 4} are live in every default run.

A range of `unknown` means genuinely unknown, not left blank: an invented
bound would be scaffolding that looks like data. Only `JumpParams.g` and
`NoiseParams.sigma` have a characterised range.

By category (the first word of each provenance): {counts} (of {total}).{other_line}

None are connectome-derived. The connectome determines each circuit's
weight matrix `W`; every scalar here sits outside it, as a gain on it, a
threshold on its output, or a mechanical hold with no neural meaning.
"Measured" means simulated against the real `W` and picked by a sweep, or
matched to a published biological timescale.
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
            lines.append(f"| `{f.name}` | `{default}` | {rng_str} | {provenance} | `{home}` |")
        lines.append("")
    assert total == scalar_count(), "generator and scalar_count() disagree -- fix one"
    lines.append(_footer(total))
    return "\n".join(lines)


SCALARS_MD_PATH = Path(__file__).parent.parent / "docs" / "SCALARS.md"

if __name__ == "__main__":
    SCALARS_MD_PATH.write_text(generate(), encoding="utf-8")
    print(f"wrote {SCALARS_MD_PATH}")
