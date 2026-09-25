"""tool/ui/widgets/run_picker.py -- the Player's run dropdown."""
from __future__ import annotations

from tool.ui.widgets.run_picker import RunPicker, label_for


def _e(n, batch=None, died=True, cancelled=False, flag=False):
    return {"number": n, "seed": 0, "batch_id": batch, "fitness": float(n),
            "summary": {"died_or_flagged": died, "cancelled": cancelled,
                        "flag_get": flag, "max_x_abs": 100.0}}


def test_label_format_and_outcomes():
    assert label_for(_e(3)) == "#3 · seed 0 · x 100 · fit 3 · died"
    assert label_for(_e(3, cancelled=True)).endswith("cancelled")
    assert label_for(_e(3, flag=True)).endswith("flag")


def test_newest_first_with_batch_header(qapp):
    picker = RunPicker()
    picker.set_entries([_e(1), _e(2, "abc"), _e(3, "abc")])
    texts = [picker.combo.itemText(i) for i in range(picker.combo.count())]
    assert texts[0].startswith("── batch abc")
    assert texts[1].startswith("#3") and texts[2].startswith("#2") and texts[3].startswith("#1")


def test_prev_next_step_by_run_number_and_emit(qapp):
    picker = RunPicker()
    picker.set_entries([_e(1), _e(2), _e(3)])
    picker.select_number(2)
    seen = []
    picker.run_selected.connect(seen.append)
    picker._step(-1)
    picker._step(1)
    picker._step(1)
    assert seen == [1, 2, 3]
    assert picker.current_number() == 3
    assert not picker.select_number(99)
