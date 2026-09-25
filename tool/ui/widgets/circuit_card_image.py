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

# In-memory cache alongside the on-disk one: every CircuitsTab build
# (main_window.py, or any test that constructs a MainWindow) calls this
# once per circuit, and disk-decoding the same 7 PNGs on every single
# construction measurably added up across a test suite that builds many
# MainWindows in a row (found running the full tool/tests suite: a
# previously reliable soft-timeout test started missing it) -- the same
# class of "reload a cheap, unchanging asset needlessly" cost CLAUDE.md's
# own run 026 already flagged for render/brain_panel.py's own _font().
_pixmap_cache: dict[str, QPixmap] = {}


def circuit_card_pixmap(entry: CircuitEntry) -> QPixmap:
    cached = _pixmap_cache.get(entry.circuit_id)
    if cached is not None:
        return cached

    if not entry.populations:
        pixmap = QPixmap(str(PLACEHOLDER_PATH))
        _pixmap_cache[entry.circuit_id] = pixmap
        return pixmap

    cache_path = GENERATED_DIR / f"{entry.circuit_id}.png"
    if cache_path.exists():
        pixmap = QPixmap(str(cache_path))
        if not pixmap.isNull():
            _pixmap_cache[entry.circuit_id] = pixmap
            return pixmap

    try:
        from PIL import ImageEnhance
        from render.brain_panel import highlight_populations
        # radius_scale=4: a sparse population (Speed=1 type, MDN=4
        # neurons) drawn at the real video's own dot size was all but
        # invisible once shrunk to a card-sized icon -- found reviewing
        # every card side by side, not every one actually showed
        # something. Dense populations (Mushroom body) already read fine
        # at 1x; a uniform 4x still reads as "cloud of dots," not
        # "blob," for those too.
        image = highlight_populations(list(entry.populations), radius_scale=4.0)
        # Ease-of-use redesign: "brighter highlight on a dark background"
        # for the card specifically -- render/brain_panel.py's own output
        # already maxes out per-soma alpha for a static highlight (shared
        # code that also feeds real run videos, so it isn't tuned for a
        # small card image); the boost lives here, tool-side only, and
        # never touches the shared rendering path. CONTRAST alone (no
        # flat brightness multiply): brightness lifted the dark ambient
        # background along with the highlight, washing the card into a
        # uniform grey instead of the punchier bright-dots-on-dark-field
        # look actually asked for -- contrast pushes already-dark pixels
        # darker and already-bright ones brighter, which is the same
        # operation in one step.
        image = ImageEnhance.Contrast(image).enhance(1.7)
        GENERATED_DIR.mkdir(parents=True, exist_ok=True)
        image.save(cache_path)
    except Exception:
        pixmap = QPixmap(str(PLACEHOLDER_PATH))
        _pixmap_cache[entry.circuit_id] = pixmap
        return pixmap

    pixmap = QPixmap(str(cache_path))
    if pixmap.isNull():
        pixmap = QPixmap(str(PLACEHOLDER_PATH))
    _pixmap_cache[entry.circuit_id] = pixmap
    return pixmap
