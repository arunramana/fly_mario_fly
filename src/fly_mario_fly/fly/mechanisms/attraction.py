"""Attraction: sweet / attractive olfactory receptor neurons (ORN_DM1, ORN_VA2, ORN_DM4) -> steering (DNa01/02).

Start from the k = 3 / N = 5 set between the three ORN types (both antennae) and DNa01/02, then prune the
relays greedily, least influential first, while the steering response stays within 10% of the full set
(done once in the old tool; data/attraction_relays.yaml is its output). 225 neurons: 163 ORNs + 62 relays.
The path ends on DNa rows, so these neurons may write into rows already in the brain.
"""
from pathlib import Path

import numpy as np
import yaml

from fly_mario_fly.fly.spec import ExtraNeurons, MechanismSpec

ORN_TYPES = ("ORN_DM1", "ORN_VA2", "ORN_DM4")
IDS = tuple(yaml.safe_load((Path(__file__).parents[1] / "data" / "attraction_relays.yaml").read_text(encoding="utf-8"))["body_ids"])


def _ids(conn):
    ids = np.array(IDS, dtype=np.int64)
    kept_orn = int(np.isin(conn.type[conn.index(ids)], ORN_TYPES).sum())
    # Only the receptors on a <= 3-hop path to DNa01/02 are in the set: 163 of the 189 ORN_DM1/VA2/DM4.
    assert kept_orn == 163 and len(ids) == 225, f"attraction set changed: {kept_orn} ORNs, {len(ids)} neurons"
    return list(IDS)


PLUGIN = MechanismSpec(
    name="attraction",
    label="Attraction (sweet smell -> steering)",
    input_groups=["ORN_L", "ORN_R"],
    output_groups=["DNa_L", "DNa_R"],
    neuron_sets=["ORN_L", "ORN_R"],
    note="Real wiring: ORN_DM1/VA2/DM4 through pruned k=3 relays onto DNa01/02.",
    build_order=2,
    extra=ExtraNeurons(
        ids=_ids,
        writes_into_base=True,
        recipe={"rule": "pruned k=3,N=5 set ORN_DM1/VA2/DM4 -> DNa01/02", "ids": list(IDS)},
    ),
)
