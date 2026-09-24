"""tool/ui/main_window.py -- header (project name, dirty marker, Save,
Play) + seven tabs (tool/PLAN.md P3/P4). Owns the Play/Cancel worker
process: a multiprocessing.Process running tool.core.runner.
run_one_streaming, polled by a QTimer, stopped by a shared
multiprocessing.Event -- "Play and Cancel through a shared stop event."
"""

from __future__ import annotations

import multiprocessing as mp

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton,
    QTabWidget, QVBoxLayout, QWidget,
)

from tool.core.fitness import fitness_of
from tool.core.run_spec import RunSpec
from tool.core.run_store import (
    export_run_bundle, next_run_number, record_run, write_run_note, list_runs,
)
from tool.core.runner import run_one_streaming
from tool.core.batch import run_batch


class MainWindow(QMainWindow):
    # Emitted at the end of set_config() with the NEW ProjectConfig --
    # tool/SPEC_ui_retro.md section 3's "one home per setting": any tab
    # showing a value it doesn't own (e.g. Goal's read-only noise.sigma
    # display) subscribes to this instead of taking a snapshot once at
    # construction, so it can never go stale after an edit made from
    # wherever that value's own single writable home actually is.
    config_changed = Signal(object)

    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self._dirty = False
        self._process: mp.Process | None = None
        self._queue: mp.Queue | None = None
        self._stop_event: mp.Event | None = None
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(33)  # ~30fps preview polling
        self._poll_timer.timeout.connect(self._poll_queue)
        self._current_run_number: int | None = None
        self._current_run_slug: str | None = None

        self.setWindowTitle(self._title())
        self.resize(1100, 800)

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)

        header = QHBoxLayout()
        self.title_label = QLabel(self._title())
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save)
        # tool/SPEC_ui_retro.md section 5: restyled and relabelled
        # "START" (the retro/arcade convention), not a new, separate
        # screen -- the project gate is already this app's own "insert
        # coin" step. objectName drives tool/ui/style.qss's
        # #startButton rule.
        header_play_button = QPushButton("START")
        header_play_button.setObjectName("startButton")
        header_play_button.clicked.connect(self.play)
        header.addWidget(self.title_label)
        header.addStretch(1)
        header.addWidget(save_button)
        header.addWidget(header_play_button)
        outer.addLayout(header)

        self.tabs = QTabWidget()
        outer.addWidget(self.tabs)

        # tool/SPEC_ui_retro.md section 10 (minimal scope): the seven tabs
        # are built by iterating TAB_REGISTRY, not seven hardcoded
        # addTab() calls -- adding a tab needs an entry there, not an
        # edit here (tool/tests/test_tab_registry.py's own dummy-entry
        # test proves it). self.character_tab/self.run_tab stay named
        # attributes (other code reaches into them directly, e.g.
        # on_player_changed -> self.run_tab.preview.set_player) --
        # `attr_name` on the matching entries is how those two still get
        # stashed, without a full self.tab(name) reach-through refactor.
        from tool.core.tab_registry import TAB_REGISTRY

        self._tab_factories = {}
        for index, entry in enumerate(TAB_REGISTRY):
            widget = entry.factory(self)
            self.tabs.addTab(widget, entry.title)
            if entry.attr_name:
                setattr(self, entry.attr_name, widget)
            # reload_tab() only ever rebuilds a tab OTHER than "run" today
            # (P7 presets, C8a's enemies/objects sync) -- run.py has no
            # reload path of its own, so it's left out of the factory map
            # exactly as it was before this registry existed.
            if entry.tab_id != "run":
                self._tab_factories[entry.tab_id] = (index, entry.factory)

        self.run_tab.refresh_history(list_runs(self.project.name))

        # P7 keyboard shortcuts. ApplicationShortcut, not the default
        # WindowShortcut: there is only ever one window open at a time
        # (the project gate closes before this one opens), so window vs.
        # application scope makes no practical difference here, and
        # ApplicationShortcut doesn't depend on the platform's own notion
        # of "the active window" -- WindowShortcut silently never fired
        # under the offscreen QPA platform tool/tests runs under, since
        # offscreen never marks a window active the way a real window
        # manager would.
        for shortcut, slot in (
            (QKeySequence(Qt.Key.Key_Space), self.play),
            (QKeySequence.StandardKey.Save, self.save),
        ):
            sc = QShortcut(shortcut, self, activated=slot)
            sc.setContext(Qt.ShortcutContext.ApplicationShortcut)

        # Escape does NOT go through QShortcut (found in real desktop
        # testing, not offscreen -- a QShortcut, Application-scoped or
        # not, is delivered through the same notify()/ShortcutOverride
        # pipeline a focused widget gets first refusal on; many widgets
        # -- a spin box mid-edit among them -- claim Escape for their own
        # "revert" behaviour and never let it reach the shortcut map at
        # all). An event filter on the QApplication itself gets every
        # key event before ANY widget's own keyPressEvent, so nothing
        # downstream ever gets a chance to swallow it first.
        QApplication.instance().installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:
        # Only claims Escape while a run is actually active -- otherwise a
        # legitimate, ordinary use of Escape elsewhere (a spin box
        # reverting an in-progress edit, a combo box closing its popup)
        # would be silently swallowed for no reason. Cancelling a run in
        # progress is the one case Escape must win unconditionally.
        if (event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape
                and self._process is not None and self._process.is_alive()):
            self.cancel()
            return True
        return super().eventFilter(obj, event)

    # ---- project state accessors (tabs read/write through these) --------

    def _title(self) -> str:
        return f"fly_mario -- {self.project.name}{' *' if self._dirty else ''}"

    def get_config(self):
        return self.project.config

    def set_config(self, config) -> None:
        self.project.config = config
        self.mark_dirty()
        self.config_changed.emit(config)

    def get_tool_settings(self):
        return self.project.tool_settings

    def set_tool_settings(self, settings) -> None:
        self.project.tool_settings = settings
        self.mark_dirty()

    def mark_dirty(self) -> None:
        self._dirty = True
        self.title_label.setText(self._title())
        self.setWindowTitle(self._title())

    def on_player_changed(self, player: str) -> None:
        self.run_tab.preview.set_player(player)

    def reload_tab(self, key: str) -> None:
        """Rebuilds one tab from current window state (P7 presets: after a
        preset load replaces window.config/tool_settings, the tab's own
        widgets -- built once from the OLD values in __init__ -- have no
        other way to pick up the change)."""
        index, factory = self._tab_factories[key]
        was_current = self.tabs.currentIndex()
        title = self.tabs.tabText(index)
        old_widget = self.tabs.widget(index)
        new_widget = factory(self)
        self.tabs.removeTab(index)
        self.tabs.insertTab(index, new_widget, title)
        # Preserve whichever tab the user was actually on -- reload_tab is
        # also used to sync a DIFFERENT tab (enemies.py/objects.py's
        # shared checkbox, C8a) than the one whose control was just
        # changed, and that must not steal focus away from it.
        self.tabs.setCurrentIndex(was_current)
        old_widget.deleteLater()
        if key == "character":
            self.character_tab = new_widget

    def save(self) -> None:
        self.project.save()
        self._dirty = False
        self.title_label.setText(self._title())
        self.setWindowTitle(self._title())

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._dirty:
            reply = QMessageBox.question(
                self, "Unsaved changes",
                "This project has unsaved changes. Save before closing?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Save:
                self.save()
            elif reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
        if self._process is not None and self._process.is_alive():
            self.cancel()
        event.accept()

    # ---- Play / Cancel, through a shared stop event ----------------------

    def _make_run_spec(self, seed: int, out_filename: str) -> RunSpec:
        return RunSpec(project_name=self.project.name, config=self.project.config,
                        tool_settings=self.project.tool_settings, seed=seed,
                        out_filename=out_filename)

    def play(self) -> None:
        if self._process is not None and self._process.is_alive():
            return
        seed = self.project.tool_settings.experiment.seeds[0]
        number = next_run_number(self.project.name)
        slug = f"{number:03d}_play_seed{seed}"
        spec = self._make_run_spec(seed, f"{slug}.mp4")
        self._current_run_number = number
        self._current_run_slug = slug

        ctx = mp.get_context("spawn")
        self._queue = ctx.Queue()
        self._stop_event = ctx.Event()
        self._process = ctx.Process(target=run_one_streaming, args=(spec, self._queue, self._stop_event))
        self._process.start()
        self.run_tab.set_running(True)
        self.run_tab.progress.setValue(0)
        self._poll_timer.start()

    def cancel(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()

    def _poll_queue(self) -> None:
        if self._queue is None:
            return
        max_frames = self.project.config.scenario.max_frames
        while not self._queue.empty():
            message = self._queue.get_nowait()
            kind = message[0]
            if kind == "frame":
                obs, row = message[1], message[2]
                self.run_tab.preview.show_frame(obs, row)
                self.run_tab.set_progress(row.get("frame", 0), max_frames)
            elif kind == "done":
                info = message[1]
                self._on_run_finished(info)
                return
            elif kind == "error":
                self._on_run_error(message[1])
                return

    def _on_run_finished(self, info: dict) -> None:
        self._poll_timer.stop()
        if self._process is not None:
            self._process.join(timeout=5)
        self._process = None
        self.run_tab.set_running(False)
        # The run is over either way (completed, died, or cancelled) -- the
        # bar should read "no run is in progress", not whatever fraction of
        # max_frames it happened to reach (found in manual testing: a
        # cancelled or early-died run left the bar visibly short of full).
        self.run_tab.progress.setValue(100)

        number, slug = self._current_run_number, self._current_run_slug
        seed = self.project.tool_settings.experiment.seeds[0]
        spec = self._make_run_spec(seed, f"{slug}.mp4")
        was_cancelled = bool(info.get("cancelled"))
        record_run(self.project.name, number, slug, seed, info, spec.to_dict())
        write_run_note(self.project.name, number, slug, seed,
                        self.project.config, self.project.tool_settings, info)
        self.run_tab.refresh_history(list_runs(self.project.name))
        self._load_telemetry_into_plots(slug)

        if was_cancelled:
            text = f"Run #{number}: CANCELLED at frame {info.get('n_frames')}"
        else:
            fitness = fitness_of(self.project.tool_settings.fitness, info)
            text = (f"Run #{number}: fitness={fitness:.1f}, frames={info.get('n_frames')}, "
                    f"died={info.get('died_or_flagged')}, max_x={info.get('max_x_abs')}")
        self.run_tab.show_result(text)
        self.statusBar().showMessage(text, 10_000)

    def _on_run_error(self, message: str) -> None:
        self._poll_timer.stop()
        if self._process is not None:
            self._process.join(timeout=5)
        self._process = None
        self.run_tab.set_running(False)
        text = f"Run failed: {message}"
        self.run_tab.show_result(text, is_error=True)
        self.statusBar().showMessage(text, 10_000)

    # ---- Batch -------------------------------------------------------

    def run_batch(self) -> None:
        seeds = list(self.project.tool_settings.experiment.seeds)
        n_workers = self.project.tool_settings.render.parallel_workers
        result = run_batch(self.project, seeds=seeds, n_workers=n_workers)
        self.run_tab.refresh_history(list_runs(self.project.name))
        self.run_tab.show_batch_result(result)

    # ---- History -------------------------------------------------------

    def _load_telemetry_into_plots(self, slug: str) -> None:
        """Shared by _on_run_finished (a run JUST played) and
        load_history_run (an OLDER run picked from the list) -- found in
        manual testing that only the latter path existed, so the Plots
        tab stayed empty after every live Play until the user separately
        went and re-selected that same run from History."""
        import pandas as pd
        from config.output_routing import resolve_telemetry_path
        telemetry_path = resolve_telemetry_path(self.project.config, f"{slug}_telemetry.csv")
        if telemetry_path.exists():
            tel = pd.read_csv(telemetry_path)
            self.run_tab.plots.set_dataframe(tel)

    def load_history_run(self, entry: dict) -> None:
        slug = entry["slug"]
        self._load_telemetry_into_plots(slug)
        from config.output_routing import resolve_run_path
        video_path = resolve_run_path(self.project.config, f"{slug}.mp4")
        if video_path.exists():
            self.run_tab.show_video(video_path)

    def export_history_run(self, entry: dict):
        return export_run_bundle(self.project.name, entry["number"])
