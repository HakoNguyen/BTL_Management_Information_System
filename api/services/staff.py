"""Nhóm 6 – Nhân viên và chi nhánh (kho D6): chức năng 6.1 đến 6.4.

Mọi lệnh ghi vào `branches`, `employees` nằm ở file này (trừ `auth.ensure_bootstrap_admin`).
Đọc D3, D4, D5 chỉ để kiểm tra điều kiện NV-02, NV-03, NV-04.
"""

from __future__ import annotations

import secrets
from datetime import timedelta
from typing import Any

import asyncpg

from common import clock
from common.auth import hash_password
from common.constants import (
    RETURN_WINDOW_DAYS,
    AccountStatus,
    BranchStatus,
    EmployeeStatus,
    ErrorCode,
    OrderStatus,
    ReturnStatus,
    Role,
    ShiftStatus,
    SlipStatus,
    TxnStatus,
    TxnType,
)
from common.errors import AppError
from common.models import (
    AccountIssued,
    AssignmentRequest,
    Branch,
    BranchCreate,
    BranchUpdate,
    Employee,
    EmployeeCreate,
    EmployeeUpdate,
)

_BRANCH_COLUMNS = "branch_id, name, address, phone, closing_time, status"
_EMPLOYEE_COLUMNS = (
    "employee_id, full_name, phone, role, branch_id, hired_on, status, username, account_status"
)
_OPEN_ORDER_STATUSES = [OrderStatus.DRAFT, OrderStatus.AWAITING_PAYMENT]


async def _patch(
    conn: asyncpg.Connection, table: str, key: str, key_value: str, changes: dict[str, Any]
) -> asyncpg.Record:
    """UPDATE các cột trong `changes`; tên cột lấy từ trường của model, không từ giá trị gửi lên."""
    columns = _BRANCH_COLUMNS if table == "branches" else _EMPLOYEE_COLUMNS
    if changes:
        sets = ", ".join(f"{column} = ${i}" for i, column in enumerate(changes, start=2))
        sql = f"UPDATE {table} SET {sets} WHERE {key} = $1 RETURNING {columns}"
    else:
        sql = f"SELECT {columns} FROM {table} WHERE {key} = $1"
    row = await conn.fetchrow(sql, key_value, *changes.values())
    if row is None:
        raise AppError(ErrorCode.NOT_FOUND, f"Không tìm thấy {key_value}")
    return row


# ---------------------------------------------------------------- 6.4 Chi nhánh


async def list_branches(conn: asyncpg.Connection) -> list[Branch]:
    rows = await conn.fetch(f"SELECT {_BRANCH_COLUMNS} FROM branches ORDER BY branch_id")
    return [Branch(**row) for row in rows]


async def create_branch(conn: asyncpg.Connection, body: BranchCreate) -> Branch:
    row = await conn.fetchrow(
        "INSERT INTO branches (branch_id, name, address, phone, closing_time)"
        " VALUES ($1, $2, $3, $4, $5) ON CONFLICT (branch_id) DO NOTHING"
        f" RETURNING {_BRANCH_COLUMNS}",
        body.branch_id,
        body.name,
        body.address,
        body.phone,
        body.closing_time,
    )
    if row is None:
        raise AppError(ErrorCode.DUPLICATE, f"Mã chi nhánh {body.branch_id} đã có", rule="NV-04")
    return Branch(**row)


async def update_branch(conn: asyncpg.Connection, branch_id: str, body: BranchUpdate) -> Branch:
    # Mã chi nhánh không đổi (NV-04): BranchUpdate không có trường branch_id
    return Branch(
        **await _patch(
            conn, "branches", "branch_id", branch_id, body.model_dump(exclude_unset=True)
        )
    )


