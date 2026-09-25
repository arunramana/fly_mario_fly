"""Ease-of-use redesign: a field with a real measured/robust range
(config/params.py's own `range`, currently jump.g, noise.sigma,
mushroom_body.trace_decay) gets a slider next to its spin box. The spin
box stays the one writable path (section 3's "one home per setting") --
the slider only ever calls spin.setValue().
"""
from __future__ import annotations

from config.project_config import ProjectConfig
from tool.ui.widgets.param_form import SLIDER_SCALE, ParamForm


def test_ranged_field_has_a_synced_slider(qtbot):
    form = ParamForm(ProjectConfig())
    slider = form._slider_by_path["jump.g"]
    spin = form._widget_by_path["jump.g"]

    lo, hi = 1.12, 3.35  # jump.g's own measured band
    assert slider.minimum() == int(lo * SLIDER_SCALE)
    assert slider.maximum() == int(hi * SLIDER_SCALE)

    slider.setValue(int(2.5 * SLIDER_SCALE))
    assert spin.value() == 2.5, "moving the slider must reach the spin box"

    spin.setValue(1.8)
    assert slider.value() == int(1.8 * SLIDER_SCALE), "editing the spin box must reach the slider"


def test_unranged_field_has_no_slider(qtbot):
    form = ParamForm(ProjectConfig())
    assert "network.alpha" not in form._slider_by_path


def test_set_config_resyncs_the_slider_without_emitting_changed(qtbot):
    import dataclasses

    form = ParamForm(ProjectConfig())
    changed = []
    form.changed.connect(changed.append)

    new_config = dataclasses.replace(
        ProjectConfig(), jump=dataclasses.replace(ProjectConfig().jump, g=2.7))
    form.set_config(new_config)

    assert form._widget_by_path["jump.g"].value() == 2.7
    assert form._slider_by_path["jump.g"].value() == int(2.7 * SLIDER_SCALE)
    assert changed == [], "set_config() must not emit changed -- it's a load, not a user edit"
