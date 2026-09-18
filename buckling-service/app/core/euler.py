"""欧拉临界力计算。

有效长度 L_eff = K * L
欧拉临界力 P_cr = pi^2 * E * I / L_eff^2

两端铰接时 K = 1，P_cr = pi^2 * E * I / L^2。
"""

from __future__ import annotations

import math


def effective_length(end_condition_factor: float, length: float) -> float:
    """有效长度 = 端部约束系数 K * 杆长 L。"""
    return end_condition_factor * length


def euler_critical_load(
    elastic_modulus: float,
    moment_of_inertia: float,
    eff_length: float,
) -> float:
    """欧拉临界力 P_cr = pi^2 * E * I / L_eff^2。

    参数须为正（由上层校验保证），此处不做重复校验。
    """
    return math.pi**2 * elastic_modulus * moment_of_inertia / eff_length**2
