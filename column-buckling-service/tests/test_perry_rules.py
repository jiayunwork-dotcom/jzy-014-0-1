"""Perry 折减、控制模式与长细比/回转半径规则。"""

import math

import pytest

from app.domain.euler import euler_critical_force
from app.domain.geometry import radius_of_gyration, slenderness_ratio
from app.domain.perry import (
    MODE_EULER,
    MODE_PERRY,
    MODE_YIELD,
    assess_buckling,
    perry_reduction_factor,
)


def test_radius_and_slenderness():
    r = radius_of_gyration(2.0e8, 7000.0)
    assert r == pytest.approx(math.sqrt(2.0e8 / 7000.0))
    lam = slenderness_ratio(6000.0, r)
    assert lam == pytest.approx(6000.0 / r)


def test_zero_imperfection_long_column_returns_euler():
    """缺陷系数为零且未触及屈服（长柱）：承载力回到欧拉临界力。"""
    ny, fe = 2.0e6, 1.0e6  # lambda_bar = sqrt(2) > 1
    assessment = assess_buckling(ny, fe, alpha=0.0)
    assert assessment.mode == MODE_EULER
    assert assessment.capacity == pytest.approx(fe)
    assert assessment.capacity_ratio_to_euler == pytest.approx(1.0)


def test_short_column_capped_at_yield_even_with_imperfection():
    """短柱承载力不得超过屈服力，绝不把欧拉力直接当短柱承载力。"""
    ny, fe = 1.0e6, 25.0e6  # lambda_bar = 0.2 边界
    a = assess_buckling(ny, fe, alpha=0.5)
    assert a.mode == MODE_YIELD
    assert a.capacity == pytest.approx(ny)
    assert a.capacity <= fe  # 短柱不会被巨大的欧拉力带高

    ny2, fe2 = 1.0e6, 100.0e6  # 极短柱
    b = assess_buckling(ny2, fe2, alpha=2.0)
    assert b.mode == MODE_YIELD
    assert b.capacity == pytest.approx(ny2)


def test_imperfection_reduces_capacity_monotonically():
    """缺陷越大、长细比越大，折减后承载力越低。"""
    ny, fe = 2.0e6, 1.0e6  # 长柱
    a0 = assess_buckling(ny, fe, alpha=0.0).capacity
    a1 = assess_buckling(ny, fe, alpha=0.21).capacity
    a2 = assess_buckling(ny, fe, alpha=0.49).capacity
    assert a2 < a1 < a0
    # 折减后不得超过欧拉，也不得超过屈服。
    assert a2 <= fe and a2 <= ny


def test_intermediate_column_uses_perry_mode():
    """中间长细比、有缺陷：Perry 折减模式，严格低于欧拉与屈服。"""
    ny, fe = 1.5e6, 2.0e6  # lambda_bar = sqrt(0.75) 介于 0.2 与 1
    a = assess_buckling(ny, fe, alpha=0.34)
    assert a.mode == MODE_PERRY
    assert a.capacity < ny
    assert a.capacity <= fe
    assert 0.0 < a.reduction_factor < 1.0


def test_capacity_never_exceeds_euler_for_long_columns():
    # lambda_bar 横跨 0.5~2，alpha 很大时 Perry 曲线也不能越过 Fe。
    for lb in (0.5, 0.8, 1.0, 1.5, 2.0):
        fe = 1.0e6
        ny = fe * lb ** 2
        a = assess_buckling(ny, fe, alpha=5.0)
        assert a.capacity <= fe * (1 + 1e-12)


def test_euler_force_positivity_guard():
    with pytest.raises(ValueError):
        euler_critical_force(2.0e5, -1.0, 6000.0, 1.0)


def test_radius_undefined_for_nonpositive_area():
    with pytest.raises(ValueError):
        radius_of_gyration(2.0e8, 0.0)


def test_perry_factor_bounds_and_stocky_plateau():
    assert perry_reduction_factor(0.34, 0.1) == 1.0
    for lb in (0.3, 0.7, 1.0, 1.5, 3.0):
        chi = perry_reduction_factor(0.34, lb)
        assert 0.0 < chi <= 1.0
