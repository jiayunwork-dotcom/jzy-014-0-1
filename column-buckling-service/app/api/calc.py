"""核算接口：欧拉临界力、折减承载力与控制模式、批量核算。"""

from typing import Any

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session
from app.errors import ServiceError
from app.repository import new_id, save_batch, save_error, save_success
from app.service import compute_euler, compute_full
from app.validation import parse_column_input

router = APIRouter(tags=["buckling"])


@router.post("/euler")
async def euler_force(
    raw: Any = Body(...),
    session: AsyncSession = Depends(get_session),
) -> Any:
    """欧拉临界力接口：Fe = π²EI / (K·L)²。"""
    try:
        data = parse_column_input(raw)
        result = compute_euler(data)
    except ServiceError as exc:
        return await _persist_error(session, "euler", raw, exc)

    record = await save_success(
        session, kind="euler", data=data, result=result
    )
    return {"calculation_id": record.id, **result}


@router.post("/buckling")
async def buckling(
    raw: Any = Body(...),
    session: AsyncSession = Depends(get_session),
) -> Any:
    """折减承载力与控制模式接口（含欧拉力、回转半径、长细比）。"""
    try:
        data = parse_column_input(raw)
        result = compute_full(
            data, relative_tolerance=settings.relative_tolerance
        )
    except ServiceError as exc:
        return await _persist_error(session, "buckling", raw, exc)

    record = await save_success(
        session, kind="buckling", data=data, result=result
    )
    return {"calculation_id": record.id, **result}


@router.post("/batch")
async def batch(
    raw: Any = Body(...),
    session: AsyncSession = Depends(get_session),
) -> Any:
    """批量核算接口。

    请求体：``{"items": [ {单组参数}, ... ]}``。
    某一组非法不影响其余各组：逐项给出成功结果或“第几组/哪个参数”的错误。
    全组记录在单个事务中落库，共享同一 batch_id。
    """
    if not isinstance(raw, dict):
        raise ServiceError(
            "INVALID_BATCH",
            "批量请求体必须是对象，形如 {'items': [ ... ]}",
        )
    items = raw.get("items")
    if not isinstance(items, list):
        raise ServiceError(
            "MISSING_FIELD",
            "批量请求必须包含数组字段 items",
            field="items",
        )
    if not items:
        raise ServiceError(
            "EMPTY_BATCH", "items 不能为空，至少提交一组核算参数", field="items"
        )
    if len(items) > settings.max_batch_items:
        raise ServiceError(
            "BATCH_TOO_LARGE",
            f"单次批量最多 {settings.max_batch_items} 组，本次 {len(items)} 组",
            field="items",
        )

    batch_id = new_id()
    responses: list[dict[str, Any]] = []
    # (data|None, 结果体, success, error体)
    entries: list[tuple] = []

    for index, item in enumerate(items):
        try:
            data = parse_column_input(item, index=index)
            result = compute_full(
                data, relative_tolerance=settings.relative_tolerance
            )
            responses.append(
                {"index": index + 1, "success": True, **result}
            )
            entries.append((data, result, True, None))
        except ServiceError as exc:
            err = exc.to_dict()
            responses.append(
                {"index": index + 1, "success": False, "error": err}
            )
            entries.append(
                (
                    None,
                    {"request": item if _json_safe(item) else None},
                    False,
                    err,
                )
            )

    records = await save_batch(
        session, batch_id=batch_id, entries=entries
    )
    for record, response in zip(records, responses, strict=True):
        response["calculation_id"] = record.id

    succeeded = sum(1 for r in responses if r["success"])
    return {
        "batch_id": batch_id,
        "summary": {
            "total": len(responses),
            "succeeded": succeeded,
            "failed": len(responses) - succeeded,
        },
        "items": responses,
    }


async def _persist_error(
    session: AsyncSession, kind: str, raw: Any, exc: ServiceError
) -> JSONResponse:
    error = exc.to_dict()
    try:
        record = await save_error(
            session, kind=kind, raw_request=raw, error=error
        )
        error["calculation_id"] = record.id
    except Exception:  # noqa: BLE001 - 持久化失败不能掩盖原始可读错误
        pass
    return JSONResponse(status_code=exc.status_code, content={"error": error})


def _json_safe(value: Any) -> bool:
    return isinstance(value, (dict, list, str, int, float, bool)) or value is None
