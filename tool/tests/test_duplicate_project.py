""""Duplicate project...": gate button and header menu, any source, unused names only."""
from __future__ import annotations

import shutil

import pytest
from PySide6.QtWidgets import QDialog

from config.output_routing import PROJECTS_ROOT
from tool.core.project import ToolProject
from tool.ui.duplicate_dialog import DuplicateProjectDialog
from tool.ui.gate import ProjectGateDialog

SRC, NEW, NEW2 = "_dup_src", "_dup_new", "_dup_new2"


@pytest.fixture()
def src():
    for n in (SRC, NEW, NEW2):
        shutil.rmtree(PROJECTS_ROOT / n, ignore_errors=True)
    p = ToolProject.create(SRC)
    yield p
    for n in (SRC, NEW, NEW2):
        shutil.rmtree(PROJECTS_ROOT / n, ignore_errors=True)


def test_name_errors_and_recency(src):
    assert ToolProject.name_error(SRC) and "already exists" in ToolProject.name_error(SRC)
    assert ToolProject.name_error("") and ToolProject.name_error("a/b") and ToolProject.name_error("..")
    assert ToolProject.name_error(NEW) is None
    assert ToolProject.list_by_recency()[0] == SRC          # just created = most recent
    assert "legacy" in ToolProject.list_by_recency()


def test_dialog_defaults_to_most_recent_and_rejects_existing_names(qtbot, src):
    d = DuplicateProjectDialog()
    qtbot.addWidget(d)
    assert d.source() == SRC
    ok = d.buttons.button(d.buttons.StandardButton.Ok)
    assert not ok.isEnabled()                                # empty name
    d.name_edit.setText(SRC)
    assert not ok.isEnabled() and "already exists" in d.error_label.text()
    d.name_edit.setText(NEW)
    assert ok.isEnabled()
    legacy = [d.source_combo.itemData(i) for i in range(d.source_combo.count())]
    assert "legacy" in legacy                                # read-only reference is offered too


def test_gate_button_duplicates_the_chosen_project(qtbot, src, monkeypatch):
    gate = ProjectGateDialog()
    qtbot.addWidget(gate)
    assert gate.duplicate_button.text() == "Duplicate project..."
    assert not hasattr(gate, "_duplicate_legacy")

    def fake_exec(self):
        self.source_combo.setCurrentIndex(self.source_combo.findData("legacy"))
        self.name_edit.setText(NEW)
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(DuplicateProjectDialog, "exec", fake_exec)
    gate.duplicate_button.click()
    assert gate.selected_project.name == NEW and (PROJECTS_ROOT / NEW / "config.json").exists()


def test_header_menu_saves_pending_edits_then_duplicates(qtbot, src, monkeypatch):
    import dataclasses
    from tool.ui.main_window import MainWindow
    w = MainWindow(src)
    qtbot.addWidget(w)
    assert w.duplicate_action.text() == "Duplicate project..." and w.project_button in w.header_buttons
    w.set_config(dataclasses.replace(w.get_config(), scenario=dataclasses.replace(w.get_config().scenario, max_frames=777)))
    assert w._dirty

    def fake_exec(self):
        assert self.source() == SRC                          # defaults to the open project
        self.name_edit.setText(NEW2)
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(DuplicateProjectDialog, "exec", fake_exec)
    got = []
    w.project_switch_requested.connect(got.append)
    w.duplicate_project()
    assert not w._dirty and got[0].name == NEW2
    assert ToolProject.open(NEW2).config.scenario.max_frames == 777    # the copy has the saved edit
