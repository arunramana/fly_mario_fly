# What this file does, in plain English:
# The slim decision-maker for the redesigned fly: each game frame it works out
# how big the nearest visible enemy looks, hands that to the looming mechanism
# (which can only excite the looming-detector neurons), lets the brain run one
# frame, and presses whatever buttons the fixed motor map reads off the output
# neurons. It decides nothing itself: no forced jumps, no held buttons.
"""brain/policy.py -- docs/SPEC_brain_core.md section 8. A `sim.protocols.Policy` over `brain.Brain`.

Layers (REDESIGN_PLAN 3.1): scene (bridge.perception, visible enemies only) -> mechanism -> Brain -> MotorMap -> action.
Phase 1 has the looming mechanism only; no goal cue yet (D2 is Phase 3), so without a drive from DNp09 the fly stands.
"""

from __future__ import annotations

from bridge.perception import VisibleRegistry
from brain import builder
from brain.brain import Brain, Readout
from brain.calibration import ELEVATION_LIMIT_DEG, Calibration
from brain.mechanisms import LoomingMechanism
from brain.motor_map import Buttons, MotorMap
from brain.perception import enemy_thetas
from mario.actions.actions import action_from_buttons
from mario.entities.registry import DEFAULT as DEFAULT_REGISTRY


class BrainPolicy:
    def __init__(self, network: builder.BuiltNetwork | None = None, calibration: Calibration | None = None,
                 shuffle_seed: int | None = None, lesion: tuple[str, ...] = ()):
        """`lesion` is a control-only argument, passed by brain/e1.py's `lesion_gf` arm and nothing else."""
        net = network or builder.load_or_build()
        if shuffle_seed is not None:
            net = net.shuffled(shuffle_seed)
        self.cal = calibration or Calibration.load()
        self.brain = Brain(net, self.cal, lesion=lesion)
        self.looming = LoomingMechanism(net)
        self.brain.attach(self.looming)
        self.motor = MotorMap(self.cal.motor)
        self._registry = VisibleRegistry(DEFAULT_REGISTRY)
        self.last_readout: Readout | None = None
        self.last_buttons: Buttons = Buttons()
        self.reset(0)

    def reset(self, seed: int) -> None:
        self.brain.reset(seed)
        self.motor.reset()
        self._prev_theta = {"L": 0.0, "R": 0.0}
        self.last_theta, self.last_distance = 0.0, None     # what the fly saw last frame (rad, px), for records only

    def act(self, observation) -> int:
        theta, dtheta, dist = enemy_thetas(observation.ram, self._prev_theta, self._registry, ELEVATION_LIMIT_DEG)
        self._prev_theta = theta
        self.last_theta, self.last_distance = theta["L"], dist["L"]
        self.brain.apply(self.looming.encode(theta, dtheta))
        self.last_readout = self.brain.step_frame()
        self.last_buttons = b = self.motor.read(self.last_readout)
        return action_from_buttons(right=b.right, left=b.left, down=b.down, up=b.up, a=b.a, b=b.b)

    def stamp(self) -> dict:
        """Build rule, calibration hash and mechanism list for whatever result this policy produced."""
        return self.brain.stamp()
