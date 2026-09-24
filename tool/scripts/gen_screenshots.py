"""tool/scripts/gen_screenshots.py -- regenerates tool/README.md's
screenshots via widget.grab() (tool/PLAN.md P7). Not part of the test
suite; run manually (`python -m tool.scripts.gen_screenshots` from the
repo root) whenever the GUI's look changes enough to be worth
re-capturing. Needs a real Qt platform with font rendering -- the
offscreen QPA platform tool/tests runs under has no fonts and produces
tofu-box text, so this does NOT set QT_QPA_PLATFORM=offscreen itself.
"""
from __future__ import annotations

import dataclasses
import shutil
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication

from config.output_routing import PROJECTS_ROOT

PROJECT_NAME = "_screenshot_gen"


def main() -> None:
    root = PROJECTS_ROOT / PROJECT_NAME
    shutil.rmtree(root, ignore_errors=True)

    app = QApplication.instance() or QApplication([])
    from tool.core.project import ToolProject
    from tool.ui.main_window import MainWindow

    project = ToolProject.create(PROJECT_NAME)
    window = MainWindow(project)
    window.resize(1100, 800)
    window.show()
    app.processEvents()

    screenshots_dir = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    window.tabs.setCurrentIndex(0)  # Character
    app.processEvents()
    window.grab().save(str(screenshots_dir / "character_tab.png"))

    window.tabs.setCurrentIndex(3)  # Circuits
    app.processEvents()
    window.grab().save(str(screenshots_dir / "circuits_tab.png"))

    window.tabs.setCurrentIndex(6)  # Run
    app.processEvents()

    project.config = dataclasses.replace(
        project.config, scenario=dataclasses.replace(project.config.scenario, max_frames=200))
    project.save()
    window.play()
    deadline = time.time() + 60
    while window._process is not None and window._process.is_alive() and time.time() < deadline:
        app.processEvents()
        time.sleep(0.05)
    app.processEvents()
    window.grab().save(str(screenshots_dir / "run_tab.png"))

    window.save()
    shutil.rmtree(root, ignore_errors=True)
    print("wrote screenshots to", screenshots_dir)


if __name__ == "__main__":
    main()
