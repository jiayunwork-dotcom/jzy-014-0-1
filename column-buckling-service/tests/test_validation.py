"""非法输入必须被拒，并返回带字段说明的可读错误，而不是算出错误结果。"""

import math

import pytest

VALID = {
    "length": 6000.0,
    "moment_of_inertia": 2.0e8,
    "elastic_modulus": 2.05e5,
    "effective_length_factor": 1.0,
    "area": 7000.0,
    "yield_strength": 345.0,
}


async def test_missing_field_rejected(client):
    payload = {k: v for k, v in VALID.items() if k != "moment_of_inertia"}
    resp = await client.post("/api/v1/buckling", json=payload)
    assert resp.status_code == 422
    err = resp.json()["error"]
    assert err["code"] == "MISSING_FIELD"
    assert err["field"] == "moment_of_inertia"


async def test_non_numeric_rejected(client):
    resp = await client.post(
        "/api/v1/buckling", json={**VALID, "length": "六米"}
    )
    assert resp.status_code == 422
    err = resp.json()["error"]
    assert err["code"] == "INVALID_NUMBER"
    assert err["field"] == "length"


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity"])
async def test_non_finite_rejected(client, token):
    resp = await client.post(
        "/api/v1/buckling",
        content=(
            '{"length": ' + token + ', "moment_of_inertia": 2e8,'
            ' "elastic_modulus": 2.05e5, "area": 7000,'
            ' "yield_strength": 345}'
        ),
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "NON_FINITE_VALUE"
    assert resp.json()["error"]["field"] == "length"


async def test_negative_inertia_rejected(client):
    resp = await client.post(
        "/api/v1/euler", json={**VALID, "moment_of_inertia": -1.0}
    )
    assert resp.status_code == 422
    err = resp.json()["error"]
    assert err["code"] == "NON_POSITIVE_VALUE"
    assert err["field"] == "moment_of_inertia"


async def test_zero_k_rejected_before_calculation(client):
    resp = await client.post(
        "/api/v1/buckling",
        json={**VALID, "effective_length_factor": 0.0},
    )
    assert resp.status_code == 422
    err = resp.json()["error"]
    assert err["code"] == "NON_POSITIVE_VALUE"
    assert err["field"] == "effective_length_factor"
    assert "铰接" in err["message"]


async def test_negative_length_rejected(client):
    resp = await client.post(
        "/api/v1/euler", json={**VALID, "length": -6000.0}
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["field"] == "length"


async def test_nonpositive_area_rejected(client):
    resp = await client.post(
        "/api/v1/buckling", json={**VALID, "area": 0.0}
    )
    assert resp.status_code == 422
    err = resp.json()["error"]
    assert err["code"] == "NON_POSITIVE_VALUE"
    assert err["field"] == "area"
    assert "回转半径" in err["message"]


async def test_negative_imperfection_rejected(client):
    resp = await client.post(
        "/api/v1/buckling", json={**VALID, "imperfection": -0.1}
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "NEGATIVE_IMPERFECTION"


async def test_unit_mismatch_suspected_and_declaration_allows(client):
    """fy/E 量纲混用（一个 MPa、一个 Pa）未声明时拒绝；显式声明后放行。"""
    mixed = {**VALID, "elastic_modulus": 205000_000_000.0, "yield_strength": 345.0}
    # 不声明 unit_system：fy/E 远大于真实材料上限 → 拒绝
    resp = await client.post("/api/v1/buckling", json=mixed)
    assert resp.status_code == 422
    err = resp.json()["error"]
    assert err["code"] == "UNIT_MISMATCH_SUSPECTED"
    assert "量纲" in err["message"] or "单位" in err["message"]

    # 显式声明二者同属一套自洽单位制（数值本身自洽）→ 正常计算
    declared = {**mixed, "unit_system": "CONSISTENT"}
    ok = await client.post("/api/v1/buckling", json=declared)
    assert ok.status_code == 200, ok.text


async def test_extra_field_rejected(client):
    resp = await client.post(
        "/api/v1/buckling", json={**VALID, "color": "red"}
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "EXTRA_FIELD"


async def test_invalid_json_body_does_not_crash(client):
    resp = await client.post(
        "/api/v1/buckling",
        content="{not valid json",
        headers={"content-type": "application/json"},
    )
    assert resp.status_code in (400, 422)
    assert "error" in resp.json()


async def test_no_body_does_not_crash(client):
    resp = await client.post(
        "/api/v1/buckling",
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "MISSING_BODY"
