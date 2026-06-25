"""FastAPI entrypoint."""

from __future__ import annotations

import uuid

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routers.query_router import query_router
from app.core.context import request_id_ctx_var
from app.core.lifespan import lifespan

from .config import APP_PORT
from .errors import AppError
from .response import fail
from .routers.accounts import router as accounts_router
from .routers.collections import router as collections_router
from .routers.customers import router as customers_router
from .routers.foundation import router as foundation_router
from .routers.loans import router as loans_router
from .routers.operations import router as operations_router
from .routers.repayments import router as repayments_router
from .routers.risk import router as risk_router
from .routers.wealth import router as wealth_router

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

OPENAPI_TAGS = [
    {"name": "query", "description": "金融问数接口"},
    {"name": "foundation", "description": "基础配置接口"},
    {"name": "customers", "description": "客户接口"},
    {"name": "accounts", "description": "账户与交易接口"},
    {"name": "wealth", "description": "理财接口"},
    {"name": "loans", "description": "信贷接口"},
    {"name": "repayments", "description": "还款与逾期接口"},
    {"name": "risk", "description": "风控与反洗钱接口"},
    {"name": "collections", "description": "催收接口"},
    {"name": "operations", "description": "运营支撑接口"},
]

app = FastAPI(
    title="Finance Data API",
    version="0.1.0",
    openapi_tags=OPENAPI_TAGS,
    lifespan=lifespan,
)

app.include_router(query_router, tags=["query"])
app.include_router(foundation_router)
app.include_router(customers_router)
app.include_router(accounts_router)
app.include_router(wealth_router)
app.include_router(loans_router)
app.include_router(repayments_router)
app.include_router(risk_router)
app.include_router(collections_router)
app.include_router(operations_router)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.middleware("http")
async def add_request_context_var(request: Request, call_next):
    request_id_ctx_var.set(str(uuid.uuid4()))
    return await call_next(request)


@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=fail(exc.code, exc.message, request.headers.get("X-Request-Id")),
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=fail(
            "VALIDATION_ERROR",
            str(exc),
            request.headers.get("X-Request-Id"),
        ),
    )


@app.exception_handler(ValueError)
async def handle_value_error(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content=fail("BAD_REQUEST", str(exc), request.headers.get("X-Request-Id")),
    )


@app.get("/health", summary="健康检查")
def health() -> dict[str, object]:
    return {"code": 0, "message": "ok", "request_id": None, "data": {"status": "ok"}}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=APP_PORT, reload=False)
