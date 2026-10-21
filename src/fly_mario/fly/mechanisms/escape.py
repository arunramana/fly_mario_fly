"""Escape: looming detectors LC4 / LPLC2 -> Giant Fiber (DNp01) -> jump muscle (TTMn).

311 detectors (126 LC4 + 185 LPLC2) converge on the 2 Giant Fibers, one per hemisphere (each detector drives
exactly one). The circuit is recurrent: lateral connections inside the detector populations are 3-9.5x their
drive onto the Giant Fiber, so it is run as a dynamical system, never collapsed to a weighted sum. All of it
sits inside the 636-neuron base; nothing is added.
"""
from fly_mario.fly.spec import MechanismSpec

PLUGIN = MechanismSpec(
    name="escape",
    label="Escape (looming -> Giant Fiber -> jump)",
    input_groups=["LC4_L", "LC4_R", "LPLC2_L", "LPLC2_R"],
    output_groups=["TTMn"],
    neuron_sets=["LC4_L", "LC4_R", "LPLC2_L", "LPLC2_R", "DNp01", "TTMn"],
    note="Real wiring: 302 of the 311 detectors have a direct >=5-synapse edge onto the Giant Fiber.",
)
