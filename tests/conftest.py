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
