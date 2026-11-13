"""Nhóm 3 – Đơn hàng (kho D3): chức năng 3.1 và phần hủy đơn của 3.4; hàm giao `mark_completed`.

Mọi lệnh ghi vào `orders`, `order_items` nằm ở file này. Chốt đơn chỉ kiểm tra tồn khả dụng qua
`inventory.check_available`, không giữ hàng (BH-02); giữ hàng là việc của 3.2 (TT-03).
"""

from __future__ import annotations

from datetime import datetime

import asyncpg

from common import clock
from common.constants import (
    OVERDUE_CANCEL_REASON,
    BranchStatus,
    ErrorCode,
    OrderStatus,
    ProductStatus,
    Role,
)
from common.errors import AppError
from common.models import CurrentUser, Order, OrderCreate, OrderItem, OrderItemInput
from services import inventory, payments

# Tổng tiền đơn là dữ liệu dẫn xuất (BH-01): NULL khi Đang lập vì chưa có đơn giá chốt
_SELECT = """
    SELECT o.*, (SELECT sum(i.quantity * i.unit_price) FROM order_items i
                 WHERE i.order_id = o.order_id)::bigint AS total
    FROM orders o
"""


# ---------------------------------------------------------------- Đọc đơn


async def _load(conn: asyncpg.Connection, rows: list[asyncpg.Record]) -> list[Order]:
    items = await conn.fetch(
        "SELECT order_id, product_id, quantity, unit_price FROM order_items"
        " WHERE order_id = ANY($1::text[]) ORDER BY product_id",
        [row["order_id"] for row in rows],
    )
    by_order: dict[str, list[OrderItem]] = {}
    for item in items:
        by_order.setdefault(item["order_id"], []).append(
            OrderItem(
                product_id=item["product_id"],
                quantity=item["quantity"],
                unit_price=item["unit_price"],
            )
        )
    return [Order(**row, items=by_order.get(row["order_id"], [])) for row in rows]


async def _owned(
    conn: asyncpg.Connection,
    order_id: str,
    user: CurrentUser,
    rule: str | None = None,
    *,
    for_update: bool = False,
) -> asyncpg.Record:
    """K-01: đơn thuộc chi nhánh người gọi. Có `rule` thì NVBH chỉ thao tác đơn mình lập."""
    lock = " FOR UPDATE" if for_update else ""
    row = await conn.fetchrow(f"SELECT * FROM orders WHERE order_id = $1{lock}", order_id)
    if row is None:
        raise AppError(ErrorCode.NOT_FOUND, f"Không tìm thấy đơn {order_id}")
    if row["branch_id"] != user.branch_id:
        raise AppError(ErrorCode.FORBIDDEN, "Đơn thuộc chi nhánh khác", rule="K-01")
    if rule and user.role == Role.SALES and row["created_by"] != user.employee_id:
        raise AppError(ErrorCode.FORBIDDEN, "Chỉ người lập hoặc QL thao tác đơn này", rule=rule)
    return row


async def list_orders(
    conn: asyncpg.Connection, user: CurrentUser, status: OrderStatus | None
) -> list[Order]:
    rows = await conn.fetch(
        f"{_SELECT} WHERE o.branch_id = $1 AND ($2::text IS NULL OR o.status = $2)"
        " ORDER BY o.created_at DESC, o.order_id DESC",
        user.branch_id,
        status,
    )
    return await _load(conn, rows)


async def get_order(conn: asyncpg.Connection, order_id: str, user: CurrentUser) -> Order:
    await _owned(conn, order_id, user)
    return (await _load(conn, [await conn.fetchrow(f"{_SELECT} WHERE o.order_id = $1", order_id)]))[
        0
    ]


# ---------------------------------------------------------------- 3.1 Lập, sửa đơn Đang lập


