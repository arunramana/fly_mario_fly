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
    QApplication, QHBoxLayout, QInputDialog, QLabel, QMainWindow, QMenu,
    QMessageBox, QPushButton, QTabWidget, QToolButton, QVBoxLayout, QWidget,
)

from tool.core.batch_summary import format_batch_result
from tool.core.fitness import fitness_of
from tool.core.run_spec import RunSpec
from tool.core.run_store import (
    export_run_bundle, next_run_number, record_run, write_run_note, list_runs,
)
from tool.core.runner import run_one_streaming
from tool.core.batch import run_batch

# Ease-of-use redesign, "Presets: move them into a single header menu":
# tab-key -> menu label, for exactly the tabs that used to carry their
# own PresetBar (tool/ui/widgets/preset_bar.py, now unused/deleted).
PRESET_TAB_KEYS = [("character", "Character"), ("circuits", "Circuits"),
                    ("goal", "Goal"), ("settings", "Settings")]


class MainWindow(QMainWindow):
    # Emitted at the end of set_config() with the NEW ProjectConfig --
    # tool/SPEC_ui_retro.md section 3's "one home per setting": any tab
    # showing a value it doesn't own (e.g. Goal's read-only noise.sigma
    # display) subscribes to this instead of taking a snapshot once at
    # construction, so it can never go stale after an edit made from
    # wherever that value's own single writable home actually is.
    config_changed = Signal(object)

    # Ease-of-use redesign: emitted once a Home click has cleared the
    # unsaved-changes guard and this window is closing -- app.py listens
    # so it can show the project gate again and open a new MainWindow,
    # instead of the app ending the way closing the window normally does.
    home_requested = Signal()

    # "Duplicate to edit" on a read-only project (tool/core/project.py's
    # READ_ONLY_PROJECT_NAMES) -- carries the newly duplicated ToolProject
    # so app.py can open it directly, skipping the gate a Home click goes
    # through (the user already said exactly which project they want).
    project_switch_requested = Signal(object)

    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self._dirty = False
        self._closing_confirmed = False
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
        # Ease-of-use redesign: returns to the project gate (the
        # unsaved-changes guard applies exactly like closing the window).
        home_button = QPushButton("Home")
        home_button.clicked.connect(self._go_home)
        self.title_label = QLabel(self._title())
        # Presets: one header menu next to Save (ease-of-use redesign),
        # not a top-level QMenuBar entry floating above the header, and
        # not a per-tab bar (tool/ui/widgets/preset_bar.py, deleted).
        self.presets_button = self._build_presets_button()
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save)
        # tool/SPEC_ui_retro.md section 5: restyled and relabelled
        # "START" (the retro/arcade convention), not a new, separate
        # screen -- the project gate is already this app's own "insert
        # coin" step. objectName drives tool/ui/style.qss's
        # #startButton rule. Ctrl+Enter, not Space -- Space now drives
        # the Run tab's video-player play/pause instead.
        header_play_button = QPushButton("START")
        header_play_button.setObjectName("startButton")
        header_play_button.clicked.connect(self.play)
        header.addWidget(home_button)
        header.addWidget(self.title_label)
        header.addStretch(1)
        header.addWidget(self.presets_button)
        header.addWidget(self.save_button)
        header.addWidget(header_play_button)
        outer.addLayout(header)

        # Ease-of-use redesign: a read-only reference project (tool/core/
        # project.py's READ_ONLY_PROJECT_NAMES, "legacy" today) shows this
        # banner instead of silently accepting edits nobody would notice
        # drifted it -- found live: habituation.hab_give_up changed 3 -> -2
        # with no record of when or why.
        self.read_only_banner = QLabel(
            "This is the read-only reference project -- every control below is "
            "disabled. Duplicate it to make changes."
        )
        self.read_only_banner.setObjectName("readOnlyBanner")
        self.read_only_banner.setWordWrap(True)
        duplicate_button = QPushButton("Duplicate to edit")
        duplicate_button.clicked.connect(self._on_duplicate_to_edit)
        banner_row = QHBoxLayout()
        banner_row.addWidget(self.read_only_banner, 1)
        banner_row.addWidget(duplicate_button)
        self.read_only_banner_row = QWidget()
        self.read_only_banner_row.setLayout(banner_row)
        self.read_only_banner_row.setVisible(self.project.is_read_only)
        outer.addWidget(self.read_only_banner_row)

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

        # Ease-of-use redesign: a read-only reference project disables
        # every editing control in one shot -- the whole tab widget,
        # Save, and the Presets menu (loading a preset would also edit
        # it). Play/batch stay enabled: RUNNING the project is fine, nor
        # does it ever call ToolProject.save().
        if self.project.is_read_only:
            self.tabs.setEnabled(False)
            self.save_button.setEnabled(False)
            self.presets_button.setEnabled(False)

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
            # Ease-of-use redesign: Space now drives the Run tab's video
            # player play/pause; START (a brand new simulation run)
            # moved to Ctrl+Enter so the two "play" actions -- watch a
            # recording vs. run a fresh episode -- don't share a key.
            (QKeySequence(Qt.Key.Key_Space), lambda: self.run_tab.toggle_playback()),
            (QKeySequence("Ctrl+Return"), self.play),
            (QKeySequence("Ctrl+Enter"), self.play),
            (QKeySequence.StandardKey.Save, self.save),
        ):
            sc = QShortcut(shortcut, self, activated=slot)
            sc.setContext(Qt.ShortcutContext.ApplicationShortcut)

        # Ease-of-use redesign: Ctrl+1..Ctrl+7 jump straight to a tab.
        for i in range(self.tabs.count()):
            sc = QShortcut(QKeySequence(f"Ctrl+{i + 1}"), self,
                            activated=lambda index=i: self.tabs.setCurrentIndex(index))
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
        if self.project.is_read_only:
            # Unreachable in normal use (the Save button is disabled),
            # but a defensive check here costs nothing and this method is
            # also what QKeySequence.StandardKey.Save calls directly.
            return
        self.project.save()
        self._dirty = False
        self.title_label.setText(self._title())
        self.setWindowTitle(self._title())

    def _on_duplicate_to_edit(self) -> None:
        """The read-only banner's own button: makes an editable copy of
        this project and switches straight to it -- app.py opens the new
        MainWindow directly, skipping the project gate, since the user
        already said exactly which project they want."""
        name, ok = QInputDialog.getText(self, "Duplicate to edit", "New project name:")
        name = name.strip()
        if not ok or not name:
            return
        try:
            new_project = self.project.duplicate(name)
        except FileExistsError as exc:
            QMessageBox.warning(self, "Project exists", str(exc))
            return
        self._closing_confirmed = True
        self.project_switch_requested.emit(new_project)
        self.close()

    def _confirm_discard_or_save(self) -> bool:
        """Returns True when it's OK to proceed (nothing unsaved, or the
        user chose Save/Discard); False means Cancel -- the caller must
        abort. Shared by closeEvent and _go_home so the guard is asked
        exactly once per action, not once by each."""
        if not self._dirty:
            return True
        reply = QMessageBox.question(
            self, "Unsaved changes",
            "This project has unsaved changes. Save before closing?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Save:
            self.save()
            return True
        return reply == QMessageBox.StandardButton.Discard

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._closing_confirmed and not self._confirm_discard_or_save():
            event.ignore()
            return
        if self._process is not None and self._process.is_alive():
            self.cancel()
        event.accept()

    def _go_home(self) -> None:
        """Ease-of-use redesign: returns to the project gate, same
        unsaved-changes guard as closing the window -- asked here, once,
        not again by closeEvent's own guard when self.close() runs below
        (_closing_confirmed short-circuits it)."""
        if not self._confirm_discard_or_save():
            return
        if self._process is not None and self._process.is_alive():
            self.cancel()
        self._closing_confirmed = True
        self.home_requested.emit()
        self.close()

    # ---- Presets menu (header) -------------------------------------------

    def _build_presets_button(self) -> QToolButton:
        """tool/SPEC_ui_retro.md's ease-of-use follow-up: one header
        button (next to Save, not a separate QMenuBar row above the
        header) instead of a PresetBar on every tab that had one. Each
        submenu is populated lazily (aboutToShow) so it always lists
        whatever presets actually exist on disk right now, not a
        snapshot from when the window opened."""
        button = QToolButton()
        button.setText("Presets")
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(button)
        for key, label in PRESET_TAB_KEYS:
            submenu = menu.addMenu(label)
            submenu.aboutToShow.connect(lambda k=key, m=submenu: self._populate_preset_submenu(k, m))
        button.setMenu(menu)
        return button

    def _populate_preset_submenu(self, key: str, submenu) -> None:
        from tool.core.presets import list_presets

        submenu.clear()
        save_action = submenu.addAction("Save current as...")
        save_action.triggered.connect(lambda: self._save_preset(key))
        names = list_presets(key)
        if names:
            submenu.addSeparator()
            for name in names:
                action = submenu.addAction(name)
                action.triggered.connect(lambda checked=False, n=name: self._load_preset(key, n))

    def _preset_tab(self, key: str):
        index, _factory = self._tab_factories[key]
        return self.tabs.widget(index)

    def _save_preset(self, key: str) -> None:
        from tool.core.presets import save_preset

        name, ok = QInputDialog.getText(self, "Save preset", "Preset name:")
        name = name.strip()
        if not ok or not name:
            return
        save_preset(key, name, self._preset_tab(key)._preset_data())

    def _load_preset(self, key: str, name: str) -> None:
        from tool.core.presets import load_preset

        self._preset_tab(key)._apply_preset(load_preset(key, name))

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
        record_run(self.project.name, number, slug, seed, info, spec.to_dict())
        write_run_note(self.project.name, number, slug, seed,
                        self.project.config, self.project.tool_settings, info)
        self.run_tab.refresh_history(list_runs(self.project.name))
        # select_number() fires row_selected -> load_history_run(), the
        # SAME path a history pick takes -- one place loads a run's data
        # into the tab, whether it just finished or was picked from the
        # table (matches "show the result line once": one formatter,
        # tool/ui/main_window.py's own _format_result_line, either way).
        if not self.run_tab.run_table.select_number(number):
            # Defensive: refresh_history's own sort should always place
            # the just-recorded run somewhere in the table.
            self.load_history_run({"number": number, "slug": slug, "seed": seed,
                                    "summary": info, "run_spec": spec.to_dict()})
        self.statusBar().showMessage(self.run_tab.result_label.text(), 10_000)

    @staticmethod
    def _format_result_line(number: int, info: dict, fitness_settings) -> str:
        """Shared by a just-finished live run and a row picked from the
        run table (load_history_run) -- "show the result line once"
        means the SAME formatting either way, not two slightly different
        summaries depending on how you got there."""
        if info.get("cancelled"):
            return f"Run #{number}: CANCELLED at frame {info.get('n_frames')}"
        fitness = fitness_of(fitness_settings, info)
        return (f"Run #{number}: fitness={fitness:.1f}, frames={info.get('n_frames')}, "
                f"died={info.get('died_or_flagged')}, max_x={info.get('max_x_abs')}")

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
        # Ease-of-use redesign: "show the result line once" -- a batch's
        # outcome goes through the same single result_label every other
        # run outcome does, not a dedicated Batch sub-tab/label.
        self.run_tab.show_result(format_batch_result(result))

    # ---- History -------------------------------------------------------

    def _load_telemetry(self, slug: str):
        """Shared by _on_run_finished (a run JUST played) and
        load_history_run (an OLDER run picked from the list) -- found in
        manual testing that only the latter path existed, so the Plots
        tab stayed empty after every live Play until the user separately
        went and re-selected that same run from History."""
        import pandas as pd
        from config.output_routing import resolve_telemetry_path
        telemetry_path = resolve_telemetry_path(self.project.config, f"{slug}_telemetry.csv")
        if telemetry_path.exists():
            return pd.read_csv(telemetry_path)
        return None

    def load_history_run(self, entry: dict) -> None:
        """A row picked from the Run tab's table (ease-of-use redesign) --
        also the path a just-finished live run takes (_on_run_finished
        selects its own new row rather than duplicating this logic).
        Loads that run's video (only if it actually has one -- "no
        recording" otherwise), plots, Data/Config drawers, and updates
        the one result line + stat chips to match."""
        slug = entry["slug"]
        summary = entry.get("summary", {})
        tel = self._load_telemetry(slug)

        raw_frames_path = summary.get("raw_frames_path")
        if raw_frames_path is not None:
            from pathlib import Path
            if not Path(raw_frames_path).exists():
                raw_frames_path = None

        from tool.core.tool_settings import FitnessSettings
        try:
            fitness_settings = FitnessSettings(**entry["run_spec"]["tool_settings"]["fitness"])
        except (KeyError, TypeError):
            fitness_settings = self.project.tool_settings.fitness

        run_config = None
        run_spec_config = entry.get("run_spec", {}).get("config")
        if run_spec_config is not None:
            from config.project_config import from_dict as config_from_dict
            run_config = config_from_dict(run_spec_config)

        self.run_tab.load_run_data(raw_frames_path, tel, summary, run_config)
        fitness = None if summary.get("cancelled") else fitness_of(fitness_settings, summary)
        self.run_tab.set_stats(summary, fitness)
        self.run_tab.show_result(self._format_result_line(entry["number"], summary, fitness_settings))

    def export_history_run(self, entry: dict):
        return export_run_bundle(self.project.name, entry["number"])
