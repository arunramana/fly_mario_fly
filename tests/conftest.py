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