async def _write_items(
    conn: asyncpg.Connection, order_id: str, items: list[OrderItemInput]
) -> None:
    """BH-01: mỗi sản phẩm một dòng, sản phẩm phải có trong danh mục; thay toàn bộ dòng của đơn."""
    wanted = [item.product_id for item in items]
    if len(set(wanted)) != len(wanted):
        raise AppError(ErrorCode.VALIDATION_ERROR, "Mỗi sản phẩm chỉ ghi một dòng", rule="BH-01")
    found = await conn.fetch(
        "SELECT product_id FROM products WHERE product_id = ANY($1::text[])", wanted
    )
    missing = sorted(set(wanted) - {row["product_id"] for row in found})
    if missing:
        raise AppError(ErrorCode.NOT_FOUND, f"Không tìm thấy sản phẩm {', '.join(missing)}")
    await conn.execute("DELETE FROM order_items WHERE order_id = $1", order_id)
    await conn.executemany(
        "INSERT INTO order_items (order_id, product_id, quantity) VALUES ($1, $2, $3)",
        [(order_id, item.product_id, item.quantity) for item in items],
    )


async def create_order(conn: asyncpg.Connection, body: OrderCreate, user: CurrentUser) -> Order:
    """BH-01: đơn Đang lập thuộc chi nhánh và người lập, đúng một mã khách."""
    async with conn.transaction():
        if not await conn.fetchval(
            "SELECT 1 FROM customers WHERE customer_id = $1", body.customer_id
        ):
            raise AppError(ErrorCode.NOT_FOUND, f"Không tìm thấy khách hàng {body.customer_id}")
        order_id = await conn.fetchval(
            "INSERT INTO orders (branch_id, customer_id, created_by, created_at)"
            " VALUES ($1, $2, $3, $4) RETURNING order_id",
            user.branch_id,
            body.customer_id,
            user.employee_id,
            clock.now(),
        )
        await _write_items(conn, order_id, body.items)
    return await get_order(conn, order_id, user)


async def update_items(
    conn: asyncpg.Connection, order_id: str, items: list[OrderItemInput], user: CurrentUser
) -> Order:
    """BH-03: chỉ sửa nội dung khi đơn Đang lập."""
    async with conn.transaction():
        row = await _owned(conn, order_id, user, "BH-03", for_update=True)
        if row["status"] != OrderStatus.DRAFT:
            raise AppError(ErrorCode.INVALID_STATE, "Chỉ sửa được đơn Đang lập", rule="BH-03")
        await _write_items(conn, order_id, items)
    return await get_order(conn, order_id, user)


# ---------------------------------------------------------------- 3.1 Chốt, mở lại


def _check_moved(result: str, order_id: str) -> None:
    """Trạng thái chỉ đi tới: UPDATE có điều kiện trạng thái liền trước phải trúng đúng một dòng."""
    if result != "UPDATE 1":
        raise AppError(ErrorCode.INVALID_STATE, f"Đơn {order_id} vừa đổi trạng thái")


