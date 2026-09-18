"""并发测试：多请求同时核算时结果互不干扰、历史记录不错乱。"""

import math
from concurrent.futures import ThreadPoolExecutor

import pytest

from tests.conftest import valid_payload

N_REQUESTS = 24


def test_concurrent_requests_do_not_interfere(client):
    # 每个请求使用不同的杆长，结果必须与各自的输入一一对应
    lengths = [2000.0 + 250.0 * i for i in range(N_REQUESTS)]

    def submit(length):
        resp = client.post(
            "/api/v1/buckling/capacity",
            json=valid_payload(length=length, label=f"concurrent-{length}"),
        )
        assert resp.status_code == 200
        return length, resp.json()

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(submit, lengths))

    for length, body in results:
        expected = math.pi**2 * 200000.0 * 8.35e7 / length**2
        assert body["euler_critical_load"] == pytest.approx(expected, rel=1e-9)
        assert body["label"] == f"concurrent-{length}"

    # 每次并发请求都应留下且只留下一条历史记录，请求与结果对应正确
    history = client.get(
        "/api/v1/history", params={"endpoint": "capacity", "limit": 500}
    ).json()
    concurrent_records = [
        r
        for r in history["records"]
        if str(r["request_payload"].get("label", "")).startswith("concurrent-")
    ]
    assert len(concurrent_records) == N_REQUESTS
    for record in concurrent_records:
        length = record["request_payload"]["length"]
        expected = math.pi**2 * 200000.0 * 8.35e7 / length**2
        assert record["response_payload"]["euler_critical_load"] == pytest.approx(
            expected, rel=1e-9
        )


def test_concurrent_batches_recorded_once_each(client):
    def submit(i):
        resp = client.post(
            "/api/v1/buckling/batch",
            json={
                "columns": [
                    valid_payload(label=f"batch-{i}-a", length=3000.0 + i),
                    valid_payload(label=f"batch-{i}-b", moment_of_inertia=-1.0),
                ]
            },
        )
        assert resp.status_code == 200
        return resp.json()

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(submit, range(6)))

    for body in results:
        assert body["total"] == 2
        assert body["succeeded"] == 1
        assert body["failed"] == 1

    history = client.get(
        "/api/v1/history", params={"endpoint": "batch", "limit": 500}
    ).json()
    assert len(history["records"]) >= 6
    partial = [r for r in history["records"] if r["status"] == "partial"]
    assert len(partial) >= 6
