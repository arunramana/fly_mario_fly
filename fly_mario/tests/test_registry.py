"""Registry finds one PLUGIN per module and rejects duplicate names."""
import pytest

from fly_mario.registry import KINDS, list_plugins, load_folder


def _write(folder, fname, name):
    (folder / fname).write_text(
        f"from types import SimpleNamespace\nPLUGIN = SimpleNamespace(name={name!r})\n")


def test_discovers_dummy(tmp_path):
    _write(tmp_path, "dummy_a.py", "a")
    _write(tmp_path, "dummy_b.py", "b")
    assert set(load_folder(tmp_path)) == {"a", "b"}


def test_duplicate_raises(tmp_path):
    _write(tmp_path, "one.py", "same")
    _write(tmp_path, "two.py", "same")
    with pytest.raises(ValueError, match="duplicate"):
        load_folder(tmp_path)


def test_real_folders_load_empty():
    for kind in KINDS:
        assert isinstance(list_plugins(kind), dict)
