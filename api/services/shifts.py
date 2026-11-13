"""Nhóm 3 – Ca thu ngân (kho D4, bảng `shifts`): chức năng 3.5, quy tắc CA-01 đến CA-04.

Mọi lệnh ghi vào `shifts` nằm ở file này. Tiền mặt kỳ vọng, chênh lệch và kết quả đối soát là dữ
liệu dẫn xuất (docs/db.md mục 6), tính từ `transactions` mỗi lần đọc.
"""

from __future__ import annotations

import asyncpg

from common import clock
from common.constants import (
    BranchStatus,
    EmployeeStatus,
    ErrorCode,
    Role,
    ShiftStatus,
    TxnMethod,
    TxnStatus,
    TxnType,
)
from common.errors import AppError
from common.models import (
    CurrentUser,
    Shift,
    ShiftClose,
    ShiftDetail,
    ShiftMethodTotal,
    ShiftOpen,
    ShiftProxyClose,
    Transaction,
)

# CA-02: tiền mặt kỳ vọng = đầu ca + Σ thu tiền mặt Thành công − Σ hoàn tiền mặt Thành công.
# $1..$4 luôn là CASH, SUCCESS, COLLECT, REFUND; tham số lọc bắt đầu từ $5.
_SELECT = """
    SELECT s.*, c.cash_collected, c.cash_refunded,
           s.opening_cash + c.cash_collected - c.cash_refunded AS expected_cash,
           s.counted_cash - (s.opening_cash + c.cash_collected - c.cash_refunded) AS variance
    FROM shifts s CROSS JOIN LATERAL (
        SELECT coalesce(sum(t.amount) FILTER (WHERE t.type = $3), 0)::bigint AS cash_collected,
               coalesce(sum(t.amount) FILTER (WHERE t.type = $4), 0)::bigint AS cash_refunded
        FROM transactions t
        WHERE t.shift_id = s.shift_id AND t.method = $1 AND t.status = $2
    ) c
"""
_CASH_ARGS = (TxnMethod.CASH, TxnStatus.SUCCESS, TxnType.COLLECT, TxnType.REFUND)


# ---------------------------------------------------------------- Đọc ca


async def _fetch(conn: asyncpg.Connection, where: str, *args: object) -> list[asyncpg.Record]:
    return await conn.fetch(f"{_SELECT} WHERE {where}", *_CASH_ARGS, *args)


async def _detail(conn: asyncpg.Connection, shift_id: str) -> ShiftDetail:
    """CA-03: kết quả đối soát gồm tiền mặt, điện tử theo phương thức, Thất bại, Chờ kết quả."""
    (row,) = await _fetch(conn, "s.shift_id = $5", shift_id)
    electronic = await conn.fetch(
        "SELECT type, method, count(*) AS count, sum(amount)::bigint AS amount FROM transactions"
        " WHERE shift_id = $1 AND method <> $2 AND status = $3"
        " GROUP BY type, method ORDER BY type, method",
        shift_id,
        TxnMethod.CASH,
        TxnStatus.SUCCESS,
    )
    txns = await conn.fetch(
        "SELECT * FROM transactions WHERE shift_id = $1 AND status <> $2 ORDER BY txn_id",
        shift_id,
        TxnStatus.SUCCESS,
    )
    return ShiftDetail(
        **row,
        electronic=[ShiftMethodTotal(**r) for r in electronic],
        failed=[Transaction(**t) for t in txns if t["status"] == TxnStatus.FAILED],
        pending=[Transaction(**t) for t in txns if t["status"] == TxnStatus.PENDING],
    )


async def _locked(conn: asyncpg.Connection, shift_id: str) -> asyncpg.Record:
    row = await conn.fetchrow("SELECT * FROM shifts WHERE shift_id = $1 FOR UPDATE", shift_id)
    if row is None:
        raise AppError(ErrorCode.NOT_FOUND, f"Không tìm thấy ca {shift_id}")
    return row


def _check_visible(row: asyncpg.Record, user: CurrentUser) -> None:
    """K-01: TN chỉ ca của mình, QL ca của chi nhánh mình, HQ mọi ca."""
    allowed = (
        user.role == Role.HQ
        or (user.role == Role.MANAGER and row["branch_id"] == user.branch_id)
        or (user.role == Role.CASHIER and row["cashier_id"] == user.employee_id)
    )
    if not allowed:
        raise AppError(ErrorCode.FORBIDDEN, "Không được thao tác ca này", rule="K-01")


