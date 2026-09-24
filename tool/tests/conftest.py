# What this file does, in plain English:
# Runs automatically before the tests. It limits the maths libraries to one
# processing thread before anything else loads them. Without this, the
# order the tests ran in could change the last digit of one number in a
# saved game log and break an exact byte comparison.
"""
Same fix as tests/conftest.py, duplicated here because pytest conftest.py
files apply to their own directory tree, not sibling ones -- tool/tests/
needs its own copy. Set BLAS/OpenMP thread counts before any test module
imports numpy; once numpy is imported, BLAS latches its thread count from
the environment, and run_steering.py's own setdefault comes too late.
Reproduced directly: tool/tests/test_palette.py importing numpy before
tool/tests/test_warm_worker_identity.py ran made the second test's
telemetry differ from an isolated run in the last digit of one float.
"""
import os

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
