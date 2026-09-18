"""Perry 型初始缺陷折减与控制模式。

约定（钉死的 Perry / Perry-Robertson 型折减）::

    lambda_bar = sqrt(Ny / Fe)              正则化长细比
    eta        = alpha * (lambda_bar - 0.2)  Perry 初始缺陷项，alpha >= 0
    phi        = 1/2 * [1 + eta + lambda_bar^2]
    chi        = 1 / (phi + sqrt(phi^2 - lambda_bar^2))   (Perry 小根)
    Nr         = chi * Ny

性质（由本模块与测试共同保证）：
- alpha=0 且尚未触及屈服（长柱）时，Nr 严格回到欧拉临界力 Fe；
- 短柱（λ̄ 很小）承载力被屈服力 Ny 封顶，绝不把欧拉力直接当短柱承载力；
- alpha 越大、λ̄ 越大，折减越深，Nr 越低（单调）；
- 控制模式三选一：``yield``（材料屈服）/ ``perry``（缺陷折减）/
  ``euler``（欧拉控制）。
"""

import math
from dataclasses import dataclass

from app.domain.geometry import normalized_slenderness

# 全截面屈服、不做缺陷折减的短柱门槛（λ̄ <= 0.2）。
STOCKY_SLENDERNESS_LIMIT = 0.2

# 控制模式常量。
MODE_YIELD = "yield"
MODE_PERRY = "perry"
MODE_EULER = "euler"

# 结果与屈服/欧拉基准“贴合”时归类的相对容差，可由配置注入。
DEFAULT_RELATIVE_TOLERANCE = 1e-9


@dataclass(frozen=True)
class BucklingAssessment:
    """折减后的核算结论。"""

    yield_force: float
    euler_force: float
    normalized_slenderness: float
    imperfection_factor: float          # 即入参 alpha
    perry_eta: float                    # 缺陷项 eta
    reduction_factor: float             # chi，折减系数（折减后力 / 屈服力）
    capacity: float                     # 折减后承载力 Nr
    mode: str                           # yield / perry / euler
    mode_label: str                     # 中文说明
    capacity_ratio_to_yield: float      # Nr / Ny
    capacity_ratio_to_euler: float      # Nr / Fe


def perry_eta(alpha: float, lambda_bar: float) -> float:
    """Perry 缺陷项 eta = alpha·(λ̄ - 0.2)，门槛以内为 0。"""
    if alpha < 0:
        raise ValueError("初始缺陷系数不得为负")
    return alpha * max(0.0, lambda_bar - STOCKY_SLENDERNESS_LIMIT)


def perry_reduction_factor(alpha: float, lambda_bar: float) -> float:
    """Perry 折减系数 chi（小根）。

    λ̄ <= 0.2 的短柱取 chi=1（全截面屈服）。
    alpha=0 时 chi = 1/max(1, λ̄²)，
    长柱（λ̄>1）下 chi·Ny 恰好等于 Fe。
    """
    if lambda_bar <= STOCKY_SLENDERNESS_LIMIT:
        return 1.0

    eta = perry_eta(alpha, lambda_bar)
    phi = 0.5 * (1.0 + eta + lambda_bar ** 2)
    radicand = phi ** 2 - lambda_bar ** 2
    # 理论上恒非负；数值噪声下夹回 0，避免开方产生 NaN。
    chi = 1.0 / (phi + math.sqrt(max(0.0, radicand)))
    return min(1.0, max(0.0, chi))


def assess_buckling(
    yield_force: float,
    euler_force: float,
    alpha: float,
    relative_tolerance: float = DEFAULT_RELATIVE_TOLERANCE,
) -> BucklingAssessment:
    """给定屈服力、欧拉力与缺陷系数，给出承载力与控制模式。"""
    lambda_bar = normalized_slenderness(yield_force, euler_force)
    chi = perry_reduction_factor(alpha, lambda_bar)
    eta = perry_eta(alpha, lambda_bar)

    capacity = chi * yield_force

    # 与屈服 / 欧拉基准的贴合判定（相对容差），用于精确归类模式。
    y_tol = yield_force * relative_tolerance
    e_tol = euler_force * relative_tolerance

    # 短柱（lambda_bar <= 0.2）直接以屈服封顶；
    # 其余情况下，凡触及屈服上限即屈服控制。
    if (
        lambda_bar <= STOCKY_SLENDERNESS_LIMIT
        or abs(capacity - yield_force) <= y_tol
    ):
        mode = MODE_YIELD
        mode_label = "材料屈服控制"
        capacity = yield_force
    # 理想直杆长柱 / 已贴到欧拉上限 → 欧拉控制。
    # Perry 曲线恒有 Nr <= Fe，故该比较同时是对欧拉上限的封顶。
    elif abs(capacity - euler_force) <= e_tol or capacity > euler_force:
        mode = MODE_EULER
        mode_label = "欧拉屈曲控制"
        capacity = euler_force
    else:
        mode = MODE_PERRY
        mode_label = "初始缺陷折减控制（Perry）"

    return BucklingAssessment(
        yield_force=yield_force,
        euler_force=euler_force,
        normalized_slenderness=lambda_bar,
        imperfection_factor=alpha,
        perry_eta=eta,
        reduction_factor=chi,
        capacity=capacity,
        mode=mode,
        mode_label=mode_label,
        capacity_ratio_to_yield=capacity / yield_force,
        capacity_ratio_to_euler=capacity / euler_force,
    )
