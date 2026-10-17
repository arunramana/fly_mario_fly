import json
import tempfile
from pathlib import Path

import pytest

from flyrun.brain import load_brain

# Test outputs never touch tracked files (7b amendment d): everything the tests record goes to a per-session tmp dir.
TEST_OUT = Path(tempfile.mkdtemp(prefix="flyrun_tests_"))
NUMBERS = TEST_OUT / "000_test_numbers.json"


def record(key, value, file=NUMBERS):
    """Append a number to the tmp-dir 000_test_numbers.json."""
    data = json.loads(file.read_text()) if file.exists() else {}
    data[key] = value
    file.write_text(json.dumps(data, indent=2))


NUMBERS2 = NUMBERS.with_name("001_test_numbers.json")


@pytest.fixture(scope="session")
def brain():
    return load_brain()
