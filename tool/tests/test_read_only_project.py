"""tool/core/project.py's READ_ONLY_PROJECT_NAMES ("legacy" today): found
live, editing the shared reference project in place through the GUI
silently drifted a scalar (habituation.hab_give_up, 3 -> -2) with no
record of when or why. The banner + disabled controls + duplicate-to-edit
flow are what actually prevent that from happening again.
"""
from __future__ import annotations

import pytest

from tool.core.project import ToolProject


def test_legacy_is_read_only():
    project = ToolProject.open("legacy")
    assert project.is_read_only is True


def test_legacy_save_raises():
    project = ToolProject.open("legacy")
    with pytest.raises(PermissionError):
        project.save()


def test_a_normal_project_is_not_read_only(qtbot):
    import shutil
    from config.output_routing import PROJECTS_ROOT

    name = "_read_only_test_normal"
    shutil.rmtree(PROJECTS_ROOT / name, ignore_errors=True)
    project = ToolProject.create(name)
    try:
        assert project.is_read_only is False
        project.save()  # must not raise
    finally:
        shutil.rmtree(PROJECTS_ROOT / name, ignore_errors=True)


def test_opening_legacy_in_the_gui_shows_the_banner_and_disables_controls(qtbot):
    from tool.ui.main_window import MainWindow

    project = ToolProject.open("legacy")
    window = MainWindow(project)
    qtbot.addWidget(window)

    # isHidden(), not isVisible(): the window itself is never shown in
    # this offscreen test, so isVisible() would read False for every
    # widget regardless of setVisible() -- isHidden() reflects the
    # explicit setVisible() call the banner row's own construction makes.
    assert not window.read_only_banner_row.isHidden()
    assert not window.tabs.isEnabled()
    assert not window.save_button.isEnabled()
    assert not window.presets_button.isEnabled()
    # Running the project is still fine -- only editing it is blocked.
    # (Play itself isn't exercised here -- that's tool/tests/test_ui_smoke.py's
    # own, slower job -- just that nothing in construction disabled it.)


def test_a_normal_project_shows_no_banner_and_stays_editable(qtbot):
    import shutil
    from config.output_routing import PROJECTS_ROOT
    from tool.ui.main_window import MainWindow

    name = "_read_only_test_editable"
    shutil.rmtree(PROJECTS_ROOT / name, ignore_errors=True)
    project = ToolProject.create(name)
    window = MainWindow(project)
    qtbot.addWidget(window)

    assert window.read_only_banner_row.isHidden()
    assert window.tabs.isEnabled()
    assert not window.save_button.isEnabled(), "nothing changed yet -- Save has nothing to do"
    window.mark_dirty()
    assert window.save_button.isEnabled(), "editable and changed -- not blocked by read-only"
    assert window.presets_button.isEnabled()
    window.save()
    assert not window.save_button.isEnabled(), "clean again immediately after saving"
    shutil.rmtree(PROJECTS_ROOT / name, ignore_errors=True)


def test_duplicate_to_edit_creates_an_editable_copy_and_emits_switch(qtbot, monkeypatch):
    import shutil
    from config.output_routing import PROJECTS_ROOT
    from PySide6.QtWidgets import QInputDialog
    from tool.ui.main_window import MainWindow

    new_name = "_read_only_test_duplicate"
    shutil.rmtree(PROJECTS_ROOT / new_name, ignore_errors=True)
    try:
        project = ToolProject.open("legacy")
        window = MainWindow(project)
        qtbot.addWidget(window)

        monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: (new_name, True))
        switched = []
        window.project_switch_requested.connect(lambda p: switched.append(p))

        window._on_duplicate_to_edit()

        assert len(switched) == 1
        assert switched[0].name == new_name
        assert switched[0].is_read_only is False
        assert (PROJECTS_ROOT / new_name / "config.json").exists()
    finally:
        shutil.rmtree(PROJECTS_ROOT / new_name, ignore_errors=True)
