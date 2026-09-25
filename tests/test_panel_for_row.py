# What this file does, in plain English:
# Checks that panel_for_row() (the new function factored out of
# render_run's own per-frame loop for the Run tab's live "Brain map"
# view) draws the exact same picture as calling panel() by hand with the
# same row's values -- the refactor moved code, it didn't change it.
"""render/brain_panel.py: panel_for_row()/_panel_context() were factored
out of render_run's own loop (tool/SPEC_ui_retro.md's ease-of-use
follow-up: the Run tab's "Brain map" toggle needs the identical
per-frame rendering on demand, for one row, not a whole video)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from render.brain_panel import ORDER, STEERING_ORDER, _panel_context, panel, panel_for_row


def _fake_telemetry(n=5) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    return pd.DataFrame({
        "lc4": rng.random(n), "lplc2": rng.random(n), "mem": rng.random(n) * 0.5,
        "spike": [False, True, False, False, False][:n],
        "ttmn": rng.random(n) * 10, "dna01": rng.random(n) * 10, "dna02": rng.random(n) * 10,
        "direction": ["R"] * n, "climb": [False] * n, "conflict": [False] * n,
        "odor_l": rng.random(n), "odor_r": rng.random(n), "hungry": [True] * n,
        "orn_a_l": rng.random(n), "orn_a_r": rng.random(n),
        "avers_l": rng.random(n), "avers_r": rng.random(n), "refusing": [False] * n,
        "r_team": rng.random(n), "l_team": rng.random(n), "gap": [0] * n, "long_jump": [False] * n,
    })


def test_panel_for_row_matches_calling_panel_directly():
    tel = _fake_telemetry()
    ctx = _panel_context(tel)
    populations = ORDER + STEERING_ORDER

    for i in range(len(tel)):
        row = tel.iloc[i]
        expected = panel(
            {"LC4": row.lc4, "LPLC2": row.lplc2, "DNp01": ctx["gf"][i], "TTMn": row.ttmn,
             "DNa01": row.dna01, "DNa02": row.dna02},
            ctx["norm"], spike=bool(row.spike), populations=populations,
            climb=bool(row.climb), conflict=bool(row.conflict), pit=bool(row.gap > 0),
            long_jump=bool(row.long_jump), odor_l=float(row.odor_l), odor_r=float(row.odor_r),
            hungry=bool(row.hungry), steer_left=bool(row.direction == "L"),
            orn_a_l=float(row.orn_a_l), orn_a_r=float(row.orn_a_r),
            avers_l=float(row.avers_l), avers_r=float(row.avers_r), refusing=bool(row.refusing),
            r_team=float(row.r_team), l_team=float(row.l_team),
        )
        actual = panel_for_row(tel, i, ctx)
        assert list(actual.getdata()) == list(expected.getdata()), f"frame {i} differs"
