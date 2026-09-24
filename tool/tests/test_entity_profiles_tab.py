"""tool/PLAN.md P6, docs/SPEC_entity_perception.md section 6: tabs 2/3's
per-kind entity profile editor. Ground rule 4 (no control lies) --
proves the checkbox + spin boxes actually change a run's telemetry, not
just a file on disk, and that the two tabs' shared checkbox stays synced.
"""
from __future__ import annotations

import dataclasses
import shutil

import pytest

from config.output_routing import PROJECTS_ROOT
from tool.core.entity_profiles_store import set_kind_field
from tool.core.run_spec import RunSpec
from tool.core.runner import run_one
from tool.core.tool_settings import EntityProfileSettings, ToolSettings

PROJECT_NAME = "_entity_profiles_tab_test"


@pytest.fixture
def clean_project():
    root = PROJECTS_ROOT / PROJECT_NAME
    shutil.rmtree(root, ignore_errors=True)
    yield root
    shutil.rmtree(root, ignore_errors=True)


def _cfg():
    from config.project_config import ProjectConfig
    return ProjectConfig(
        scenario=dataclasses.replace(ProjectConfig().scenario, level="1-1", max_frames=300),
        output=dataclasses.replace(ProjectConfig().output, project_name=PROJECT_NAME),
    )


def test_enabling_with_an_override_changes_telemetry(clean_project):
    set_kind_field(PROJECT_NAME, "GOOMBA", "danger_weight", 2.0)
    cfg = _cfg()
    settings_off = ToolSettings()
    settings_on = dataclasses.replace(settings_off, entity_profile=EntityProfileSettings(enabled=True))

    spec_off = RunSpec(project_name=PROJECT_NAME, config=cfg, tool_settings=settings_off,
                        seed=0, out_filename="off.mp4")
    spec_on = RunSpec(project_name=PROJECT_NAME, config=cfg, tool_settings=settings_on,
                       seed=0, out_filename="on.mp4")

    tel_off, _ = run_one(spec_off)
    tel_on, _ = run_one(spec_on)
    assert not tel_off["ttmn"].equals(tel_on["ttmn"]), (
        "enabling entity profiles with a GOOMBA danger_weight override "
        "produced identical telemetry to the default -- the tab's control "
        "isn't reaching a real run"
    )


def test_enabled_with_no_override_reproduces_disabled(clean_project):
    """No entity_profiles.json written -- enabling should be equivalent
    to a profile that's all shipped defaults, which SPEC section 2
    already requires to reproduce entity_profiles=None exactly."""
    cfg = _cfg()
    settings_off = ToolSettings()
    settings_on = dataclasses.replace(settings_off, entity_profile=EntityProfileSettings(enabled=True))

    spec_off = RunSpec(project_name=PROJECT_NAME, config=cfg, tool_settings=settings_off,
                        seed=0, out_filename="off.mp4")
    spec_on = RunSpec(project_name=PROJECT_NAME, config=cfg, tool_settings=settings_on,
                       seed=0, out_filename="on.mp4")

    tel_off, _ = run_one(spec_off)
    tel_on, _ = run_one(spec_on)
    assert tel_off.equals(tel_on)


def test_valence_checkbox_round_trips_and_changes_telemetry(qtbot, clean_project):
    """tool/SPEC_ui_retro.md section 4: toggling the Enemies tab's GOOMBA
    "Smells good" checkbox must (a) write sign=+1 into
    projects/<name>/entity_profiles.json and (b) actually move telemetry
    -- ground rule 4, no control lies."""
    import json

    from tool.core.project import ToolProject
    from tool.ui.main_window import MainWindow

    project = ToolProject.create(PROJECT_NAME)
    window = MainWindow(project)
    qtbot.addWidget(window)

    from mario.entities.kinds import EntityKind
    enemies_tab = window.tabs.widget(1)
    enemies_tab.enable_checkbox.setChecked(True)
    goomba_check = enemies_tab._valence_checks[EntityKind.GOOMBA]
    assert goomba_check.isChecked() is False  # GOOMBA ships aversive by default

    goomba_check.setChecked(True)

    override_path = PROJECTS_ROOT / PROJECT_NAME / "entity_profiles.json"
    override = json.loads(override_path.read_text(encoding="utf-8"))
    assert override["GOOMBA"]["odours"][0]["sign"] == 1

    cfg = _cfg()
    settings_flipped = window.get_tool_settings()
    settings_default = dataclasses.replace(
        settings_flipped, entity_profile=EntityProfileSettings(enabled=False))

    spec_default = RunSpec(project_name=PROJECT_NAME, config=cfg, tool_settings=settings_default,
                            seed=0, out_filename="default.mp4")
    spec_flipped = RunSpec(project_name=PROJECT_NAME, config=cfg, tool_settings=settings_flipped,
                            seed=0, out_filename="flipped.mp4")
    tel_default, _ = run_one(spec_default)
    tel_flipped, _ = run_one(spec_flipped)
    assert not tel_default["odor_r"].equals(tel_flipped["odor_r"]), (
        "flipping GOOMBA's valence through the Enemies tab produced identical "
        "food-odour telemetry -- the checkbox isn't reaching a real run"
    )
    window.save()


def test_tabs_build_and_checkbox_stays_synced(qtbot, clean_project):
    from tool.core.project import ToolProject
    from tool.ui.main_window import MainWindow

    project = ToolProject.create(PROJECT_NAME)
    window = MainWindow(project)
    qtbot.addWidget(window)

    enemies_tab = window.tabs.widget(1)
    objects_tab = window.tabs.widget(2)
    assert enemies_tab.enable_checkbox.isChecked() is False
    assert objects_tab.enable_checkbox.isChecked() is False

    enemies_tab.enable_checkbox.setChecked(True)
    assert window.get_tool_settings().entity_profile.enabled is True
    new_objects_tab = window.tabs.widget(2)
    assert new_objects_tab is not objects_tab  # reloaded
    assert new_objects_tab.enable_checkbox.isChecked() is True
    window.save()  # leave clean: qtbot's teardown close() would else hit the real unsaved-changes prompt


def test_kind_inputs_disabled_until_profiles_are_enabled(qtbot, clean_project):
    """Found in manual testing: the per-kind spin boxes were editable
    even with the checkbox off, when they can't do anything (ground rule
    4 -- no control lies)."""
    from tool.core.project import ToolProject
    from tool.ui.main_window import MainWindow

    project = ToolProject.create(PROJECT_NAME)
    window = MainWindow(project)
    qtbot.addWidget(window)

    enemies_tab = window.tabs.widget(1)
    objects_tab = window.tabs.widget(2)
    assert not any(box.isEnabled() for box in enemies_tab._kind_boxes)
    assert not any(box.isEnabled() for box in objects_tab._kind_boxes)

    enemies_tab.enable_checkbox.setChecked(True)
    new_objects_tab = window.tabs.widget(2)
    assert all(box.isEnabled() for box in enemies_tab._kind_boxes)
    assert all(box.isEnabled() for box in new_objects_tab._kind_boxes)

    enemies_tab.enable_checkbox.setChecked(False)
    newer_objects_tab = window.tabs.widget(2)
    assert not any(box.isEnabled() for box in enemies_tab._kind_boxes)
    assert not any(box.isEnabled() for box in newer_objects_tab._kind_boxes)
    assert window.tabs.currentIndex() == 0  # reload_tab("objects") didn't steal focus

    window.save()
