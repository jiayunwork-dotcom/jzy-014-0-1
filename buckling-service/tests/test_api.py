"""HTTP 接口行为测试：校验、错误可读性、批量部分失败、历史持久化、配置回显。"""

import math

import pytest

from tests.conftest import valid_payload


def test_capacity_endpoint_pinned_example(client):
    resp = client.post("/api/v1/buckling/capacity", json=valid_payload())
    assert resp.status_code == 200
    body = resp.json()
    expected = math.pi**2 * 200000.0 * 8.35e7 / 4000.0**2
    assert body["euler_critical_load"] == pytest.approx(expected, rel=1e-9)
    assert body["governing_mode"] in (
        "material_yield",
        "euler_buckling",
        "imperfection_interaction",
    )


def test_preset_example_round_trip(client):
    example = client.get("/api/v1/examples/pinned-pinned").json()
    payload = example["payload"]
    assert payload["end_condition_factor"] == 1.0
    resp = client.post("/api/v1/buckling/capacity", json=payload)
    assert resp.status_code == 200
    expected = (
        math.pi**2
        * payload["elastic_modulus"]
        * payload["moment_of_inertia"]
        / payload["length"] ** 2
    )
    assert resp.json()["euler_critical_load"] == pytest.approx(expected, rel=1e-9)


def test_missing_field_rejected_with_readable_error(client):
    payload = valid_payload()
    del payload["length"]
    resp = client.post("/api/v1/buckling/capacity", json=payload)
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"] == "invalid input"
    assert any("length" in d["field"] for d in body["details"])


def test_non_numeric_value_rejected(client):
    resp = client.post(
        "/api/v1/buckling/capacity", json=valid_payload(length="four meters")
    )
    assert resp.status_code == 422
    assert any("length" in d["field"] for d in resp.json()["details"])


def test_non_finite_value_rejected(client):
    resp = client.post(
        "/api/v1/buckling/capacity", json=valid_payload(elastic_modulus="Infinity")
    )
    assert resp.status_code == 422


def test_negative_inertia_rejected(client):
    resp = client.post(
        "/api/v1/buckling/capacity", json=valid_payload(moment_of_inertia=-8.35e7)
    )
    assert resp.status_code == 422
    assert any("moment_of_inertia" in d["field"] for d in resp.json()["details"])


def test_zero_end_condition_factor_rejected(client):
    resp = client.post(
        "/api/v1/buckling/capacity", json=valid_payload(end_condition_factor=0.0)
    )
    assert resp.status_code == 422
    assert any("end_condition_factor" in d["field"] for d in resp.json()["details"])


def test_zero_length_rejected(client):
    resp = client.post("/api/v1/buckling/capacity", json=valid_payload(length=0.0))
    assert resp.status_code == 422


def test_unit_mismatch_between_modulus_and_yield_rejected(client):
    # fy 写成 Pa 量级而 E 用 MPa：E/fy 远超合理区间，必须报错而非给出错误承载力
    resp = client.post(
        "/api/v1/buckling/capacity",
        json=valid_payload(yield_strength=355.0e-9),
    )
    assert resp.status_code == 400
    assert "unit inconsistency" in resp.json()["error"]


def test_euler_endpoint(client):
    resp = client.post(
        "/api/v1/buckling/euler",
        json={
            "length": 4000.0,
            "moment_of_inertia": 8.35e7,
            "elastic_modulus": 200000.0,
            "end_condition_factor": 1.0,
            "units": "N-mm",
        },
    )
    assert resp.status_code == 200
    expected = math.pi**2 * 200000.0 * 8.35e7 / 4000.0**2
    assert resp.json()["euler_critical_load"] == pytest.approx(expected, rel=1e-9)


def test_batch_partial_failure_others_succeed(client):
    good = valid_payload(label="ok-1")
    bad = valid_payload(label="bad", moment_of_inertia=-1.0)
    good2 = valid_payload(label="ok-2", length=5000.0)
    resp = client.post(
        "/api/v1/buckling/batch", json={"columns": [good, bad, good2]}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert body["succeeded"] == 2
    assert body["failed"] == 1

    failed_item = body["items"][1]
    assert failed_item["status"] == "error"
    assert failed_item["index"] == 1
    assert "item 1" in failed_item["error"]
    assert "moment_of_inertia" in failed_item["error"]

    assert body["items"][0]["status"] == "success"
    assert body["items"][2]["status"] == "success"
    expected = math.pi**2 * 200000.0 * 8.35e7 / 5000.0**2
    assert body["items"][2]["result"]["euler_critical_load"] == pytest.approx(
        expected, rel=1e-9
    )


def test_history_persists_requests_and_results(client):
    before = client.get("/api/v1/history", params={"endpoint": "capacity"}).json()["total"]

    payload = valid_payload(label="history-check")
    calc = client.post("/api/v1/buckling/capacity", json=payload).json()

    history = client.get("/api/v1/history", params={"endpoint": "capacity"}).json()
    assert history["total"] >= before + 1
    latest = history["records"][0]
    assert latest["endpoint"] == "capacity"
    assert latest["status"] == "success"
    assert latest["request_payload"]["label"] == "history-check"
    assert latest["response_payload"]["capacity"] == pytest.approx(calc["capacity"])


def test_history_records_failed_requests(client):
    client.post("/api/v1/buckling/capacity", json=valid_payload(yield_strength=1e-9))
    history = client.get(
        "/api/v1/history", params={"endpoint": "capacity", "status": "error"}
    ).json()
    assert history["total"] >= 1
    assert "unit inconsistency" in history["records"][0]["error_message"]


def test_config_endpoint_echoes_perry_convention(client):
    body = client.get("/api/v1/config").json()
    perry = body["perry_convention"]
    assert perry["plateau_slenderness"] == 0.2
    assert perry["capacity_tolerance"] > 0
    assert "formula" in perry
    assert "N-mm" in body["accepted_unit_systems"]


def test_health_endpoint(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["database"] is True
    assert body["records"] >= 0
