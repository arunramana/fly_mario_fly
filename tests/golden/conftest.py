import pytest

from golden_data import load


@pytest.fixture(scope="session")
def golden():
    """Loader for a frozen fixture in tests/data/golden/ (json, json.gz)."""
    return load
