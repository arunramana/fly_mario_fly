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
from tool.ui.screen_fit import apply_initial_geometry, save_geometry

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
        from tool.core.fps_meter import FpsMeter
        self._fps = FpsMeter()
        self._train_process: mp.Process | None = None
        self._train_queue: mp.Queue | None = None
        self._train_stop: mp.Event | None = None
        self._train_timer = QTimer(self)
        self._train_timer.setInterval(500)
        self._train_timer.timeout.connect(self._poll_training)
        self._arousal_value = None   # a shared mp.Value while a run is playing (live slider)
        self._current_run_number: int | None = None
        self._current_run_slug: str | None = None
        self._current_run_spec: RunSpec | None = None

        self.setWindowTitle(self._title())
        apply_initial_geometry(self)

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)

        header = QHBoxLayout()
        # Run tab / header redesign: navigation on the left (Home, project
        # name, unsaved marker -- title_label already carries both), the
        # three actions on the right. All four buttons share ONE QSS rule
        # (tool/ui/style.qss's `[headerButton="true"]` selector) -- same
        # size/padding/font for every one of them, set via a Qt dynamic
        # property rather than an objectName so a QPushButton and a
        # QToolButton (Presets) can match the same rule.
        home_button = QPushButton("Home")
        home_button.clicked.connect(self._go_home)
        self.title_label = QLabel(self._title())
        self.presets_button = self._build_presets_button()
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save)
        # START: Ctrl+Enter, not Space -- Space drives the Run tab's own
        # video-player play/pause instead. Stands out by colour only
        # (`headerAccent`), never by size -- see style.qss's own comment.
        header_play_button = QPushButton("START")
        header_play_button.clicked.connect(self.play)
        self.header_buttons = (home_button, self.presets_button, self.save_button, header_play_button)
        for button in self.header_buttons:
            button.setProperty("headerButton", True)
        header_play_button.setProperty("headerAccent", True)
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
        self.tabs.setUsesScrollButtons(True)   # 7 wide tab labels overflow a small window: scroll them
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
            self.presets_button.setEnabled(False)
        self._update_save_enabled()

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
            # Run tab / player redesign: transport, event nav, fullscreen,
            # overlay toggles, and the shortcut-help list -- all centralised
            # here (not registered a second time inside RunPlayer itself)
            # so _shortcut_for's "exactly one QShortcut per key sequence"
            # assumption (tool/tests/test_shortcuts.py) stays true.
            (QKeySequence(Qt.Key.Key_Left), lambda: self.run_tab.step_frame(-1)),
            (QKeySequence(Qt.Key.Key_Right), lambda: self.run_tab.step_frame(1)),
            (QKeySequence("Shift+Left"), lambda: self.run_tab.jump_seconds(-1)),
            (QKeySequence("Shift+Right"), lambda: self.run_tab.jump_seconds(1)),
            (QKeySequence(Qt.Key.Key_N), lambda: self.run_tab.next_event()),
            (QKeySequence(Qt.Key.Key_P), lambda: self.run_tab.prev_event()),
            (QKeySequence(Qt.Key.Key_F), lambda: self.run_tab.toggle_fullscreen()),
            (QKeySequence(Qt.Key.Key_B), lambda: self.run_tab.toggle_brain_map()),
            (QKeySequence(Qt.Key.Key_I), lambda: self.run_tab.toggle_controller_overlay()),
            (QKeySequence(Qt.Key.Key_D), lambda: self.run_tab.toggle_data_overlay()),
            (QKeySequence(Qt.Key.Key_C), lambda: self.run_tab.toggle_config_overlay()),
            (QKeySequence(Qt.Key.Key_Question), lambda: self.run_tab.show_shortcut_help()),
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
        self._update_save_enabled()

    def _update_save_enabled(self) -> None:
        """Header redesign: Save is disabled when there's nothing to save
        (not dirty) or the project is read-only -- either way, clicking
        it would do nothing, so it shouldn't invite the click."""
        self.save_button.setEnabled(self._dirty and not self.project.is_read_only)

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
        self._update_save_enabled()

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
        if (self._process is not None and self._process.is_alive()) or self.training_active():
            self.cancel()
        if QApplication.platformName() != "offscreen":   # tests must not write the user's saved geometry
            save_geometry(self)
        event.accept()

    def _go_home(self) -> None:
        """Ease-of-use redesign: returns to the project gate, same
        unsaved-changes guard as closing the window -- asked here, once,
        not again by closeEvent's own guard when self.close() runs below
        (_closing_confirmed short-circuits it)."""
        if not self._confirm_discard_or_save():
            return
        if (self._process is not None and self._process.is_alive()) or self.training_active():
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
        if self.training_active():
            self.statusBar().showMessage("Training is running -- cancel it first.", 5000)
            return
        seed = self.project.tool_settings.experiment.seeds[0]
        number = next_run_number(self.project.name)
        slug = f"{number:03d}_play_seed{seed}"
        spec = self._make_run_spec(seed, f"{slug}.mp4")
        # Kept for _on_run_finished: the run's OWN config snapshot. Rebuilding
        # the spec at finish time used whatever the project's config had
        # become by then (edit the level mid-run and a 1-1 run recorded 1-3).
        self._current_run_spec = spec
        self._current_run_number = number
        self._current_run_slug = slug

        ctx = mp.get_context("spawn")
        self._queue = ctx.Queue()
        self._stop_event = ctx.Event()
        arousal = spec.config.modules.arousal
        self._arousal_value = ctx.Value("d", arousal.arousal if arousal else 0.0)
        self._process = ctx.Process(target=run_one_streaming,
                                    args=(spec, self._queue, self._stop_event, self._arousal_value))
        self._process.start()
        self.run_tab.set_running(True)
        self.run_tab.progress.setValue(0)
        self._fps.reset()
        self._poll_timer.start()

    def set_arousal_live(self, level: float) -> None:
        """The Character tab's Arousal slider, applied to the run in progress
        (the policy reads the shared value every frame; the per-frame level is
        in the `arousal` telemetry column)."""
        if self._arousal_value is not None and self._process is not None and self._process.is_alive():
            self._arousal_value.value = float(level)

    def cancel(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()
        self.cancel_training()

    # ---- Training (Goal tab's Train button) --------------------------------

    @property
    def goal_tab(self):
        """The Goal tab (rebuilt by reload_tab, so looked up, not stored)."""
        index, _factory = self._tab_factories["goal"]
        return self.tabs.widget(index)

    def training_active(self) -> bool:
        return self._train_process is not None and self._train_process.is_alive()

    def start_training(self) -> None:
        """Spawns tool.core.training.run_training in a child process on the
        window's live project (unsaved edits included). Every episode is
        recorded through the run store by the worker; this window only
        refreshes the dropdown and the Learning chart as they arrive."""
        if self.training_active() or (self._process is not None and self._process.is_alive()):
            return
        if self.project.is_read_only:
            self.statusBar().showMessage("Read-only project: duplicate it to train.", 5000)
            return
        from tool.core.training import run_training_streaming
        ctx = mp.get_context("spawn")
        self._train_queue = ctx.Queue()
        self._train_stop = ctx.Event()
        self._train_process = ctx.Process(
            target=run_training_streaming,
            args=(self.project, self.project.tool_settings.training, self._train_queue, self._train_stop))
        self._train_process.start()
        self._train_timer.start()
        self.goal_tab.set_training_state(True, "starting...")
        self.run_tab.cancel_button.setEnabled(True)
        self.run_tab.sub_tabs.setCurrentWidget(self.run_tab.learning)

    def cancel_training(self) -> None:
        if self._train_stop is not None and self.training_active():
            self._train_stop.set()
            self.goal_tab.set_training_state(True, "cancelling after this frame...")

    def _poll_training(self) -> None:
        if self._train_queue is None:
            return
        changed = False
        while not self._train_queue.empty():
            kind, payload = self._train_queue.get_nowait()
            if kind == "phase":
                self.goal_tab.set_training_state(True, f"training: {payload}")
            elif kind == "test":
                changed = True   # the Learning tab re-reads training_eval.json on refresh
                self.goal_tab.set_training_state(
                    True, f"test {payload['network']} ep {payload['episode']}: "
                          f"{payload['wins']}/{len(payload['seeds'])} wins, mean max_x {payload['mean_max_x']:.0f}")
            elif kind == "episode":
                changed = True
                self.goal_tab.set_training_state(
                    True, f"{payload['network']} episode {payload['episode']}: max_x {payload['max_x']}")
            elif kind in ("finished", "error"):
                self._train_timer.stop()
                if self._train_process is not None:
                    self._train_process.join(timeout=5)
                self._train_process = None
                if kind == "error":
                    status = f"failed: {payload}"
                else:
                    status = "cancelled" if payload.get("cancelled") else "done"
                self.goal_tab.set_training_state(False, status)
                self.goal_tab.refresh_checkpoints()
                self.run_tab.cancel_button.setEnabled(False)
                changed = True
                break
        if changed:
            self.run_tab.refresh_history(list_runs(self.project.name))

    def _poll_queue(self) -> None:
        """Drain the queue, but draw only the LATEST frame this tick: rendering every
        queued frame made the UI fall behind the sim. Progress and the data overlays
        follow that last row. The fps readout separates sim rate from displayed rate."""
        if self._queue is None:
            return
        max_frames = self.project.config.scenario.max_frames
        latest = None
        terminal = None
        while not self._queue.empty():
            message = self._queue.get_nowait()
            kind = message[0]
            if kind == "frame":
                latest = message
                frame = message[2].get("frame")
                if frame is not None:
                    self._fps.sim_frame(frame)
            else:
                terminal = message
                break
        if latest is not None:
            obs, row = latest[1], latest[2]
            self.run_tab.preview.show_frame(obs, row)
            self._fps.shown_frame()
            self.run_tab.set_progress(row.get("frame", 0), max_frames)
            self.run_tab.set_fps(*self._fps.rates())
        if terminal is None:
            return
        if terminal[0] == "done":
            self._on_run_finished(terminal[1])
        elif terminal[0] == "error":
            self._on_run_error(terminal[1])

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
        spec = self._current_run_spec
        seed = spec.seed
        record_run(self.project.name, number, slug, seed, info, spec.to_dict())
        write_run_note(self.project.name, number, slug, seed,
                        spec.config, spec.tool_settings, info)
        self.run_tab.refresh_history(list_runs(self.project.name))
        if info.get("saved_checkpoint"):   # a Play with keep-learning on wrote play_NNN.npy
            self.goal_tab.refresh_checkpoints()
        # The SAME path a playlist pick takes (select_history_run) -- one
        # place loads a run's data into the tab, whether it just finished
        # or was picked from the playlist (matches "show the result line
        # once": one formatter, tool/ui/main_window.py's own
        # _format_result_line, either way).
        self.run_tab.select_run(number)
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
        if result.numbers:
            self.run_tab.show_batch_for(result.numbers[0])
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

    def save_state_here(self) -> None:
        """Player's "Save state here": the current run at the current frame
        becomes a project save state (tool/core/savestates.py)."""
        number = self.run_tab.playlist.current_number()
        entry = next((e for e in list_runs(self.project.name) if e["number"] == number), None)
        if entry is None:
            self.statusBar().showMessage("No run selected.", 5000)
            return
        frame = self.run_tab.player._current_frame_index
        from PySide6.QtWidgets import QApplication
        from tool.core.savestates import FRESH_BRAIN_NOTE, capture_from_run
        try:
            if not entry.get("summary", {}).get("actions_path") and not entry.get("training"):
                self.statusBar().showMessage(f"Run #{number} has no action log: re-simulating it...", 0)
                QApplication.processEvents()
            result = capture_from_run(self.project.name, entry, frame)
        except (ValueError, OSError) as exc:
            self.statusBar().showMessage(f"Could not save a state: {exc}", 10_000)
            return
        goal = self.goal_tab
        if hasattr(goal, "refresh_states"):
            goal.refresh_states()
        how = " (re-simulated)" if result["resimulated"] else ""
        self.statusBar().showMessage(
            f"Saved state {result['name']!r} at frame {result['frame']}{how}. {FRESH_BRAIN_NOTE}", 12_000)

    def select_history_run(self, number: int) -> None:
        """A run picked from the Run tab's playlist (run_playlist.py's
        run_selected signal, connected in run.py) -- resolves the run
        number to its own recorded entry and loads it exactly like
        _on_run_finished does for a just-finished run."""
        for entry in list_runs(self.project.name):
            if entry["number"] == number:
                self.load_history_run(entry)
                return

    def load_history_run(self, entry: dict) -> None:
        """A run picked from the Run tab's playlist (via select_history_run)
        -- also the path a just-finished live run takes (_on_run_finished
        calls this directly rather than duplicating this logic). Loads
        that run's video (only if it actually has one -- "no recording"
        otherwise), plots, and the Brain map/Data/Config overlays, and
        updates the one result line + stat chips to match."""
        slug = entry["slug"]
        summary = entry.get("summary", {})
        tel = self._load_telemetry(slug)

        raw_frames_path = summary.get("raw_frames_path")
        if raw_frames_path is not None:
            from pathlib import Path
            if not Path(raw_frames_path).exists():
                raw_frames_path = None

        if entry.get("training") and raw_frames_path is None:
            summary = {**summary, "telemetry_only": True}

        from tool.core.run_store import resolve_run_spec
        from tool.core.tool_settings import FitnessSettings
        run_spec = resolve_run_spec(entry, project_name=self.project.name)
        try:
            fitness_settings = FitnessSettings(**run_spec["tool_settings"]["fitness"])
        except (KeyError, TypeError):
            fitness_settings = self.project.tool_settings.fitness

        run_config = None
        run_spec_config = run_spec.get("config")
        if run_spec_config is not None:
            from config.project_config import from_dict as config_from_dict
            run_config = config_from_dict(run_spec_config)

        self.run_tab.load_run_data(raw_frames_path, tel, summary, run_config, run_spec.get("tool_settings"))
        fitness = None if summary.get("cancelled") else fitness_of(fitness_settings, summary)
        self.run_tab.set_stats(summary, fitness)
        self.run_tab.show_result(self._format_result_line(entry["number"], summary, fitness_settings))

    def export_history_run(self, entry: dict):
        return export_run_bundle(self.project.name, entry["number"])
