"""Shared pytest setup.

Without $FLY_MARIO_FLY_DATA the tests that need the MaleCNS data (about 1.2 GB, see README) cannot run. Most of them skip
themselves; the rest raise the "set $FLY_MARIO_FLY_DATA" RuntimeError from `data_dir()`. Turn that one error into a skip,
so a fresh checkout (and CI) gets a clean run instead of 16 failures. Any other error still fails.

Do not point the variable at an empty folder to "make the skips go away": the first test that needs the weights downloads them.
"""
import os

import pytest


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    outcome = yield
    exc = outcome.excinfo
    if (exc and not os.environ.get("FLY_MARIO_FLY_DATA") and isinstance(exc[1], RuntimeError)
            and "FLY_MARIO_FLY_DATA" in str(exc[1])):
        outcome.force_exception(pytest.skip.Exception("FLY_MARIO_FLY_DATA not set"))
