"""FastAPI 应用入口。"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.db.database import Base, engine
from app.models import db_models  # noqa: F401  确保表模型已注册
from app.services.validation import CalculationError

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Column Buckling Assessment Service",
    version="1.0.0",
    description="轴压杆屈曲核算：欧拉临界力、长细比、Perry 缺陷折减承载力与控制模式。",
)


@app.exception_handler(CalculationError)
async def calculation_error_handler(_request: Request, exc: CalculationError):
    return JSONResponse(status_code=400, content={"error": str(exc)})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError):
    details = [
        {
            "field": ".".join(str(loc) for loc in err["loc"] if loc != "body"),
            "message": err["msg"],
        }
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={"error": "invalid input", "details": details},
    )


app.include_router(router)
