"""Aversion: acid (sour) olfactory receptors ORN_DC4 -> moonwalker descending neurons (MDN).

The L2c k/N set from ORN_DC4 to MDN: 13 ORN_DC4, 9 relays, 4 MDN (26 neurons). Read-only: edges from these
neurons onto rows already in the brain are dropped, because one relay (DNpe023) alone puts 322 synapses on
DNa02 and would renormalise rows the other mechanisms depend on. MDN responds identically without them.
"""
import numpy as np

from fly_mario.fly.spec import ExtraNeurons, MechanismSpec

IDS = (
    10184, 10763, 11288, 11332, 11449, 12348, 14784, 15353, 17430, 95720, 97057, 117725, 135249, 137038,
    137465, 148268, 163129, 167320, 168415, 174815, 214896, 230155, 237101, 520393, 521624, 1014647942,
)


def _ids(conn):
    types = conn.type[conn.index(np.array(IDS, dtype=np.int64))]
    assert (types == "ORN_DC4").sum() == 13 and (types == "MDN").sum() == 4, "DC4 / MDN counts changed"
    return list(IDS)


PLUGIN = MechanismSpec(
    name="aversion",
    label="Aversion (acid smell -> moonwalker)",
    input_groups=["DC4_L", "DC4_R"],
    output_groups=["MDN"],
    neuron_sets=["DC4_L", "DC4_R", "MDN"],
    note="Real wiring: ORN_DC4 through 9 relays onto the 4 MDN; read-only into the older rows.",
    build_order=3,
    extra=ExtraNeurons(
        ids=_ids,
        writes_into_base=False,
        recipe={"rule": "L2c k=3,N=5 set ORN_DC4 -> MDN", "ids": list(IDS)},
    ),
)
