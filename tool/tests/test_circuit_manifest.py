"""tool/SPEC_ui_retro.md section 10: "adding a circuit needs no UI code."
tool/ui/tabs/circuits.py builds its card grid by iterating
tool/core/circuit_manifest.CIRCUIT_REGISTRY -- registering a dummy entry
there (a real config group, "noise", standing in for "a fake group with
one scalar") must make a card appear with no edit to circuits.py itself.
"""
from __future__ import annotations

import shutil

import pytest

from config.output_routing import PROJECTS_ROOT
from tool.core.circuit_manifest import CIRCUIT_REGISTRY, CircuitEntry

PROJECT_NAME = "_circuit_manifest_test"


@pytest.fixture
def clean_project():
    root = PROJECTS_ROOT / PROJECT_NAME
    shutil.rmtree(root, ignore_errors=True)
    yield root
    shutil.rmtree(root, ignore_errors=True)


@pytest.fixture
def dummy_circuit_entry():
    """populations=() so this never touches the connectome data --
    circuit_card_pixmap falls back to the placeholder for an entry with
    no populations, same path OTHER_ENTRY already uses."""
    entry = CircuitEntry(
        "dummy_test_circuit", "Dummy Test Circuit", ("noise",), (),
        "A fake circuit for section 10's own extensibility test.", None,
    )
    CIRCUIT_REGISTRY.append(entry)
    yield entry
    CIRCUIT_REGISTRY.remove(entry)


def test_a_dummy_circuit_entry_gets_a_card(qtbot, clean_project, dummy_circuit_entry):
    from tool.core.project import ToolProject
    from tool.ui.main_window import MainWindow

    project = ToolProject.create(PROJECT_NAME)
    window = MainWindow(project)
    qtbot.addWidget(window)

    circuits_tab = window.tabs.widget(3)
    assert dummy_circuit_entry.circuit_id in circuits_tab._circuit_buttons
    button = circuits_tab._circuit_buttons[dummy_circuit_entry.circuit_id]
    assert button.text() == "Dummy Test Circuit"

    button.click()
    # isHidden(), not isVisible(): the window itself is never shown in
    # this offscreen test, so isVisible() would read False for every
    # widget regardless of setVisible() -- isHidden() reflects the
    # explicit setVisible() call show_only_groups() actually makes.
    assert not circuits_tab.param_form._group_boxes["noise"].isHidden()
    assert circuits_tab.param_form._group_boxes["jump"].isHidden()
    window.save()