async def list_shifts(
    conn: asyncpg.Connection, user: CurrentUser, status: ShiftStatus | None
) -> list[Shift]:
    branch_id = user.branch_id if user.role == Role.MANAGER else None
    cashier_id = user.employee_id if user.role == Role.CASHIER else None
    rows = await _fetch(
        conn,
        "($5::text IS NULL OR s.branch_id = $5) AND ($6::text IS NULL OR s.cashier_id = $6)"
        " AND ($7::text IS NULL OR s.status = $7) ORDER BY s.opened_at DESC, s.shift_id DESC",
        branch_id,
        cashier_id,
        status,
    )
    return [Shift(**row) for row in rows]


async def get_shift(conn: asyncpg.Connection, shift_id: str, user: CurrentUser) -> ShiftDetail:
    row = await conn.fetchrow("SELECT * FROM shifts WHERE shift_id = $1", shift_id)
    if row is None:
        raise AppError(ErrorCode.NOT_FOUND, f"Không tìm thấy ca {shift_id}")
    _check_visible(row, user)
    return await _detail(conn, shift_id)


async def current_shift(conn: asyncpg.Connection, user: CurrentUser) -> ShiftDetail | None:
    shift_id = await conn.fetchval(
        "SELECT shift_id FROM shifts WHERE cashier_id = $1 AND status = $2",
        user.employee_id,
        ShiftStatus.OPEN,
    )
    return await _detail(conn, shift_id) if shift_id else None


# ---------------------------------------------------------------- CA-01 Mở ca


async def open_shift(conn: asyncpg.Connection, body: ShiftOpen, user: CurrentUser) -> ShiftDetail:
    """CA-01: tiền đầu ca ≥ 0, chi nhánh Hoạt động, tối đa một ca Đang mở; ca gắn cố định thu ngân
    và chi nhánh lúc mở."""
    if body.opening_cash < 0:
        raise AppError(ErrorCode.VALIDATION_ERROR, "Tiền đầu ca không được âm", rule="CA-01")
    async with conn.transaction():
        branch_status = await conn.fetchval(
            "SELECT status FROM branches WHERE branch_id = $1", user.branch_id
        )
        if branch_status != BranchStatus.ACTIVE:
            raise AppError(
                ErrorCode.RULE_VIOLATION, "Chi nhánh Ngừng hoạt động không mở ca", rule="CA-01"
            )
        try:
            shift_id = await conn.fetchval(
                "INSERT INTO shifts (branch_id, cashier_id, opened_at, opening_cash)"
                " VALUES ($1, $2, $3, $4) RETURNING shift_id",
                user.branch_id,
                user.employee_id,
                clock.now(),
                body.opening_cash,
            )
        except asyncpg.UniqueViolationError:  # shifts_one_open_per_cashier
            raise AppError(
                ErrorCode.INVALID_STATE, "Thu ngân đang có một ca Đang mở", rule="CA-01"
            ) from None
    return await _detail(conn, shift_id)


# ---------------------------------------------------------------- CA-02, CA-04 Đóng ca


async def _close(
    conn: asyncpg.Connection,
    row: asyncpg.Record,
    body: ShiftClose,
    proxy: tuple[str, str, str] | None = None,
) -> ShiftDetail:
    """CA-02: ca Đang mở, không còn giao dịch tiền mặt Chờ kết quả; chênh lệch khác 0 phải có lý do.
    `proxy` = (người đóng thay, người làm chứng, lý do) theo CA-04."""
    shift_id = row["shift_id"]
    if row["status"] != ShiftStatus.OPEN:
        raise AppError(ErrorCode.INVALID_STATE, "Chỉ đóng được ca Đang mở", rule="CA-02")
    if body.counted_cash < 0:
        raise AppError(ErrorCode.VALIDATION_ERROR, "Tiền kiểm đếm không được âm", rule="CA-02")
    if await conn.fetchval(
        "SELECT 1 FROM transactions WHERE shift_id = $1 AND method = $2 AND status = $3",
        shift_id,
        TxnMethod.CASH,
        TxnStatus.PENDING,
    ):
        raise AppError(
            ErrorCode.RULE_VIOLATION, "Ca còn giao dịch tiền mặt Chờ kết quả", rule="CA-02"
        )
    (current,) = await _fetch(conn, "s.shift_id = $5", shift_id)
    reason = (body.variance_reason or "").strip() or None
    if body.counted_cash != current["expected_cash"] and reason is None:
        raise AppError(ErrorCode.RULE_VIOLATION, "Chênh lệch khác 0 phải nhập lý do", rule="CA-02")
    proxy_by, witness_id, proxy_reason = proxy or (None, None, None)
    result = await conn.execute(
        "UPDATE shifts SET status = $2, closed_at = $3, counted_cash = $4, variance_reason = $5,"
        " proxy_closed_by = $6, witness_id = $7, proxy_reason = $8"
        " WHERE shift_id = $1 AND status = $9",
        shift_id,
        ShiftStatus.AWAITING_CONFIRMATION,
        clock.now(),
        body.counted_cash,
        reason,
        proxy_by,
        witness_id,
        proxy_reason,
        ShiftStatus.OPEN,
    )
    if result != "UPDATE 1":
        raise AppError(ErrorCode.INVALID_STATE, f"Ca {shift_id} vừa đổi trạng thái", rule="CA-02")
    return await _detail(conn, shift_id)


