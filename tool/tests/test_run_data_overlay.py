"""tool/ui/widgets/run_data_overlay.py -- run summary + every telemetry
column for the current frame, grouped."""
from __future__ import annotations

from tool.ui.widgets.run_data_overlay import GROUPS, DataOverlayContent


def test_placeholders(qapp):
    w = DataOverlayContent()
    text = w.toPlainText()
    assert "no run selected" in text and "no frame" in text


def test_summary_at_top_then_grouped_columns(qapp):
    w = DataOverlayContent()
    w.set_summary({"n_frames": 10, "max_x_abs": 447, "mb_weights": "skip"})
    w.update_from_row({"frame": 3, "mario_x": 40, "press_a": True, "theta": 0.5, "gap": 2,
                       "ttmn": 1.0, "hab_escape": 1, "weird_new_col": 7})
    text = w.toPlainText()
    assert text.index("n_frames = 10") < text.index("CURRENT FRAME")
    assert "mb_weights" not in text
    for heading in ("Position / motion", "Buttons", "Looming", "Gap / terrain", "Neurons", "Cooldown"):
        assert heading in text
    assert "mario_x = 40" in text and "press_a = yes" in text
    assert "Other" in text and "weird_new_col = 7" in text


def test_every_telemetry_column_is_grouped():
    known = {c for _t, cols in GROUPS for c in cols}
    for col in ("frame", "mario_x", "theta", "dlmn", "gap", "odor_l", "hab_escape", "press_b", "long_jump"):
        assert col in known


def test_updates_on_new_row(qapp):
    w = DataOverlayContent()
    w.update_from_row({"mario_x": 1})
    w.update_from_row({"mario_x": 2})
    assert "mario_x = 2" in w.toPlainText()
