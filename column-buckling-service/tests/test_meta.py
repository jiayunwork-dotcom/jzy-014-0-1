"""元信息接口与监控探针。"""

import math


async def test_convention_endpoint(client):
    resp = await client.get("/api/v1/convention")
    assert resp.status_code == 200
    body = resp.json()

    assert "pi^2 * E * I / Le^2" in body["formulas"]["euler_critical_force"]
    assert body["constants"]["pinned_effective_length_factor"] == 1.0
    assert body["tolerance"]["relative_tolerance"] == 1e-9
    modes = {m["mode"] for m in body["control_modes"]}
    assert modes == {"yield", "euler", "perry"}
    # 量纲混用可疑区间与批量上限也回显。
    low, high = body["validation"]["fy_over_e_suspect_range"]
    assert low == 1e-5 and high == 0.1
    assert body["batch"]["max_items"] >= 1


async def test_preset_example_pinned_formula(client):
    resp = await client.get("/api/v1/example")
    assert resp.status_code == 200
    body = resp.json()
    inp = body["request"]

    assert inp["effective_length_factor"] == 1.0
    ref = body["reference_euler"]["euler_critical_force"]
    expected = (
        math.pi ** 2
        * inp["elastic_modulus"]
        * inp["moment_of_inertia"]
        / inp["length"] ** 2
    )
    assert ref == expected
    # 实算临界力与参考式一致（K=1）。
    assert body["result"]["euler_critical_force"] == ref
    assert body["checks"]["k_equals_1_matches_formula"] is True
    # 该工字型量级截面为短柱，承载力被屈服封顶，而非远超屈服的欧拉力。
    assert body["result"]["control_mode"] == "yield"
    assert body["result"]["capacity"] == inp["yield_strength"] * inp["area"]
    assert body["result"]["capacity"] < ref


async def test_health_and_ready(client):
    health = await client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    ready = await client.get("/ready")
    assert ready.status_code == 200
    assert ready.json()["database"] == "reachable"
