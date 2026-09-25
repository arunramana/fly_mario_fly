"""tool/ui/widgets/card_button.py -- ease-of-use redesign: one shared
"picture card" button -- image on top, caption below, wraps to fit --
used by the character, entity and circuit card grids instead of each
tab hand-rolling its own QPushButton layout. A plain QPushButton puts its
icon and text side by side, competing for the same horizontal space; a
card's own name (some of them long -- "Mushroom body", "Question Block")
needs the width QPushButton would give the icon, so this is a QToolButton
with `ToolButtonTextUnderIcon` instead.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QToolButton


def make_card_button(text: str, pixmap: QPixmap, icon_px: int, tooltip: str | None = None) -> QToolButton:
    button = QToolButton()
    button.setCheckable(True)
    button.setAutoExclusive(False)  # callers that want exclusivity manage it themselves (a card GRID, not radios)
    button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
    button.setIcon(pixmap)
    button.setIconSize(QSize(icon_px, icon_px))
    button.setText(text)
    button.setToolTip(tooltip if tooltip is not None else text)
    # Generous width: text wraps under the icon rather than clipping, but
    # the button still needs to be at least as wide as its own longest
    # word (Qt's own word-wrap won't split "Mushroom" mid-word).
    button.setMinimumSize(icon_px + 24, icon_px + 56)
    button.setMaximumWidth(icon_px + 80)
    return button
