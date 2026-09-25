"""tool/ui/tabs/goal.py -- tab 5: level, max frames, noise sigma + seed,
fitness weights (points/distance/time), seeds x episodes, learning on/off.
"""

from __future__ import annotations

import dataclasses

from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QGroupBox, QLineEdit,
    QCheckBox, QVBoxLayout, QWidget,
)

from tool.core.tool_settings import ExperimentSettings, FitnessSettings
from tool.ui.widgets.no_scroll_inputs import NoScrollDoubleSpinBox, NoScrollSpinBox

LEVELS = ["1-1", "1-2", "1-3", "1-4"]


class GoalTab(QWidget):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self._window = window
        layout = QVBoxLayout(self)
        config = window.get_config()
        settings = window.get_tool_settings()

        # Presets for this tab live in the header's Presets menu now
        # (ease-of-use redesign) -- _preset_data/_apply_preset below are
        # unchanged, main_window.py's menu calls them directly.
        scenario_box = QGroupBox("Scenario")
        scenario_form = QFormLayout(scenario_box)
        self.level_combo = QComboBox()
        self.level_combo.addItems(LEVELS)
        self.level_combo.setCurrentText(config.scenario.level)
        self.level_combo.currentTextChanged.connect(self._on_level_changed)
        scenario_form.addRow("Level", self.level_combo)

        self.max_frames_spin = NoScrollSpinBox()
        self.max_frames_spin.setRange(1, 100_000)
        self.max_frames_spin.setValue(config.scenario.max_frames)
        self.max_frames_spin.valueChanged.connect(self._on_max_frames_changed)
        scenario_form.addRow("Max frames", self.max_frames_spin)

        # tool/SPEC_ui_retro.md section 3, "one home per setting": found
        # noise.sigma editable in BOTH this tab and the Circuits tab
        # (schema.py's ParamForm covers all 49, sigma among them), nothing
        # keeping the two in sync by construction. The Circuits tab is now
        # the one writable home; this is read-only, always showing the
        # live config.noise.sigma via MainWindow.config_changed (not a
        # value snapshotted once at construction, which would go stale
        # the moment the Circuits tab's own widget changed it).
        self.sigma_spin = NoScrollDoubleSpinBox()
        self.sigma_spin.setRange(0.0, 1.0)
        self.sigma_spin.setDecimals(4)
        self.sigma_spin.setSingleStep(0.01)
        self.sigma_spin.setValue(config.noise.sigma)
        self.sigma_spin.setEnabled(False)
        self.sigma_spin.setToolTip("Read-only -- change noise.sigma from the Circuits tab.")
        window.config_changed.connect(self._on_config_changed_externally)
        scenario_form.addRow("Noise sigma (see Circuits tab)", self.sigma_spin)

        self.seeds_edit = QLineEdit(" ".join(str(s) for s in settings.experiment.seeds))
        self.seeds_edit.setToolTip("Space-separated seeds -- one run each on Play/Batch")
        self.seeds_edit.editingFinished.connect(self._on_seeds_changed)
        scenario_form.addRow("Seeds", self.seeds_edit)

        self.learning_checkbox = QCheckBox("Event-proximal dopamine (docs/TRACE_BIOLOGY.md)")
        self.learning_checkbox.setChecked(settings.experiment.learning_enabled)
        self.learning_checkbox.toggled.connect(self._on_learning_changed)
        scenario_form.addRow("Learning", self.learning_checkbox)
        layout.addWidget(scenario_box)

        fitness_box = QGroupBox("Fitness weights (points/distance/time)")
        fitness_form = QFormLayout(fitness_box)
        self.points_spin = self._fitness_spin(settings.fitness.points, self._on_points_changed)
        self.distance_spin = self._fitness_spin(settings.fitness.distance, self._on_distance_changed)
        self.time_spin = self._fitness_spin(settings.fitness.time, self._on_time_changed)
        fitness_form.addRow("Points", self.points_spin)
        fitness_form.addRow("Distance", self.distance_spin)
        fitness_form.addRow("Time", self.time_spin)
        layout.addWidget(fitness_box)

        layout.addStretch(1)

    @staticmethod
    def _fitness_spin(value: float, slot) -> NoScrollDoubleSpinBox:
        spin = NoScrollDoubleSpinBox()
        spin.setRange(0.0, 1000.0)
        spin.setDecimals(3)
        spin.setValue(value)
        spin.valueChanged.connect(slot)
        return spin

    def _on_level_changed(self, level: str) -> None:
        config = self._window.get_config()
        scenario = dataclasses.replace(config.scenario, level=level)
        self._window.set_config(dataclasses.replace(config, scenario=scenario))

    def _on_max_frames_changed(self, value: int) -> None:
        config = self._window.get_config()
        scenario = dataclasses.replace(config.scenario, max_frames=value)
        self._window.set_config(dataclasses.replace(config, scenario=scenario))

    def _on_config_changed_externally(self, config) -> None:
        """MainWindow.config_changed -- keeps the read-only sigma display
        live no matter which tab actually changed it."""
        self.sigma_spin.blockSignals(True)
        self.sigma_spin.setValue(config.noise.sigma)
        self.sigma_spin.blockSignals(False)

    def _on_seeds_changed(self) -> None:
        text = self.seeds_edit.text().strip()
        try:
            seeds = tuple(int(s) for s in text.split()) if text else (0,)
        except ValueError:
            seeds = (0,)
            self.seeds_edit.setText("0")
        settings = self._window.get_tool_settings()
        experiment = dataclasses.replace(settings.experiment, seeds=seeds)
        self._window.set_tool_settings(dataclasses.replace(settings, experiment=experiment))

    def _on_learning_changed(self, checked: bool) -> None:
        settings = self._window.get_tool_settings()
        experiment = dataclasses.replace(settings.experiment, learning_enabled=checked)
        self._window.set_tool_settings(dataclasses.replace(settings, experiment=experiment))

    def _on_points_changed(self, value: float) -> None:
        settings = self._window.get_tool_settings()
        fitness = dataclasses.replace(settings.fitness, points=value)
        self._window.set_tool_settings(dataclasses.replace(settings, fitness=fitness))

    def _on_distance_changed(self, value: float) -> None:
        settings = self._window.get_tool_settings()
        fitness = dataclasses.replace(settings.fitness, distance=value)
        self._window.set_tool_settings(dataclasses.replace(settings, fitness=fitness))

    def _on_time_changed(self, value: float) -> None:
        settings = self._window.get_tool_settings()
        fitness = dataclasses.replace(settings.fitness, time=value)
        self._window.set_tool_settings(dataclasses.replace(settings, fitness=fitness))

    def _preset_data(self) -> dict:
        config = self._window.get_config()
        settings = self._window.get_tool_settings()
        return {
            "level": config.scenario.level,
            "max_frames": config.scenario.max_frames,
            "sigma": config.noise.sigma,
            "fitness": dataclasses.asdict(settings.fitness),
            "experiment": dataclasses.asdict(settings.experiment),
        }

    def _apply_preset(self, data: dict) -> None:
        config = self._window.get_config()
        scenario = dataclasses.replace(
            config.scenario, level=data["level"], max_frames=data["max_frames"])
        noise = dataclasses.replace(config.noise, sigma=data["sigma"])
        self._window.set_config(dataclasses.replace(config, scenario=scenario, noise=noise))

        settings = self._window.get_tool_settings()
        fitness = FitnessSettings(**data["fitness"])
        experiment = ExperimentSettings(**{
            **data["experiment"], "seeds": tuple(data["experiment"]["seeds"]),
        })
        self._window.set_tool_settings(
            dataclasses.replace(settings, fitness=fitness, experiment=experiment)
        )
        self._window.reload_tab("goal")
