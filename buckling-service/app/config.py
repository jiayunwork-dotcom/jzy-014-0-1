"""服务级配置：Perry 约定回显、单位制与量纲合理性检查参数。"""

from __future__ import annotations

from app.core.perry import PERRY_CONVENTION

# 接受的单位制声明（仅作声明与回显，计算要求调用方保证单位一致）
ACCEPTED_UNIT_SYSTEMS = ("N-mm", "N-m", "kN-m", "kN-mm")

# 弹性模量与屈服强度比值的合理区间。
# 钢材约 200000/235 ~ 850，混凝土约 30000/30 ~ 1000；
# 越界通常意味着屈服强度与弹性模量量纲混用（如一个用 MPa、一个用 Pa）。
E_OVER_FY_MIN = 10.0
E_OVER_FY_MAX = 1.0e5


def config_snapshot() -> dict:
    """回显 Perry 折减约定与容差配置。"""
    return {
        "perry_convention": PERRY_CONVENTION.as_dict(),
        "accepted_unit_systems": list(ACCEPTED_UNIT_SYSTEMS),
        "unit_consistency_check": {
            "elastic_modulus_over_yield_strength_min": E_OVER_FY_MIN,
            "elastic_modulus_over_yield_strength_max": E_OVER_FY_MAX,
        },
    }
