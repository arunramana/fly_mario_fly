"""tool/ui/widgets/scroll_page.py -- make a tab scroll instead of clip.

On a laptop-sized window a tab's content can be taller or wider than the
viewport; without a scroll area Qt just squashes it (overlapping rows) or
cuts it off. `install_scroll_page(tab, content)` puts `content` inside a
QScrollArea that fills `tab`, so the tab object itself stays the widget
`QTabWidget.widget(i)` returns (tests and main_window reach into it).
"""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QScrollArea, QVBoxLayout, QWidget


def install_scroll_page(tab: QWidget, content: QWidget) -> QScrollArea:
    outer = QVBoxLayout(tab)
    outer.setContentsMargins(0, 0, 0, 0)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setWidget(content)
    outer.addWidget(scroll)
    tab.page_scroll = scroll
    return scroll