async def deactivate_branch(conn: asyncpg.Connection, branch_id: str) -> Branch:
    """NV-04: chỉ ngừng khi đủ mọi điều kiện; từ chối thì liệt kê mọi điều kiện chưa đạt."""
    async with conn.transaction():
        # Khóa dòng chi nhánh: tạo nhân viên, phân công vào chi nhánh đọc dòng này FOR SHARE
        status = await conn.fetchval(
            "SELECT status FROM branches WHERE branch_id = $1 FOR UPDATE", branch_id
        )
        if status is None:
            raise AppError(ErrorCode.NOT_FOUND, f"Không tìm thấy chi nhánh {branch_id}")
        if status != BranchStatus.ACTIVE:
            raise AppError(ErrorCode.INVALID_STATE, "Chi nhánh đã ngừng hoạt động")
        check = await conn.fetchrow(
            """
            SELECT
              EXISTS (SELECT 1 FROM stock WHERE branch_id = $1 AND quantity > 0) AS stock_left,
              EXISTS (SELECT 1 FROM shifts WHERE branch_id = $1 AND status <> $2) AS open_shift,
              EXISTS (SELECT 1 FROM orders WHERE branch_id = $1 AND status = ANY($3::text[]))
                AS open_order,
              EXISTS (SELECT 1 FROM stock_slips WHERE branch_id = $1 AND status = $4)
                AS pending_stock_slip,
              EXISTS (SELECT 1 FROM return_slips r JOIN orders o USING (order_id)
                      WHERE o.branch_id = $1 AND r.status = $5) AS pending_return,
              EXISTS (SELECT 1 FROM return_slips r JOIN orders o USING (order_id)
                      WHERE o.branch_id = $1 AND r.status = $6
                        AND NOT EXISTS (SELECT 1 FROM transactions t
                                        WHERE t.return_id = r.return_id
                                          AND t.type = $7 AND t.status = $8))
                AS unrefunded_return,
              (SELECT max(completed_at) FROM orders WHERE branch_id = $1) AS last_completed_at
            """,
            branch_id,
            ShiftStatus.SETTLED,
            _OPEN_ORDER_STATUSES,
            SlipStatus.PENDING,
            ReturnStatus.PENDING,
            ReturnStatus.APPROVED,
            TxnType.REFUND,
            TxnStatus.SUCCESS,
        )
        last = check["last_completed_at"]
        unmet = [
            message
            for failed, message in (
                (check["stock_left"], "còn tồn kho khác 0"),
                (check["open_shift"], "còn ca chưa chốt"),
                (check["open_order"], "còn đơn Đang lập hoặc Chờ thanh toán"),
                (check["pending_stock_slip"], "còn phiếu kho chờ xử lý"),
                (check["pending_return"], "còn phiếu trả chờ duyệt"),
                (check["unrefunded_return"], "còn phiếu trả Đã duyệt chưa hoàn tiền xong"),
                (
                    last is not None and clock.now() <= last + timedelta(days=RETURN_WINDOW_DAYS),
                    f"chưa quá {RETURN_WINDOW_DAYS} ngày kể từ đơn hoàn tất gần nhất",
                ),
            )
            if failed
        ]
        if unmet:
            raise AppError(
                ErrorCode.RULE_VIOLATION,
                "Chưa thể ngừng hoạt động chi nhánh: " + "; ".join(unmet),
                rule="NV-04",
            )
        row = await conn.fetchrow(
            f"UPDATE branches SET status = $2 WHERE branch_id = $1 AND status = $3"
            f" RETURNING {_BRANCH_COLUMNS}",
            branch_id,
            BranchStatus.INACTIVE,
            BranchStatus.ACTIVE,
        )
        if row is None:
            raise AppError(ErrorCode.INVALID_STATE, "Chi nhánh đã ngừng hoạt động")
        return Branch(**row)


# ---------------------------------------------------------------- 6.1 Hồ sơ nhân viên


async def _check_role_branch(conn: asyncpg.Connection, role: Role, branch_id: str | None) -> None:
    """NV-01: trụ sở không thuộc chi nhánh, nhân viên cửa hàng thuộc một chi nhánh Hoạt động."""
    if (role == Role.HQ) != (branch_id is None):
        raise AppError(
            ErrorCode.RULE_VIOLATION,
            "Nhân viên trụ sở không thuộc chi nhánh; nhân viên cửa hàng phải thuộc một chi nhánh",
            rule="NV-01",
        )
    if branch_id is None:
        return
    status = await conn.fetchval(
        "SELECT status FROM branches WHERE branch_id = $1 FOR SHARE", branch_id
    )
    if status is None:
        raise AppError(ErrorCode.NOT_FOUND, f"Không tìm thấy chi nhánh {branch_id}")
    if status != BranchStatus.ACTIVE:
        raise AppError(ErrorCode.RULE_VIOLATION, "Chi nhánh đã ngừng hoạt động", rule="NV-04")