async def close_shift(
    conn: asyncpg.Connection, shift_id: str, body: ShiftClose, user: CurrentUser
) -> ShiftDetail:
    async with conn.transaction():
        row = await _locked(conn, shift_id)
        if row["cashier_id"] != user.employee_id:
            raise AppError(ErrorCode.FORBIDDEN, "Chỉ thu ngân của ca được đóng ca", rule="K-01")
        return await _close(conn, row, body)


async def proxy_close(
    conn: asyncpg.Connection, shift_id: str, body: ShiftProxyClose, user: CurrentUser
) -> ShiftDetail:
    """CA-04: QL chi nhánh đóng thay cùng một nhân viên làm chứng Đang làm cùng chi nhánh, khác QL
    và khác thu ngân của ca (giả định đã duyệt, docs/plan.md mục 7)."""
    async with conn.transaction():
        row = await _locked(conn, shift_id)
        _check_visible(row, user)
        witness_ok = body.witness_id not in (user.employee_id, row["cashier_id"]) and (
            await conn.fetchval(
                "SELECT 1 FROM employees WHERE employee_id = $1 AND branch_id = $2 AND status = $3",
                body.witness_id,
                row["branch_id"],
                EmployeeStatus.WORKING,
            )
        )
        if not witness_ok:
            raise AppError(
                ErrorCode.RULE_VIOLATION,
                "Người làm chứng phải là nhân viên Đang làm cùng chi nhánh, khác QL và thu ngân",
                rule="CA-04",
            )
        return await _close(conn, row, body, (user.employee_id, body.witness_id, body.proxy_reason))


# ---------------------------------------------------------------- CA-03 Xác nhận chốt


async def confirm_shift(conn: asyncpg.Connection, shift_id: str, user: CurrentUser) -> ShiftDetail:
    """CA-03: ca Chờ xác nhận, không còn giao dịch Chờ kết quả. Ca thu ngân tự đóng do QL chi nhánh
    xác nhận; ca QL đóng thay chỉ trụ sở xác nhận (CA-04, K-02)."""
    async with conn.transaction():
        row = await _locked(conn, shift_id)
        _check_visible(row, user)
        if row["status"] != ShiftStatus.AWAITING_CONFIRMATION:
            raise AppError(
                ErrorCode.INVALID_STATE, "Chỉ xác nhận được ca Chờ xác nhận", rule="CA-03"
            )
        if row["proxy_closed_by"] and user.role != Role.HQ:
            raise AppError(
                ErrorCode.FORBIDDEN, "Ca do QL đóng thay phải do trụ sở xác nhận", rule="CA-04"
            )
        if not row["proxy_closed_by"] and user.role == Role.HQ:
            raise AppError(
                ErrorCode.FORBIDDEN, "Ca thu ngân tự đóng do QL chi nhánh xác nhận", rule="K-02"
            )
        if await conn.fetchval(
            "SELECT 1 FROM transactions WHERE shift_id = $1 AND status = $2",
            shift_id,
            TxnStatus.PENDING,
        ):
            raise AppError(ErrorCode.RULE_VIOLATION, "Ca còn giao dịch Chờ kết quả", rule="CA-03")
        result = await conn.execute(
            "UPDATE shifts SET status = $2, settled_at = $3, confirmed_by = $4"
            " WHERE shift_id = $1 AND status = $5",
            shift_id,
            ShiftStatus.SETTLED,
            clock.now(),
            user.employee_id,
            ShiftStatus.AWAITING_CONFIRMATION,
        )
        if result != "UPDATE 1":
            raise AppError(ErrorCode.INVALID_STATE, f"Ca {shift_id} vừa đổi trạng thái")
    return await _detail(conn, shift_id)
