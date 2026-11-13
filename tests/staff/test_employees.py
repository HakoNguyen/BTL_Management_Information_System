"""6.1 Cập nhật hồ sơ nhân viên (NV-01, NV-03, K-05). Không thuộc 16 tình huống KT."""

from __future__ import annotations

import asyncpg
import httpx
import pytest
from fixtures import (
    BRANCH_1,
    BRANCH_2,
    CASHIER_ID,
    HQ_ID,
    MANAGER_ID,
    SALES_ID,
    TEST_PASSWORD,
    login_as,
    seed_employee,
    seed_shift,
    seed_staff,
)

from common.constants import (
    AccountStatus,
    EmployeeStatus,
    ErrorCode,
    Role,
    ShiftStatus,
)

pytestmark = pytest.mark.db

EMPLOYEE_FIELDS = {
    "employee_id",
    "full_name",
    "phone",
    "role",
    "branch_id",
    "hired_on",
    "status",
    "username",
    "account_status",
}


@pytest.fixture
async def hq(client: httpx.AsyncClient, conn: asyncpg.Connection) -> dict[str, str]:
    await seed_staff(conn)
    return await login_as(client, HQ_ID)


def _new(role: Role = Role.SALES, branch_id: str | None = BRANCH_1) -> dict[str, object]:
    return {
        "employee_id": "NV-MOI",
        "full_name": "Trần Lan",
        "phone": "0901234567",
        "hired_on": "2026-11-01",
        "role": role,
        "branch_id": branch_id,
    }


async def _status(conn: asyncpg.Connection, employee_id: str) -> str:
    return await conn.fetchval("SELECT status FROM employees WHERE employee_id = $1", employee_id)


def _assert_rule(response: httpx.Response, status: int, code: ErrorCode, rule: str) -> None:
    assert response.status_code == status, response.text
    assert response.json()["error_code"] == code
    assert response.json()["details"]["rule"] == rule


@pytest.mark.parametrize(("role", "branch_id"), [(Role.SALES, BRANCH_1), (Role.HQ, None)])
async def test_create_employee(
    client: httpx.AsyncClient, hq: dict[str, str], role: Role, branch_id: str | None
) -> None:
    """NV-01: nhân viên cửa hàng thuộc một chi nhánh, trụ sở không thuộc chi nhánh."""
    response = await client.post("/employees", json=_new(role, branch_id), headers=hq)
    assert response.status_code == 201
    assert response.json() == {
        **_new(role, branch_id),
        "status": EmployeeStatus.WORKING,
        "username": None,
        "account_status": None,
    }


async def test_create_employee_without_branch_field(
    client: httpx.AsyncClient, hq: dict[str, str]
) -> None:
    body = _new(Role.HQ)
    del body["branch_id"]
    response = await client.post("/employees", json=body, headers=hq)
    assert response.status_code == 201
    assert response.json()["branch_id"] is None


async def test_create_duplicate_id(
    client: httpx.AsyncClient, conn: asyncpg.Connection, hq: dict[str, str]
) -> None:
    """NV-01: mã nhân viên duy nhất."""
    response = await client.post("/employees", json={**_new(), "employee_id": SALES_ID}, headers=hq)
    _assert_rule(response, 409, ErrorCode.DUPLICATE, "NV-01")
    name = await conn.fetchval("SELECT full_name FROM employees WHERE employee_id = $1", SALES_ID)
    assert name == f"Nhân viên {SALES_ID}"


@pytest.mark.parametrize(("role", "branch_id"), [(Role.HQ, BRANCH_1), (Role.SALES, None)])
async def test_create_role_branch_mismatch(
    client: httpx.AsyncClient, hq: dict[str, str], role: Role, branch_id: str | None
) -> None:
    """NV-01."""
    response = await client.post("/employees", json=_new(role, branch_id), headers=hq)
    _assert_rule(response, 422, ErrorCode.RULE_VIOLATION, "NV-01")


async def test_create_unknown_branch(client: httpx.AsyncClient, hq: dict[str, str]) -> None:
    response = await client.post("/employees", json=_new(branch_id="CN9"), headers=hq)
    assert response.status_code == 404
    assert response.json()["error_code"] == ErrorCode.NOT_FOUND


async def test_create_in_inactive_branch(
    client: httpx.AsyncClient, conn: asyncpg.Connection, hq: dict[str, str]
) -> None:
    """NV-04: chi nhánh Ngừng hoạt động không nhận nhân viên (quyết định vòng 1)."""
    assert (await client.post(f"/branches/{BRANCH_2}/deactivate", headers=hq)).status_code == 200
    response = await client.post("/employees", json=_new(branch_id=BRANCH_2), headers=hq)
    _assert_rule(response, 422, ErrorCode.RULE_VIOLATION, "NV-04")
    assert await conn.fetchval("SELECT count(*) FROM employees WHERE employee_id = 'NV-MOI'") == 0


async def test_list_employees(client: httpx.AsyncClient, hq: dict[str, str]) -> None:
    response = await client.get("/employees", headers=hq)
    assert response.status_code == 200
    rows = response.json()
    assert [row["employee_id"] for row in rows] == sorted(row["employee_id"] for row in rows)
    assert all(set(row) == EMPLOYEE_FIELDS for row in rows)
    sales = next(row for row in rows if row["employee_id"] == SALES_ID)
    assert sales["username"] == SALES_ID.lower()
    assert sales["account_status"] == AccountStatus.ACTIVE


