"""欧拉临界力与有效长度。

约定（钉死）::

    K  = 有效长度系数，两端铰接时 K = 1
    Le = K * L                         有效长度
    Fe = pi^2 * E * I / Le^2           欧拉临界力

关键性质（由本模块与测试共同保证）：
- L 加倍 → Fe 变为 1/4
- K 从 1 改到 2 → Fe 变为 1/4
- I 加倍 → Fe 加倍
- E 加倍 → Fe 加倍
- 铰接 K=1 时严格对上 pi^2 E I / L^2
"""

import math

PI_SQUARED = math.pi ** 2


def effective_length(length: float, k: float) -> float:
    """有效长度 Le = K·L。"""
    return k * length


def euler_critical_force(
    elastic_modulus: float,
    moment_of_inertia: float,
    length: float,
    k: float = 1.0,
) -> float:
    """欧拉临界力 Fe = π²EI / (K·L)²。

    参数必须在调用前通过校验：E、I、L 为正，K > 0。
    """
    if elastic_modulus <= 0:
        raise ValueError("弹性模量必须为正")
    if moment_of_inertia <= 0:
        raise ValueError("截面惯性矩必须为正")
    if length <= 0:
        raise ValueError("杆长必须为正")
    if k <= 0:
        raise ValueError("有效长度系数K必须为正")
    le = effective_length(length, k)
    return PI_SQUARED * elastic_modulus * moment_of_inertia / (le ** 2)
