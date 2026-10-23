"""fly_mario_fly: attach MaleCNS fly senses to Super Mario objects; watch, rewind, retry."""
import os as _os
import sys as _sys

# Deprecated for one release: the env vars were FLY_MARIO_DATA and FLY_MARIO_FLIES_DIR. Accept them, say so once.
for _old, _new in (("FLY_MARIO_DATA", "FLY_MARIO_FLY_DATA"), ("FLY_MARIO_FLIES_DIR", "FLY_MARIO_FLY_FLIES_DIR")):
    if _old in _os.environ and _new not in _os.environ:
        _os.environ[_new] = _os.environ[_old]
        print(f"fly_mario_fly: ${_old} is deprecated, set ${_new} instead", file=_sys.stderr)
