"""tool/ui/app.py -- QApplication + the project gate (cannot be skipped)
+ the main window (tool/PLAN.md P3). tool/SPEC_ui_retro.md section 5: the
retro theme (bundled font + tool/ui/style.qss) loads here, once, before
any widget is constructed.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase, QGuiApplication
from PySide6.QtWidgets import QApplication, QDialog

ASSETS_ROOT = Path(__file__).resolve().parent.parent / "assets"
STYLE_QSS_PATH = Path(__file__).resolve().parent / "style.qss"
FONT_PATH = ASSETS_ROOT / "fonts" / "PressStart2P-Regular.ttf"


REFERENCE_SCREEN_W = 1700   # logical px the QSS point sizes were tuned on (a 1080p-ish desktop)
MIN_FONT_SCALE = 0.8        # never shrink the pixel font below this: it turns illegible


def font_scale_for(available_width: int) -> float:
    """QSS sizes are logical px/pt, so Qt's own DPI handling already scales them with the
    display; what it can't know is that a laptop's *logical* screen is smaller. Shrink the
    point sizes in proportion (never grow them, never below MIN_FONT_SCALE)."""
    return max(MIN_FONT_SCALE, min(1.0, available_width / REFERENCE_SCREEN_W))


def _scale_points(stylesheet: str, scale: float) -> str:
    return re.sub(r"(\d+(?:\.\d+)?)pt\b", lambda m: f"{max(6.0, float(m.group(1)) * scale):.1f}pt", stylesheet)


def enable_high_dpi() -> None:
    """Must run before the QApplication exists. PassThrough keeps fractional Windows scaling
    (125%/150%) exact instead of rounding it to 100/200%, which is what made the laptop
    layout blow up."""
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)


def load_theme(app: QApplication) -> None:
    """Bundled, not system-installed (section 5): `QFontDatabase.
    addApplicationFont` before any widget exists, so the QSS's own
    `font-family: "Press Start 2P"` rule resolves regardless of what's
    installed on the machine running it. Missing font/QSS files (not
    supplied yet, or a partial checkout) degrade to Qt's own default
    widget style rather than crashing the whole app -- the same
    never-crash-on-a-missing-asset rule section 9's placeholder follows."""
    if FONT_PATH.exists():
        QFontDatabase.addApplicationFont(str(FONT_PATH))
    if STYLE_QSS_PATH.exists():
        from tool.ui import palette_colors
        stylesheet = STYLE_QSS_PATH.read_text(encoding="utf-8")
        for name in ("SKY_BLUE", "MARIO_RED", "LUIGI_GREEN", "BRICK_BROWN", "BLACK", "WHITE"):
            stylesheet = stylesheet.replace(f"@{name}@", getattr(palette_colors, name))
        screen = app.primaryScreen()
        if screen is not None:
            stylesheet = _scale_points(stylesheet, font_scale_for(screen.availableGeometry().width()))
        app.setStyleSheet(stylesheet)


def main(argv=None) -> int:
    enable_high_dpi()
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("fly_mario")
    load_theme(app)

    # Ease-of-use redesign: a Home button in the main window returns to
    # this same gate instead of quitting the app -- quitOnLastWindowClosed
    # would otherwise end the whole application the instant the main
    # window closes, before a new one gets a chance to open.
    app.setQuitOnLastWindowClosed(False)
    state: dict = {"window": None}

    def open_window(project) -> None:
        from tool.ui.main_window import MainWindow

        window = MainWindow(project)
        window.home_requested.connect(open_project)
        # "Duplicate to edit" on a read-only project (tool/core/
        # project.py): open the new project directly, skipping the gate
        # -- the user already said exactly which project they want.
        window.project_switch_requested.connect(open_window)
        state["window"] = window  # keep a live Python reference; app.py's
        # own module scope would otherwise let this get garbage-collected
        # out from under the C++ widget the instant this function returns
        window.show()

    def open_project() -> None:
        from tool.ui.gate import ProjectGateDialog

        gate = ProjectGateDialog()
        if gate.exec() != QDialog.DialogCode.Accepted or gate.selected_project is None:
            app.quit()
            return
        open_window(gate.selected_project)

    open_project()
    return app.exec()
