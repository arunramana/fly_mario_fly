"""tool/ui/tabs/run.py -- tab 7: Run tab / player redesign. Two sub-tabs,
"▶ Player" (the video, its auto-hiding transport, the run playlist,
and the Brain map/Data/Config overlays) and "Plots" (the telemetry grid,
playhead synced to the player). Play lives only in the header
(main_window.py's START button, Ctrl+Enter; Space drives the player's own
play/pause) -- this tab keeps Cancel (no header equivalent) and the batch
button.

`self.preview`/`self.preview.frame_label`/`self.preview.show_frame` stay
as aliases for `self.player` -- tool/tests monkeypatches `window.run_tab.
preview.show_frame` directly (the exact call site main_window.py's poll
loop uses) and reads `.frame_label.pixmap()`, unaffected by this tab's own
internal reshuffle.

Explicitly deferred, not built here (by request, so a future sprint knows
this was a choice, not an oversight): A/B comparison, clip export,
bookmarks, looping a section.
"""

from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QMessageBox, QProgressBar, QPushButton, QTabWidget, QVBoxLayout, QWidget,
)

from tool.core.batch_summary import entries_in_batch
from tool.ui.widgets.batch_summary_table import BatchSummaryTable
from tool.ui.widgets.controller_pad import ControllerPad
from tool.ui.widgets.learning_chart import LearningChart
from tool.ui.widgets.plots import TelemetryPlots
from tool.ui.widgets.run_brain_map_overlay import BrainMapOverlayContent
from tool.ui.widgets.run_data_overlay import DataOverlayContent
from tool.ui.widgets.run_detail_panels import ConfigPanelContent
from tool.ui.widgets.run_edge_panel import EdgePanel
from tool.ui.widgets.run_player import RunPlayer
from tool.ui.widgets.scroll_page import install_scroll_page
from tool.ui.widgets.run_picker import RunPicker
from tool.ui.widgets.stat_chips import StatChips

MIN_VIDEO_AREA_SCREEN_FRACTION = 0.45   # the player never gets less than this share of screen height; the tab scrolls instead

SHORTCUT_HELP = """Space -- play / pause
← / → -- step one frame back / forward
Shift+← / Shift+→ -- jump 1 second back / forward
N / P -- next / previous event (jump, climb, stomp, death/flag)
F -- fullscreen
B -- toggle the Brain map overlay
I -- toggle the controller overlay (◀ ▶ B A)
D -- toggle the Data overlay
C -- toggle the Config overlay
? -- this list
Ctrl+Enter -- START a new run
Ctrl+S -- Save
Ctrl+1..7 -- switch tabs
Escape -- cancel a running run"""


