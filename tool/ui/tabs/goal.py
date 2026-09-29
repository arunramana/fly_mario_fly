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

from tool.ui.widgets.scroll_page import install_scroll_page
from tool.core.tool_settings import ExperimentSettings, FitnessSettings
from tool.ui.widgets.no_scroll_inputs import NoScrollDoubleSpinBox, NoScrollSpinBox

LEVELS = ["1-1", "1-2", "1-3", "1-4"]


class GoalTab(QWidget):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self._window = window
        content = QWidget()
        layout = QVBoxLayout(content)
        install_scroll_page(self, content)
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

        # noise.sigma is ONE config value with two editors (here and in Circuits ->
        # Other parameters). Neither owns a copy: each writes through
        # window.set_config and re-reads config.noise.sigma on
        # MainWindow.config_changed, so they cannot disagree.
        self.sigma_spin = NoScrollDoubleSpinBox()
        self.sigma_spin.setRange(0.0, 1.0)
        self.sigma_spin.setDecimals(4)
        self.sigma_spin.setSingleStep(0.01)
        self.sigma_spin.setMaximumWidth(130)
        self.sigma_spin.setValue(config.noise.sigma)
        self.sigma_spin.setToolTip("noise.sigma: per-step noise on every circuit. 0 = deterministic. "
                                   "Same value as Circuits > Other parameters.")
        self.sigma_spin.valueChanged.connect(self._on_sigma_changed)
        window.config_changed.connect(self._on_config_changed_externally)
        scenario_form.addRow("Noise sigma", self.sigma_spin)

        self.seeds_edit = QLineEdit(" ".join(str(s) for s in settings.experiment.seeds))
        self.seeds_edit.setToolTip("Space-separated seeds -- one run each on Play/Batch. A seed is also the "
                                   "noise seed: with sigma > 0 it fixes the noise sequence.")
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
        self.start_state_combo = QComboBox()
        self.start_state_combo.currentIndexChanged.connect(self._on_start_state_changed)
        scenario_form.addRow("Start from", self.start_state_combo)
        from tool.core.savestates import FRESH_BRAIN_NOTE
        note = QLabel(FRESH_BRAIN_NOTE)
        note.setWordWrap(True)
        scenario_form.addRow(note)
        self.refresh_states()

        # docs/SPEC_learning_v2.md section 2: which KC->MBON weights Play and Run batch use.
        self.brain_weights_combo = QComboBox()
        self.brain_weights_combo.setToolTip(
            "fresh: the connectome's own KC->MBON weights (default). A checkpoint: run that trained brain "
            "(from Train, or a Play that kept learning). Applies to Play and Run batch; recorded in the run.")
        self.brain_weights_combo.currentIndexChanged.connect(self._on_brain_weights_changed)
        scenario_form.addRow("Brain weights", self.brain_weights_combo)
        self.keep_learning_checkbox = QCheckBox("Keep learning during play (saves play_NNN.npy after a Play)")
        self.keep_learning_checkbox.setChecked(settings.experiment.keep_learning)
        self.keep_learning_checkbox.setToolTip(
            "Off: a checkpoint is frozen for the run (learning rate 0), so the run is of that checkpoint. "
            "On: it learns as it plays; a single Play saves the updated weights as a new checkpoint. "
            "A batch never saves or chains: every seed starts from the same checkpoint.")
        self.keep_learning_checkbox.toggled.connect(self._on_keep_learning_changed)
        scenario_form.addRow("", self.keep_learning_checkbox)
        layout.addWidget(scenario_box)

        fitness_box = QGroupBox("Fitness weights (points/distance/time/power-up)")
        fitness_form = QFormLayout(fitness_box)
        self.points_spin = self._fitness_spin(settings.fitness.points, self._on_points_changed)
        self.distance_spin = self._fitness_spin(settings.fitness.distance, self._on_distance_changed)
        self.time_spin = self._fitness_spin(settings.fitness.time, self._on_time_changed)
        fitness_form.addRow("Points", self.points_spin)
        fitness_form.addRow("Distance", self.distance_spin)
        fitness_form.addRow("Time", self.time_spin)
        self.powerup_spin = self._fitness_spin(settings.fitness.powerup, self._on_powerup_changed)
        self.powerup_spin.setToolTip(
            "Weight of one power-up eaten (Mario becoming Super). Above 0 it also makes eating one a "
            "dopamine reward (needs the Learning box above): a fixed pulse like a ? block hit, the value "
            "only weights the score. docs/SPEC_learning_v2.md section 4.")
        fitness_form.addRow("Power-up", self.powerup_spin)
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
        self.train_seed_mode_combo = QComboBox()
        self.train_seed_mode_combo.addItem("fixed: every episode uses the base seed", "fixed")
        self.train_seed_mode_combo.addItem("vary: episode i uses base + i", "vary")
        self.train_seed_mode_combo.setCurrentIndex(max(0, self.train_seed_mode_combo.findData(t.seed_mode)))
        self.train_seed_mode_combo.currentIndexChanged.connect(
            lambda _i: self._set_training(seed_mode=self.train_seed_mode_combo.currentData()))
        form.addRow("Seed mode", self.train_seed_mode_combo)
        self.train_seed_base_spin = NoScrollSpinBox()
        self.train_seed_base_spin.setRange(-1, 2_000_000_000)
        self.train_seed_base_spin.setSpecialValueText("first Goal seed")
        self.train_seed_base_spin.setValue(-1 if t.seed_base is None else t.seed_base)
        self.train_seed_base_spin.valueChanged.connect(
            lambda v: self._set_training(seed_base=(v if v >= 0 else None)))
        form.addRow("Base seed", self.train_seed_base_spin)
        self.train_test_every_spin = NoScrollSpinBox()
        self.train_test_every_spin.setRange(0, 10_000)
        self.train_test_every_spin.setSpecialValueText("never")
        self.train_test_every_spin.setValue(t.test_every)
        self.train_test_every_spin.setToolTip(
            "Every N episodes, run the current weights FROZEN (no learning) on the held-out test seeds "
            "below and plot the win-rate on the Learning tab. Test seeds are never used for training.")
        self.train_test_every_spin.valueChanged.connect(lambda v: self._set_training(test_every=v))
        form.addRow("Test every N episodes", self.train_test_every_spin)
        self.train_test_seeds_edit = QLineEdit(" ".join(str(s) for s in t.test_seeds))
        self.train_test_seeds_edit.setToolTip("Space-separated held-out seeds (default 100-109).")
        self.train_test_seeds_edit.editingFinished.connect(self._on_test_seeds_changed)
        form.addRow("Test seeds", self.train_test_seeds_edit)
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
        """Lists projects/<name>/checkpoints/ (real_epNNN.npy = "checkpoint N", play_NNN.npy = "played
        run N") in both the Train "Start from" and the Scenario "Brain weights" combos
        (fresh weights when none is chosen)."""
        from tool.core.training import list_checkpoints
        settings = self._window.get_tool_settings()
        names = list_checkpoints(self._window.project.name)
        for combo, current in ((self.train_checkpoint_combo, settings.training.checkpoint),
                               (self.brain_weights_combo, settings.experiment.brain_weights)):
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("fresh weights", None)
            for name in names:
                combo.addItem(self._checkpoint_label(name), name)
            combo.setCurrentIndex(max(0, combo.findData(current)))
            combo.blockSignals(False)

    @staticmethod
    def _checkpoint_label(name: str) -> str:
        stem = name.rsplit(".", 1)[0]
        if "_ep" in stem:
            return f"checkpoint {int(stem.rsplit('_ep', 1)[1])}"
        return f"played run {int(stem.rsplit('_', 1)[1])}"

    def _on_brain_weights_changed(self, _index: int) -> None:
        settings = self._window.get_tool_settings()
        experiment = dataclasses.replace(settings.experiment, brain_weights=self.brain_weights_combo.currentData())
        self._window.set_tool_settings(dataclasses.replace(settings, experiment=experiment))

    def _on_keep_learning_changed(self, checked: bool) -> None:
        settings = self._window.get_tool_settings()
        experiment = dataclasses.replace(settings.experiment, keep_learning=checked)
        self._window.set_tool_settings(dataclasses.replace(settings, experiment=experiment))

    def _on_test_seeds_changed(self) -> None:
        text = self.train_test_seeds_edit.text().strip()
        try:
            seeds = tuple(int(s) for s in text.split())
        except ValueError:
            seeds = ()
        if not seeds:
            seeds = tuple(range(100, 110))
            self.train_test_seeds_edit.setText(" ".join(str(s) for s in seeds))
        self._set_training(test_seeds=seeds)

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

    def refresh_states(self) -> None:
        """"power-on" plus the project's saved states (Player > Save state here)."""
        from tool.core.savestates import list_states
        current = self._window.get_tool_settings().experiment.start_state
        combo = self.start_state_combo
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("power-on", None)
        for name in list_states(self._window.project.name):
            combo.addItem(f"saved state: {name}", name)
        combo.setCurrentIndex(max(0, combo.findData(current)))
        combo.blockSignals(False)

    def _on_start_state_changed(self, _index: int) -> None:
        settings = self._window.get_tool_settings()
        experiment = dataclasses.replace(settings.experiment, start_state=self.start_state_combo.currentData())
        self._window.set_tool_settings(dataclasses.replace(settings, experiment=experiment))

    def _on_level_changed(self, level: str) -> None:
        config = self._window.get_config()
        scenario = dataclasses.replace(config.scenario, level=level)
        self._window.set_config(dataclasses.replace(config, scenario=scenario))

    def _on_graded_pits_changed(self, checked: bool) -> None:
        config = self._window.get_config()
        scenario = dataclasses.replace(config.scenario, graded_pit_response=checked)
        self._window.set_config(dataclasses.replace(config, scenario=scenario))

    def _on_sigma_changed(self, value: float) -> None:
        config = self._window.get_config()
        if config.noise.sigma != value:
            self._window.set_config(dataclasses.replace(config, noise=dataclasses.replace(config.noise, sigma=value)))

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

    def _on_powerup_changed(self, value: float) -> None:
        settings = self._window.get_tool_settings()
        fitness = dataclasses.replace(settings.fitness, powerup=value)
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
