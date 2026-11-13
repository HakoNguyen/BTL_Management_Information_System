"""Mã cố định và hàm dựng dữ liệu dùng chung cho test (docs/tests.md mục 2).

Mỗi vòng nghiệp vụ thêm hàm dựng dữ liệu của mình vào đây (sản phẩm, tồn, đơn…), dùng lại các mã này
để test, dữ liệu demo và tài liệu khớp nhau.
"""

from __future__ import annotations

from datetime import date, time

import asyncpg
import httpx

from common.auth import hash_password
from common.constants import AccountStatus, EmployeeStatus, Role

TEST_SECRET = "khoa-bi-mat-chi-dung-cho-test"
TEST_PASSWORD = "mat-khau-test"
# Băm một lần cho cả phiên test: scrypt cố ý chậm
_TEST_PASSWORD_HASH = hash_password(TEST_PASSWORD)

BRANCH_1 = "CN1"
BRANCH_2 = "CN2"

# Mỗi vai trò một nhân viên mẫu; tên đăng nhập trùng mã nhân viên viết thường
HQ_ID = "NV-TS"
MANAGER_ID = "NV-QL1"
SALES_ID = "NV-BH1"
CASHIER_ID = "NV-TN1"
WAREHOUSE_ID = "NV-KHO1"


async def seed_branch(
    conn: asyncpg.Connection, branch_id: str = BRANCH_1, closing_time: time = time(22, 0)
) -> str:
    await conn.execute(
        "INSERT INTO branches (branch_id, name, closing_time) VALUES ($1, $2, $3)",
        branch_id,
        f"Chi nhánh {branch_id}",
        closing_time,
    )
    return branch_id


async def seed_employee(
    conn: asyncpg.Connection,
    employee_id: str,
    role: Role,
    branch_id: str | None = None,
    *,
    with_account: bool = True,
    account_status: AccountStatus = AccountStatus.ACTIVE,
    status: EmployeeStatus = EmployeeStatus.WORKING,
) -> str:
    """Tạo nhân viên; có tài khoản thì tên đăng nhập là mã viết thường, mật khẩu TEST_PASSWORD."""
    await conn.execute(
        "INSERT INTO employees (employee_id, full_name, role, branch_id, hired_on, status,"
        " username, password_hash, account_status) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)",
        employee_id,
        f"Nhân viên {employee_id}",
        role,
        branch_id,
        date(2026, 1, 1),
        status,
        employee_id.lower() if with_account else None,
        _TEST_PASSWORD_HASH if with_account else None,
        account_status if with_account else None,
    )
    return employee_id


async def login_as(client: httpx.AsyncClient, employee_id: str) -> dict[str, str]:
    """Đăng nhập bằng nhân viên đã seed; trả header Authorization để gắn vào các request sau."""
    response = await client.post(
        "/auth/login", json={"username": employee_id.lower(), "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}
