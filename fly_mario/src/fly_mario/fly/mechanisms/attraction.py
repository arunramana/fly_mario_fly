"""Attraction: sweet / attractive olfactory receptor neurons (ORN_DM1, ORN_VA2, ORN_DM4) -> steering (DNa01/02).

Start from the k = 3 / N = 5 set between the three ORN types (both antennae) and DNa01/02, then prune the
relays greedily, least influential first, while the steering response stays within 10% of the full set
(done once in the old flyrun/m2_brain.py; IDS below is its output). 225 neurons: 163 ORNs + 62 relays.
The path ends on DNa rows, so these neurons may write into rows already in the brain.
"""
import numpy as np

from fly_mario.fly.spec import ExtraNeurons, MechanismSpec

ORN_TYPES = ("ORN_DM1", "ORN_VA2", "ORN_DM4")
IDS = (
    10038, 10176, 10390, 10561, 10567, 10702, 10816, 11111, 11195, 11297, 11455, 11610, 11723, 12171,
    12471, 13289, 13986, 14192, 14212, 16508, 17436, 18147, 19306, 19519, 19828, 21688, 24396, 26551,
    27893, 28186, 38338, 46409, 46788, 48301, 48545, 56308, 60498, 67789, 69439, 70325, 75421, 76486,
    84747, 105395, 116618, 119181, 120627, 123123, 123968, 126824, 135957, 137788, 138423, 141308, 141372,
    141661, 142802, 142962, 145253, 145847, 148445, 150947, 153046, 153849, 154416, 156151, 157520, 158617,
    158649, 159524, 160357, 160643, 161922, 162611, 162635, 163657, 164269, 164384, 165341, 167640, 169187,
    169422, 170322, 170403, 170735, 170950, 171201, 173031, 173387, 173751, 173912, 173968, 174237, 176260,
    176862, 178532, 179108, 179786, 180317, 180465, 180771, 181207, 181625, 182888, 183425, 183973, 184230,
    184468, 184729, 186029, 186200, 186397, 187949, 188007, 189075, 189355, 189518, 189605, 190032, 190294,
    190954, 191144, 192555, 192631, 194874, 195280, 198139, 199488, 202140, 202321, 202705, 204248, 204564,
    204881, 205907, 207430, 210364, 210853, 212914, 214857, 214895, 214985, 217507, 218745, 220183, 221747,
    222974, 226401, 226920, 235199, 240470, 250249, 255283, 255865, 258551, 260128, 276359, 279476, 296449,
    301799, 308608, 353891, 363119, 369074, 414342, 416090, 436473, 437025, 512118, 514053, 514510, 517723,
    519131, 520155, 520466, 521190, 521197, 521420, 523497, 524732, 524893, 527409, 527410, 527588, 529571,
    530667, 530668, 532745, 536451, 536550, 541552, 544744, 551689, 551768, 552278, 555881, 556859, 561669,
    564451, 569249, 569993, 569995, 900877, 921954, 922590, 925375, 925376, 925639, 925694, 956071,
    212945075, 222256845, 237355379, 282395216, 442779736, 499769368, 526888712, 616971586, 648510281,
    676893250, 683472058, 742571852, 802014155, 821459348, 907638584,
)


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