async def _lock_employee(conn: asyncpg.Connection, employee_id: str) -> asyncpg.Record:
    row = await conn.fetchrow(
        f"SELECT {_EMPLOYEE_COLUMNS} FROM employees WHERE employee_id = $1 FOR UPDATE", employee_id
    )
    if row is None:
        raise AppError(ErrorCode.NOT_FOUND, f"Không tìm thấy nhân viên {employee_id}")
    return row


def _require_working(employee: asyncpg.Record, rule: str | None = None) -> None:
    if employee["status"] != EmployeeStatus.WORKING:
        raise AppError(ErrorCode.INVALID_STATE, "Nhân viên đã nghỉ", rule=rule)


async def list_employees(conn: asyncpg.Connection) -> list[Employee]:
    rows = await conn.fetch(f"SELECT {_EMPLOYEE_COLUMNS} FROM employees ORDER BY employee_id")
    return [Employee(**row) for row in rows]


async def create_employee(conn: asyncpg.Connection, body: EmployeeCreate) -> Employee:
    async with conn.transaction():
        await _check_role_branch(conn, body.role, body.branch_id)
        row = await conn.fetchrow(
            "INSERT INTO employees (employee_id, full_name, phone, role, branch_id, hired_on)"
            " VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT (employee_id) DO NOTHING"
            f" RETURNING {_EMPLOYEE_COLUMNS}",
            body.employee_id,
            body.full_name,
            body.phone,
            body.role,
            body.branch_id,
            body.hired_on,
        )
        if row is None:
            raise AppError(
                ErrorCode.DUPLICATE, f"Mã nhân viên {body.employee_id} đã có", rule="NV-01"
            )
        return Employee(**row)


async def update_employee(
    conn: asyncpg.Connection, employee_id: str, body: EmployeeUpdate
) -> Employee:
    changes = body.model_dump(exclude_unset=True)
    return Employee(**await _patch(conn, "employees", "employee_id", employee_id, changes))


async def leave_employee(conn: asyncpg.Connection, employee_id: str) -> Employee:
    """NV-03: chuyển Đã nghỉ khi tài khoản đã khóa (hoặc chưa cấp) và không còn ca chưa chốt."""
    async with conn.transaction():
        employee = await _lock_employee(conn, employee_id)
        _require_working(employee)
        if employee["account_status"] == AccountStatus.ACTIVE:
            raise AppError(
                ErrorCode.RULE_VIOLATION,
                "Phải khóa tài khoản trước khi chuyển nhân viên sang Đã nghỉ",
                rule="NV-03",
            )
        if await conn.fetchval(
            "SELECT 1 FROM shifts WHERE cashier_id = $1 AND status <> $2 LIMIT 1",
            employee_id,
            ShiftStatus.SETTLED,
        ):
            raise AppError(
                ErrorCode.RULE_VIOLATION, "Nhân viên còn ca thu ngân chưa chốt", rule="NV-03"
            )
        row = await conn.fetchrow(
            f"UPDATE employees SET status = $2 WHERE employee_id = $1 AND status = $3"
            f" RETURNING {_EMPLOYEE_COLUMNS}",
            employee_id,
            EmployeeStatus.LEFT,
            EmployeeStatus.WORKING,
        )
        if row is None:
            raise AppError(ErrorCode.INVALID_STATE, "Nhân viên đã nghỉ")
        return Employee(**row)


# ---------------------------------------------------------------- 6.2 Phân công


