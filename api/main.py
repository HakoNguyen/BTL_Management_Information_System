"""QLBH API: một ứng dụng FastAPI cho cả 6 nhóm chức năng (docs/api.md).

Chạy: uvicorn main:app (thư mục làm việc là api/, gốc repo nằm trong PYTHONPATH).
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI
from routers import auth, customers, products, staff
from services import auth as auth_service

from common.constants import (
    ENV_ADMIN_PASSWORD,
    ENV_ADMIN_USERNAME,
    ENV_DB_URL,
    ENV_SECRET_KEY,
)
from common.errors import install_error_handlers
from common.models import HealthResponse
from db.migrate import migrate

log = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    state = app.state
    state.secret_key = os.environ[ENV_SECRET_KEY]
    state.pool = await asyncpg.create_pool(os.environ[ENV_DB_URL])
    async with state.pool.acquire() as conn:
        applied = await migrate(conn)
        if applied:
            log.info("Đã áp dụng migration: %s", applied)
        await auth_service.ensure_bootstrap_admin(
            conn, os.environ[ENV_ADMIN_USERNAME], os.environ[ENV_ADMIN_PASSWORD]
        )
    try:
        yield
    finally:
        await state.pool.close()


def create_app() -> FastAPI:
    app = FastAPI(title="QLBH API", lifespan=lifespan)
    install_error_handlers(app)

    @app.get("/health")
    async def health() -> HealthResponse:
        return HealthResponse(status="ok")

    # Mỗi vòng nghiệp vụ đăng ký router của mình bằng một dòng (docs/plan.md)
    app.include_router(auth.router)
    app.include_router(staff.router)
    app.include_router(products.router)
    app.include_router(customers.router)
    return app


app = create_app()
