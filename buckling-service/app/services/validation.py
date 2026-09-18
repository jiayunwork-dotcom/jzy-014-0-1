"""输入校验：跨字段的物理合理性检查。

字段级校验（正数、有限值、必填）由 Pydantic 模型完成；
这里处理需要多个字段联合判断的规则，目前主要是
弹性模量与屈服强度的量纲混用检测。
"""

from __future__ import annotations

from app.config import E_OVER_FY_MAX, E_OVER_FY_MIN


class CalculationError(ValueError):
    """可读的核算错误：消息面向调用方，说明哪个参数、为什么被拒绝。"""


def check_stress_unit_consistency(elastic_modulus: float, yield_strength: float) -> None:
    """检查 E 与 fy 是否疑似量纲混用。

    真实工程材料的 E/fy 大致落在 [10, 1e5]；越界几乎总是因为
    一个用 MPa、另一个用 Pa 之类的单位混用。此时拒绝计算，
    而不是算出一个看似正常其实错误的承载力。
    """
    ratio = elastic_modulus / yield_strength
    if not (E_OVER_FY_MIN <= ratio <= E_OVER_FY_MAX):
        raise CalculationError(
            "suspected unit inconsistency between 'elastic_modulus' and "
            f"'yield_strength': E/fy = {ratio:.6g} is outside the plausible "
            f"range [{E_OVER_FY_MIN:g}, {E_OVER_FY_MAX:g}] for real materials. "
            "Check that both are declared in the same stress unit as the "
            "'units' field (e.g. MPa for 'N-mm')."
        )
