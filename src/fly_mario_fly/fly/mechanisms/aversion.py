"""Aversion: acid (sour) olfactory receptors ORN_DC4 -> moonwalker descending neurons (MDN).

The k/N set from ORN_DC4 to MDN: 13 ORN_DC4, 9 relays, 4 MDN (26 neurons). Read-only: edges from these
neurons onto rows already in the brain are dropped, because one relay (DNpe023) alone puts 322 synapses on
DNa02 and would renormalise rows the other mechanisms depend on. MDN responds identically without them.
"""
from pathlib import Path

import numpy as np
import yaml

from fly_mario_fly.fly.spec import ExtraNeurons, MechanismSpec
from fly_mario_fly.rules import Route, declare

IDS = tuple(yaml.safe_load((Path(__file__).parents[1] / "data" / "aversion_relays.yaml").read_text(encoding="utf-8"))["body_ids"])


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
        recipe={"rule": "k=3,N=5 set ORN_DC4 -> MDN (data/aversion_relays.yaml)", "ids": list(IDS)},
    ),
)


DECLARATION = declare(
    "mechanism", "fly",
    "Real wiring: acid-smell receptor neurons ORN_DC4 and relays onto the moonwalker descending neurons (MDN). Read-only: it adds "
    "no connections onto neurons already in the brain.",
    route=Route("aversion", ("ORN_DC4", "MDN"), "ORN_DC4 -> relays -> MDN"))
