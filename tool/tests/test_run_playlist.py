"""tool/ui/widgets/run_playlist.py -- the Run tab's playlist panel:
thumbnails, prev/next, batch grouping. No real recordings involved --
entries without a raw_frames_path get a placeholder thumbnail.
"""
from __future__ import annotations

from PySide6.QtCore import Qt

from tool.ui.widgets.run_playlist import RunPlaylist


def _entry(number, batch_id=None, died=True, cancelled=False, max_x=100.0):
    return {
        "number": number, "batch_id": batch_id, "fitness": float(number),
        "summary": {"died_or_flagged": died, "cancelled": cancelled, "max_x_abs": max_x,
                    "flag_get": False, "raw_frames_path": None},
    }


def test_set_entries_populates_list_newest_first(qapp):
    playlist = RunPlaylist()
    playlist.set_entries([_entry(1), _entry(2), _entry(3)])
    numbers = [playlist.list_widget.item(i).data(Qt.ItemDataRole.UserRole)
               for i in range(playlist.list_widget.count())]
    assert numbers == [3, 2, 1]


def test_select_number_and_prev_next(qapp):
    playlist = RunPlaylist()
    playlist.set_entries([_entry(1), _entry(2), _entry(3)])
    assert playlist.select_number(2)

    seen = []
    playlist.run_selected.connect(seen.append)
    playlist._step(1)  # newest-first order: from 2, "next" moves toward older -> 1
    assert seen == [1]
    seen.clear()
    playlist._step(-1)
    playlist._step(-1)
    assert seen[-1] == 3


def test_select_number_unknown_returns_false(qapp):
    playlist = RunPlaylist()
    playlist.set_entries([_entry(1)])
    assert not playlist.select_number(999)


def test_batch_entries_get_a_group_header(qapp):
    playlist = RunPlaylist()
    playlist.set_entries([_entry(1, batch_id="abc"), _entry(2, batch_id="abc"), _entry(3)])
    texts = [playlist.list_widget.item(i).text() for i in range(playlist.list_widget.count())]
    assert any("batch abc" in t for t in texts)


def test_placeholder_thumbnail_for_a_run_with_no_recording(qapp):
    playlist = RunPlaylist()
    playlist.set_entries([_entry(1)])
    item = playlist.list_widget.item(0)
    assert not item.icon().isNull()
