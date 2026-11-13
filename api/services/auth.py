"""Đăng nhập và tài khoản trụ sở đầu tiên.

Đăng nhập không thuộc 27 chức năng BFD; nó phục vụ nguyên tắc kiểm soát K-01.
"""

from __future__ import annotations

from typing import Any

import asyncpg

from common import clock
from common.auth import hash_password, verify_password
from common.constants import (
    BOOTSTRAP_ADMIN_ID,
    AccountStatus,
    EmployeeStatus,
    ErrorCode,
    Role,
)
from common.errors import AppError

_SESSION_COLUMNS = "employee_id, full_name, role, branch_id"
# Tên đăng nhập không tồn tại vẫn băm một lần, để thời gian phản hồi không lộ tên nào có thật
_DUMMY_HASH = hash_password("")


async def get_active_employee(conn: asyncpg.Connection, employee_id: str) -> dict[str, Any] | None:
    """Nhân viên Đang làm có tài khoản Hoạt động; khác thì None (K-01, NV-03)."""
    row = await conn.fetchrow(
        f"SELECT {_SESSION_COLUMNS} FROM employees"
        " WHERE employee_id = $1 AND status = $2 AND account_status = $3",
        employee_id,
        EmployeeStatus.WORKING,
        AccountStatus.ACTIVE,
    )
    return dict(row) if row else None


async def login(conn: asyncpg.Connection, username: str, password: str) -> dict[str, Any]:
    row = await conn.fetchrow(
        f"SELECT {_SESSION_COLUMNS}, password_hash, status, account_status"
        " FROM employees WHERE username = $1",
        username,
    )
    # shortcut: chưa giới hạn số lần thử đăng nhập; thêm khi hệ thống mở ra ngoài mạng nội bộ.
    password_ok = verify_password(password, row["password_hash"] if row else _DUMMY_HASH)
    # Cùng một thông báo cho sai tên và sai mật khẩu để không lộ tên đăng nhập nào tồn tại
    if row is None or not password_ok:
        raise AppError(ErrorCode.UNAUTHORIZED, "Sai tên đăng nhập hoặc mật khẩu")
    if row["account_status"] != AccountStatus.ACTIVE or row["status"] != EmployeeStatus.WORKING:
        raise AppError(ErrorCode.FORBIDDEN, "Tài khoản đang bị khóa", rule="K-01")
    return {key: row[key] for key in ("employee_id", "full_name", "role", "branch_id")}


async def ensure_bootstrap_admin(conn: asyncpg.Connection, username: str, password: str) -> None:
    """Chỉ trụ sở cấp được tài khoản (6.3), nên tài khoản trụ sở đầu tiên phải tạo lúc khởi động.

    Không làm gì nếu đã có nhân viên trụ sở. Từ vòng 1, mọi tài khoản khác do nhóm 6 tạo.
    """
    if await conn.fetchval("SELECT 1 FROM employees WHERE role = $1 LIMIT 1", Role.HQ):
        return
    await conn.execute(
        "INSERT INTO employees (employee_id, full_name, role, hired_on,"
        " username, password_hash, account_status) VALUES ($1, $2, $3, $4, $5, $6, $7)",
        BOOTSTRAP_ADMIN_ID,
        "Quản trị trụ sở",
        Role.HQ,
        clock.now().date(),
        username,
        hash_password(password),
        AccountStatus.ACTIVE,
    )
