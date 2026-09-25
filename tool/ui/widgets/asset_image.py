"""tool/ui/widgets/asset_image.py -- tool/SPEC_ui_retro.md section 9: the
ONE place card image loading happens. Every card loads through
load_asset(asset_id), never opens a file path directly -- an id the
manifest doesn't have, a manifest entry naming a file that isn't actually
on disk, or a corrupt image file all fall back to the same
placeholder.png rather than a crash or a blank card.
"""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

ASSETS_ROOT = Path(__file__).resolve().parent.parent.parent / "assets"
MANIFEST_PATH = ASSETS_ROOT / "manifest.json"
PLACEHOLDER_PATH = ASSETS_ROOT / "placeholder.png"

_manifest_cache: dict | None = None


def _manifest() -> dict:
    global _manifest_cache
    if _manifest_cache is None:
        _manifest_cache = (
            json.loads(MANIFEST_PATH.read_text(encoding="utf-8")) if MANIFEST_PATH.exists() else {}
        )
    return _manifest_cache


# Card icons render at up to 96px, but NES sprites are ~16px, and QIcon never
# scales an image *up*. Enlarge small sources by a whole-number factor with
# nearest-neighbour sampling so pixel art stays crisp instead of tiny or blurry.
_MIN_CARD_PX = 128


def _upscale_pixel_art(pixmap: QPixmap) -> QPixmap:
    longest = max(pixmap.width(), pixmap.height())
    factor = _MIN_CARD_PX // longest if longest else 1
    if factor <= 1:
        return pixmap
    return pixmap.scaled(pixmap.width() * factor, pixmap.height() * factor,
                         Qt.AspectRatioMode.IgnoreAspectRatio,
                         Qt.TransformationMode.FastTransformation)


def load_asset(asset_id: str) -> QPixmap:
    rel_path = _manifest().get(asset_id)
    if rel_path:
        path = ASSETS_ROOT / rel_path
        if path.exists():
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                return _upscale_pixel_art(pixmap)
    return QPixmap(str(PLACEHOLDER_PATH))
