import json
from pathlib import Path

import pytest

from flyrun.brain import load_brain

NUMBERS = Path(__file__).resolve().parent.parent / "runs" / "000_test_numbers.json"


def record(key, value, file=NUMBERS):
    """Append a number to runs/000_test_numbers.json (feeds runs/000_scaffold.md)."""
    data = json.loads(file.read_text()) if file.exists() else {}
    data[key] = value
    file.write_text(json.dumps(data, indent=2))


NUMBERS2 = NUMBERS.with_name("001_test_numbers.json")


@pytest.fixture(scope="session")
def brain():
    return load_brain()