async def test_update_profile(client: httpx.AsyncClient, hq: dict[str, str]) -> None:
    """6.1 chỉ sửa hồ sơ; vai trò, chi nhánh đổi qua 6.2."""
    body = {
        "full_name": "Tên mới",
        "phone": "0909",
        "hired_on": "2025-05-05",
        "role": Role.HQ,
        "branch_id": None,
    }
    response = await client.patch(f"/employees/{SALES_ID}", json=body, headers=hq)
    assert response.status_code == 200
    data = response.json()
    assert (data["full_name"], data["phone"], data["hired_on"]) == ("Tên mới", "0909", "2025-05-05")
    assert (data["role"], data["branch_id"]) == (Role.SALES, BRANCH_1)

    response = await client.patch(f"/employees/{SALES_ID}", json={"phone": None}, headers=hq)
    assert response.json()["phone"] is None
    assert response.json()["full_name"] == "Tên mới"

    assert (await client.patch("/employees/NV-X", json={}, headers=hq)).status_code == 404


async def test_leave(
    client: httpx.AsyncClient, conn: asyncpg.Connection, hq: dict[str, str]
) -> None:
    """NV-03: tài khoản đã khóa, không còn ca chưa chốt thì chuyển Đã nghỉ."""
    await seed_shift(conn, CASHIER_ID, status=ShiftStatus.SETTLED)
    lock = await client.post(f"/employees/{CASHIER_ID}/account/lock", headers=hq)
    assert lock.status_code == 200
    response = await client.post(f"/employees/{CASHIER_ID}/leave", headers=hq)
    assert response.status_code == 200
    assert response.json()["status"] == EmployeeStatus.LEFT
    assert await _status(conn, CASHIER_ID) == EmployeeStatus.LEFT
    login = await client.post(
        "/auth/login", json={"username": CASHIER_ID.lower(), "password": TEST_PASSWORD}
    )
    assert login.status_code == 403


async def test_leave_without_account(
    client: httpx.AsyncClient, conn: asyncpg.Connection, hq: dict[str, str]
) -> None:
    """NV-03: chưa từng có tài khoản thì không cần khóa (quyết định vòng 1)."""
    await seed_employee(conn, "NV-MOI", Role.SALES, BRANCH_1, with_account=False)
    response = await client.post("/employees/NV-MOI/leave", headers=hq)
    assert response.status_code == 200
    assert response.json()["status"] == EmployeeStatus.LEFT

    again = await client.post("/employees/NV-MOI/leave", headers=hq)
    assert again.status_code == 409
    assert again.json()["error_code"] == ErrorCode.INVALID_STATE
    assert (await client.post("/employees/NV-X/leave", headers=hq)).status_code == 404


async def test_leave_requires_locked_account(
    client: httpx.AsyncClient, conn: asyncpg.Connection, hq: dict[str, str]
) -> None:
    """NV-03."""
    response = await client.post(f"/employees/{SALES_ID}/leave", headers=hq)
    _assert_rule(response, 422, ErrorCode.RULE_VIOLATION, "NV-03")
    assert await _status(conn, SALES_ID) == EmployeeStatus.WORKING


@pytest.mark.parametrize("shift_status", [ShiftStatus.OPEN, ShiftStatus.AWAITING_CONFIRMATION])
async def test_leave_rejected_with_unsettled_shift(
    client: httpx.AsyncClient,
    conn: asyncpg.Connection,
    hq: dict[str, str],
    shift_status: ShiftStatus,
) -> None:
    """NV-03: còn ca chưa chốt thì chưa được nghỉ."""
    await seed_shift(conn, CASHIER_ID, status=shift_status)
    await client.post(f"/employees/{CASHIER_ID}/account/lock", headers=hq)
    response = await client.post(f"/employees/{CASHIER_ID}/leave", headers=hq)
    _assert_rule(response, 422, ErrorCode.RULE_VIOLATION, "NV-03")
    assert await _status(conn, CASHIER_ID) == EmployeeStatus.WORKING


ENDPOINTS = [
    ("GET", "/employees", None),
    ("POST", "/employees", _new()),
    ("PATCH", f"/employees/{SALES_ID}", {"full_name": "X"}),
    ("POST", f"/employees/{SALES_ID}/leave", None),
    ("PUT", f"/employees/{SALES_ID}/assignment", {"role": Role.SALES, "branch_id": BRANCH_2}),
    ("POST", f"/employees/{SALES_ID}/account", {"username": "moi"}),
    ("POST", f"/employees/{SALES_ID}/account/lock", None),
    ("POST", f"/employees/{SALES_ID}/account/unlock", None),
]


@pytest.mark.parametrize("caller", [MANAGER_ID, SALES_ID])
@pytest.mark.parametrize(("method", "path", "body"), ENDPOINTS)
async def test_employee_endpoints_require_hq(
    client: httpx.AsyncClient,
    hq: dict[str, str],
    caller: str,
    method: str,
    path: str,
    body: dict[str, object] | None,
) -> None:
    """K-01: chỉ Trụ sở dùng 6.1–6.3 (ma trận 2.2)."""
    headers = await login_as(client, caller)
    response = await client.request(method, path, json=body, headers=headers)
    assert response.status_code == 403
    assert response.json()["details"]["rule"] == "K-01"


async def test_employee_cannot_be_deleted(client: httpx.AsyncClient, hq: dict[str, str]) -> None:
    """NV-01, K-05: không có thao tác xóa nhân viên."""
    assert (await client.delete(f"/employees/{SALES_ID}", headers=hq)).status_code == 405
