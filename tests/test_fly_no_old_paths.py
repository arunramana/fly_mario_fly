"""Nothing under src/fly_mario reads from the old repo's folders: only the package itself and $FLY_MARIO_DATA."""
import re
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "fly_mario"
OLD = re.compile(r"tutorials|flyrun|(?<![A-Za-z])_cache|L2c|\.\./data|malecns_v1\.0/derived")
FILES = sorted(SRC.rglob("*.py"))


def test_files_found():
    assert FILES


@pytest.mark.parametrize("path", FILES, ids=lambda p: str(p.relative_to(SRC)))
def test_no_old_folder_names(path):
    hits = [(n, line.strip()) for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1) if OLD.search(line)]
    assert not hits, f"{path.name} mentions an old-repo path: {hits}"


def test_the_relay_lists_ship_inside_the_package():
    for name in ("attraction_relays.yaml", "aversion_relays.yaml"):
        text = (SRC / "fly" / "data" / name).read_text(encoding="utf-8")
        assert "not re-derived by rule" in text.splitlines()[1]
