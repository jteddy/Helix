"""
Built-in CS2 recoil patterns.
Each step is (x, y, delay_seconds) — identical format to parsed script vectors.
x: horizontal offset (positive = right), y: vertical offset (positive = down).
All steps use 0.1 s inter-shot delay matching CS2's fire rate.
"""
from typing import Dict, List, Tuple

# AK-47 — 29 steps
_AK47: List[Tuple[float, float, float]] = [
    (0,    10,  0.1),
    (5,    35,  0.1),
    (-8,   58,  0.1),
    (0,    60,  0.1),
    (23,   60,  0.1),
    (17,   55,  0.1),
    (25,   38,  0.1),
    (-30,  30,  0.1),
    (-75,  0,   0.1),
    (-60,  5,   0.1),
    (30,   15,  0.1),
    (-20,  10,  0.1),
    (-46,  -13, 0.1),
    (-18,  5,   0.1),
    (60,   10,  0.1),
    (60,   11,  0.1),
    (25,   12,  0.1),
    (45,   0,   0.1),
    (65,   -13, 0.1),
    (-15,  0,   0.1),
    (-5,   0,   0.1),
    (-10,  10,  0.1),
    (-10,  13,  0.1),
    (20,   -5,  0.1),
    (10,   0,   0.1),
    (-25,  4,   0.1),
    (-60,  0,   0.1),
    (-86,  -35, 0.1),
    (-40,  0,   0.1),
]

# M4A1-S — 18 steps
_M4A1S: List[Tuple[float, float, float]] = [
    (0,    10,  0.1),
    (0,    10,  0.1),
    (-5,   20,  0.1),
    (5,    34,  0.1),
    (-10,  35,  0.1),
    (-7,   38,  0.1),
    (24,   23,  0.1),
    (15,   23,  0.1),
    (30,   4,   0.1),
    (-7,   18,  0.1),
    (-25,  5,   0.1),
    (-45,  0,   0.1),
    (-45,  0,   0.1),
    (-29,  -10, 0.1),
    (0,    0,   0.1),
    (15,   8,   0.1),
    (-20,  0,   0.1),
    (-5,   0,   0.1),
]

# Keys used in API + state; labels shown in the UI
CS2_WEAPONS: Dict[str, List[Tuple[float, float, float]]] = {
    "ak47":   _AK47,
    "m4a1s":  _M4A1S,
}

CS2_WEAPON_LABELS: Dict[str, str] = {
    "ak47":   "AK-47",
    "m4a1s":  "M4A1-S",
}
