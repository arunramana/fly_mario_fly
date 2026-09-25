"""tool/ui/widgets/run_data_overlay.py -- the Data overlay's compact
readout: x, buttons, and the top-N active neurons by their own calibrated
max (tool/ui/widgets/neuron_activity_strip.py's BARS)."""
from __future__ import annotations

from tool.ui.widgets.run_data_overlay import DataOverlayContent


def test_no_frame_shows_placeholder(qapp):
    widget = DataOverlayContent()
    widget.update_from_row(None)
    assert "no frame" in widget._lines.text()


def test_shows_x_and_direction(qapp):
    widget = DataOverlayContent()
    widget.update_from_row({"mario_x": 123, "direction": "R", "press_a": True, "press_b": False})
    text = widget._lines.text()
    assert "123" in text
    assert "R" in text


def test_ranks_the_highest_normalized_population_first(qapp):
    widget = DataOverlayContent()
    # ttmn's own max is JumpParams().spike_amp (50 by default) -- 40/50 = 0.8,
    # comfortably higher than lc4's 1.0/4.0 = 0.25, so ttmn should rank first
    # regardless of raw magnitude.
    widget.update_from_row({"mario_x": 10, "direction": "R", "lc4": 1.0, "ttmn": 40.0})
    text = widget._lines.text()
    top_line = text.splitlines()[3]
    assert "TTMn" in top_line
