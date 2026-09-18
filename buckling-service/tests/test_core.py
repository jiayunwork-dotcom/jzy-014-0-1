"""核心核算规则测试：欧拉临界力、长细比、Perry 折减的不变量。"""

import math

import pytest

from app.core import euler, perry, slenderness
from app.models.schemas import ColumnInput
from app.services.calculator import assess_column

E = 200000.0
I = 8.35e7
L = 4000.0
A = 8450.0
FY = 355.0


def make_column(**overrides):
    data = {
        "length": L,
        "moment_of_inertia": I,
        "elastic_modulus": E,
        "end_condition_factor": 1.0,
        "area": A,
        "yield_strength": FY,
        "imperfection_factor": 0.0,
        "units": "N-mm",
    }
    data.update(overrides)
    return ColumnInput(**data)


def test_pinned_pinned_k1_matches_pi2ei_over_l2():
    result = assess_column(make_column())
    assert result.euler_critical_load == pytest.approx(math.pi**2 * E * I / L**2, rel=1e-12)
    assert result.effective_length == pytest.approx(L)


def test_doubling_length_quarters_euler_load():
    base = assess_column(make_column())
    doubled = assess_column(make_column(length=2 * L))
    assert doubled.euler_critical_load == pytest.approx(base.euler_critical_load / 4, rel=1e-12)


def test_k_from_1_to_2_quarters_euler_load():
    base = assess_column(make_column(end_condition_factor=1.0))
    doubled_k = assess_column(make_column(end_condition_factor=2.0))
    assert doubled_k.euler_critical_load == pytest.approx(base.euler_critical_load / 4, rel=1e-12)


def test_doubling_inertia_doubles_euler_load():
    base = assess_column(make_column())
    doubled = assess_column(make_column(moment_of_inertia=2 * I))
    assert doubled.euler_critical_load == pytest.approx(2 * base.euler_critical_load, rel=1e-12)


def test_doubling_modulus_doubles_euler_load():
    base = assess_column(make_column())
    doubled = assess_column(make_column(elastic_modulus=2 * E))
    assert doubled.euler_critical_load == pytest.approx(2 * base.euler_critical_load, rel=1e-12)


def test_zero_imperfection_returns_to_euler_below_yield():
    # 长柱：欧拉远低于屈服，缺陷为零时承载力必须回到欧拉临界力
    result = assess_column(make_column(length=12000.0, imperfection_factor=0.0))
    assert result.euler_critical_load < result.yield_load
    assert result.capacity == pytest.approx(result.euler_critical_load, rel=1e-9)
    assert result.governing_mode == perry.MODE_EULER_BUCKLING


def test_short_column_capped_by_yield():
    # 短柱：欧拉极高，承载力不得超过屈服力，且不得把欧拉值当承载力
    result = assess_column(make_column(length=300.0, imperfection_factor=0.0))
    assert result.euler_critical_load > result.yield_load
    assert result.capacity == pytest.approx(result.yield_load, rel=1e-9)
    assert result.capacity <= FY * A
    assert result.governing_mode == perry.MODE_MATERIAL_YIELD


def test_doubling_yield_strength_doubles_short_column_capacity():
    base = assess_column(make_column(length=300.0, imperfection_factor=0.0))
    doubled = assess_column(make_column(length=300.0, yield_strength=2 * FY, imperfection_factor=0.0))
    assert doubled.capacity == pytest.approx(2 * base.capacity, rel=1e-9)


def test_doubling_yield_strength_leaves_euler_unchanged():
    base = assess_column(make_column())
    doubled = assess_column(make_column(yield_strength=2 * FY))
    assert doubled.euler_critical_load == pytest.approx(base.euler_critical_load, rel=1e-12)


def test_imperfection_reduces_capacity_below_euler():
    clean = assess_column(make_column(imperfection_factor=0.0))
    imperfect = assess_column(make_column(imperfection_factor=0.5))
    assert imperfect.capacity < clean.capacity
    assert imperfect.capacity < imperfect.euler_critical_load
    assert imperfect.governing_mode == perry.MODE_IMPERFECTION_INTERACTION


def test_larger_imperfection_means_lower_capacity():
    small = assess_column(make_column(imperfection_factor=0.2))
    large = assess_column(make_column(imperfection_factor=0.6))
    assert large.capacity < small.capacity


def test_slenderness_and_radius_of_gyration():
    r = slenderness.radius_of_gyration(I, A)
    assert r == pytest.approx(math.sqrt(I / A))
    lam = slenderness.slenderness_ratio(L, r)
    assert lam == pytest.approx(L / r)


def test_non_positive_area_rejected_for_radius_of_gyration():
    with pytest.raises(ValueError):
        slenderness.radius_of_gyration(I, 0.0)


def test_euler_scaling_identity():
    p_cr = euler.euler_critical_load(E, I, L)
    assert p_cr == pytest.approx(math.pi**2 * E * I / L**2, rel=1e-12)
