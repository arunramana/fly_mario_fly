"""tool/ui/app.py -- QApplication + the project gate (cannot be skipped)
+ the main window (tool/PLAN.md P3).
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QDialog


def main(argv=None) -> int:
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("fly_mario")

    from tool.ui.gate import ProjectGateDialog

    gate = ProjectGateDialog()
    if gate.exec() != QDialog.DialogCode.Accepted or gate.selected_project is None:
        return 0

    from tool.ui.main_window import MainWindow

    window = MainWindow(gate.selected_project)
    window.show()
    return app.exec()
