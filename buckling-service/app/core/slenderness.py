"""回转半径与长细比。

回转半径 r = sqrt(I / A)
长细比   lambda = L_eff / r
"""

from __future__ import annotations

import math


def radius_of_gyration(moment_of_inertia: float, area: float) -> float:
    """回转半径 r = sqrt(I / A)。截面积必须为正，否则回转半径无定义。"""
    if area <= 0:
        raise ValueError("area must be positive to define radius of gyration")
    return math.sqrt(moment_of_inertia / area)


def slenderness_ratio(eff_length: float, radius: float) -> float:
    """长细比 lambda = L_eff / r。"""
    if radius <= 0:
        raise ValueError("radius of gyration must be positive")
    return eff_length / radius
