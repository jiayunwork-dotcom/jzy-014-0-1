"""欧拉临界力规则的端到端验证（题目要求“必须守住”的行为）。"""

import math

import pytest

BASE = {
    "length": 6000.0,
    "moment_of_inertia": 2.0e8,
    "elastic_modulus": 2.05e5,
    "effective_length_factor": 1.0,
    "area": 7000.0,
    "yield_strength": 345.0,
    "imperfection": 0.0,
    "unit_system": "MPA_MM",
}


def _expected_euler(payload: dict) -> float:
    return (
        math.pi ** 2
        * payload["elastic_modulus"]
        * payload["moment_of_inertia"]
        / (payload["effective_length_factor"] * payload["length"]) ** 2
    )


@pytest.mark.parametrize("path", ["/api/v1/euler", "/api/v1/buckling"])
async def test_pinned_k1_matches_formula(client, path):
    """两端铰接 K=1 时临界力严格对上 π²EI/L²。"""
    resp = await client.post(path, json=BASE)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["effective_length_factor"] == 1.0
    assert body["effective_length"] == pytest.approx(BASE["length"])
    assert body["euler_critical_force"] == pytest.approx(_expected_euler(BASE))


@pytest.mark.parametrize("path", ["/api/v1/euler", "/api/v1/buckling"])
async def test_double_length_quarters_force(client, path):
    """只把杆长加倍，欧拉临界力变为 1/4。"""
    before = (await client.post(path, json=BASE)).json()
    doubled = {**BASE, "length": BASE["length"] * 2}
    after = (await client.post(path, json=doubled)).json()
    assert after["euler_critical_force"] == pytest.approx(
        before["euler_critical_force"] / 4.0
    )


@pytest.mark.parametrize("path", ["/api/v1/euler", "/api/v1/buckling"])
async def test_double_k_quarters_force(client, path):
    """只把 K 从 1 改到 2，欧拉临界力变为 1/4，有效长度加倍。"""
    before = (await client.post(path, json=BASE)).json()
    doubled = {**BASE, "effective_length_factor": 2.0}
    after = (await client.post(path, json=doubled)).json()
    assert after["effective_length"] == pytest.approx(
        before["effective_length"] * 2.0
    )
    assert after["euler_critical_force"] == pytest.approx(
        before["euler_critical_force"] / 4.0
    )


@pytest.mark.parametrize("path", ["/api/v1/euler", "/api/v1/buckling"])
async def test_double_inertia_doubles_force(client, path):
    before = (await client.post(path, json=BASE)).json()
    doubled = {**BASE, "moment_of_inertia": BASE["moment_of_inertia"] * 2}
    after = (await client.post(path, json=doubled)).json()
    assert after["euler_critical_force"] == pytest.approx(
        before["euler_critical_force"] * 2.0
    )


@pytest.mark.parametrize("path", ["/api/v1/euler", "/api/v1/buckling"])
async def test_double_modulus_doubles_force(client, path):
    before = (await client.post(path, json=BASE)).json()
    doubled = {**BASE, "elastic_modulus": BASE["elastic_modulus"] * 2}
    after = (await client.post(path, json=doubled)).json()
    assert after["euler_critical_force"] == pytest.approx(
        before["euler_critical_force"] * 2.0
    )


async def test_double_yield_strength_short_column_doubles_capacity(client):
    """屈服强度加倍：短柱控制的承载力加倍。"""
    before = (await client.post("/api/v1/buckling", json=BASE)).json()
    assert before["control_mode"] == "yield"
    doubled = {**BASE, "yield_strength": BASE["yield_strength"] * 2}
    after = (await client.post("/api/v1/buckling", json=doubled)).json()
    assert after["control_mode"] == "yield"
    assert after["capacity"] == pytest.approx(before["capacity"] * 2.0)


async def test_double_yield_strength_long_column_euler_unchanged(client):
    """屈服强度加倍：长柱欧拉值不变。"""
    long_column = {**BASE, "length": 20000.0}
    before = (await client.post("/api/v1/buckling", json=long_column)).json()
    assert before["control_mode"] == "euler"
    doubled = {**long_column, "yield_strength": BASE["yield_strength"] * 2}
    after = (await client.post("/api/v1/buckling", json=doubled)).json()
    # 杆足够长，屈服翻倍后仍由欧拉控制，欧拉值完全不变。
    assert after["euler_critical_force"] == pytest.approx(
        before["euler_critical_force"]
    )
    assert after["capacity"] == pytest.approx(before["capacity"])
    assert after["control_mode"] == "euler"