async def confirm_order(conn: asyncpg.Connection, order_id: str, user: CurrentUser) -> Order:
    """BH-02: chi nhánh Hoạt động, sản phẩm Đang bán, đủ tồn khả dụng; chép giá hiện hành.
    Không đạt thì transaction hủy, đơn vẫn Đang lập. Chốt không giữ hàng."""
    async with conn.transaction():
        row = await _owned(conn, order_id, user, "BH-03", for_update=True)
        if row["status"] != OrderStatus.DRAFT:
            raise AppError(ErrorCode.INVALID_STATE, "Chỉ chốt được đơn Đang lập", rule="BH-02")
        branch_status = await conn.fetchval(
            "SELECT status FROM branches WHERE branch_id = $1", row["branch_id"]
        )
        if branch_status != BranchStatus.ACTIVE:
            raise AppError(
                ErrorCode.RULE_VIOLATION, "Chi nhánh Ngừng hoạt động không chốt đơn", rule="BH-02"
            )
        lines = await conn.fetch(
            "SELECT i.product_id, i.quantity, p.status FROM order_items i"
            " JOIN products p USING (product_id) WHERE i.order_id = $1 ORDER BY i.product_id",
            order_id,
        )
        stopped = [line["product_id"] for line in lines if line["status"] != ProductStatus.ON_SALE]
        if stopped:
            raise AppError(
                ErrorCode.RULE_VIOLATION,
                f"Sản phẩm đã ngừng bán: {', '.join(stopped)}",
                rule="BH-02",
                details={"product_ids": stopped},
            )
        short = await inventory.check_available(
            conn, row["branch_id"], [(line["product_id"], line["quantity"]) for line in lines]
        )
        if short:
            raise AppError(
                ErrorCode.INSUFFICIENT_STOCK,
                "Số lượng vượt tồn khả dụng",
                rule="BH-02",
                details={"lines": short},
            )
        await conn.execute(
            "UPDATE order_items i SET unit_price = p.current_price FROM products p"
            " WHERE i.order_id = $1 AND p.product_id = i.product_id",
            order_id,
        )
        result = await conn.execute(
            "UPDATE orders SET status = $2, confirmed_at = $3 WHERE order_id = $1 AND status = $4",
            order_id,
            OrderStatus.AWAITING_PAYMENT,
            clock.now(),
            OrderStatus.DRAFT,
        )
        _check_moved(result, order_id)
    return await get_order(conn, order_id, user)


async def reopen_order(conn: asyncpg.Connection, order_id: str, user: CurrentUser) -> Order:
    """BH-03: đơn Chờ thanh toán không có giao dịch Chờ kết quả về Đang lập; bỏ giá đã chốt."""
    async with conn.transaction():
        row = await _owned(conn, order_id, user, "BH-03", for_update=True)
        if row["status"] != OrderStatus.AWAITING_PAYMENT:
            raise AppError(
                ErrorCode.INVALID_STATE, "Chỉ mở lại được đơn Chờ thanh toán", rule="BH-03"
            )
        if await payments.has_pending_txn(conn, order_id):
            raise AppError(
                ErrorCode.INVALID_STATE, "Đơn đang có giao dịch Chờ kết quả", rule="BH-03"
            )
        result = await conn.execute(
            "UPDATE orders SET status = $2, confirmed_at = NULL"
            " WHERE order_id = $1 AND status = $3",
            order_id,
            OrderStatus.DRAFT,
            OrderStatus.AWAITING_PAYMENT,
        )
        _check_moved(result, order_id)
        await conn.execute("UPDATE order_items SET unit_price = NULL WHERE order_id = $1", order_id)
    return await get_order(conn, order_id, user)


# ---------------------------------------------------------------- 3.4 Hủy đơn


async def cancel_order(
    conn: asyncpg.Connection, order_id: str, reason: str, user: CurrentUser
) -> Order:
    """BH-04: chỉ hủy đơn Đang lập/Chờ thanh toán không có giao dịch Chờ kết quả; ghi người,
    thời điểm, lý do (K-03). Không đổi tồn, không phát sinh hoàn tiền."""
    async with conn.transaction():
        row = await _owned(conn, order_id, user, "BH-04", for_update=True)
        if row["status"] not in (OrderStatus.DRAFT, OrderStatus.AWAITING_PAYMENT):
            raise AppError(
                ErrorCode.INVALID_STATE,
                "Chỉ hủy được đơn Đang lập hoặc Chờ thanh toán",
                rule="BH-04",
            )
        if await payments.has_pending_txn(conn, order_id):
            raise AppError(
                ErrorCode.INVALID_STATE, "Đơn đang có giao dịch Chờ kết quả", rule="BH-04"
            )
        result = await conn.execute(
            "UPDATE orders SET status = $2, cancelled_at = $3, cancelled_by = $4,"
            " cancel_reason = $5 WHERE order_id = $1 AND status = $6",
            order_id,
            OrderStatus.CANCELLED,
            clock.now(),
            user.employee_id,
            reason,
            row["status"],
        )
        _check_moved(result, order_id)
    return await get_order(conn, order_id, user)


