"""回转半径与长细比。

约定（钉死）::

    r  = sqrt(I / A)                    回转半径
    lambda_   = Le / r                  （绝对）长细比
    lambda_bar = sqrt(Ny / Fe) = Le/r * sqrt(A/I)...    正则化长细比

其中 ``lambda_bar = 1`` 正是屈服力与欧拉临界力的分界
（``lambda_bar < 1`` 时 Fe > Ny，短柱；``> 1`` 时长柱）。
"""

import math


def radius_of_gyration(moment_of_inertia: float, area: float) -> float:
    """回转半径 r = sqrt(I/A)。I 与 A 必须为正。"""
    if area <= 0:
        raise ValueError("截面积非正时回转半径无法定义")
    if moment_of_inertia <= 0:
        raise ValueError("惯性矩必须为正")
    return math.sqrt(moment_of_inertia / area)


def slenderness_ratio(effective_length: float, radius: float) -> float:
    """（绝对）长细比 λ = Le / r。"""
    if radius <= 0:
        raise ValueError("回转半径无法定义（截面积非正）时不能计算长细比")
    if effective_length <= 0:
        raise ValueError("有效长度非正时不能计算长细比")
    return effective_length / radius


def normalized_slenderness(yield_force: float, euler_force: float) -> float:
    """正则化长细比 λ̄ = sqrt(Ny / Fe)。

    λ̄ < 1：屈服先于欧拉（短柱）；λ̄ > 1：欧拉先于屈服（长柱）。
    """
    if yield_force <= 0 or euler_force <= 0:
        raise ValueError("屈服力与欧拉临界力都必须为正")
    return math.sqrt(yield_force / euler_force)