class RunTab(QWidget):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self._window = window
        self._current_summary: dict | None = None
        content = QWidget()
        layout = QVBoxLayout(content)
        install_scroll_page(self, content)

        controls = QHBoxLayout()
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(window.cancel)
        self.cancel_button.setEnabled(False)
        self.batch_button = QPushButton("Run batch (seeds from Goal tab)")
        self.batch_button.clicked.connect(window.run_batch)
        self.progress = QProgressBar()
        controls.addWidget(self.cancel_button)
        controls.addWidget(self.batch_button)
        controls.addWidget(self.progress)
        layout.addLayout(controls)

        self.stat_chips = StatChips()
        layout.addWidget(self.stat_chips)
        self.result_label = QLabel("")
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)
        self.fps_label = QLabel("")     # live runs only: sim frames/s vs displayed frames/s
        layout.addWidget(self.fps_label)
        self.batch_table = BatchSummaryTable()
        layout.addWidget(self.batch_table)
        self._entries: list[dict] = []

        self.sub_tabs = QTabWidget()
        screen = self.screen() or QGuiApplication.primaryScreen()
        self.sub_tabs.setMinimumHeight(int(screen.availableGeometry().height() * MIN_VIDEO_AREA_SCREEN_FRACTION))
        layout.addWidget(self.sub_tabs, 1)

        self._build_player_page()
        self.plots = TelemetryPlots()
        self.plots.seek_requested.connect(self._on_plot_seek)
        self.sub_tabs.addTab(self.plots, "Plots")
        self.learning = LearningChart()
        self.learning.point_selected.connect(self._on_learning_point)
        self.sub_tabs.addTab(self.learning, "Learning")

        self.player.frame_changed.connect(self._on_frame_changed)
        self.player.live_row.connect(self._on_live_row)
        self.playlist.run_selected.connect(self._on_playlist_run_selected)
        self.playlist.save_state_requested.connect(lambda: window.save_state_here())

    # ---- Player sub-tab: video + playlist + overlays --------------------

    def _build_player_page(self) -> None:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        self.playlist = RunPicker()  # top bar: run dropdown + prev/next
        page_layout.addWidget(self.playlist)
        self.player = RunPlayer()
        # QLabel-era compatibility alias -- see this module's own docstring.
        self.preview = self.player
        page_layout.addWidget(self.player, 1)

        # Panels are children of the canvas placed by absolute geometry --
        # never in a layout, so they can't move or resize the video.
        canvas = self.player.canvas
        self.brain_map_content = BrainMapOverlayContent()
        self.brain_overlay = EdgePanel("brain_map", "◀ Brain", self.brain_map_content, QSize(260, 330), canvas)
        self.data_content = DataOverlayContent()
        self.data_overlay = EdgePanel("data", "Data ▶", self.data_content, QSize(260, 150), canvas)
        self.config_content = ConfigPanelContent()
        self.config_overlay = EdgePanel("config", "Config ▶", self.config_content, QSize(260, 220), canvas)
        # The controller pad: a child of the canvas like the panels, placed over
        # the bottom strip of the VIDEO rect; on by default, toggled with I.
        self.controller_pad = ControllerPad(canvas)
        for panel in (self.brain_overlay, self.data_overlay, self.config_overlay):
            panel.toggled.connect(lambda _open: self._place_panels())
        self.brain_overlay.toggled.connect(self._refresh_brain_map)
        self.player.canvas_resized.connect(self._place_panels)
        self._place_panels()
        self._refresh_brain_map()

        self.sub_tabs_page = page
        self.sub_tabs.addTab(page, "▶ Player")

    def _place_panels(self) -> None:
        """Left: Brain, full height. Right: Data above Config. Width = the
        margin beside the video (at least the drawer's width fraction: narrower windows let
        the panels overlap the video, transparently). Sizes never touch the
        canvas, so the video rect is unchanged."""
        canvas = self.player.canvas
        w, h = canvas.width(), canvas.height()
        margin = max(0, (w - canvas.target_rect().width()) // 2)
        pw = max(margin, *(p.min_width_for(w) for p in (self.brain_overlay, self.data_overlay, self.config_overlay)))
        avail = max(60, h - self.player.transport.sizeHint().height() - 8)
        tab = self.brain_overlay.tab.sizeHint().height()

        def body(panel, height):
            panel.content.setFixedSize(QSize(pw, max(20, height - tab)))
            panel.adjustSize()

        body(self.brain_overlay, avail)
        data, cfg = self.data_overlay, self.config_overlay
        if data.is_open() and cfg.is_open():
            body(data, int(avail * 0.6) - 3)
            body(cfg, avail - int(avail * 0.6) - 3)
        else:
            body(data, avail - tab - 6)
            body(cfg, avail - tab - 6)
        self.brain_overlay.move(0, 4)
        data.move(w - data.width(), 4)
        cfg.move(w - cfg.width(), 4 + data.height() + 6)
        for panel in (self.brain_overlay, data, cfg):
            panel.raise_()
        # Pad: the bottom strip of the video itself, never resizing anything.
        video = canvas.target_rect()
        pad_w = int(min(video.width() * 0.5, 280))
        pad_h = int(min(video.height() * 0.14, 56))
        self.controller_pad.setGeometry(video.x() + (video.width() - pad_w) // 2,
                                        video.y() + video.height() - pad_h - 6, pad_w, pad_h)
        self.controller_pad.raise_()
        self._refresh_brain_map()

    def _refresh_brain_map(self, *_args) -> None:
        if self.brain_overlay.is_open():
            self.brain_map_content.update_frame(self.player._current_frame_index)

    def toggle_brain_map(self) -> None:
        self.brain_overlay.toggle()

    def toggle_controller_overlay(self) -> None:
        self.controller_pad.setVisible(self.controller_pad.isHidden())

    def toggle_data_overlay(self) -> None:
        self.data_overlay.toggle()

    def toggle_config_overlay(self) -> None:
        self.config_overlay.toggle()

    def show_shortcut_help(self) -> None:
        QMessageBox.information(self, "Player shortcuts", SHORTCUT_HELP)

    def show_batch_for(self, number: int) -> None:
        """Show the summary table of the batch run `number` belongs to (hide it for a plain run)."""
        entry = next((e for e in self._entries if e["number"] == number), None)
        self.batch_table.set_entries(entries_in_batch(self._entries, entry.get("batch_id") if entry else None))

    def set_fps(self, sim: float | None, shown: float | None = None) -> None:
        self.fps_label.setText("" if sim is None else f"live: sim {sim:.0f} fps · displayed {shown:.0f} fps")

    def _on_playlist_run_selected(self, number: int) -> None:
        self.show_batch_for(number)
        self._window.select_history_run(number)

    def _on_learning_point(self, number: int) -> None:
        """A point on the Learning chart: load that episode in the Player
        ("telemetry only" if its frames weren't kept)."""
        self.playlist.select_number(number)
        self._window.select_history_run(number)
        self.sub_tabs.setCurrentIndex(0)

    # ---- transport delegation (main_window.py's keyboard shortcuts) ------

    def toggle_playback(self) -> None:
        self.player.toggle_playback()

    def step_frame(self, delta: int) -> None:
        self.player.step_frame(delta)

    def jump_seconds(self, delta: float) -> None:
        self.player.jump_seconds(delta)

    def next_event(self) -> None:
        self.player.next_event()

    def prev_event(self) -> None:
        self.player.prev_event()

    def toggle_fullscreen(self) -> None:
        self.player.toggle_fullscreen()

    # ---- frame -> Plots/overlays sync -------------------------------------

    def _on_frame_changed(self, frame: int) -> None:
        self.plots.set_playhead(frame)
        row = self.player.current_row()
        row_dict = row.to_dict() if row is not None else None
        action = self.player.current_action()
        if action is not None:      # the button actually pressed, from the run's action log
            self.controller_pad.set_from_action(action)
        else:                       # no log (older run): fall back to the telemetry
            self.controller_pad.set_from_row(row_dict)
        self.data_content.update_from_row(row_dict)
        if self.brain_overlay.is_open():
            self.brain_map_content.update_frame(frame)

    def _on_live_row(self, row: dict) -> None:
        self.controller_pad.set_from_row(row)          # the pad shows during live runs too
        self.data_content.update_from_row(row)

    def _on_plot_seek(self, frame: int) -> None:
        self.player.seek_frame(frame)
        self.sub_tabs.setCurrentIndex(0)

    # ---- run lifecycle (main_window.py's own calls) -----------------------

    def set_running(self, running: bool) -> None:
        self.cancel_button.setEnabled(running)
        if not running:
            self.set_fps(None)
        self.batch_button.setEnabled(not running)
        self.player.set_live(running)

    def set_progress(self, frame: int, max_frames: int) -> None:
        pct = int(100 * frame / max_frames) if max_frames else 0
        self.progress.setValue(min(100, pct))

    def show_result(self, text: str, is_error: bool = False) -> None:
        color = "red" if is_error else "black"
        self.result_label.setStyleSheet(f"color: {color}")
        self.result_label.setText(text)

    def set_stats(self, summary: dict | None, fitness: float | None) -> None:
        self._current_summary = summary
        self.data_content.set_summary(summary)
        self.stat_chips.set_summary(summary, fitness)

    def refresh_history(self, entries: list[dict]) -> None:
        from tool.core.fitness import fitness_of
        fitness_settings = self._window.project.tool_settings.fitness
        enriched = []
        for entry in entries:
            summary = entry.get("summary", {})
            fitness = None if summary.get("cancelled") else fitness_of(fitness_settings, summary)
            enriched.append({**entry, "fitness": fitness})
        self._entries = list(entries)
        self.playlist.set_entries(enriched)
        self.learning.set_entries(entries)

    def select_run(self, number: int) -> bool:
        self.show_batch_for(number)
        return self.playlist.select_number(number)

    def load_run_data(self, raw_frames_path, tel, info: dict, run_config=None) -> None:
        """Feeds the player, plots, and overlays from one completed run --
        the single place all of a run's own displays get updated
        together, so they can never show data from two different runs
        at once."""
        self.player.load_run(raw_frames_path, tel, info)
        if tel is not None:
            self.plots.set_dataframe(tel)
        # Summary before Config, and Config guarded: a config that cannot be
        # rendered must never leave the other panels showing the previous run.
        self.data_content.set_summary(info)
        try:
            self.config_content.set_config(run_config)
        except Exception as exc:  # noqa: BLE001 -- display only; never block the rest
            self.config_content.panel.setHtml(
                f"<i>(config could not be shown: {type(exc).__name__}: {exc})</i>")
        self.brain_map_content.set_telemetry(tel)
        self._refresh_brain_map()
        row = self.player.current_row()
        self.data_content.update_from_row(row.to_dict() if row is not None else None)
