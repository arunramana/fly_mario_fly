"""tool/ui/tabs/run.py -- tab 7: live preview, progress, cancel; run
history; telemetry plots; video playback; a batch view of the spread
across seeds (tool/PLAN.md P4). Play is also always in the header
(main_window.py) so edit->play doesn't need a tab switch -- both call the
same MainWindow methods.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QProgressBar,
    QPushButton, QSplitter, QTabWidget, QVBoxLayout, QWidget,
)

from tool.ui.widgets.plots import TelemetryPlots
from tool.ui.widgets.preview import PreviewWidget


class RunTab(QWidget):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self._window = window
        layout = QVBoxLayout(self)

        controls = QHBoxLayout()
        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(window.play)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(window.cancel)
        self.cancel_button.setEnabled(False)
        self.batch_button = QPushButton("Run batch (seeds from Goal tab)")
        self.batch_button.clicked.connect(window.run_batch)
        self.progress = QProgressBar()
        controls.addWidget(self.play_button)
        controls.addWidget(self.cancel_button)
        controls.addWidget(self.batch_button)
        controls.addWidget(self.progress)
        layout.addLayout(controls)

        # Non-blocking result line -- a run finishing must never pop a
        # modal dialog: nothing dismisses one in an automated/offscreen
        # run, and it's a bad interruption in normal use too (a Play ->
        # Play cycle should stay fluid). main_window.py also mirrors this
        # onto the window's status bar.
        self.result_label = QLabel("")
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        self.preview = PreviewWidget()
        left_layout.addWidget(self.preview)
        splitter.addWidget(left)

        right = QTabWidget()
        self.plots = TelemetryPlots()
        right.addTab(self.plots, "Plots")

        self.video_widget = QVideoWidget()
        self.media_player = QMediaPlayer()
        self.media_player.setVideoOutput(self.video_widget)
        right.addTab(self.video_widget, "Video")

        self.history_list = QListWidget()
        self.history_list.itemDoubleClicked.connect(self._on_history_selected)
        right.addTab(self.history_list, "History")

        self.batch_label = QLabel("No batch run yet.")
        self.batch_label.setWordWrap(True)
        right.addTab(self.batch_label, "Batch")

        splitter.addWidget(right)
        layout.addWidget(splitter)

    def set_running(self, running: bool) -> None:
        self.play_button.setEnabled(not running)
        self.cancel_button.setEnabled(running)
        self.batch_button.setEnabled(not running)

    def set_progress(self, frame: int, max_frames: int) -> None:
        pct = int(100 * frame / max_frames) if max_frames else 0
        self.progress.setValue(min(100, pct))

    def show_result(self, text: str, is_error: bool = False) -> None:
        """Non-blocking: a label, not a dialog -- see this tab's own
        __init__ docstring note on why a run finishing must never pop a
        modal."""
        color = "red" if is_error else "black"
        self.result_label.setStyleSheet(f"color: {color}")
        self.result_label.setText(text)

    def refresh_history(self, entries: list[dict]) -> None:
        self.history_list.clear()
        for entry in reversed(entries):
            summary = entry.get("summary", {})
            text = (
                f"#{entry['number']:03d}  seed={entry['seed']}  "
                f"frames={summary.get('n_frames')}  "
                f"died={summary.get('died_or_flagged')}  "
                f"max_x={summary.get('max_x_abs')}"
            )
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self.history_list.addItem(item)

    def _on_history_selected(self, item: QListWidgetItem) -> None:
        entry = item.data(Qt.ItemDataRole.UserRole)
        self._window.load_history_run(entry)

    def show_video(self, path) -> None:
        from PySide6.QtCore import QUrl
        self.media_player.setSource(QUrl.fromLocalFile(str(path)))
        self.media_player.play()

    def show_batch_result(self, result) -> None:
        lines = [f"seed {seed}: fitness={fit:.1f}"
                 for seed, fit in zip(getattr(result, "seeds", []), result.fitnesses)]
        if not lines:
            lines = [f"fitness={fit:.1f}" for fit in result.fitnesses]
        mean = sum(result.fitnesses) / len(result.fitnesses) if result.fitnesses else 0.0
        lines.append(f"\nmean={mean:.1f}  min={min(result.fitnesses):.1f}  max={max(result.fitnesses):.1f}")
        self.batch_label.setText("\n".join(lines))
