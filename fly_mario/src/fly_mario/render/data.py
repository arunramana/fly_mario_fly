"""Plain data the renderer draws from. Nothing here knows about the runner, the fly or Mario."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class BrainData:
    """Once per run: where the somata are, which group each circuit neuron is in, and the group colours.

    all_xyz     (N, 3) voxel soma positions of every MaleCNS neuron that has one (the dim cloud)
    xyz         {group: (n, 3)} positions of that group's neurons (JO / ORN drawn at their brain terminals)
    colours     {group: (r, g, b)}
    other_xyz   (m, 3) circuit neurons that belong to no group (relays): drawn faint, they have no rate of their own
    index       [(label, role, [groups])] the rows of the index; a row's value is the neuron-weighted mean of its groups
    rate_max    {group: float} the group's maximum over the run: brightness = rate / rate_max
    counts      {group: neurons in the group}, the weights of an index row's mean
    """
    all_xyz: np.ndarray
    xyz: dict
    colours: dict
    other_xyz: np.ndarray = field(default_factory=lambda: np.zeros((0, 3)))
    other_colour: tuple = (110, 118, 130)
    index: list = field(default_factory=list)
    rate_max: dict = field(default_factory=dict)
    counts: dict = field(default_factory=dict)
    big: frozenset = frozenset()                # groups drawn with the larger core (the few, important cells)
    n_neurons: int = 0


@dataclass
class FrameData:
    """Per frame: the game as the emulator drew it, what the senses want drawn on it, and the group rates."""
    game: np.ndarray                            # (240, 256, 3) uint8
    overlay: list = field(default_factory=list)  # list[OverlayItem], geometry in level pixels
    rates: dict = field(default_factory=dict)    # {group: mean rate}
    scroll_x: float = 0.0                       # level x of the screen's left edge, to put the overlay on the screen
    frame: int = 0
