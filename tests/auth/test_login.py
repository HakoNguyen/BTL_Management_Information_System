"""Đăng nhập, phiên và kiểm tra vai trò (K-01). Không thuộc 16 tình huống KT."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated

import asyncpg
import httpx
import pytest
from deps import require_role
from fastapi import Depends
from fixtures import (
    BRANCH_1,
    HQ_ID,
    SALES_ID,
    TEST_PASSWORD,
    login_as,
    seed_branch,
    seed_employee,
)
from services import auth as auth_service

from common import clock
from common.clock import VN_TZ
from common.constants import (
    BOOTSTRAP_ADMIN_ID,
    TOKEN_TTL_SECONDS,
    AccountStatus,
    EmployeeStatus,
    ErrorCode,
    Role,
)
from common.models import CurrentUser

pytestmark = pytest.mark.db


@pytest.fixture
async def staff(conn: asyncpg.Connection) -> None:
    await seed_branch(conn)
    await seed_employee(conn, HQ_ID, Role.HQ)
    await seed_employee(conn, SALES_ID, Role.SALES, BRANCH_1)


async def test_health(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_login_returns_token_and_session_info(client: httpx.AsyncClient, staff: None) -> None:
    response = await client.post(
        "/auth/login", json={"username": SALES_ID.lower(), "password": TEST_PASSWORD}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["user"] == {
        "employee_id": SALES_ID,
        "full_name": f"Nhân viên {SALES_ID}",
        "role": Role.SALES,
        "branch_id": BRANCH_1,
    }
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {body['token']}"})
    assert me.status_code == 200
    assert me.json() == body["user"]


@pytest.mark.parametrize(
    ("username", "password"), [(SALES_ID.lower(), "sai"), ("khong-ton-tai", TEST_PASSWORD)]
)
async def test_login_wrong_credentials(
    client: httpx.AsyncClient, staff: None, username: str, password: str
) -> None:
    response = await client.post("/auth/login", json={"username": username, "password": password})
    assert response.status_code == 401
    assert response.json()["error_code"] == ErrorCode.UNAUTHORIZED


async def test_login_validation_error_shape(client: httpx.AsyncClient) -> None:
    response = await client.post("/auth/login", json={"username": ""})
    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == ErrorCode.VALIDATION_ERROR
    assert set(body) == {"error_code", "message", "details"}


async def test_locked_account_cannot_login(
    client: httpx.AsyncClient, conn: asyncpg.Connection
) -> None:
    await seed_employee(conn, HQ_ID, Role.HQ, account_status=AccountStatus.LOCKED)
    response = await client.post(
        "/auth/login", json={"username": HQ_ID.lower(), "password": TEST_PASSWORD}
    )
    assert response.status_code == 403
    assert response.json()["details"]["rule"] == "K-01"


async def test_me_requires_valid_token(client: httpx.AsyncClient) -> None:
    for headers in ({}, {"Authorization": "Bearer rac"}, {"Authorization": "Basic abc"}):
        response = await client.get("/auth/me", headers=headers)
        assert response.status_code == 401
        assert response.json()["error_code"] == ErrorCode.UNAUTHORIZED


async def test_token_expires(client: httpx.AsyncClient, staff: None) -> None:
    start = datetime(2026, 11, 1, 8, 0, tzinfo=VN_TZ)
    clock.freeze(start)
    headers = await login_as(client, SALES_ID)
    clock.freeze(start + timedelta(seconds=TOKEN_TTL_SECONDS - 1))
    assert (await client.get("/auth/me", headers=headers)).status_code == 200
    clock.freeze(start + timedelta(seconds=TOKEN_TTL_SECONDS))
    assert (await client.get("/auth/me", headers=headers)).status_code == 401


@pytest.mark.parametrize(
    "lock_sql",
    [
        f"UPDATE employees SET account_status = '{AccountStatus.LOCKED}' WHERE employee_id = $1",
        f"UPDATE employees SET status = '{EmployeeStatus.LEFT}' WHERE employee_id = $1",
    ],
)
async def test_locking_account_revokes_existing_session(
    client: httpx.AsyncClient, conn: asyncpg.Connection, staff: None, lock_sql: str
) -> None:
    """K-01: tài khoản Bị khóa không thực hiện được thao tác nào, kể cả với token đã cấp."""
    headers = await login_as(client, SALES_ID)
    await conn.execute(lock_sql, SALES_ID)
    assert (await client.get("/auth/me", headers=headers)).status_code == 401


async def test_require_role_guards_by_role(app, client: httpx.AsyncClient, staff: None) -> None:  # type: ignore[no-untyped-def]
    @app.get("/_hq_only")
    async def hq_only(user: Annotated[CurrentUser, Depends(require_role(Role.HQ))]) -> str:
        return user.employee_id

    assert (await client.get("/_hq_only")).status_code == 401
    forbidden = await client.get("/_hq_only", headers=await login_as(client, SALES_ID))
    assert forbidden.status_code == 403
    assert forbidden.json()["error_code"] == ErrorCode.FORBIDDEN
    allowed = await client.get("/_hq_only", headers=await login_as(client, HQ_ID))
    assert allowed.status_code == 200
    assert allowed.json() == HQ_ID


async def test_bootstrap_admin_created_once(
    client: httpx.AsyncClient, conn: asyncpg.Connection
) -> None:
    await auth_service.ensure_bootstrap_admin(conn, "admin", "mat-khau-admin")
    # Lần hai, kể cả với thông tin khác, không tạo thêm và không đổi mật khẩu
    await auth_service.ensure_bootstrap_admin(conn, "admin2", "khac")
    rows = await conn.fetch("SELECT employee_id, username FROM employees")
    assert [(row["employee_id"], row["username"]) for row in rows] == [
        (BOOTSTRAP_ADMIN_ID, "admin")
    ]
    response = await client.post(
        "/auth/login", json={"username": "admin", "password": "mat-khau-admin"}
    )
    assert response.status_code == 200
    assert response.json()["user"]["role"] == Role.HQ
