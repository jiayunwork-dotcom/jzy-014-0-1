"""历史查询接口：按条件检索已持久化的核算请求与结果。"""

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session
from app.errors import ServiceError
from app.repository import query_history, serialize_record

router = APIRouter(tags=["history"])


@router.get("/history")
async def history(
    kind: str | None = Query(default=None, pattern="^(euler|buckling|batch)$"),
    success: bool | None = Query(default=None),
    control_mode: str | None = Query(
        default=None, pattern="^(yield|euler|perry)$"
    ),
    batch_id: str | None = Query(default=None),
    limit: int = Query(default=settings.default_history_limit, ge=1),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """按条件分页查询历史记录，按时间倒序返回。"""
    limit = min(limit, settings.max_history_limit)
    records, total = await query_history(
        session,
        kind=kind,
        success=success,
        control_mode=control_mode,
        batch_id=batch_id,
        limit=limit,
        offset=offset,
    )
    return {
        "query": {
            "kind": kind,
            "success": success,
            "control_mode": control_mode,
            "batch_id": batch_id,
            "limit": limit,
            "offset": offset,
        },
        "total": total,
        "count": len(records),
        "items": [serialize_record(record) for record in records],
    }


@router.get("/history/{record_id}")
async def history_detail(
    record_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """按 id 取单条历史记录。"""
    from sqlalchemy import select

    from app.models import CalculationRecord

    record = (
        await session.execute(
            select(CalculationRecord).where(CalculationRecord.id == record_id)
        )
    ).scalar_one_or_none()
    if record is None:
        raise ServiceError(
            "NOT_FOUND",
            f"未找到 id 为 {record_id} 的核算记录",
            status_code=404,
        )
    return serialize_record(record)
