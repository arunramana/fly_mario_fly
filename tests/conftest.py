# What this file does, in plain English:
# Runs automatically before the tests. It limits the maths libraries to one
# processing thread before anything else loads them. The file's own note
# says that without this, the order the tests ran in could change the last
# digit of one number in a saved game log and break the exact comparisons.
"""
Set BLAS/OpenMP thread counts before any test module imports numpy. Once
numpy is imported, BLAS latches its thread count from the environment, and
run_steering.py's own setdefault comes too late: running test_entities.py
first then made the goldens differ in the last digit of one float.
"""
import os

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")


# ---- test tiers (docs/SPEC_redesign_phase6c_part2.md) ----------------------------------------------------------------------
# fast = goldens, import / non-influence guards, the generated-scalars doc check. Run every sprint with `pytest -m fast`.
# slow = everything else (marked automatically below): on request or before a release.
FAST_FILES = {"test_golden.py", "test_scalars_doc.py", "test_import_guard.py"}
FAST_TESTS = {
    "test_brain_core.py": {"test_no_other_path_adds_current", "test_motor_map_has_no_route_into_the_brain",
                           "test_motor_table_leaves_down_and_up_unassigned_and_names_only_outputs",
                           "test_every_calibration_constant_is_registered_and_the_doc_is_generated_from_it"},
    "test_shadow.py": {"test_only_the_human_action_reaches_env_step_and_the_policy_result_is_dropped",
                       "test_the_brain_path_has_no_emulator_import_no_env_calls_and_no_ram_writes"},
}


def pytest_configure(config):
    config.addinivalue_line("markers", "fast: goldens, import/non-influence guards, scalars doc (run every sprint)")
    config.addinivalue_line("markers", "slow: everything not marked fast (on request / before a release)")


def pytest_collection_modifyitems(config, items):
    import pytest
    for item in items:
        fname = item.path.name
        fast = fname in FAST_FILES or item.originalname in FAST_TESTS.get(fname, ())
        item.add_marker(pytest.mark.fast if fast else pytest.mark.slow)
