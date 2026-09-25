"""tool/ui/tabs/run.py -- tab 7: the video player (ease-of-use redesign),
plus a collapsible run browser (left) and Plots/Data/Config drawers
(right). Play lives only in the header now (main_window.py's START
button, Ctrl+Enter; Space drives the PLAYER's own play/pause instead) --
this tab keeps Cancel (there's no header equivalent) and the batch
button.

`self.preview`/`self.preview.frame_label` stay as aliases for
`self.video_player` -- tool/tests monkeypatches
`window.run_tab.preview.show_frame` directly (the exact call site
main_window.py's poll loop uses) and reads `.frame_label.pixmap()`,
unaffected by this tab's own internal reshuffle.
"""

from __future__ import annotations

import dataclasses

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QProgressBar, QPushButton, QSplitter, QVBoxLayout, QWidget,
)

from tool.core.tool_settings import RunTabUIState
from tool.ui.widgets.collapsible_drawer import CollapsibleDrawer
from tool.ui.widgets.plots import TelemetryPlots
from tool.ui.widgets.run_detail_panels import ConfigDiffPanel, DataPanel
from tool.ui.widgets.run_table import RunTable
from tool.ui.widgets.stat_chips import StatChips
from tool.ui.widgets.video_player import VideoPlayer


class RunTab(QWidget):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self._window = window
        ui_state = window.get_tool_settings().run_tab_ui
        layout = QVBoxLayout(self)

        controls = QHBoxLayout()
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(window.cancel)
        self.cancel_button.setEnabled(False)
        self.batch_button = QPushButton("Run batch (seeds from Goal tab)")
        self.batch_button.clicked.connect(window.run_batch)
        self.progress = QProgressBar()
        controls.addWidget(self.cancel_button)
        controls.addWidget(self.batch_button)
        controls.addWidget(self.progress, 1)
        layout.addLayout(controls)

        # Compact result chips (ease-of-use redesign) + the one full-
        # sentence result line (still used by main_window.py's show_result
        # for a batch summary or an error, which don't fit a chip well).
        self.stat_chips = StatChips()
        layout.addWidget(self.stat_chips)
        self.result_label = QLabel("")
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)

        body = QSplitter(Qt.Orientation.Horizontal)

        # ---- left drawer: run browser ---------------------------------
        runs_side = QWidget()
        runs_layout = QVBoxLayout(runs_side)
        runs_layout.setContentsMargins(4, 4, 4, 4)
        nav_row = QHBoxLayout()
        self.prev_run_button = QPushButton("< Prev run")
        self.prev_run_button.clicked.connect(lambda: self.run_table.select_adjacent(-1))
        self.next_run_button = QPushButton("Next run >")
        self.next_run_button.clicked.connect(lambda: self.run_table.select_adjacent(1))
        nav_row.addWidget(self.prev_run_button)
        nav_row.addWidget(self.next_run_button)
        runs_layout.addLayout(nav_row)
        self.run_table = RunTable()
        self.run_table.row_selected.connect(self._on_row_selected)
        runs_layout.addWidget(self.run_table, 1)
        self.export_button = QPushButton("Export selected run's bundle")
        self.export_button.clicked.connect(self._on_export_clicked)
        runs_layout.addWidget(self.export_button)
        self.runs_drawer = CollapsibleDrawer(
            "Runs", runs_side, open=ui_state.runs_drawer_open, width=ui_state.runs_drawer_width)
        self.runs_drawer.toggled.connect(lambda _open: self._save_ui_state())
        body.addWidget(self.runs_drawer)

        # ---- centre: the player itself, "as large as fits" -------------
        self.video_player = VideoPlayer()
        self.video_player.set_player(window.get_tool_settings().character.player)
        self.video_player.frame_changed.connect(self._on_frame_changed)
        self.video_player.brain_map_toggled.connect(self._on_brain_map_toggled)
        self.video_player.brain_map_button.setChecked(ui_state.brain_map_visible)
        body.addWidget(self.video_player)
        body.setStretchFactor(1, 1)  # the player claims whatever space the drawers don't
        # Backward-compatible aliases: tool/tests monkeypatches
        # window.run_tab.preview.show_frame directly and reads
        # .frame_label.pixmap() -- both still resolve correctly since
        # VideoPlayer keeps that exact method/attribute name.
        self.preview = self.video_player
        self.activity_strip = self.video_player.activity_strip

        # ---- right drawers: Plots / Data / Config -----------------------
        self.plots = TelemetryPlots()
        self.plots.seek_requested.connect(self.video_player.seek_frame)
        self.plots_drawer = CollapsibleDrawer(
            "Plots", self.plots, open=ui_state.plots_drawer_open, width=ui_state.plots_drawer_width)
        self.plots_drawer.toggled.connect(lambda _open: self._save_ui_state())
        body.addWidget(self.plots_drawer)

        self.data_panel = DataPanel()
        self.data_drawer = CollapsibleDrawer(
            "Data", self.data_panel, open=ui_state.data_drawer_open, width=ui_state.data_drawer_width)
        self.data_drawer.toggled.connect(lambda _open: self._save_ui_state())
        body.addWidget(self.data_drawer)

        self.config_panel = ConfigDiffPanel()
        self.config_drawer = CollapsibleDrawer(
            "Config", self.config_panel, open=ui_state.config_drawer_open,
            width=ui_state.config_drawer_width)
        self.config_drawer.toggled.connect(lambda _open: self._save_ui_state())
        body.addWidget(self.config_drawer)

        layout.addWidget(body, 1)

        self._current_summary: dict | None = None
        self._current_fitness: float | None = None

    # ---- header/keyboard entry points --------------------------------

    def toggle_playback(self) -> None:
        self.video_player.toggle_playback()

    # ---- run lifecycle (main_window.py calls these) -------------------

    def set_running(self, running: bool) -> None:
        self.cancel_button.setEnabled(running)
        self.batch_button.setEnabled(not running)

    def set_progress(self, frame: int, max_frames: int) -> None:
        pct = int(100 * frame / max_frames) if max_frames else 0
        self.progress.setValue(min(100, pct))

    def show_result(self, text: str, is_error: bool = False) -> None:
        """Non-blocking: a label, not a dialog -- a run finishing must
        never pop a modal (nothing dismisses one in an automated/
        offscreen run, and it interrupts a fluid Play -> Play cycle).
        Chips carry the at-a-glance numbers now; this stays for the
        fuller sentence (and errors/batch summaries, which don't fit a
        chip well)."""
        color = "red" if is_error else "black"
        self.result_label.setStyleSheet(f"color: {color}")
        self.result_label.setText(text)

    def set_stats(self, summary: dict | None, fitness: float | None) -> None:
        self._current_summary = summary
        self._current_fitness = fitness
        self.stat_chips.set_summary(summary, fitness)

    def refresh_history(self, entries: list[dict]) -> None:
        self.run_table.set_entries(entries)

    def load_run_data(self, raw_frames_path, tel, info: dict, run_config=None) -> None:
        """Feeds the player, plots, and both text drawers from one
        completed run -- the single place all of a run's own displays get
        updated together, so they can never show data from two different
        runs at once."""
        self._current_summary = info
        self.video_player.load_run(raw_frames_path, tel, info)
        if tel is not None:
            self.plots.set_dataframe(tel)
        self.config_panel.set_config(run_config)
        self._refresh_data_panel()

    def _refresh_data_panel(self) -> None:
        row = self.video_player.current_row()
        self.data_panel.set_content(row, self._current_summary)

    # ---- internal wiring ------------------------------------------------

    def _on_frame_changed(self, frame: int) -> None:
        self.plots.set_playhead(frame)
        self._refresh_data_panel()

    def _on_brain_map_toggled(self, _checked: bool) -> None:
        self._save_ui_state()

    def _on_row_selected(self, entry: dict) -> None:
        self._window.load_history_run(entry)

    def _on_export_clicked(self) -> None:
        number = self.run_table.selected_number()
        if number is None:
            self.show_result("Select a run in the table to export.", is_error=True)
            return
        path = self._window.export_history_run({"number": number})
        self.show_result(f"Exported #{number:03d} to {path}")

    def _save_ui_state(self) -> None:
        """"Remember which drawers are open and how wide" -- persisted
        into ToolSettings (tool.json), not just this session's memory."""
        settings = self._window.get_tool_settings()
        new_state = RunTabUIState(
            runs_drawer_open=self.runs_drawer.is_open(),
            runs_drawer_width=self.runs_drawer.width_when_open(),
            plots_drawer_open=self.plots_drawer.is_open(),
            plots_drawer_width=self.plots_drawer.width_when_open(),
            data_drawer_open=self.data_drawer.is_open(),
            data_drawer_width=self.data_drawer.width_when_open(),
            config_drawer_open=self.config_drawer.is_open(),
            config_drawer_width=self.config_drawer.width_when_open(),
            brain_map_visible=self.video_player.brain_map_button.isChecked(),
        )
        self._window.set_tool_settings(dataclasses.replace(settings, run_tab_ui=new_state))
