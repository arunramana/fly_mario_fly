# What this file does, in plain English:
# The ordered list of the main window's seven tabs -- which widget class
# builds each one and what its title reads -- as data instead of seven
# hand-written lines inside the window's own constructor.
"""tool/core/tab_registry.py -- tool/SPEC_ui_retro.md section 10, MINIMAL
scope (flagged there as the part most likely to need its own follow-up):
main_window.py's __init__ iterates TAB_REGISTRY to build self.tabs and
self._tab_factories, instead of seven hardcoded self.tabs.addTab() calls.
`attr_name` covers the two tabs OTHER code reaches into directly today
(self.character_tab, self.run_tab -- e.g. on_player_changed calls
self.run_tab.preview.set_player) -- MainWindow still stashes those two as
named attributes after construction, rather than the full self.tab(name)
reach-through refactor the SPEC itself calls out as a bigger, separate
decision. Section 10's own test bar (register a dummy tab, no
main_window.py edit) is met by this list being the actual construction
source, not a description of it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class TabRegistryEntry:
    tab_id: str
    title: str
    factory: Callable  # factory(window) -> QWidget
    attr_name: str | None = None


def _character_factory(window):
    from tool.ui.tabs.character import CharacterTab
    return CharacterTab(window)


def _enemies_factory(window):
    from tool.ui.tabs.enemies import EnemiesTab
    return EnemiesTab(window)


def _objects_factory(window):
    from tool.ui.tabs.objects import ObjectsTab
    return ObjectsTab(window)


def _circuits_factory(window):
    from tool.ui.tabs.circuits import CircuitsTab
    return CircuitsTab(window)


def _goal_factory(window):
    from tool.ui.tabs.goal import GoalTab
    return GoalTab(window)


def _settings_factory(window):
    from tool.ui.tabs.settings import SettingsTab
    return SettingsTab(window)


def _run_factory(window):
    from tool.ui.tabs.run import RunTab
    return RunTab(window)


def _experiments_factory(window):
    from tool.ui.tabs.experiments import ExperimentsTab
    return ExperimentsTab(window)


def _mechanisms_factory(window):
    from tool.ui.tabs.mechanisms import MechanismsTab
    return MechanismsTab(window)


def _results_factory(window):
    from tool.ui.tabs.results import ResultsTab
    return ResultsTab(window)


TAB_REGISTRY: list[TabRegistryEntry] = [
    TabRegistryEntry("character", "1 Character", _character_factory, attr_name="character_tab"),
    TabRegistryEntry("enemies", "2 Enemies", _enemies_factory),
    TabRegistryEntry("objects", "3 Objects", _objects_factory),
    TabRegistryEntry("circuits", "4 Circuits", _circuits_factory),
    TabRegistryEntry("goal", "5 Goal", _goal_factory),
    TabRegistryEntry("settings", "6 Settings", _settings_factory),
    TabRegistryEntry("run", "7 Run", _run_factory, attr_name="run_tab"),
    # Redesign phase 2 (docs/SPEC_tool_phase2.md): the brain path. "7 Run" is Watch for brain runs too.
    TabRegistryEntry("experiments", "8 Experiments", _experiments_factory),
    TabRegistryEntry("mechanisms", "9 Mechanisms", _mechanisms_factory),
    TabRegistryEntry("results", "10 Results", _results_factory),
]
