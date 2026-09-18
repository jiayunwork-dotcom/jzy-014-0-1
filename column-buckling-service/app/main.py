"""FastAPI 应用入口与全局装配。

- 启动时建表；
- 健康检查 /health（探活）与 /ready（连通数据库，供监控采集）；
- 统一把 ServiceError、请求体解析错误、未预期异常转成可读 JSON，绝不崩溃。
"""

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app import __version__
from app.api import calc, history, meta
from app.config import settings
from app.database import AsyncSessionLocal, dispose_db, init_db
from app.errors import ServiceError

logger = logging.getLogger("column_buckling")
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    logger.info("database initialized: %s", _redact(settings.database_url))
    yield
    await dispose_db()


app = FastAPI(
    title="轴压杆屈曲核算服务",
    version=__version__,
    description=(
        "纯服务端压杆稳定计算组件：欧拉临界力、长细比、"
        "Perry 型缺陷折减承载力与控制模式，支持批量与历史查询。"
    ),
    lifespan=lifespan,
)

API_PREFIX = "/api/v1"
app.include_router(meta.router, prefix=API_PREFIX)
app.include_router(calc.router, prefix=API_PREFIX)
app.include_router(history.router, prefix=API_PREFIX)


@app.exception_handler(ServiceError)
async def service_error_handler(_: Request, exc: ServiceError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code, content={"error": exc.to_dict()}
    )


def _request_error(exc: Exception) -> dict[str, str] | None:
    """识别“请求体不是合法 JSON / 缺请求体”，给出可读说明。"""
    name = type(exc).__name__
    if name in ("JsonDecodeError", "JSONDecodeError"):
        return {
            "code": "INVALID_JSON",
            "message": "请求体不是合法 JSON，请提交可解析的核算参数对象",
        }
    return None


@app.exception_handler(RequestValidationError)
async def request_validation_handler(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    # 请求体缺失等形状类问题（非字段级，字段级校验都在 validation 层处理）。
    body = None
    for err in exc.errors():
        if err.get("type") in ("missing", "model_attributes_type"):
            body = {
                "code": "MISSING_BODY",
                "message": "缺少 JSON 请求体：请提交包含各字段的核算参数对象",
            }
            break
    if body is None:
        body = {
            "code": "INVALID_REQUEST",
            "message": "请求格式不合法，无法解析为核算参数对象",
        }
    return JSONResponse(status_code=422, content={"error": body})


@app.exception_handler(Exception)
async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    # 兜底：任何未预期错误都转成可读 500，不向前端泄露堆栈。
    logger.exception("unhandled error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "服务内部错误，请联系管理员；本次请求未产生核算结果",
            }
        },
    )


@app.get("/health", tags=["monitoring"])
async def health() -> dict[str, Any]:
    """轻量探活，不依赖数据库。"""
    return {"status": "ok", "service": "column-buckling", "version": __version__}


@app.get("/ready", tags=["monitoring"])
async def ready() -> JSONResponse:
    """就绪检查：验证数据库可连通，供监控/编排采集。"""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return JSONResponse(
            {"status": "ok", "database": "reachable", "version": __version__}
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("readiness check failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "database": "unreachable"},
        )


def _redact(url: str) -> str:
    return url.split("@")[-1] if "@" in url else url
