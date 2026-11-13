"""Nhóm 3 – Phiếu trả (kho D3, bảng `return_slips`, `return_slip_items`): phần phiếu trả của 3.4.

Mọi lệnh ghi vào `return_slips`, `return_slip_items` nằm ở file này. Duyệt phiếu làm trong một
transaction: phiếu Đã duyệt, `inventory.receive_return` (hàng tốt), `orders.mark_returned` (TH-05).
Giao dịch hoàn tiền thuộc D4, nằm ở `payments.py`.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import asyncpg

from common import clock
from common.constants import (
    OVERDUE_REJECT_REASON,
    RETURN_WINDOW_DAYS,
    BranchStatus,
    ErrorCode,
    OrderStatus,
    RefundStatus,
    ReturnStatus,
    Role,
    TxnStatus,
)
from common.errors import AppError
from common.models import CurrentUser, ReturnCreate, ReturnDecision, ReturnItem, ReturnSlip
from services import inventory, orders

_SELECT = "SELECT r.*, o.branch_id FROM return_slips r JOIN orders o USING (order_id)"


# ---------------------------------------------------------------- Đọc phiếu


def _refund_status(slip: asyncpg.Record, txn_statuses: set[str]) -> RefundStatus | None:
    """Dẫn xuất (db.md mục 6): Đã hoàn > Đang chờ kết quả > Chưa hoàn; chỉ với phiếu Đã duyệt."""
    if slip["status"] != ReturnStatus.APPROVED:
        return None
    if TxnStatus.SUCCESS in txn_statuses:
        return RefundStatus.REFUNDED
    if TxnStatus.PENDING in txn_statuses:
        return RefundStatus.PENDING
    return RefundStatus.NOT_REFUNDED


async def _load(conn: asyncpg.Connection, rows: list[asyncpg.Record]) -> list[ReturnSlip]:
    ids = [row["return_id"] for row in rows]
    items = await conn.fetch(
        "SELECT i.return_id, i.product_id, i.good_qty, i.defective_qty, oi.unit_price"
        " FROM return_slip_items i JOIN return_slips r USING (return_id)"
        " JOIN order_items oi ON oi.order_id = r.order_id AND oi.product_id = i.product_id"
        " WHERE i.return_id = ANY($1::text[]) ORDER BY i.product_id",
        ids,
    )
    txns = await conn.fetch(
        "SELECT return_id, status FROM transactions WHERE return_id = ANY($1::text[])", ids
    )
    by_slip: dict[str, list[ReturnItem]] = {}
    for item in items:
        by_slip.setdefault(item["return_id"], []).append(
            ReturnItem(
                product_id=item["product_id"],
                good_qty=item["good_qty"],
                defective_qty=item["defective_qty"],
                unit_price=item["unit_price"],
                amount=(item["good_qty"] + item["defective_qty"]) * item["unit_price"],
            )
        )
    statuses: dict[str, set[str]] = {}
    for txn in txns:
        statuses.setdefault(txn["return_id"], set()).add(txn["status"])
    result = []
    for row in rows:
        slip_items = by_slip.get(row["return_id"], [])
        result.append(
            ReturnSlip(
                **row,
                value=sum(item.amount for item in slip_items),  # TH-04
                refund_status=_refund_status(row, statuses.get(row["return_id"], set())),
                items=slip_items,
            )
        )
    return result


def _forbid_other_branch(branch_id: str, user: CurrentUser) -> None:
    """K-01: HQ thao tác mọi chi nhánh; vai trò khác chỉ chi nhánh mình."""
    if user.role != Role.HQ and branch_id != user.branch_id:
        raise AppError(ErrorCode.FORBIDDEN, "Phiếu trả thuộc chi nhánh khác", rule="K-01")


async def _owned(
    conn: asyncpg.Connection, return_id: str, user: CurrentUser, *, for_update: bool = False
) -> asyncpg.Record:
    lock = " FOR UPDATE OF r" if for_update else ""
    row = await conn.fetchrow(f"{_SELECT} WHERE r.return_id = $1{lock}", return_id)
    if row is None:
        raise AppError(ErrorCode.NOT_FOUND, f"Không tìm thấy phiếu trả {return_id}")
    _forbid_other_branch(row["branch_id"], user)
    return row


async def list_returns(
    conn: asyncpg.Connection,
    user: CurrentUser,
    status: ReturnStatus | None,
    refund_status: RefundStatus | None,
) -> list[ReturnSlip]:
    rows = await conn.fetch(
        f"{_SELECT} WHERE ($1::text IS NULL OR o.branch_id = $1)"
        " AND ($2::text IS NULL OR r.status = $2)"
        " ORDER BY r.created_at DESC, r.return_id DESC",
        None if user.role == Role.HQ else user.branch_id,
        status,
    )
    slips = await _load(conn, rows)
    # shortcut: lọc tình trạng hoàn sau khi tải; chuyển vào SQL khi danh sách phiếu lớn
    return [s for s in slips if refund_status is None or s.refund_status == refund_status]


async def get_return(conn: asyncpg.Connection, return_id: str, user: CurrentUser) -> ReturnSlip:
    return (await _load(conn, [await _owned(conn, return_id, user)]))[0]


async def slip_value(conn: asyncpg.Connection, return_id: str) -> int:
    """TH-04: Σ (tốt + lỗi) × đơn giá chốt trên đơn gốc; cho 3.4 hoàn tiền."""
    return await conn.fetchval(
        "SELECT sum((i.good_qty + i.defective_qty) * oi.unit_price)::bigint"
        " FROM return_slip_items i JOIN return_slips r USING (return_id)"
        " JOIN order_items oi ON oi.order_id = r.order_id AND oi.product_id = i.product_id"
        " WHERE i.return_id = $1",
        return_id,
    )


async def returns_of_customer(conn: asyncpg.Connection, customer_id: str) -> list[ReturnSlip]:
    """2.4: phiếu trả của các đơn của khách, mới nhất trước."""
    rows = await conn.fetch(
        f"{_SELECT} WHERE o.customer_id = $1 ORDER BY r.created_at DESC, r.return_id DESC",
        customer_id,
    )
    return await _load(conn, rows)


# ---------------------------------------------------------------- Lượng còn được trả (TH-02)


async def _remaining(
    conn: asyncpg.Connection,
    order_id: str,
    statuses: list[ReturnStatus],
    exclude: str | None = None,
) -> dict[str, int]:
    """Theo sản phẩm: lượng mua − lượng trên các phiếu ở `statuses` (trừ phiếu `exclude`)."""
    rows = await conn.fetch(
        "SELECT oi.product_id, oi.quantity - coalesce(sum(i.good_qty + i.defective_qty)"
        "   FILTER (WHERE r.status = ANY($2::text[]) AND r.return_id IS DISTINCT FROM $3), 0)"
        "   AS remaining"
        " FROM order_items oi"
        " LEFT JOIN return_slips r ON r.order_id = oi.order_id"
        " LEFT JOIN return_slip_items i ON i.return_id = r.return_id"
        "   AND i.product_id = oi.product_id"
        " WHERE oi.order_id = $1 GROUP BY oi.product_id, oi.quantity",
        order_id,
        statuses,
        exclude,
    )
    return {row["product_id"]: row["remaining"] for row in rows}


async def _check_quantities(
    conn: asyncpg.Connection, order_id: str, lines: dict[str, int], exclude: str | None = None
) -> None:
    """TH-02: sản phẩm có trong đơn gốc; lượng trả ≤ mua − đã trả (Đã duyệt) − Chờ duyệt khác."""
    remaining = await _remaining(
        conn, order_id, [ReturnStatus.APPROVED, ReturnStatus.PENDING], exclude
    )
    foreign = sorted(set(lines) - set(remaining))
    if foreign:
        raise AppError(
            ErrorCode.RULE_VIOLATION,
            f"Sản phẩm không có trong đơn gốc: {', '.join(foreign)}",
            rule="TH-02",
            details={"product_ids": foreign},
        )
    over = [
        {"product_id": pid, "requested": qty, "remaining": remaining[pid]}
        for pid, qty in sorted(lines.items())
        if qty > remaining[pid]
    ]
    if over:
        raise AppError(
            ErrorCode.RULE_VIOLATION,
            "Số lượng trả vượt lượng còn được trả",
            rule="TH-02",
            details={"lines": over},
        )


# ---------------------------------------------------------------- Lập phiếu (TH-01, TH-02)


async def create_return(
    conn: asyncpg.Connection, body: ReturnCreate, user: CurrentUser
) -> ReturnSlip:
    """TH-01: đơn Hoàn tất/Đã trả một phần, tại chi nhánh của đơn đang Hoạt động, trong 7 ngày.
    TH-02: dòng hợp lệ, không vượt lượng còn được trả. Phiếu Chờ duyệt, hàng vẫn do khách giữ."""
    at = clock.now()
    wanted = [item.product_id for item in body.items]
    if len(set(wanted)) != len(wanted):
        raise AppError(ErrorCode.VALIDATION_ERROR, "Mỗi sản phẩm chỉ ghi một dòng", rule="TH-02")
    if any(item.good_qty + item.defective_qty == 0 for item in body.items):
        raise AppError(
            ErrorCode.VALIDATION_ERROR, "Tổng số lượng tốt và lỗi phải lớn hơn 0", rule="TH-02"
        )
    async with conn.transaction():
        # khóa đơn: các phiếu trả của cùng đơn lập, duyệt lần lượt nên tổng lượng trả không vượt
        order = await conn.fetchrow(
            "SELECT o.branch_id, o.status, o.completed_at, b.status AS branch_status"
            " FROM orders o JOIN branches b USING (branch_id)"
            " WHERE o.order_id = $1 FOR UPDATE OF o",
            body.order_id,
        )
        if order is None:
            raise AppError(ErrorCode.NOT_FOUND, f"Không tìm thấy đơn {body.order_id}")
        _forbid_other_branch(order["branch_id"], user)
        if order["status"] not in (OrderStatus.COMPLETED, OrderStatus.PARTIALLY_RETURNED):
            raise AppError(
                ErrorCode.INVALID_STATE,
                "Chỉ nhận trả cho đơn Hoàn tất hoặc Đã trả một phần",
                rule="TH-01",
            )
        if order["branch_status"] != BranchStatus.ACTIVE:
            raise AppError(
                ErrorCode.RULE_VIOLATION, "Chi nhánh Ngừng hoạt động không nhận trả", rule="TH-01"
            )
        if at > order["completed_at"] + timedelta(days=RETURN_WINDOW_DAYS):
            raise AppError(
                ErrorCode.RULE_VIOLATION,
                f"Đã quá hạn trả hàng {RETURN_WINDOW_DAYS} ngày kể từ lúc hoàn tất",
                rule="TH-01",
            )
        await _check_quantities(
            conn,
            body.order_id,
            {item.product_id: item.good_qty + item.defective_qty for item in body.items},
        )
        return_id = await conn.fetchval(
            "INSERT INTO return_slips (order_id, created_by, created_at, reason)"
            " VALUES ($1, $2, $3, $4) RETURNING return_id",
            body.order_id,
            user.employee_id,
            at,
            body.reason,
        )
        await conn.executemany(
            "INSERT INTO return_slip_items (return_id, product_id, good_qty, defective_qty)"
            " VALUES ($1, $2, $3, $4)",
            [(return_id, i.product_id, i.good_qty, i.defective_qty) for i in body.items],
        )
    return await get_return(conn, return_id, user)


# ---------------------------------------------------------------- Duyệt, từ chối (TH-03, TH-05)


async def _pending_for_decision(
    conn: asyncpg.Connection, return_id: str, user: CurrentUser
) -> asyncpg.Record:
    """K-02: người quyết định khác người lập. TH-03: chỉ quyết định phiếu Chờ duyệt."""
    slip = await _owned(conn, return_id, user, for_update=True)
    if slip["created_by"] == user.employee_id:
        raise AppError(
            ErrorCode.FORBIDDEN, "Người lập phiếu không tự quyết định phiếu", rule="K-02"
        )
    if slip["status"] != ReturnStatus.PENDING:
        raise AppError(ErrorCode.INVALID_STATE, "Phiếu trả đã được quyết định", rule="TH-03")
    return slip


async def _decide(
    conn: asyncpg.Connection,
    return_id: str,
    status: ReturnStatus,
    note: str | None,
    user: CurrentUser,
) -> None:
    """Chỉ đi tới: Chờ duyệt sang Đã duyệt/Từ chối, ghi người, thời điểm, lý do (K-03)."""
    result = await conn.execute(
        "UPDATE return_slips SET status = $2, decided_by = $3, decided_at = $4,"
        " decision_note = $5 WHERE return_id = $1 AND status = $6",
        return_id,
        status,
        user.employee_id,
        clock.now(),
        note,
        ReturnStatus.PENDING,
    )
    if result != "UPDATE 1":
        raise AppError(ErrorCode.INVALID_STATE, "Phiếu trả vừa được quyết định", rule="TH-03")


def _note(decision: ReturnDecision) -> str | None:
    return (decision.decision_note or "").strip() or None


async def approve_return(
    conn: asyncpg.Connection, return_id: str, decision: ReturnDecision, user: CurrentUser
) -> ReturnSlip:
    """TH-03, TH-05: kiểm tra lại TH-02; hàng tốt nhập lại tồn đúng một lần; đơn Đã trả một phần
    hoặc toàn bộ. HQ duyệt thay phải ghi lý do (K-02)."""
    note = _note(decision)
    if user.role == Role.HQ and note is None:
        raise AppError(ErrorCode.VALIDATION_ERROR, "Trụ sở duyệt thay phải ghi lý do", rule="K-02")
    async with conn.transaction():
        # khóa đơn trước phiếu, cùng thứ tự với lập phiếu
        order_id = await conn.fetchval(
            "SELECT order_id FROM return_slips WHERE return_id = $1", return_id
        )
        if order_id is not None:
            await conn.execute("SELECT 1 FROM orders WHERE order_id = $1 FOR UPDATE", order_id)
        slip = await _pending_for_decision(conn, return_id, user)
        items = await conn.fetch(
            "SELECT product_id, good_qty, defective_qty FROM return_slip_items"
            " WHERE return_id = $1 ORDER BY product_id",
            return_id,
        )
        await _check_quantities(
            conn,
            order_id,
            {i["product_id"]: i["good_qty"] + i["defective_qty"] for i in items},
            exclude=return_id,
        )
        await _decide(conn, return_id, ReturnStatus.APPROVED, note, user)
        at = clock.now()
        await inventory.receive_return(
            conn,
            return_id,
            slip["branch_id"],
            [(i["product_id"], i["good_qty"]) for i in items if i["good_qty"] > 0],
            at,
        )
        remaining = await _remaining(conn, order_id, [ReturnStatus.APPROVED])
        await orders.mark_returned(conn, order_id, all(q == 0 for q in remaining.values()))
    return await get_return(conn, return_id, user)


async def reject_return(
    conn: asyncpg.Connection, return_id: str, decision: ReturnDecision, user: CurrentUser
) -> ReturnSlip:
    """TH-03: Từ chối không đổi tồn, đơn, tiền; K-03: bắt buộc lý do."""
    note = _note(decision)
    if note is None:
        raise AppError(ErrorCode.VALIDATION_ERROR, "Từ chối phải ghi lý do", rule="K-03")
    async with conn.transaction():
        await _pending_for_decision(conn, return_id, user)
        await _decide(conn, return_id, ReturnStatus.REJECTED, note, user)
    return await get_return(conn, return_id, user)


async def reject_overdue(
    conn: asyncpg.Connection, branch_id: str, closing_at: datetime, at: datetime
) -> list[str]:
    """TH-03: đến giờ đóng cửa, phiếu Chờ duyệt lập trước mốc tự Từ chối, lý do Quá hạn duyệt,
    người quyết định NULL (Hệ thống). Không đổi tồn, đơn, tiền."""
    rows = await conn.fetch(
        "UPDATE return_slips r SET status = $3, decided_by = NULL, decided_at = $4,"
        " decision_note = $5 FROM orders o"
        " WHERE o.order_id = r.order_id AND o.branch_id = $1 AND r.status = $6"
        " AND r.created_at <= $2 RETURNING r.return_id",
        branch_id,
        closing_at,
        ReturnStatus.REJECTED,
        at,
        OVERDUE_REJECT_REASON,
        ReturnStatus.PENDING,
    )
    return sorted(row["return_id"] for row in rows)
