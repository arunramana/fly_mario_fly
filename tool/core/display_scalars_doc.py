# What this file does, in plain English:
# Writes tool/SCALARS_UI.md, a table of every hand-picked DISPLAY-ONLY
# number in tool/core/display_params.py. Mirrors config/scalars_doc.py,
# for the tool's own scalars rather than the simulation's.
"""tool/core/display_scalars_doc.py -- generates tool/SCALARS_UI.md from
tool/core/display_params.py. tool/tests/test_display_scalars_doc.py fails
if the committed file differs.

    .venv/Scripts/python.exe -m tool.core.display_scalars_doc
"""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path

from tool.core.display_params import ALL_DISPLAY_PARAM_CLASSES, scalar_count

HEADER = """# Display scalars

Every hand-set, DISPLAY-ONLY scalar in the tool (never read by the
simulation -- see `tool/core/display_params.py`'s own docstring),
generated from that file. Regenerate after any change to it:

```
.venv/Scripts/python.exe -m tool.core.display_scalars_doc
```

`tool/tests/test_display_scalars_doc.py` fails if this file and
`tool/core/display_params.py` disagree. The simulation's own scalars are
tracked separately in `docs/SCALARS.md`, generated from
`config/params.py`.
"""


def generate() -> str:
    lines = [HEADER]
    total = 0
    for cls in ALL_DISPLAY_PARAM_CLASSES:
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
    lines.append(
        f"## Totals\n\n**{total} display-only scalars.** Two related values are "
        f"deliberately NOT here -- they duplicate an existing simulation "
        f"scalar and are read directly instead: `tool/core/palette.py`'s "
        f"Mario sprite width reads `config.entity.entity_width_px`; "
        f"`tool/ui/widgets/preview.py`'s TTMn bar max reads "
        f"`config.jump.spike_amp`.\n"
    )
    return "\n".join(lines)


SCALARS_MD_PATH = Path(__file__).parent.parent / "SCALARS_UI.md"

if __name__ == "__main__":
    SCALARS_MD_PATH.write_text(generate(), encoding="utf-8")
    print(f"wrote {SCALARS_MD_PATH}")
