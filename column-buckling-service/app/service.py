"""计算编排：把校验后的输入送进纯计算域，组装对外结果。

这里不做 HTTP、不碰数据库，方便单测与复用。
"""

from app.domain.euler import effective_length, euler_critical_force
from app.domain.geometry import (
    radius_of_gyration,
    slenderness_ratio,
)
from app.domain.perry import assess_buckling
from app.schemas import ColumnInput


def compute_euler(data: ColumnInput) -> dict:
    """仅算欧拉临界力（有效长度系数 K、有效长度一并回显）。"""
    le = effective_length(data.length, data.effective_length_factor)
    fe = euler_critical_force(
        data.elastic_modulus,
        data.moment_of_inertia,
        data.length,
        data.effective_length_factor,
    )
    return {
        "effective_length_factor": data.effective_length_factor,
        "effective_length": le,
        "euler_critical_force": fe,
    }


def compute_full(data: ColumnInput, relative_tolerance: float = 1e-9) -> dict:
    """完整核算：欧拉力、回转半径、长细比、缺陷折减承载力与控制模式。"""
    k = data.effective_length_factor
    le = effective_length(data.length, k)
    fe = euler_critical_force(
        data.elastic_modulus, data.moment_of_inertia, data.length, k
    )
    radius = radius_of_gyration(data.moment_of_inertia, data.area)
    slenderness = slenderness_ratio(le, radius)
    yield_force = data.yield_strength * data.area

    assessment = assess_buckling(
        yield_force=yield_force,
        euler_force=fe,
        alpha=data.imperfection,
        relative_tolerance=relative_tolerance,
    )

    return {
        "inputs": _echo_inputs(data),
        "effective_length_factor": k,
        "effective_length": le,
        "radius_of_gyration": radius,
        "slenderness_ratio": slenderness,
        "yield_force": yield_force,
        "euler_critical_force": fe,
        "normalized_slenderness": assessment.normalized_slenderness,
        "imperfection_factor": assessment.imperfection_factor,
        "perry_eta": assessment.perry_eta,
        "reduction_factor": assessment.reduction_factor,
        "capacity": assessment.capacity,
        "control_mode": assessment.mode,
        "control_mode_label": assessment.mode_label,
        "capacity_ratio_to_yield": assessment.capacity_ratio_to_yield,
        "capacity_ratio_to_euler": assessment.capacity_ratio_to_euler,
    }


def _echo_inputs(data: ColumnInput) -> dict:
    return {
        "length": data.length,
        "moment_of_inertia": data.moment_of_inertia,
        "elastic_modulus": data.elastic_modulus,
        "effective_length_factor": data.effective_length_factor,
        "area": data.area,
        "yield_strength": data.yield_strength,
        "imperfection": data.imperfection,
        "unit_system": data.unit_system,
    }
