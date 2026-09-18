"""Perry 型缺陷折减（钉死的约定，不在运行时开放修改）。

约定：
  屈服力       P_y = fy * A
  相对长细比   lambda_bar = sqrt(P_y / P_cr)
  缺陷放大系数 eta = imperfection_factor * max(lambda_bar - PLATEAU_SLENDERNESS, 0)
  Perry 应力   sigma 满足 (fy - sigma) * (sigma_e - sigma) = eta * sigma_e * sigma
               取较小根：sigma = a - sqrt(a^2 - fy * sigma_e)
               其中 a = (fy + (1 + eta) * sigma_e) / 2, sigma_e = P_cr / A
  折减承载力   P_rd = sigma * A，且不超过 P_y

性质：
  * eta = 0 时 sigma = min(fy, sigma_e)，即未触及屈服时承载力回到欧拉临界力；
  * 缺陷越大、长细比越大，承载力越低；
  * 短柱（P_y <= P_cr）由屈服控制，承载力不超过屈服力。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class PerryConvention:
    """Perry 折减约定与容差配置（冻结，对外通过 /config 回显）。"""

    plateau_slenderness: float = 0.2
    """相对长细比低于该平台值时缺陷不起作用（eta = 0）。"""

    capacity_tolerance: float = 1e-6
    """判定控制模式时使用的相对容差。"""

    formula: str = "(fy - s) * (s_e - s) = eta * s_e * s, eta = alpha * max(lambda_bar - plateau, 0)"

    def as_dict(self) -> dict:
        return asdict(self)


PERRY_CONVENTION = PerryConvention()

# 控制模式
MODE_MATERIAL_YIELD = "material_yield"
MODE_EULER_BUCKLING = "euler_buckling"
MODE_IMPERFECTION_INTERACTION = "imperfection_interaction"


def yield_load(yield_strength: float, area: float) -> float:
    """屈服力 P_y = fy * A。"""
    return yield_strength * area


def relative_slenderness(yield_load_value: float, euler_load: float) -> float:
    """相对长细比 lambda_bar = sqrt(P_y / P_cr)。"""
    return math.sqrt(yield_load_value / euler_load)


def imperfection_amplification(
    imperfection_factor: float,
    rel_slenderness: float,
    convention: PerryConvention = PERRY_CONVENTION,
) -> float:
    """eta = alpha * max(lambda_bar - plateau, 0)。"""
    return imperfection_factor * max(rel_slenderness - convention.plateau_slenderness, 0.0)


def perry_stress(yield_strength: float, euler_stress: float, eta: float) -> float:
    """Perry 方程的较小根，即计入缺陷后的极限应力。"""
    a = (yield_strength + (1.0 + eta) * euler_stress) / 2.0
    discriminant = a * a - yield_strength * euler_stress
    # 数值上 discriminant >= 0；防御负零
    return a - math.sqrt(max(discriminant, 0.0))


def reduced_capacity(
    yield_strength: float,
    area: float,
    euler_load: float,
    imperfection_factor: float,
    convention: PerryConvention = PERRY_CONVENTION,
) -> dict:
    """折减承载力与控制模式。

    返回 dict，含屈服力、相对长细比、eta、承载力与控制模式。
    """
    p_y = yield_load(yield_strength, area)
    lam_bar = relative_slenderness(p_y, euler_load)
    eta = imperfection_amplification(imperfection_factor, lam_bar, convention)

    sigma_e = euler_load / area
    sigma = perry_stress(yield_strength, sigma_e, eta)
    capacity = min(sigma * area, p_y)  # 短柱绝不超过屈服力

    tol = convention.capacity_tolerance
    if capacity >= p_y * (1.0 - tol):
        mode = MODE_MATERIAL_YIELD
    elif capacity >= euler_load * (1.0 - tol):
        mode = MODE_EULER_BUCKLING
    else:
        mode = MODE_IMPERFECTION_INTERACTION

    return {
        "yield_load": p_y,
        "relative_slenderness": lam_bar,
        "imperfection_amplification": eta,
        "capacity": capacity,
        "governing_mode": mode,
        "capacity_to_euler_ratio": capacity / euler_load,
    }
