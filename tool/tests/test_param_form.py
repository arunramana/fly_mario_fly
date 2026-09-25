"""tool/ui/widgets/param_form.py: found in manual testing, a control's
measured range (config/params.py's own `range` field, a robust-band
HINT, not a hard limit) was being used as the spin box's actual Qt
range -- Qt's own setRange()/setValue() clamps a value outside that
range to the nearest edge, so noise.sigma=0.0 (its own measured range is
0.04-0.06) displayed as 0.04, silently lying about the loaded config.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QCheckBox

from config.project_config import load as load_project_config
from tool.core.schema import all_controls, get_value
from tool.ui.widgets.param_form import ParamForm

LEGACY_CONFIG_PATH = Path(__file__).resolve().parents[2] / "projects" / "legacy" / "config.json"

# QDoubleSpinBox is fundamentally decimal-rounding, not bit-exact: even at
# 17 decimals, 1/90 (0.011111111111111112) round-trips as
# 0.01111111111111111, off in the last digit. This tolerance is far
# tighter than anything that could be confused with the actual bug here
# (a value silently clamped to the far edge of a measured range, e.g.
# 0.0 displayed as 0.04) -- it only forgives the widget's own decimal
# storage, not a wrong number.
FLOAT_TOLERANCE = 1e-9


def _assert_widget_shows(widget, expected, path) -> None:
    if isinstance(widget, QCheckBox):
        assert widget.isChecked() == bool(expected), path
    else:
        assert widget.value() == pytest.approx(expected, abs=FLOAT_TOLERANCE), (
            f"{path}: widget shows {widget.value()!r}, config has {expected!r} "
            f"-- a range hint must never clamp the displayed value"
        )


def test_every_field_from_legacy_config_displays_its_exact_value(qtbot):
    config = load_project_config(LEGACY_CONFIG_PATH)
    form = ParamForm(config)

    checked_at_least_one_out_of_range_field = False
    for control in all_controls():
        widget = form._widget_by_path[control.path]
        expected = get_value(config, control.path)
        _assert_widget_shows(widget, expected, control.path)
        if control.range is not None and not (control.range[0] <= expected <= control.range[1]):
            checked_at_least_one_out_of_range_field = True

    assert checked_at_least_one_out_of_range_field, (
        "projects/legacy/config.json no longer has any field outside its own "
        "measured range -- this test needs a genuinely out-of-range value to "
        "actually exercise the clamping bug (noise.sigma=0.0 was it when written)"
    )


def test_set_config_also_never_clamps(qtbot):
    """set_config() (loading a different project into an already-open
    form) takes a separate code path from __init__ -- same bug, same
    fix, needs its own check."""
    config = load_project_config(LEGACY_CONFIG_PATH)
    default_config = config.__class__()  # a fresh default config to build the form from first
    form = ParamForm(default_config)
    form.set_config(config)

    for control in all_controls():
        widget = form._widget_by_path[control.path]
        expected = get_value(config, control.path)
        _assert_widget_shows(widget, expected, control.path)


def test_a_tiny_scalar_displays_in_scientific_notation_not_a_lying_zero(qtbot):
    """network.denormal_flush_threshold = 1e-30 -- at any readable fixed-
    decimal count this rounds to "0.00", silently lying about it being
    nonzero (ground rule 4). Found live: this is exactly the value a
    user reported seeing as "0.00"."""
    from tool.ui.widgets.no_scroll_inputs import ScientificDoubleSpinBox

    form = ParamForm(load_project_config(LEGACY_CONFIG_PATH))
    widget = form._widget_by_path["network.denormal_flush_threshold"]
    assert isinstance(widget, ScientificDoubleSpinBox)
    assert widget.value() == pytest.approx(1e-30)
    assert "0.00" not in widget.text()
