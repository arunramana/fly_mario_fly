"""tool/ui/screen_fit.py -- size the main window to the screen it is on.

Everything here works in Qt *logical* pixels (already divided by the
Windows DPI scale), so a 150%-scaled laptop and a 100% external monitor
both get "90% of what is actually available" without any pixel constants.
"""

from __future__ import annotations

from PySide6.QtCore import QRect, QSettings
from PySide6.QtGui import QGuiApplication, QScreen
from PySide6.QtWidgets import QWidget

OPEN_FRACTION = 0.9
MIN_WINDOW = (1024, 640)   # the ceiling for any hard minimum: below this the tabs scroll

_SETTINGS = QSettings("fly_mario", "main_window")


def screen_for(widget: QWidget) -> QScreen:
    screen = widget.screen() if widget is not None else None
    return screen or QGuiApplication.primaryScreen()


def centered_fraction(available: QRect, fraction: float = OPEN_FRACTION) -> QRect:
    w, h = int(available.width() * fraction), int(available.height() * fraction)
    return QRect(available.x() + (available.width() - w) // 2,
                 available.y() + (available.height() - h) // 2, w, h)


def clamp_to(available: QRect, rect: QRect) -> QRect:
    """`rect` shrunk to fit inside `available`, then slid back inside it."""
    w, h = min(rect.width(), available.width()), min(rect.height(), available.height())
    x = min(max(rect.x(), available.x()), available.right() + 1 - w)
    y = min(max(rect.y(), available.y()), available.bottom() + 1 - h)
    return QRect(x, y, w, h)


def apply_initial_geometry(window: QWidget, settings: QSettings | None = None) -> None:
    """Restore the saved geometry clamped to the current screen, or open at 90% centered."""
    settings = settings if settings is not None else _SETTINGS
    available = screen_for(window).availableGeometry()
    window.setMinimumSize(min(MIN_WINDOW[0], available.width()), min(MIN_WINDOW[1], available.height()))
    saved = settings.value("geometry")
    rect = saved if isinstance(saved, QRect) and saved.isValid() else None
    window.setGeometry(clamp_to(available, rect) if rect else centered_fraction(available))


def save_geometry(window: QWidget, settings: QSettings | None = None) -> None:
    (settings if settings is not None else _SETTINGS).setValue("geometry", window.geometry())
