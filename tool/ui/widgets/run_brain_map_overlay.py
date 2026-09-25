"""tool/ui/widgets/run_brain_map_overlay.py -- Run tab / player redesign:
the Brain map overlay's content -- render.brain_panel.panel_for_row on
demand for the player's current frame, the same live per-frame render the
old drawer-based Brain map toggle used, now inside the Player's left edge
panel (tool/ui/widgets/run_edge_panel.py) instead of a side-by-side panel.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class BrainMapOverlayContent(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._panel_ctx = None
        self._tel = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._label = QLabel("(no run loaded)")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setScaledContents(False)
        layout.addWidget(self._label)

    def set_telemetry(self, tel) -> None:
        self._tel = tel
        if tel is not None and len(tel):
            from render.brain_panel import _panel_context
            self._panel_ctx = _panel_context(tel.fillna(0).reset_index(drop=True))
        else:
            self._panel_ctx = None

    def update_frame(self, frame: int) -> None:
        if self._panel_ctx is None or self._tel is None or not len(self._tel):
            self._label.setText("(no telemetry for this run)")
            return
        from render.brain_panel import panel_for_row
        tel_frame = min(frame, len(self._tel) - 1)
        image = panel_for_row(self._tel, tel_frame, self._panel_ctx)
        pixmap = _pil_to_pixmap(image)
        target = self.size() if self.size().width() > 1 else pixmap.size()
        self._label.setPixmap(pixmap.scaled(
            target, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))


def _pil_to_pixmap(image) -> QPixmap:
    arr = np.array(image.convert("RGB"))
    h, w, _ = arr.shape
    qimage = QImage(arr.tobytes(), w, h, 3 * w, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimage.copy())
