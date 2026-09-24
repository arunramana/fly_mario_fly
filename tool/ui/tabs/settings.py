"""tool/ui/tabs/settings.py -- tab 6: parallel workers, frame skip, video
on/off, brain panel on/off, live preview fps (throttles Play's live
preview -- tool/core/runner.py's every-Nth-frame send, P7), output folder
(info only).
"""

from __future__ import annotations

import dataclasses

from PySide6.QtWidgets import (
    QCheckBox, QFormLayout, QGroupBox, QLabel, QSpinBox, QVBoxLayout, QWidget,
)

from tool.core.tool_settings import RenderSettings
from tool.ui.widgets.preset_bar import PresetBar


class SettingsTab(QWidget):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self._window = window
        layout = QVBoxLayout(self)
        settings = window.get_tool_settings()

        layout.addWidget(PresetBar("settings", self._preset_data, self._apply_preset))

        box = QGroupBox("Rendering / batching")
        form = QFormLayout(box)

        self.workers_spin = QSpinBox()
        self.workers_spin.setRange(1, 32)
        self.workers_spin.setValue(settings.render.parallel_workers)
        self.workers_spin.valueChanged.connect(self._on_workers_changed)
        form.addRow("Parallel workers", self.workers_spin)

        self.frame_skip_spin = QSpinBox()
        self.frame_skip_spin.setRange(1, 30)
        self.frame_skip_spin.setValue(settings.render.frame_skip)
        self.frame_skip_spin.valueChanged.connect(self._on_frame_skip_changed)
        form.addRow("Frame skip", self.frame_skip_spin)

        self.video_checkbox = QCheckBox("Record video")
        self.video_checkbox.setChecked(settings.render.record_video)
        self.video_checkbox.toggled.connect(self._on_video_changed)
        form.addRow(self.video_checkbox)

        self.brain_panel_checkbox = QCheckBox("Brain panel in recorded video")
        self.brain_panel_checkbox.setChecked(settings.render.brain_panel)
        self.brain_panel_checkbox.toggled.connect(self._on_brain_panel_changed)
        form.addRow(self.brain_panel_checkbox)

        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 60)
        self.fps_spin.setValue(settings.render.live_preview_fps)
        self.fps_spin.setToolTip(
            "runner.py sends every Nth frame (60 / this value), shrunk 2x -- P7"
        )
        self.fps_spin.valueChanged.connect(self._on_fps_changed)
        form.addRow("Live preview fps", self.fps_spin)

        layout.addWidget(box)

        info_box = QGroupBox("Output (info only)")
        info_form = QFormLayout(info_box)
        info_form.addRow("Project folder", QLabel(str(window.project.root)))
        info_form.addRow("GPU", QLabel("not offered -- CLAUDE.md: measured slower on this workload"))
        layout.addWidget(info_box)

        layout.addStretch(1)

    def _on_workers_changed(self, value: int) -> None:
        settings = self._window.get_tool_settings()
        render = dataclasses.replace(settings.render, parallel_workers=value)
        self._window.set_tool_settings(dataclasses.replace(settings, render=render))

    def _on_frame_skip_changed(self, value: int) -> None:
        settings = self._window.get_tool_settings()
        render = dataclasses.replace(settings.render, frame_skip=value)
        self._window.set_tool_settings(dataclasses.replace(settings, render=render))

    def _on_video_changed(self, checked: bool) -> None:
        settings = self._window.get_tool_settings()
        render = dataclasses.replace(settings.render, record_video=checked)
        self._window.set_tool_settings(dataclasses.replace(settings, render=render))

    def _on_brain_panel_changed(self, checked: bool) -> None:
        settings = self._window.get_tool_settings()
        render = dataclasses.replace(settings.render, brain_panel=checked)
        self._window.set_tool_settings(dataclasses.replace(settings, render=render))

    def _on_fps_changed(self, value: int) -> None:
        settings = self._window.get_tool_settings()
        render = dataclasses.replace(settings.render, live_preview_fps=value)
        self._window.set_tool_settings(dataclasses.replace(settings, render=render))

    def _preset_data(self) -> dict:
        return dataclasses.asdict(self._window.get_tool_settings().render)

    def _apply_preset(self, data: dict) -> None:
        settings = self._window.get_tool_settings()
        self._window.set_tool_settings(
            dataclasses.replace(settings, render=RenderSettings(**data))
        )
        self._window.reload_tab("settings")
