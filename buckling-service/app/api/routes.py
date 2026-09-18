"""HTTP 路由：欧拉核算、折减承载力核算、批量核算、历史查询、配置回显、健康检查。"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, Query
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.config import config_snapshot
from app.db.database import get_db
from app.models.schemas import (
    BatchItemResult,
    BatchResult,
    ColumnInput,
    EulerInput,
)
from app.services import calculator, persistence
from app.services.validation import CalculationError

router = APIRouter()

ENDPOINT_EULER = "euler"
ENDPOINT_CAPACITY = "capacity"
ENDPOINT_BATCH = "batch"


def _first_validation_message(exc: ValidationError) -> str:
    """把 Pydantic 错误翻译成可读的一句话：哪个参数、什么问题。"""
    err = exc.errors()[0]
    field = ".".join(str(loc) for loc in err["loc"]) or "(unknown)"
    return f"parameter '{field}': {err['msg']}"


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    """基本运行状态，供监控采集。"""
    db_ok = True
    record_count = None
    try:
        record_count = persistence.count_records(db)
    except Exception:
        db_ok = False
    return {"status": "ok" if db_ok else "degraded", "database": db_ok, "records": record_count}


@router.get("/api/v1/config")
def get_config() -> dict:
    """回显 Perry 折减约定与容差配置。"""
    return config_snapshot()


@router.get("/api/v1/examples/pinned-pinned")
def pinned_pinned_example() -> dict:
    """预置算例：两端铰接（K=1）、常见工字型量级截面。

    直接 POST 其中的 payload 到 /api/v1/buckling/capacity 即可复算，
    临界力与 pi^2 * E * I / L^2 一致。
    """
    payload = {
        "label": "pinned-pinned-I-section",
        "length": 4000.0,            # mm
        "moment_of_inertia": 8.35e7, # mm^4，常见工字型量级
        "elastic_modulus": 200000.0, # MPa
        "end_condition_factor": 1.0, # 两端铰接
        "area": 8450.0,              # mm^2
        "yield_strength": 355.0,     # MPa
        "imperfection_factor": 0.21,
        "units": "N-mm",
    }
    return {
        "description": "pinned-pinned column (K=1), typical I-section; "
        "euler_critical_load equals pi^2 * E * I / L^2",
        "payload": payload,
    }


@router.post("/api/v1/buckling/euler")
def buckling_euler(payload: EulerInput, db: Session = Depends(get_db)) -> dict:
    """欧拉临界力接口。"""
    result = calculator.assess_euler(payload)
    persistence.save_record(
        db,
        endpoint=ENDPOINT_EULER,
        status="success",
        request_payload=payload.model_dump(),
        response_payload=result.model_dump(),
    )
    return result.model_dump()


@router.post("/api/v1/buckling/capacity")
def buckling_capacity(payload: ColumnInput, db: Session = Depends(get_db)) -> dict:
    """折减承载力与控制模式接口。"""
    try:
        result = calculator.assess_column(payload)
    except CalculationError as exc:
        persistence.save_record(
            db,
            endpoint=ENDPOINT_CAPACITY,
            status="error",
            request_payload=payload.model_dump(),
            error_message=str(exc),
        )
        raise
    persistence.save_record(
        db,
        endpoint=ENDPOINT_CAPACITY,
        status="success",
        request_payload=payload.model_dump(),
        response_payload=result.model_dump(),
    )
    return result.model_dump()


@router.post("/api/v1/buckling/batch")
def buckling_batch(body: dict = Body(...), db: Session = Depends(get_db)) -> dict:
    """批量核算接口。

    逐组独立校验与计算：某一组非法时指出第几组、哪个参数，
    其余各组照常返回结果。
    """
    raw_columns: Any = body.get("columns") if isinstance(body, dict) else None
    if not isinstance(raw_columns, list) or not raw_columns:
        raise CalculationError(
            "request body must contain a non-empty 'columns' array"
        )

    items: list[BatchItemResult] = []
    for idx, raw in enumerate(raw_columns):
        label = raw.get("label") if isinstance(raw, dict) else None
        try:
            column = ColumnInput.model_validate(raw)
            result = calculator.assess_column(column)
            items.append(
                BatchItemResult(
                    index=idx, label=column.label, status="success", result=result
                )
            )
        except ValidationError as exc:
            items.append(
                BatchItemResult(
                    index=idx,
                    label=label,
                    status="error",
                    error=f"item {idx}: {_first_validation_message(exc)}",
                )
            )
        except CalculationError as exc:
            items.append(
                BatchItemResult(
                    index=idx, label=label, status="error", error=f"item {idx}: {exc}"
                )
            )

    failed = sum(1 for it in items if it.status == "error")
    batch = BatchResult(
        total=len(items), succeeded=len(items) - failed, failed=failed, items=items
    )
    status = "success" if failed == 0 else ("error" if failed == len(items) else "partial")
    persistence.save_record(
        db,
        endpoint=ENDPOINT_BATCH,
        status=status,
        request_payload=body,
        response_payload=batch.model_dump(),
    )
    return batch.model_dump()


@router.get("/api/v1/history")
def history(
    endpoint: Optional[str] = Query(default=None, description="按接口过滤：euler/capacity/batch"),
    status: Optional[str] = Query(default=None, description="按状态过滤：success/error/partial"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    """历史核算记录查询。"""
    total, rows = persistence.query_records(
        db, endpoint=endpoint, status=status, limit=limit, offset=offset
    )
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "records": [r.as_dict() for r in rows],
    }
