"""Helpers for the golden tests: the old code's answers, frozen once by tools/freeze_golden.py into tests/data/golden/.
These tests import NO old code; they compare the new code to the recorded answers."""
import gzip
import json
from pathlib import Path



GOLDEN = Path(__file__).resolve().parents[1] / "data" / "golden"


def load(name: str):
    path = GOLDEN / name
    if name.endswith(".gz"):
        with gzip.open(path, "rb") as f:
            return json.loads(f.read())
    return json.loads(path.read_text(encoding="utf-8"))


def expand(runs) -> list:
    """Undo the run-length encoding of the fixtures: [[item, count], ...] -> one item per frame."""
    return [item for item, n in runs for _ in range(n)]


def buttons_of(token: str) -> tuple:
    return tuple(token.split("+")) if token else ()



