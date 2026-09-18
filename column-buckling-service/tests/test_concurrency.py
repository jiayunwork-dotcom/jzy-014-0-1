"""并发多请求：结果互不干扰、历史记录不错乱。"""

import asyncio
import math

import pytest

VALID = {
    "moment_of_inertia": 2.0e8,
    "elastic_modulus": 2.05e5,
    "effective_length_factor": 1.0,
    "area": 7000.0,
    "yield_strength": 345.0,
    "imperfection": 0.0,
    "unit_system": "MPA_MM",
}


async def test_concurrent_requests_do_not_cross_talk(client):
    n = 12

    def payload(i: int) -> dict:
        # 每根杆杆长不同，欧拉力因此各不相同。
        return {**VALID, "length": 3000.0 + i * 500.0}

    def expected(payload: dict) -> float:
        return (
            math.pi ** 2
            * payload["elastic_modulus"]
            * payload["moment_of_inertia"]
            / payload["length"] ** 2
        )

    async def one(i: int) -> dict:
        p = payload(i)
        resp = await client.post("/api/v1/buckling", json=p)
        assert resp.status_code == 200
        body = resp.json()
        # 回显输入必须是自己的杆长，绝不能串到别的请求。
        assert body["inputs"]["length"] == p["length"]
        assert body["euler_critical_force"] == pytest.approx(expected(p))
        assert body["effective_length"] == pytest.approx(p["length"])
        return body

    results = await asyncio.gather(*(one(i) for i in range(n)))

    # 返回体与 id 一一对应、互不相同。
    ids = [r["calculation_id"] for r in results]
    assert len(set(ids)) == n
    forces = [r["euler_critical_force"] for r in results]
    assert len(set(forces)) == n  # 杆长不同 → 力也不同，没有串号

    # 历史落库数量与配对关系正确（按各自杆长精确配对，不串号）。
    hist = await client.get("/api/v1/history?kind=buckling")
    assert hist.json()["total"] == n
    by_length = {
        item["request"]["length"]: item for item in hist.json()["items"]
    }
    for i in range(n):
        p = payload(i)
        record = by_length[p["length"]]
        assert record["id"] == results[i]["calculation_id"]
        assert record["capacity"] == results[i]["capacity"]
        assert record["euler_critical_force"] == pytest.approx(expected(p))


async def test_concurrent_batches_isolated(client):
    async def batch(tag_k: float) -> str:
        items = [
            {**VALID, "length": 4000.0, "effective_length_factor": tag_k},
            {**VALID, "length": 8000.0, "effective_length_factor": tag_k},
        ]
        resp = await client.post("/api/v1/batch", json={"items": items})
        assert resp.status_code == 200
        body = resp.json()
        for item in body["items"]:
            assert item["success"] is True
            assert item["effective_length_factor"] == tag_k
        return body["batch_id"]

    batch_ids = await asyncio.gather(batch(1.0), batch(2.0), batch(3.0))
    assert len(set(batch_ids)) == 3
    for batch_id in batch_ids:
        records = (
            await client.get(f"/api/v1/history?batch_id={batch_id}")
        ).json()["items"]
        assert len(records) == 2
        assert all(r["batch_id"] == batch_id for r in records)
