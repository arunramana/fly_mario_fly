"""Walking: LC10a (visual target tracking) -> DNp09 (forward walking descending neuron).

There is no direct LC10a -> DNp09 edge; the drive reaches DNp09 through the relays of the 636-neuron base.
The DNa steering cells (DNa01 / DNa02, left and right) sit in the same base and are read as left / right.
"""
from fly_mario_fly.fly.spec import MechanismSpec

PLUGIN = MechanismSpec(
    name="walking",
    label="Walking (LC10a -> DNp09)",
    input_groups=["LC10a_L", "LC10a_R"],
    output_groups=["DNp09", "DNa_L", "DNa_R"],
    neuron_sets=["LC10a_L", "LC10a_R", "DNp09", "DNa_L", "DNa_R"],
    note="Walking and steering come from the same LC10a cells through the base relays.",
)
