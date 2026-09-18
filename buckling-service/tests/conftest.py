import os
import tempfile

# 必须在导入 app 之前指向独立的测试数据库
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp(prefix='buckling-test-')}/test.db"

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def valid_payload(**overrides):
    """一根两端铰接、工字型量级截面的基准压杆。"""
    payload = {
        "label": "baseline",
        "length": 4000.0,
        "moment_of_inertia": 8.35e7,
        "elastic_modulus": 200000.0,
        "end_condition_factor": 1.0,
        "area": 8450.0,
        "yield_strength": 355.0,
        "imperfection_factor": 0.0,
        "units": "N-mm",
    }
    payload.update(overrides)
    return payload