async def cancel_overdue(
    conn: asyncpg.Connection, branch_id: str, closing_at: datetime, at: datetime
) -> list[str]:
    """BH-05: đến giờ đóng cửa, Hệ thống (người hủy NULL) hủy đơn Đang lập/Chờ thanh toán lập
    trước mốc, lý do Quá hạn; đơn có giao dịch Chờ kết quả giữ nguyên để tra soát."""
    cancelled: list[str] = []
    async with conn.transaction():
        # khóa đơn như 3.2 để không lọt giao dịch vừa tạo giữa lúc kiểm tra và lúc hủy
        rows = await conn.fetch(
            "SELECT order_id, status FROM orders WHERE branch_id = $1"
            " AND status = ANY($2::text[]) AND created_at <= $3 ORDER BY order_id FOR UPDATE",
            branch_id,
            [OrderStatus.DRAFT, OrderStatus.AWAITING_PAYMENT],
            closing_at,
        )
        for row in rows:
            if await payments.has_pending_txn(conn, row["order_id"]):
                continue
            result = await conn.execute(
                "UPDATE orders SET status = $2, cancelled_at = $3, cancelled_by = NULL,"
                " cancel_reason = $4 WHERE order_id = $1 AND status = $5",
                row["order_id"],
                OrderStatus.CANCELLED,
                at,
                OVERDUE_CANCEL_REASON,
                row["status"],
            )
            _check_moved(result, row["order_id"])
            cancelled.append(row["order_id"])
    return cancelled


# ---------------------------------------------------------------- Hàm giao cho 3.2


async def mark_completed(conn: asyncpg.Connection, order_id: str, at: datetime) -> None:
    """3.2 thu Thành công: đơn Chờ thanh toán sang Hoàn tất, ghi thời điểm hoàn tất (TT-03)."""
    result = await conn.execute(
        "UPDATE orders SET status = $2, completed_at = $3 WHERE order_id = $1 AND status = $4",
        order_id,
        OrderStatus.COMPLETED,
        at,
        OrderStatus.AWAITING_PAYMENT,
    )
    _check_moved(result, order_id)


# ---------------------------------------------------------------- Hàm giao cho 3.4 trả hàng


async def mark_returned(conn: asyncpg.Connection, order_id: str, fully: bool) -> None:
    """3.4 phiếu trả Đã duyệt: đơn Đã trả toàn bộ nếu mọi dòng đã trả hết, ngược lại Đã trả một
    phần; giữ thời điểm hoàn tất (TH-05)."""
    current = await conn.fetchval("SELECT status FROM orders WHERE order_id = $1", order_id)
    if current not in (OrderStatus.COMPLETED, OrderStatus.PARTIALLY_RETURNED):
        raise AppError(ErrorCode.INVALID_STATE, f"Đơn {order_id} không nhận trả", rule="TH-05")
    result = await conn.execute(
        "UPDATE orders SET status = $2 WHERE order_id = $1 AND status = $3",
        order_id,
        OrderStatus.FULLY_RETURNED if fully else OrderStatus.PARTIALLY_RETURNED,
        current,
    )
    _check_moved(result, order_id)


async def completed_orders_of_customer(conn: asyncpg.Connection, customer_id: str) -> list[Order]:
    """2.4: các đơn từng Hoàn tất của khách (kể cả đã trả), mới nhất trước."""
    rows = await conn.fetch(
        f"{_SELECT} WHERE o.customer_id = $1 AND o.status = ANY($2::text[])"
        " ORDER BY o.completed_at DESC, o.order_id DESC",
        customer_id,
        [OrderStatus.COMPLETED, OrderStatus.PARTIALLY_RETURNED, OrderStatus.FULLY_RETURNED],
    )
    return await _load(conn, rows)
