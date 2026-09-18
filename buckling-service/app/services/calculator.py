"""核算编排：把校验、欧拉、长细比、Perry 折减串成一次完整核算。"""

from __future__ import annotations

from app.core import euler, perry, slenderness
from app.models.schemas import CapacityResult, ColumnInput, EulerInput, EulerResult
from app.services.validation import check_stress_unit_consistency


def assess_euler(inp: EulerInput) -> EulerResult:
    """欧拉临界力核算。"""
    l_eff = euler.effective_length(inp.end_condition_factor, inp.length)
    p_cr = euler.euler_critical_load(inp.elastic_modulus, inp.moment_of_inertia, l_eff)
    return EulerResult(
        effective_length=l_eff,
        euler_critical_load=p_cr,
        units=inp.units,
        label=inp.label,
    )


def assess_column(inp: ColumnInput) -> CapacityResult:
    """完整核算：欧拉临界力、长细比、计入缺陷的折减承载力与控制模式。"""
    check_stress_unit_consistency(inp.elastic_modulus, inp.yield_strength)

    l_eff = euler.effective_length(inp.end_condition_factor, inp.length)
    p_cr = euler.euler_critical_load(inp.elastic_modulus, inp.moment_of_inertia, l_eff)
    r = slenderness.radius_of_gyration(inp.moment_of_inertia, inp.area)
    lam = slenderness.slenderness_ratio(l_eff, r)

    reduction = perry.reduced_capacity(
        yield_strength=inp.yield_strength,
        area=inp.area,
        euler_load=p_cr,
        imperfection_factor=inp.imperfection_factor,
    )

    return CapacityResult(
        effective_length=l_eff,
        euler_critical_load=p_cr,
        units=inp.units,
        label=inp.label,
        area=inp.area,
        radius_of_gyration=r,
        slenderness_ratio=lam,
        imperfection_factor=inp.imperfection_factor,
        **reduction,
    )
