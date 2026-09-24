"""tool/ui/widgets/circuit_card_image.py -- tool/SPEC_ui_retro.md section
8: a circuit card's brain-map image, generated (not user-supplied) via
render.brain_panel.highlight_populations(), cached to
tool/assets/generated/<circuit_id>.png so it's built once per circuit,
not once per tab open. Falls back to the same placeholder.png as a
missing user-supplied asset (tool/ui/widgets/asset_image.py) if the
connectome annotation data isn't present on this machine (CLAUDE.md:
`../data/malecns_v1.0/` is gitignored, 1GB, not guaranteed to exist
wherever this GUI runs) -- a circuit card must never crash the tab it's
on just because the connectome data isn't downloaded here.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QPixmap

from tool.core.circuit_manifest import CircuitEntry
from tool.ui.widgets.asset_image import PLACEHOLDER_PATH

GENERATED_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "generated"


def circuit_card_pixmap(entry: CircuitEntry) -> QPixmap:
    if not entry.populations:
        return QPixmap(str(PLACEHOLDER_PATH))

    cache_path = GENERATED_DIR / f"{entry.circuit_id}.png"
    if cache_path.exists():
        pixmap = QPixmap(str(cache_path))
        if not pixmap.isNull():
            return pixmap

    try:
        from render.brain_panel import highlight_populations
        image = highlight_populations(list(entry.populations))
        GENERATED_DIR.mkdir(parents=True, exist_ok=True)
        image.save(cache_path)
    except Exception:
        return QPixmap(str(PLACEHOLDER_PATH))

    pixmap = QPixmap(str(cache_path))
    return pixmap if not pixmap.isNull() else QPixmap(str(PLACEHOLDER_PATH))
