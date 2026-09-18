"""持久化仓储：核算记录的写入与条件查询。

写入统一在此层提交；批量请求在单个事务内逐行写入，
保证“全组记录一起落库”，并发请求使用各自会话，互不串扰。
"""

import math
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CalculationRecord
from app.schemas import ColumnInput


def new_id() -> str:
    return uuid.uuid4().hex


def sanitize_json(value: Any) -> Any:
    """把结果清洗成严格可 JSON 序列化的值（NaN/Inf → None，避免脏数据）。"""
    if isinstance(value, dict):
        return {str(k): sanitize_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize_json(v) for v in value]
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return str(value)


def _scalars(data: ColumnInput) -> dict[str, float | None]:
    return {
        "length": data.length,
        "effective_length_factor": data.effective_length_factor,
        "imperfection": data.imperfection,
    }


async def save_success(
    session: AsyncSession,
    *,
    kind: str,
    data: ColumnInput,
    result: dict[str, Any],
    batch_id: str | None = None,
    batch_index: int | None = None,
) -> CalculationRecord:
    """写入一行成功记录并提交，返回已带 id 的记录。"""
    record = CalculationRecord(
        id=new_id(),
        kind=kind,
        success=True,
        control_mode=result.get("control_mode"),
        batch_id=batch_id,
        batch_index=batch_index,
        **_scalars(data),
        euler_critical_force=_safe(result.get("euler_critical_force")),
        capacity=_safe(result.get("capacity")),
        slenderness_ratio=_safe(result.get("slenderness_ratio")),
        request_payload=sanitize_json(data.model_dump()),
        result_payload=sanitize_json(result),
        error_payload=None,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def save_batch(
    session: AsyncSession,
    *,
    batch_id: str,
    entries: list[tuple[ColumnInput | None, dict, bool, dict | None]],
) -> list[CalculationRecord]:
    """批量写入：entries 为 (data|None, 结果体, success, error体) 顺序列表。

    单事务提交；失败项没有解析出的输入时标量字段留空。
    """
    records: list[CalculationRecord] = []
    for index, (data, body, success, error) in enumerate(entries):
        result = body if success else {}
        record = CalculationRecord(
            id=new_id(),
            kind="batch",
            success=success,
            control_mode=result.get("control_mode") if success else None,
            batch_id=batch_id,
            batch_index=index,
            **(_scalars(data) if data is not None else _empty_scalars()),
            euler_critical_force=_safe(result.get("euler_critical_force"))
            if success
            else None,
            capacity=_safe(result.get("capacity")) if success else None,
            slenderness_ratio=_safe(result.get("slenderness_ratio"))
            if success
            else None,
            request_payload=sanitize_json(
                data.model_dump() if data is not None else body.get("request") or {}
            ),
            result_payload=sanitize_json(result),
            error_payload=sanitize_json(error) if error else None,
        )
        session.add(record)
        records.append(record)
    await session.commit()
    for record in records:
        await session.refresh(record)
    return records


async def save_error(
    session: AsyncSession,
    *,
    kind: str,
    raw_request: Any,
    error: dict[str, Any],
) -> CalculationRecord:
    """写入一行失败记录（如量纲混用被拒），便于审计非法请求。"""
    record = CalculationRecord(
        id=new_id(),
        kind=kind,
        success=False,
        control_mode=None,
        batch_id=None,
        batch_index=None,
        **_empty_scalars(),
        request_payload={"raw": sanitize_json(raw_request)},
        result_payload={},
        error_payload=sanitize_json(error),
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def query_history(
    session: AsyncSession,
    *,
    kind: str | None = None,
    success: bool | None = None,
    control_mode: str | None = None,
    batch_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[CalculationRecord], int]:
    """按条件查询历史，返回 (记录列表（时间倒序）, 总数)。"""
    conditions = []
    if kind is not None:
        conditions.append(CalculationRecord.kind == kind)
    if success is not None:
        conditions.append(CalculationRecord.success == success)
    if control_mode is not None:
        conditions.append(CalculationRecord.control_mode == control_mode)
    if batch_id is not None:
        conditions.append(CalculationRecord.batch_id == batch_id)

    base = select(CalculationRecord)
    count_stmt = select(CalculationRecord.id)
    for condition in conditions:
        base = base.where(condition)
        count_stmt = count_stmt.where(condition)

    total = len((await session.execute(count_stmt)).all())
    rows = (
        await session.execute(
            base.order_by(CalculationRecord.created_at.desc(), CalculationRecord.id)
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return list(rows), total


def serialize_record(record: CalculationRecord) -> dict[str, Any]:
    def dt(value: datetime | None) -> str | None:
        return value.isoformat() if value else None

    return {
        "id": record.id,
        "kind": record.kind,
        "success": record.success,
        "control_mode": record.control_mode,
        "batch_id": record.batch_id,
        "batch_index": record.batch_index,
        "length": record.length,
        "effective_length_factor": record.effective_length_factor,
        "euler_critical_force": record.euler_critical_force,
        "capacity": record.capacity,
        "slenderness_ratio": record.slenderness_ratio,
        "imperfection": record.imperfection,
        "request": record.request_payload,
        "result": record.result_payload,
        "error": record.error_payload,
        "created_at": dt(record.created_at),
    }


def _safe(value: Any) -> float | None:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    return None


def _empty_scalars() -> dict[str, None]:
    return {
        "length": None,
        "effective_length_factor": None,
        "imperfection": None,
    }
