# What this file does, in plain English:
# The few things the user may set about what the fly's senses pick up: which kinds
# of object it pursues (a mushroom by default, a Goomba not) and how strong the
# home landmark on the right is, and how aroused the fly is (a fly-state input
# that scales pursuit, set here, never read from the fly's own output). These change what the senses see, never what
# the fly does; they are what the Mechanisms tab edits.
"""brain/settings.py -- docs/SPEC_phase3.md sections 4 and 6.

`SenseSettings` is handed to `BrainPolicy`; it chooses which LC10a mechanisms are attached and their world properties.
`settings_for` applies an experiment's own mechanism list (E1: looming only; E0: home landmark; E3: pursuit) to the user's
settings, so an experiment never silently uses a mechanism it does not list.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from brain import calibration as C

PURSUABLE_KINDS = ("goomba", "koopa", "enemy", "powerup")      # mario.entities.kinds.EntityKind values of enemy-slot objects
DEFAULT_PURSUIT_KINDS = ("powerup",)                           # mushroom and other collectibles; a Goomba is NOT pursued by default


@dataclass(frozen=True)
class SenseSettings:
    pursuit_kinds: tuple[str, ...] = ()        # empty = pursuit not attached
    goal_cue_salience: float = 0.0             # 0 = home landmark not attached
    pursuit_arousal: float = C.PURSUIT_AROUSAL  # fly-state input in [0, 1] scaling pursuit's gain (set here, never read from the fly)

    def __post_init__(self):
        bad = [k for k in self.pursuit_kinds if k not in PURSUABLE_KINDS]
        if bad:
            raise ValueError(f"cannot pursue {bad}; choose from {PURSUABLE_KINDS}")
        if self.goal_cue_salience < 0:
            raise ValueError("goal_cue_salience must be >= 0")
        if not 0.0 <= self.pursuit_arousal <= 1.0:
            raise ValueError("pursuit_arousal must be in [0, 1]")

    def to_dict(self) -> dict:
        d = asdict(self)
        d["pursuit_kinds"] = list(self.pursuit_kinds)
        return d

    @classmethod
    def from_dict(cls, d: dict | None) -> "SenseSettings":
        if d is None:
            return cls()                       # nothing given: no mechanisms (callers wanting the tool's defaults use user_default())
        return cls(tuple(d.get("pursuit_kinds", ())), float(d.get("goal_cue_salience", 0.0)),
                   float(d.get("pursuit_arousal", C.PURSUIT_AROUSAL)))

    @classmethod
    def user_default(cls) -> "SenseSettings":
        """What the Mechanisms tab starts with."""
        return cls(DEFAULT_PURSUIT_KINDS, C.GOAL_CUE_SALIENCE, C.PURSUIT_AROUSAL)


def settings_for(experiment_id: str, user: SenseSettings | None = None) -> SenseSettings:
    """The settings an experiment actually runs with: only the mechanisms its library entry lists, with the user's values."""
    from brain.library import experiment
    user = user or SenseSettings.user_default()
    on = experiment(experiment_id).mechanisms
    return SenseSettings(user.pursuit_kinds if "pursuit" in on else (),
                         user.goal_cue_salience if "goal_direction" in on else 0.0, user.pursuit_arousal)
