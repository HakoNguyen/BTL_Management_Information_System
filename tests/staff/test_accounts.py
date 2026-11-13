"""6.3 Cấp và khóa tài khoản (NV-03, K-01). Không thuộc 16 tình huống KT."""

from __future__ import annotations

import asyncpg
import httpx
import pytest
from fixtures import (
    BRANCH_1,
    HQ_ID,
    SALES_ID,
    TEST_PASSWORD,
    login_as,
    seed_employee,
    seed_staff,
)

from common.constants import AccountStatus, EmployeeStatus, ErrorCode, Role

pytestmark = pytest.mark.db

NEW_ID = "NV-MOI"


@pytest.fixture
async def hq(client: httpx.AsyncClient, conn: asyncpg.Connection) -> dict[str, str]:
    await seed_staff(conn)
    await seed_employee(conn, NEW_ID, Role.SALES, BRANCH_1, with_account=False)
    return await login_as(client, HQ_ID)


async def _issue(
    client: httpx.AsyncClient, headers: dict[str, str], employee_id: str, username: str
) -> httpx.Response:
    return await client.post(
        f"/employees/{employee_id}/account", json={"username": username}, headers=headers
    )


async def _login(client: httpx.AsyncClient, username: str, password: str) -> httpx.Response:
    return await client.post("/auth/login", json={"username": username, "password": password})


async def _account(conn: asyncpg.Connection, employee_id: str) -> tuple[str | None, str | None]:
    row = await conn.fetchrow(
        "SELECT username, account_status FROM employees WHERE employee_id = $1", employee_id
    )
    return row["username"], row["account_status"]


async def test_issue_account(client: httpx.AsyncClient, hq: dict[str, str]) -> None:
    """6.3: sinh mật khẩu tạm, trả đúng một lần để bàn giao."""
    response = await _issue(client, hq, NEW_ID, "  lan.tran  ")
    assert response.status_code == 201
    body = response.json()
    password = body.pop("temporary_password")
    assert body == {
        "employee_id": NEW_ID,
        "username": "lan.tran",
        "account_status": AccountStatus.ACTIVE,
    }
    assert len(password) >= 12
    assert (await _login(client, "lan.tran", password)).status_code == 200

    listed = (await client.get("/employees", headers=hq)).json()
    row = next(row for row in listed if row["employee_id"] == NEW_ID)
    assert (row["username"], row["account_status"]) == ("lan.tran", AccountStatus.ACTIVE)
    assert password not in str(listed)


async def test_issue_twice(
    client: httpx.AsyncClient, conn: asyncpg.Connection, hq: dict[str, str]
) -> None:
    """NV-03: đã có tài khoản thì không cấp lại."""
    response = await _issue(client, hq, SALES_ID, "ten-khac")
    assert response.status_code == 409
    assert response.json()["error_code"] == ErrorCode.INVALID_STATE
    assert response.json()["details"]["rule"] == "NV-03"
    assert await _account(conn, SALES_ID) == (SALES_ID.lower(), AccountStatus.ACTIVE)


@pytest.mark.parametrize("taken", [SALES_ID.lower(), "nv-cu"])
async def test_username_unique(
    client: httpx.AsyncClient, conn: asyncpg.Connection, hq: dict[str, str], taken: str
) -> None:
    """NV-03: tên đăng nhập duy nhất, không tái sử dụng kể cả của người đã nghỉ."""
    await seed_employee(
        conn,
        "NV-CU",
        Role.SALES,
        BRANCH_1,
        account_status=AccountStatus.LOCKED,
        status=EmployeeStatus.LEFT,
    )
    response = await _issue(client, hq, NEW_ID, taken)
    assert response.status_code == 409
    assert response.json()["error_code"] == ErrorCode.DUPLICATE
    assert response.json()["details"]["rule"] == "NV-03"
    assert await _account(conn, NEW_ID) == (None, None)


async def test_issue_for_left_employee(
    client: httpx.AsyncClient, conn: asyncpg.Connection, hq: dict[str, str]
) -> None:
    """Nhân viên Đã nghỉ không được cấp tài khoản (quyết định vòng 1)."""
    await seed_employee(
        conn, "NV-CU", Role.SALES, BRANCH_1, with_account=False, status=EmployeeStatus.LEFT
    )
    response = await _issue(client, hq, "NV-CU", "nv-cu")
    assert response.status_code == 409
    assert response.json()["error_code"] == ErrorCode.INVALID_STATE
    assert await _account(conn, "NV-CU") == (None, None)


async def test_issue_invalid_input(client: httpx.AsyncClient, hq: dict[str, str]) -> None:
    assert (await _issue(client, hq, "NV-X", "ai-do")).status_code == 404
    blank = await _issue(client, hq, NEW_ID, "   ")
    assert blank.status_code == 400
    assert blank.json()["error_code"] == ErrorCode.VALIDATION_ERROR


async def test_lock_account(
    client: httpx.AsyncClient, conn: asyncpg.Connection, hq: dict[str, str]
) -> None:
    """NV-03, K-01: khóa thì mất phiên ngay, không đăng nhập được; dữ liệu giữ nguyên."""
    sales_headers = await login_as(client, SALES_ID)
    response = await client.post(f"/employees/{SALES_ID}/account/lock", headers=hq)
    assert response.status_code == 200
    assert response.json()["account_status"] == AccountStatus.LOCKED
    assert response.json()["status"] == EmployeeStatus.WORKING
    assert (await client.get("/auth/me", headers=sales_headers)).status_code == 401
    login = await _login(client, SALES_ID.lower(), TEST_PASSWORD)
    assert login.status_code == 403
    assert login.json()["details"]["rule"] == "K-01"
    assert await _account(conn, SALES_ID) == (SALES_ID.lower(), AccountStatus.LOCKED)


async def test_lock_invalid(client: httpx.AsyncClient, hq: dict[str, str]) -> None:
    assert (await client.post(f"/employees/{SALES_ID}/account/lock", headers=hq)).status_code == 200
    for employee_id in (SALES_ID, NEW_ID):  # đã khóa; chưa cấp tài khoản
        response = await client.post(f"/employees/{employee_id}/account/lock", headers=hq)
        assert response.status_code == 409
        assert response.json()["error_code"] == ErrorCode.INVALID_STATE
    assert (await client.post("/employees/NV-X/account/lock", headers=hq)).status_code == 404


async def test_unlock_account(client: httpx.AsyncClient, hq: dict[str, str]) -> None:
    await client.post(f"/employees/{SALES_ID}/account/lock", headers=hq)
    response = await client.post(f"/employees/{SALES_ID}/account/unlock", headers=hq)
    assert response.status_code == 200
    assert response.json()["account_status"] == AccountStatus.ACTIVE
    assert (await _login(client, SALES_ID.lower(), TEST_PASSWORD)).status_code == 200

    for employee_id in (SALES_ID, NEW_ID):  # đang hoạt động; chưa cấp tài khoản
        again = await client.post(f"/employees/{employee_id}/account/unlock", headers=hq)
        assert again.status_code == 409
        assert again.json()["error_code"] == ErrorCode.INVALID_STATE
