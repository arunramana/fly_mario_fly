"""Hearing: Johnston's organ (JO) -> Giant Fiber.

The 20 JO neurons with a >=5-synapse edge straight onto the Giant Fiber (13 JO-B1_a, 6 JO-B1_c, 1 JO-CA1;
689 synapses) are added to the base. Their output onto the Giant Fiber IS the circuit, so they may write
into the rows already in the brain.
"""
import numpy as np

from fly_mario.fly.spec import ExtraNeurons, MechanismSpec


def _jo_onto_giant_fiber(conn):
    pre, post, _ = conn.edge_table()
    jo = np.flatnonzero(np.char.startswith(conn.type, "JO"))
    gf = np.flatnonzero(conn.type == "DNp01")
    ids = conn.ids[np.unique(pre[np.isin(post, gf) & np.isin(pre, jo)])]
    assert len(ids) == 20, f"expected 20 JO neurons onto the Giant Fiber, found {len(ids)}"
    return [int(i) for i in ids]


PLUGIN = MechanismSpec(
    name="hearing",
    label="Hearing (JO -> Giant Fiber)",
    input_groups=["JO"],
    output_groups=["DNp01", "TTMn"],
    neuron_sets=["JO"],
    note="Real wiring: direct JO -> Giant Fiber.",
    build_order=1,
    extra=ExtraNeurons(
        ids=_jo_onto_giant_fiber,
        writes_into_base=True,
        recipe={"rule": "JO* types with a >=5 synapse edge onto DNp01, ascending body id", "min_syn": 5},
    ),
)