async def assign_employee(
    conn: asyncpg.Connection, employee_id: str, body: AssignmentRequest
) -> Employee:
    """NV-02: còn chứng từ chưa kết thúc do mình lập thì không đổi vai trò, chi nhánh.

    Chỉ sửa hồ sơ nhân viên; chứng từ cũ giữ chi nhánh và người lập gốc (K-05).
    """
    async with conn.transaction():
        employee = await _lock_employee(conn, employee_id)
        _require_working(employee)
        await _check_role_branch(conn, body.role, body.branch_id)
        blocking = await conn.fetch(
            """
            SELECT shift_id AS code FROM shifts WHERE cashier_id = $1 AND status <> $2
            UNION ALL
            SELECT order_id FROM orders WHERE created_by = $1 AND status = ANY($3::text[])
            UNION ALL
            SELECT return_id FROM return_slips WHERE created_by = $1 AND status = $4
            UNION ALL
            SELECT slip_id FROM stock_slips WHERE created_by = $1 AND status = $5
            ORDER BY code
            """,
            employee_id,
            ShiftStatus.SETTLED,
            _OPEN_ORDER_STATUSES,
            ReturnStatus.PENDING,
            SlipStatus.PENDING,
        )
        if blocking:
            codes = ", ".join(row["code"] for row in blocking)
            raise AppError(
                ErrorCode.RULE_VIOLATION,
                f"Nhân viên còn ca, đơn hoặc phiếu chưa kết thúc: {codes}",
                rule="NV-02",
            )
        row = await conn.fetchrow(
            "UPDATE employees SET role = $2, branch_id = $3 WHERE employee_id = $1 AND status = $4"
            f" RETURNING {_EMPLOYEE_COLUMNS}",
            employee_id,
            body.role,
            body.branch_id,
            EmployeeStatus.WORKING,
        )
        if row is None:
            raise AppError(ErrorCode.INVALID_STATE, "Nhân viên đã nghỉ")
        return Employee(**row)


# ---------------------------------------------------------------- 6.3 Tài khoản


async def issue_account(conn: asyncpg.Connection, employee_id: str, username: str) -> AccountIssued:
    """NV-03: cấp một lần; tên đăng nhập duy nhất, kể cả với người đã nghỉ (không tái sử dụng)."""
    async with conn.transaction():
        employee = await _lock_employee(conn, employee_id)
        _require_working(employee, rule="NV-03")
        if employee["username"] is not None:
            raise AppError(ErrorCode.INVALID_STATE, "Nhân viên đã được cấp tài khoản", rule="NV-03")
        password = secrets.token_urlsafe(12)  # 16 ký tự; trả một lần để trụ sở bàn giao
        try:
            result = await conn.execute(
                "UPDATE employees SET username = $2, password_hash = $3, account_status = $4"
                " WHERE employee_id = $1 AND username IS NULL",
                employee_id,
                username,
                hash_password(password),
                AccountStatus.ACTIVE,
            )
        except asyncpg.UniqueViolationError:
            raise AppError(
                ErrorCode.DUPLICATE, f"Tên đăng nhập {username} đã được dùng", rule="NV-03"
            ) from None
        if result != "UPDATE 1":
            raise AppError(ErrorCode.INVALID_STATE, "Nhân viên đã được cấp tài khoản", rule="NV-03")
    return AccountIssued(
        employee_id=employee_id,
        username=username,
        temporary_password=password,
        account_status=AccountStatus.ACTIVE,
    )


async def set_account_status(
    conn: asyncpg.Connection, employee_id: str, target: AccountStatus
) -> Employee:
    """Khóa hoặc mở khóa (NV-03). Khóa có hiệu lực ngay vì mỗi request đọc lại tài khoản (K-01)."""
    current = AccountStatus.LOCKED if target == AccountStatus.ACTIVE else AccountStatus.ACTIVE
    row = await conn.fetchrow(
        "UPDATE employees SET account_status = $2 WHERE employee_id = $1 AND account_status = $3"
        f" RETURNING {_EMPLOYEE_COLUMNS}",
        employee_id,
        target,
        current,
    )
    if row is not None:
        return Employee(**row)
    if await conn.fetchval("SELECT 1 FROM employees WHERE employee_id = $1", employee_id):
        raise AppError(ErrorCode.INVALID_STATE, "Tài khoản chưa được cấp hoặc đã ở trạng thái này")
    raise AppError(ErrorCode.NOT_FOUND, f"Không tìm thấy nhân viên {employee_id}")
