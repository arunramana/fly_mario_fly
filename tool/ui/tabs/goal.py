"""tool/ui/tabs/goal.py -- tab 5: level, max frames, noise sigma + seed,
fitness weights (points/distance/time), seeds x episodes, learning on/off.
"""

from __future__ import annotations

import dataclasses

from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QGroupBox, QLineEdit,
    QCheckBox, QVBoxLayout, QWidget,
)

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton

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

        self.graded_pits_checkbox = QCheckBox("Graded pit response (docs/SPEC_pits.md)")
        self.graded_pits_checkbox.setChecked(config.scenario.graded_pit_response)
        self.graded_pits_checkbox.setToolTip(
            "Opt-in controller scaffolding, not circuit behaviour: overrides the jump "
            "cooldown near a pit, launches the long jump by distance, holds B for a run-up. "
            "A science change when on (CLAUDE.md rule 3).")
        self.graded_pits_checkbox.toggled.connect(self._on_graded_pits_changed)
        scenario_form.addRow("Pits", self.graded_pits_checkbox)
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

        layout.addWidget(self._build_training_box(settings.training))
        layout.addStretch(1)

    # ---- Training (tool/core/training.py) --------------------------------

    def _build_training_box(self, t) -> QGroupBox:
        box = QGroupBox("Train the mushroom body (background worker)")
        form = QFormLayout(box)
        self.train_episodes_spin = NoScrollSpinBox()
        self.train_episodes_spin.setRange(1, 5000)
        self.train_episodes_spin.setValue(t.episodes)
        self.train_episodes_spin.valueChanged.connect(lambda v: self._set_training(episodes=v))
        form.addRow("Episodes", self.train_episodes_spin)
        self.train_frame_cap_spin = NoScrollSpinBox()
        self.train_frame_cap_spin.setRange(60, 100_000)
        self.train_frame_cap_spin.setValue(t.frame_cap)
        self.train_frame_cap_spin.valueChanged.connect(lambda v: self._set_training(frame_cap=v))
        form.addRow("Frame cap per episode", self.train_frame_cap_spin)
        self.train_lr_spin = NoScrollDoubleSpinBox()
        self.train_lr_spin.setDecimals(5)
        self.train_lr_spin.setRange(0.0, 1.0)
        self.train_lr_spin.setSingleStep(0.0005)
        self.train_lr_spin.setSpecialValueText("project value")
        self.train_lr_spin.setValue(t.learning_rate or 0.0)
        self.train_lr_spin.setToolTip(
            "Learning rate: how far one unit of dopamine (reward for progress, "
            "punishment on death) depresses an eligible KC->MBON synapse. "
            "Minimum = keep the project's own value.")
        self.train_lr_spin.valueChanged.connect(
            lambda v: self._set_training(learning_rate=(v if v > 0 else None)))
        form.addRow("Reward / punishment strength", self.train_lr_spin)
        self.train_event_checkbox = QCheckBox("Reward only ? blocks and stomps (event-proximal), not any progress")
        self.train_event_checkbox.setChecked(t.event_proximal)
        self.train_event_checkbox.toggled.connect(lambda v: self._set_training(event_proximal=v))
        form.addRow(self.train_event_checkbox)
        self.train_shuffled_checkbox = QCheckBox("Include shuffled controls (invariant 6)")
        self.train_shuffled_checkbox.setChecked(t.include_shuffled)
        self.train_shuffled_checkbox.toggled.connect(lambda v: self._set_training(include_shuffled=v))
        form.addRow(self.train_shuffled_checkbox)
        self.train_n_shuffled_spin = NoScrollSpinBox()
        self.train_n_shuffled_spin.setRange(1, 10)
        self.train_n_shuffled_spin.setValue(t.n_shuffled)
        self.train_n_shuffled_spin.valueChanged.connect(lambda v: self._set_training(n_shuffled=v))
        form.addRow("Number of shuffled networks", self.train_n_shuffled_spin)
        self.train_checkpoint_combo = QComboBox()
        self.train_checkpoint_combo.currentIndexChanged.connect(self._on_checkpoint_changed)
        form.addRow("Start from", self.train_checkpoint_combo)
        self.refresh_checkpoints()
        row = QHBoxLayout()
        self.train_button = QPushButton("Train")
        self.train_button.clicked.connect(self._window.start_training)
        self.train_cancel_button = QPushButton("Cancel training")
        self.train_cancel_button.setEnabled(False)
        self.train_cancel_button.clicked.connect(self._window.cancel_training)
        self.train_status = QLabel("")
        row.addWidget(self.train_button)
        row.addWidget(self.train_cancel_button)
        row.addWidget(self.train_status, 1)
        form.addRow(row)
        return box

    def _set_training(self, **changes) -> None:
        settings = self._window.get_tool_settings()
        self._window.set_tool_settings(dataclasses.replace(
            settings, training=dataclasses.replace(settings.training, **changes)))

    def refresh_checkpoints(self) -> None:
        """Lists projects/<name>/checkpoints/real_epNNN.npy as "start from
        checkpoint N" (fresh weights when none is chosen)."""
        from tool.core.training import list_checkpoints
        current = self._window.get_tool_settings().training.checkpoint
        combo = self.train_checkpoint_combo
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("fresh weights", None)
        for name in list_checkpoints(self._window.project.name):
            n = int(name.rsplit("_ep", 1)[1].split(".")[0])
            combo.addItem(f"checkpoint {n}", name)
        index = combo.findData(current)
        combo.setCurrentIndex(max(0, index))
        combo.blockSignals(False)

    def _on_checkpoint_changed(self, _index: int) -> None:
        self._set_training(checkpoint=self.train_checkpoint_combo.currentData())

    def set_training_state(self, running: bool, status: str = "") -> None:
        self.train_button.setEnabled(not running)
        self.train_cancel_button.setEnabled(running)
        self.train_status.setText(status)

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

    def _on_graded_pits_changed(self, checked: bool) -> None:
        config = self._window.get_config()
        scenario = dataclasses.replace(config.scenario, graded_pit_response=checked)
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
