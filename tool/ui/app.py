"""tool/ui/app.py -- QApplication + the project gate (cannot be skipped)
+ the main window (tool/PLAN.md P3). tool/SPEC_ui_retro.md section 5: the
retro theme (bundled font + tool/ui/style.qss) loads here, once, before
any widget is constructed.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication, QDialog

ASSETS_ROOT = Path(__file__).resolve().parent.parent / "assets"
STYLE_QSS_PATH = Path(__file__).resolve().parent / "style.qss"
FONT_PATH = ASSETS_ROOT / "fonts" / "PressStart2P-Regular.ttf"


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
        app.setStyleSheet(stylesheet)


def main(argv=None) -> int:
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
