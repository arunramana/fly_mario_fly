# flyrun

Assisted, disclosed Mario 1-1 run by the fly circuit (see `runs/` for the numbered notes).

**Interpreter.** flyrun runs on the *system* Python 3.12 (`C:\Users\arunr\AppData\Local\Programs\Python\Python312`), not the
repo `.venv` (which lacks nes_py, gym, cma and PyYAML). `requirements.txt` is synced to that interpreter (pip freeze, trimmed
to what flyrun imports). Every Part 7 output is stamped with `sys.version` and a hash of the full `pip freeze`; the freeze
itself is written to `runs/008_env.txt`.

Tests write their numbers to a per-session tmp dir (`tests/conftest.py`), never to tracked files.
