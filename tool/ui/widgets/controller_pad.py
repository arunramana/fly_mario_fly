"""tool/ui/widgets/controller_pad.py -- a small NES-style pad (◀ ▶ B A) drawn
semi-transparent over the bottom strip of the Player's video. Each button
lights from the frame's telemetry (`direction`, `press_b`, `press_a`). A
child of the video canvas placed by absolute geometry and transparent to the
mouse, so showing or hiding it never changes the video's size.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPolygonF
from PySide6.QtWidgets import QWidget

_LIT = QColor(255, 220, 60, 235)
_DIM = QColor(255, 255, 255, 55)
_BODY = QColor(20, 20, 28, 120)


class ControllerPad(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setObjectName("controllerPad")
        self.left = self.right = self.b = self.a = False

    # ---- state -----------------------------------------------------------

    def state(self) -> tuple[bool, bool, bool, bool]:
        return self.left, self.right, self.b, self.a

    def set_state(self, direction, press_b, press_a) -> None:
        new = (direction == "L", direction == "R", bool(press_b), bool(press_a))
        if new != self.state():
            self.left, self.right, self.b, self.a = new
            self.update()

    def set_from_row(self, row) -> None:
        """`row`: a telemetry row (dict or Series) or None (nothing lit)."""
        if row is None:
            self.set_state(None, False, False)
            return
        self.set_state(row.get("direction"), row.get("press_b", False), row.get("press_a", False))

    # ---- drawing ---------------------------------------------------------

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_BODY)
        p.drawRoundedRect(QRectF(0, 0, w, h), h * 0.3, h * 0.3)
        s = h * 0.62                       # button size
        cy = h / 2
        # ◀ ▶ (a D-pad's left/right arms)
        for cx, lit, sign in ((w * 0.16, self.left, -1), (w * 0.34, self.right, 1)):
            p.setBrush(_LIT if lit else _DIM)
            p.drawRoundedRect(QRectF(cx - s / 2, cy - s / 2, s, s), s * 0.2, s * 0.2)
            p.setBrush(QColor(20, 20, 28, 230))
            tri = QPolygonF([QPointF(cx + sign * s * 0.22, cy), QPointF(cx - sign * s * 0.16, cy - s * 0.26),
                             QPointF(cx - sign * s * 0.16, cy + s * 0.26)])
            p.drawPolygon(tri)
        # B and A: the two round NES buttons, B left of A
        font = QFont()
        font.setBold(True)
        font.setPixelSize(max(8, int(s * 0.45)))
        p.setFont(font)
        for cx, lit, label in ((w * 0.66, self.b, "B"), (w * 0.84, self.a, "A")):
            p.setBrush(_LIT if lit else _DIM)
            p.drawEllipse(QRectF(cx - s / 2, cy - s / 2, s, s))
            p.setPen(QColor(20, 20, 28, 230))
            p.drawText(QRectF(cx - s / 2, cy - s / 2, s, s), Qt.AlignmentFlag.AlignCenter, label)
            p.setPen(Qt.PenStyle.NoPen)
        p.end()
