"""核算历史的持久化与查询。"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models.db_models import CalculationRecord


def save_record(
    db: Session,
    *,
    endpoint: str,
    status: str,
    request_payload: dict,
    response_payload: Optional[dict] = None,
    error_message: Optional[str] = None,
) -> CalculationRecord:
    record = CalculationRecord(
        endpoint=endpoint,
        status=status,
        request_payload=request_payload,
        response_payload=response_payload,
        error_message=error_message,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def query_records(
    db: Session,
    *,
    endpoint: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[int, list[CalculationRecord]]:
    q = db.query(CalculationRecord)
    if endpoint:
        q = q.filter(CalculationRecord.endpoint == endpoint)
    if status:
        q = q.filter(CalculationRecord.status == status)
    total = q.count()
    rows = (
        q.order_by(CalculationRecord.id.desc()).offset(offset).limit(limit).all()
    )
    return total, rows


def count_records(db: Session) -> int:
    return db.query(CalculationRecord).count()
