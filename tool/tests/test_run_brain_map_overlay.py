"""tool/ui/widgets/run_brain_map_overlay.py -- renders a real brain-panel
frame for the player's current row on demand."""
from __future__ import annotations

import numpy as np
import pandas as pd

from tool.ui.widgets.run_brain_map_overlay import BrainMapOverlayContent


def _fake_telemetry(n=5) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    return pd.DataFrame({
        "lc4": rng.random(n), "lplc2": rng.random(n), "mem": rng.random(n) * 0.5,
        "spike": [False] * n, "ttmn": rng.random(n) * 10, "dna01": rng.random(n) * 10,
        "dna02": rng.random(n) * 10, "direction": ["R"] * n, "climb": [False] * n,
        "conflict": [False] * n, "odor_l": rng.random(n), "odor_r": rng.random(n),
        "hungry": [True] * n, "dnp09": rng.random(n), "dlmn": rng.random(n),
        "frame": np.arange(n),
    })


def test_no_telemetry_shows_placeholder(qapp):
    widget = BrainMapOverlayContent()
    assert "no run loaded" in widget._label.text()


def test_update_frame_renders_a_real_image(qapp):
    widget = BrainMapOverlayContent()
    widget.set_telemetry(_fake_telemetry())
    widget.update_frame(2)
    assert not widget._label.pixmap().isNull()


def test_update_frame_past_telemetry_length_clamps_to_last_row(qapp):
    widget = BrainMapOverlayContent()
    widget.set_telemetry(_fake_telemetry(n=5))
    widget.update_frame(999)  # must not raise (IndexError on tel.iloc)
    assert not widget._label.pixmap().isNull()
