"""tool/ui/widgets/run_overlay.py -- Run tab / player redesign: the
Brain map / Data / Config overlays. Each is a movable, resizable panel
that can float as its own top-level window (native OS move/resize) or
dock as a fixed-corner child of the video canvas. Position and size are
remembered per overlay through QSettings -- a local, per-machine user
preference, not part of a project's own tool.json (this redesign only
touches tool/ui).
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QSettings, QSize, Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizeGrip, QVBoxLayout, QWidget

_SETTINGS = QSettings("fly_mario", "run_tab_overlays")


class OverlayPanel(QWidget):
    """`key`: a short, stable name ("brain_map"/"data"/"config") used as
    the QSettings key prefix. `content`: the widget shown below the title
    bar. Starts docked, hidden -- toggle_visible() (bound to B/D/C) shows
    it in whichever state (docked/floating) it last remembered."""

    closed = Signal()
    docked_changed = Signal(bool)

    DEFAULT_DOCK_CORNER = Qt.Corner.TopRightCorner
    DEFAULT_SIZE = QSize(280, 220)

    def __init__(self, key: str, title: str, content: QWidget, parent=None, settings: QSettings | None = None):
        super().__init__(parent)
        self._key = key
        # Injectable for tests -- the real, module-level QSettings persists
        # to this machine's actual per-user config store, which a test
        # must not pollute or depend on across runs.
        self._settings = settings if settings is not None else _SETTINGS
        self._docked = self._settings.value(f"{key}/docked", True, type=bool)
        self._drag_start_global: QPoint | None = None
        self._drag_start_pos: QPoint | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title_bar = QWidget()
        title_bar.setObjectName("overlayTitleBar")
        title_row = QHBoxLayout(title_bar)
        title_row.setContentsMargins(6, 4, 6, 4)
        self._title_label = QLabel(title)
        title_row.addWidget(self._title_label)
        title_row.addStretch(1)
        self.dock_button = QPushButton("Dock" if not self._docked else "Undock")
        self.dock_button.setToolTip("Toggle floating (own window) vs docked (fixed corner over the video)")
        self.dock_button.clicked.connect(self.toggle_docked)
        title_row.addWidget(self.dock_button)
        self.close_button = QPushButton("x")
        self.close_button.setToolTip("Hide this overlay")
        self.close_button.clicked.connect(self.hide_panel)
        title_row.addWidget(self.close_button)
        title_bar.mousePressEvent = self._title_press
        title_bar.mouseMoveEvent = self._title_move
        layout.addWidget(title_bar)

        layout.addWidget(content, 1)
        self._content = content

        grip_row = QHBoxLayout()
        grip_row.setContentsMargins(0, 0, 0, 0)
        grip_row.addStretch(1)
        grip = QSizeGrip(self)
        grip_row.addWidget(grip)
        layout.addLayout(grip_row)

        size = self._settings.value(f"{key}/size", self.DEFAULT_SIZE, type=QSize)
        self.resize(size)
        self.setVisible(False)

    # ---- dock / float --------------------------------------------------

    def toggle_docked(self) -> None:
        self.set_docked(not self._docked)

    def set_docked(self, docked: bool) -> None:
        self._docked = docked
        self._settings.setValue(f"{self._key}/docked", docked)
        self.dock_button.setText("Undock" if docked else "Dock")
        if docked:
            self.setWindowFlags(Qt.WindowType.Widget)
        else:
            # FramelessWindowHint: this panel already draws its own title
            # bar (drag/dock/close) -- a native OS frame on top of that
            # would be a second, redundant title bar.
            self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                                 | Qt.WindowType.WindowStaysOnTopHint)
        if self.isVisible():
            self.show()  # re-apply window flags (Qt requires a re-show)
        self.docked_changed.emit(docked)

    def is_docked(self) -> bool:
        return self._docked

    # ---- visibility / position ------------------------------------------

    def show_panel(self, anchor_widget: QWidget | None = None) -> None:
        if self._docked and anchor_widget is not None:
            self.setParent(anchor_widget)
            self.setWindowFlags(Qt.WindowType.Widget)
            pos = self._settings.value(f"{self._key}/docked_pos", None, type=QPoint)
            if pos is None:
                pos = QPoint(anchor_widget.width() - self.width() - 12, 12)
            self.move(pos)
        elif not self._docked:
            pos = self._settings.value(f"{self._key}/floating_pos", None, type=QPoint)
            if pos is not None:
                self.move(pos)
        self.show()
        self.raise_()

    def hide_panel(self) -> None:
        self.setVisible(False)
        self.closed.emit()

    def toggle_visible(self, anchor_widget: QWidget | None = None) -> None:
        if self.isVisible():
            self.hide_panel()
        else:
            self.show_panel(anchor_widget)

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        key = f"{self._key}/{'docked_pos' if self._docked else 'floating_pos'}"
        self._settings.setValue(key, self.pos())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._settings.setValue(f"{self._key}/size", self.size())

    # ---- dragging the docked panel by its title bar ----------------------

    def _title_press(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_global = event.globalPosition().toPoint()
            self._drag_start_pos = self.pos()

    def _title_move(self, event) -> None:
        if self._drag_start_global is None or not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        delta = event.globalPosition().toPoint() - self._drag_start_global
        self.move(self._drag_start_pos + delta)
