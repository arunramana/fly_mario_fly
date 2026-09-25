"""tool/ui/widgets/no_scroll_inputs.py -- drop-in QSpinBox/QDoubleSpinBox/
QSlider replacements that ignore the mouse wheel unless actually focused.

Found live in projects/legacy/config.json: scrolling PAST a field (not
scrolling it deliberately) silently changed its value -- the scroll
landed on whatever spin box happened to be under the cursor, with no
click and no visible feedback. `event.ignore()` (not swallowing the
event) is what makes Qt bubble an unfocused wheel scroll up to the
enclosing QScrollArea instead, so scrolling the page past a field still
scrolls the page. `Qt.StrongFocus` (a QSlider's own default is weaker)
is what makes "focused" reachable by click or Tab in the first place, so
deliberately scrolling a field the user just clicked into still works.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDoubleSpinBox, QSlider, QSpinBox


class NoScrollSpinBox(QSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event) -> None:
        if not self.hasFocus():
            event.ignore()
        else:
            super().wheelEvent(event)


class NoScrollDoubleSpinBox(QDoubleSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event) -> None:
        if not self.hasFocus():
            event.ignore()
        else:
            super().wheelEvent(event)


class NoScrollSlider(QSlider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event) -> None:
        if not self.hasFocus():
            event.ignore()
        else:
            super().wheelEvent(event)


class ScientificDoubleSpinBox(NoScrollDoubleSpinBox):
    """Displays and edits its value in scientific notation ("1.00e-30"),
    not fixed decimals -- found live: a value like
    network.denormal_flush_threshold (1e-30) rounded to "0.00" at any
    readable fixed-decimal count, silently lying about it being nonzero
    (ground rule 4). Qt's own QDoubleSpinBox rounds the STORED value to
    `decimals()` internally, independent of the displayed text -- 323
    (Qt's own ceiling) keeps that internal rounding from ever being the
    thing that zeroes out a genuinely tiny value; only the display/edit
    text is scientific.
    """

    def __init__(self, *args, sig_figs: int = 2, **kwargs):
        super().__init__(*args, **kwargs)
        self._sig_figs = sig_figs
        self.setDecimals(323)

    def textFromValue(self, value: float) -> str:
        return f"{value:.{self._sig_figs}e}"

    def valueFromText(self, text: str) -> float:
        try:
            return float(text.strip())
        except ValueError:
            return self.value()

    def validate(self, text, pos):
        from PySide6.QtGui import QValidator

        stripped = text.strip()
        if stripped in ("", "-", "+"):
            return (QValidator.State.Intermediate, text, pos)
        try:
            float(stripped)
            return (QValidator.State.Acceptable, text, pos)
        except ValueError:
            # Mid-typing a scientific literal ("1.0e", "1.0e-") isn't a
            # valid float yet, but isn't garbage either -- let it through
            # as Intermediate instead of rejecting the next keystroke.
            body = stripped.lower().replace("e", "", 1)
            if body.replace("+", "").replace("-", "").replace(".", "").isdigit():
                return (QValidator.State.Intermediate, text, pos)
            return (QValidator.State.Invalid, text, pos)
