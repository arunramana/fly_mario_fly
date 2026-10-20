"""Colours and index rows of the approved R3b look. Group names are the runner's (fly/groups.yaml)."""
from __future__ import annotations

BG = (6, 6, 8)
DIM, TXT, OFF = (130, 130, 124), (205, 204, 196), (80, 80, 76)
OTHER = (110, 118, 130)         # relays of the base circuit: neutral

COLOURS = {
    "LC4_L": (57, 135, 229), "LC4_R": (57, 135, 229), "LPLC2_L": (25, 158, 112), "LPLC2_R": (25, 158, 112),
    "DNp01": (217, 89, 38), "TTMn": (230, 103, 103), "DNp09": (99, 200, 226),
    "LC10a_L": (235, 235, 235), "LC10a_R": (235, 235, 235), "DNa_L": (168, 121, 224), "DNa_R": (222, 178, 60),
    "JO": (240, 140, 200), "ORN_L": (200, 200, 90), "ORN_R": (200, 200, 90),
    "DC4_L": (250, 215, 60), "DC4_R": (250, 215, 60), "MDN": (255, 128, 64),
}
BIG = frozenset({"DNp01", "TTMn", "DNp09", "DNa_L", "DNa_R", "MDN"})

# (label, role, groups): the approved ten rows, then the two that the later senses add.
INDEX = [
    ("LC4", "looming", ["LC4_L", "LC4_R"]), ("LPLC2", "looming", ["LPLC2_L", "LPLC2_R"]),
    ("DNp01", "Giant Fiber", ["DNp01"]), ("TTMn", "jump muscle", ["TTMn"]),
    ("DNa L", "steering", ["DNa_L"]), ("DNa R", "steering", ["DNa_R"]),
    ("DNp09", "forward walking", ["DNp09"]), ("LC10a", "home", ["LC10a_L", "LC10a_R"]),
    ("JO", "hum (hearing)", ["JO"]), ("ORN", "smell", ["ORN_L", "ORN_R"]),
    ("DC4", "sour smell", ["DC4_L", "DC4_R"]), ("MDN", "walk backwards", ["MDN"]),
]
