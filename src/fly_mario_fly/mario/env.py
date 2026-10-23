"""The NES half: a thin wrapper over gym-super-mario-bros / nes-py. Knows nothing about flies.

Same env family and versions as the old code (gym 0.23, nes-py, numpy 1.26). The controller byte goes to
nes-py directly, so any button combination works (no fixed action list).
"""
from __future__ import annotations

import pickle
import uuid
from dataclasses import dataclass
from typing import Any, Iterable

import setuptools  # noqa: F401  -- must precede gym on Python 3.12 (distutils shim)

import gym
import gym_super_mario_bros
import numpy as np

from fly_mario_fly.mario.facts import load_facts

assert np.__version__.startswith("1.26"), np.__version__
assert gym.__version__.startswith("0.23"), gym.__version__

# nes-py controller bits
BUTTONS = {"right": 0x80, "left": 0x40, "down": 0x20, "up": 0x10, "start": 0x08, "select": 0x04, "B": 0x02, "A": 0x01}
ROMS = {"v0": 0, "v1": 1, "v2": 2, "v3": 3}   # vanilla, downsample, pixel, rectangle
# the three whole-game envs besides the 32 stages
GAMES = {"full": "SuperMarioBros", "random": "SuperMarioBrosRandomStages", "lost_levels": "SuperMarioBros2"}


def level_ids() -> list:
    """Every selectable level id: 8 worlds x 4 stages, plus the three whole-game envs (35 in all)."""
    return [f"{w}-{s}" for w in range(1, 9) for s in range(1, 5)] + list(GAMES)


def env_id(level: str, rom: str = "v0") -> str:
    if rom not in ROMS:
        raise ValueError(f"unknown rom {rom!r}; one of {sorted(ROMS)}")
    n = ROMS[rom]
    if level in GAMES:
        return f"{GAMES[level]}-v{n}"
    if level not in level_ids():
        raise ValueError(f"unknown level {level!r}")
    w, s = level.split("-")
    return f"SuperMarioBros-{w}-{s}-v{n}"


def button_byte(buttons: Iterable[str]) -> int:
    b = 0
    for name in buttons:
        if name not in BUTTONS:
            raise ValueError(f"unknown button {name!r}")
        b |= BUTTONS[name]
    return b


@dataclass
class Step:
    ram: np.ndarray        # copy of the 2 KB CPU RAM after the frame
    frame: np.ndarray      # copy of the 240x256x3 screen
    done: bool
    info: dict


class MarioEnv:
    """reset / step / save_state / load_state over one emulator."""

    def __init__(self):
        self._gym: Any = None
        self._key = None
        self._ops: list = []      # everything that touched the game since reset: ("s", byte) or ("p", addr, value)
        self.level = "1-1"
        self.rom = "v0"
        self.noop = 0
        self.done = False
        self._slot = None         # in-memory fast path: the newest save_state() of this session (see save_state)
        self._slot_dirty = False  # nes-py's one backup slot holds a saved moment, not the level start

    # -- live RAM -------------------------------------------------------------
    @property
    def ram(self) -> np.ndarray:
        """The emulator's live RAM. Write through poke() so save states see the write."""
        return self._core().ram

    def _core(self):
        """The emulator env that owns the RAM (the random-stages env wraps one env per stage)."""
        u = self._gym.unwrapped
        return u.env if hasattr(u, "envs") else u

    @property
    def facts(self):
        """Facts for the level this env is on (the objects' remove() reads addresses from here)."""
        return load_facts(self.level)

    @property
    def frame_count(self) -> int:
        return sum(1 for op in self._ops if op[0] == "s")

    def poke(self, addr: int, value: int) -> None:
        """Write one RAM byte. Logged, so a save state replays it."""
        self.ram[addr] = value
        self._ops.append(("p", int(addr), int(value)))

    # -- lifecycle ------------------------------------------------------------
    def reset(self, level: str = "1-1", rom: str = "v0", noop: int = 0) -> Step:
        """Start `level` from the beginning, then idle `noop` frames."""
        key = (level, rom)
        if self._slot_dirty:      # reset() restores nes-py's backup slot, which now holds a saved moment: rebuild the env
            self._key = None
        self._slot = None
        if key != self._key:
            gym_id = env_id(level, rom)           # validate before touching the old env
            if self._gym is not None:
                self._gym.close()
            self._gym = gym_super_mario_bros.make(gym_id)
            self._key = key
            self._slot_dirty = False
        self.level, self.rom, self.noop = level, rom, int(noop)
        self._gym.reset(seed=0) if level == "random" else self._gym.reset()   # random stages: a fixed stage per seed
        self.done = False
        self._ops = []
        out = self._snapshot({})
        for _ in range(self.noop):
            out = self.step(())
        return out

    def step(self, buttons: Iterable[str] = ()) -> Step:
        return self._step_byte(button_byte(buttons))

    def _step_byte(self, b: int, snapshot: bool = True):
        _, _, done, info = self._gym.unwrapped.step(b)
        self.done = bool(done)
        self._ops.append(("s", b))
        return self._snapshot(info) if snapshot else None

    def _snapshot(self, info: dict) -> Step:
        return Step(self.ram.copy(), np.array(self._gym.unwrapped.screen, copy=True), self.done, dict(info))

    # -- save states ----------------------------------------------------------
    # The saved format is the recipe: (level, rom, every button byte and RAM poke since reset). Loading replays it
    # on the same deterministic emulator and gives back the identical RAM, at the emulator's ~1.3 ms per frame.
    # Fast path: nes-py has ONE in-process backup slot, so save_state() also puts the moment there (with the screen
    # and gym's two python counters) and tags the blob with a token. load_state() of the NEWEST blob of this session
    # restores in about a millisecond; an older blob, or one from another process, replays. That slot is also what
    # reset() restores, so the first reset after a save rebuilds the emulator env (cheap, once).
    _PY_STATE = ("_time_last", "_x_position_last")

    def save_state(self) -> bytes:
        token = uuid.uuid4().hex
        if self.level != "random":                    # random stages: the core env changes on reset, replay only
            core = self._core()
            core._backup()
            self._slot_dirty = True
            self._slot = dict(token=token, done=self.done, screen=np.array(self._gym.unwrapped.screen, copy=True),
                              py={k: getattr(core, k) for k in self._PY_STATE})
        return pickle.dumps({"level": self.level, "rom": self.rom, "ops": list(self._ops), "token": token})

    def load_state(self, blob: bytes) -> Step:
        s = pickle.loads(blob)
        slot = self._slot
        if slot is not None and slot["token"] == s.get("token") and (self.level, self.rom) == (s["level"], s["rom"]):
            core = self._core()
            core._restore()
            for k, v in slot["py"].items():
                setattr(core, k, v)
            self.done = slot["done"]
            self._ops = list(s["ops"])
            return Step(self.ram.copy(), slot["screen"].copy(), self.done, {})
        self.reset(s["level"], s["rom"], 0)
        for op in s["ops"]:
            if op[0] == "p":
                self.poke(op[1], op[2])
            else:
                self._step_byte(op[1], snapshot=False)      # no frame copies while replaying
        return self._snapshot({})

    def close(self) -> None:
        if self._gym is not None:
            self._gym.close()
            self._gym = None
            self._key = None
