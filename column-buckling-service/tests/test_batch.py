"""批量核算：部分失败时指出第几组、哪个参数，其余各组照常返回。"""

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


async def test_batch_partial_failure_others_succeed(client):
    items = [
        VALID,
        {**VALID, "length": -1.0},                       # 第2组：杆长非正
        {**VALID, "moment_of_inertia": -5.0},            # 第3组：惯性矩为负
        {**VALID, "effective_length_factor": 2.0},       # 第4组：合法
        {**VALID, "yield_strength": "abc"},              # 第5组：非数值
    ]
    resp = await client.post("/api/v1/batch", json={"items": items})
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["summary"] == {"total": 5, "succeeded": 2, "failed": 3}
    by_index = {item["index"]: item for item in body["items"]}

    assert by_index[1]["success"] is True
    assert by_index[4]["success"] is True

    assert by_index[2]["success"] is False
    err2 = by_index[2]["error"]
    assert "第2组" in err2["message"]
    assert err2["field"] == "length"

    assert by_index[3]["success"] is False
    assert "第3组" in by_index[3]["error"]["message"]
    assert by_index[3]["error"]["field"] == "moment_of_inertia"

    assert by_index[5]["success"] is False
    assert "第5组" in by_index[5]["error"]["message"]
    assert by_index[5]["error"]["field"] == "yield_strength"


async def test_batch_empty_rejected(client):
    resp = await client.post("/api/v1/batch", json={"items": []})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "EMPTY_BATCH"


async def test_batch_missing_items(client):
    resp = await client.post("/api/v1/batch", json={})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "MISSING_FIELD"


async def test_batch_item_not_object(client):
    resp = await client.post("/api/v1/batch", json={"items": [VALID, 42]})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert items[0]["success"] is True
    assert items[1]["success"] is False
    assert "第2组" in items[1]["error"]["message"]


async def test_batch_persists_under_one_batch_id(client):
    items = [VALID, {**VALID, "length": -1.0}, {**VALID, "area": 1.0}]
    resp = await client.post("/api/v1/batch", json={"items": items})
    batch_id = resp.json()["batch_id"]

    hist = await client.get(f"/api/v1/history?batch_id={batch_id}")
    records = hist.json()["items"]
    assert hist.json()["total"] == 3
    assert all(record["batch_id"] == batch_id for record in records)
    # 时间倒序，失败项同样落库。
    statuses = sorted(record["success"] for record in records)
    assert statuses == [False, True, True]
