"""历史持久化与条件查询。"""

import pytest

VALID = {
    "length": 6000.0,
    "moment_of_inertia": 2.0e8,
    "elastic_modulus": 2.05e5,
    "effective_length_factor": 1.0,
    "area": 7000.0,
    "yield_strength": 345.0,
    "imperfection": 0.0,
    "unit_system": "MPA_MM",
}


async def test_euler_and_buckling_are_persisted(client):
    e = await client.post("/api/v1/euler", json=VALID)
    b = await client.post("/api/v1/buckling", json=VALID)
    euler_id = e.json()["calculation_id"]
    buckling_id = b.json()["calculation_id"]

    hist = await client.get("/api/v1/history")
    ids = {item["id"] for item in hist.json()["items"]}
    assert euler_id in ids and buckling_id in ids
    assert hist.json()["total"] == 2


async def test_failed_request_is_persisted(client):
    bad = {**VALID, "length": -3.0}
    resp = await client.post("/api/v1/buckling", json=bad)
    assert resp.status_code == 422
    failed_id = resp.json()["error"].get("calculation_id")
    assert failed_id  # 失败也带可追踪 id

    records = (
        await client.get("/api/v1/history?success=false")
    ).json()["items"]
    assert records[0]["id"] == failed_id
    assert records[0]["success"] is False
    assert records[0]["error"]["field"] == "length"


async def test_history_filter_by_kind_and_mode(client):
    await client.post("/api/v1/euler", json=VALID)
    await client.post("/api/v1/buckling", json=VALID)  # 短柱 → yield

    euler_only = await client.get("/api/v1/history?kind=euler")
    assert euler_only.json()["total"] == 1
    assert euler_only.json()["items"][0]["kind"] == "euler"

    yield_mode = await client.get(
        "/api/v1/history?control_mode=yield&kind=buckling"
    )
    assert yield_mode.json()["total"] == 1
    assert yield_mode.json()["items"][0]["control_mode"] == "yield"


async def test_history_detail_by_id(client):
    created = (await client.post("/api/v1/euler", json=VALID)).json()
    detail = await client.get(f"/api/v1/history/{created['calculation_id']}")
    assert detail.status_code == 200
    record = detail.json()
    assert record["request"]["length"] == VALID["length"]
    assert record["result"]["euler_critical_force"] == pytest.approx(
        created["euler_critical_force"]
    )

    missing = await client.get("/api/v1/history/does-not-exist")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"


async def test_history_pagination(client):
    for _ in range(3):
        await client.post("/api/v1/euler", json=VALID)
    page1 = await client.get("/api/v1/history?limit=2&offset=0")
    page2 = await client.get("/api/v1/history?limit=2&offset=2")
    assert page1.json()["total"] == 3
    assert len(page1.json()["items"]) == 2
    assert len(page2.json()["items"]) == 1
    ids1 = {i["id"] for i in page1.json()["items"]}
    ids2 = {i["id"] for i in page2.json()["items"]}
    assert ids1.isdisjoint(ids2)
