"""Nhóm 4 – Tồn kho (kho D5): chức năng 4.1 đến 4.5 và năm hàm giao cho nhóm 3.

Mọi lệnh ghi vào `stock`, `stock_slips`, `stock_slip_items`, `replenishment_requests`,
`replenishment_request_items` nằm ở file này (TK-01).
Trước khi tính tồn khả dụng để giữ hàng: khóa dòng `stock` bằng `SELECT … FOR UPDATE` theo
`product_id` tăng dần, để hai giao dịch tranh cùng hàng không cùng qua được (TK-03, KT-06).
Hàm giao (`docs/api.md` mục 5) chạy trong transaction của bên gọi; hàm cho router tự mở transaction.
"""

from __future__ import annotations

from datetime import datetime

import asyncpg

from common import clock
from common.constants import BranchStatus, ErrorCode, ProductStatus, SlipStatus, SlipType
from common.errors import AppError
from common.models import (
    CurrentUser,
    InboundSlipCreate,
    ReplenishmentCreate,
    ReplenishmentRequest,
    StockLevel,
    StockSlip,
    StockSlipCreate,
    StockSlipItem,
)

Lines = list[tuple[str, int]]  # (product_id, quantity)

# Phiếu xuất giữ hàng khi Chờ xử lý, trừ tồn khi Đã ghi nhận (TK-03)
OUT_TYPES = (
    SlipType.OUT_SALE,
    SlipType.OUT_DISPOSAL,
    SlipType.OUT_TO_WAREHOUSE,
    SlipType.ADJUST_DOWN,
)
# Phiếu NV kho lập, QL duyệt (TK-03, TK-04)
APPROVAL_TYPES = (
    SlipType.ADJUST_UP,
    SlipType.OUT_DISPOSAL,
    SlipType.OUT_TO_WAREHOUSE,
    SlipType.ADJUST_DOWN,
)

# Tồn khả dụng = tồn − Σ phiếu xuất Chờ xử lý cùng chi nhánh, sản phẩm (TK-01, dẫn xuất)
_AVAILABLE = f"""
    COALESCE(s.quantity, 0) - COALESCE((
        SELECT sum(i.quantity) FROM stock_slip_items i JOIN stock_slips k USING (slip_id)
        WHERE k.branch_id = $1 AND i.product_id = p.product_id
          AND k.status = '{SlipStatus.PENDING}' AND k.type = ANY($2::text[])
    ), 0)
"""
_LEVEL = f"""
    SELECT p.product_id, COALESCE(s.quantity, 0) AS quantity, {_AVAILABLE} AS available,
           s.min_level
    FROM products p LEFT JOIN stock s ON s.product_id = p.product_id AND s.branch_id = $1
"""


def _out_types() -> list[str]:
    return [str(t) for t in OUT_TYPES]


# ---------------------------------------------------------------- 4.1 Tồn, tồn khả dụng


async def list_stock(conn: asyncpg.Connection, branch_id: str) -> list[StockLevel]:
    rows = await conn.fetch(f"{_LEVEL} ORDER BY p.product_id", branch_id, _out_types())
    return [StockLevel(**row) for row in rows]


async def _shortages(conn: asyncpg.Connection, branch_id: str, lines: Lines) -> list[dict]:
    rows = await conn.fetch(
        f"{_LEVEL} WHERE p.product_id = ANY($3::text[])",
        branch_id,
        _out_types(),
        [product_id for product_id, _ in lines],
    )
    available = {row["product_id"]: row["available"] for row in rows}
    return [
        {"product_id": product_id, "quantity": quantity, "available": available.get(product_id, 0)}
        for product_id, quantity in sorted(lines)
        if quantity > available.get(product_id, 0)
    ]


async def check_available(conn: asyncpg.Connection, branch_id: str, lines: Lines) -> list[dict]:
    """Hàm giao cho 3.1: các dòng thiếu kèm tồn khả dụng; không giữ hàng."""
    return await _shortages(conn, branch_id, lines)


async def _lock_and_check(conn: asyncpg.Connection, branch_id: str, lines: Lines) -> None:
    """TK-03: khóa dòng stock theo mã sản phẩm rồi mới tính; vượt tồn khả dụng thì ném lỗi."""
    await conn.execute(
        "SELECT 1 FROM stock WHERE branch_id = $1 AND product_id = ANY($2::text[])"
        " ORDER BY product_id FOR UPDATE",
        branch_id,
        [product_id for product_id, _ in lines],
    )
    short = await _shortages(conn, branch_id, lines)
    if short:
        raise AppError(
            ErrorCode.INSUFFICIENT_STOCK,
            "Số lượng vượt tồn khả dụng",
            rule="TK-03",
            details={"lines": short},
        )


# ---------------------------------------------------------------- Ghi phiếu, cập nhật tồn


async def _insert_slip(
    conn: asyncpg.Connection,
    branch_id: str,
    type_: SlipType,
    status: SlipStatus,
    at: datetime,
    lines: Lines,
    **columns: str | None,
) -> str:
    # tên cột lấy từ tham số trong code, không từ dữ liệu gửi lên
    names = ["branch_id", "type", "status", "created_at", "finalized_at", *columns]
    values = [branch_id, type_, status, at, None if status == SlipStatus.PENDING else at]
    values += list(columns.values())
    marks = ", ".join(f"${i}" for i in range(1, len(names) + 1))
    slip_id = await conn.fetchval(
        f"INSERT INTO stock_slips ({', '.join(names)}) VALUES ({marks}) RETURNING slip_id", *values
    )
    await conn.executemany(
        "INSERT INTO stock_slip_items (slip_id, product_id, quantity) VALUES ($1, $2, $3)",
        [(slip_id, product_id, quantity) for product_id, quantity in sorted(lines)],
    )
    return slip_id


async def _apply(conn: asyncpg.Connection, slip_id: str, branch_id: str, type_: str) -> None:
    """TK-01: tồn chỉ đổi khi phiếu sang Đã ghi nhận; khóa theo thứ tự mã sản phẩm."""
    if type_ in OUT_TYPES:
        # hàng đã được giữ khi lập phiếu nên tồn không âm
        await conn.execute(
            "SELECT 1 FROM stock s JOIN stock_slip_items i USING (product_id)"
            " WHERE s.branch_id = $1 AND i.slip_id = $2 ORDER BY s.product_id FOR UPDATE OF s",
            branch_id,
            slip_id,
        )
        await conn.execute(
            "UPDATE stock s SET quantity = s.quantity - i.quantity FROM stock_slip_items i"
            " WHERE i.slip_id = $2 AND s.branch_id = $1 AND s.product_id = i.product_id",
            branch_id,
            slip_id,
        )
    else:
        await conn.execute(
            "INSERT INTO stock (branch_id, product_id, quantity)"
            " SELECT $1, product_id, quantity FROM stock_slip_items WHERE slip_id = $2"
            " ORDER BY product_id"
            " ON CONFLICT (branch_id, product_id)"
            " DO UPDATE SET quantity = stock.quantity + EXCLUDED.quantity",
            branch_id,
            slip_id,
        )


async def _finalize(
    conn: asyncpg.Connection,
    slip_id: str,
    status: SlipStatus,
    at: datetime,
    approved_by: str | None = None,
    decision_reason: str | None = None,
) -> asyncpg.Record:
    """Trạng thái chỉ đi tới: Chờ xử lý → Đã ghi nhận hoặc Đã hủy."""
    row = await conn.fetchrow(
        "UPDATE stock_slips SET status = $2, finalized_at = $3, approved_by = $4,"
        " decision_reason = $5 WHERE slip_id = $1 AND status = $6 RETURNING branch_id, type",
        slip_id,
        status,
        at,
        approved_by,
        decision_reason,
        SlipStatus.PENDING,
    )
    if row is None:
        raise AppError(ErrorCode.INVALID_STATE, f"Phiếu {slip_id} không còn ở trạng thái Chờ xử lý")
    if status == SlipStatus.POSTED:
        await _apply(conn, slip_id, row["branch_id"], row["type"])
    return row


def _validate_lines(items: list[StockSlipItem]) -> Lines:
    lines = [(item.product_id, item.quantity) for item in items]
    if len({product_id for product_id, _ in lines}) != len(lines):
        raise AppError(ErrorCode.VALIDATION_ERROR, "Mỗi sản phẩm chỉ ghi một dòng trên phiếu")
    return lines


async def _ensure_products(conn: asyncpg.Connection, lines: Lines) -> None:
    wanted = {product_id for product_id, _ in lines}
    found = await conn.fetch(
        "SELECT product_id FROM products WHERE product_id = ANY($1::text[])", list(wanted)
    )
    missing = sorted(wanted - {row["product_id"] for row in found})
    if missing:
        raise AppError(ErrorCode.NOT_FOUND, f"Không tìm thấy sản phẩm {', '.join(missing)}")


# ---------------------------------------------------------------- Xem phiếu


async def _load(conn: asyncpg.Connection, rows: list[asyncpg.Record]) -> list[StockSlip]:
    items = await conn.fetch(
        "SELECT slip_id, product_id, quantity FROM stock_slip_items"
        " WHERE slip_id = ANY($1::text[]) ORDER BY product_id",
        [row["slip_id"] for row in rows],
    )
    by_slip: dict[str, list[StockSlipItem]] = {}
    for item in items:
        by_slip.setdefault(item["slip_id"], []).append(
            StockSlipItem(product_id=item["product_id"], quantity=item["quantity"])
        )
    return [StockSlip(**row, items=by_slip.get(row["slip_id"], [])) for row in rows]


async def _owned_slip(
    conn: asyncpg.Connection, slip_id: str, user: CurrentUser, *, for_update: bool = False
) -> asyncpg.Record:
    """K-01: phiếu phải thuộc chi nhánh của người gọi."""
    lock = " FOR UPDATE" if for_update else ""
    row = await conn.fetchrow(f"SELECT * FROM stock_slips WHERE slip_id = $1{lock}", slip_id)
    if row is None:
        raise AppError(ErrorCode.NOT_FOUND, f"Không tìm thấy phiếu kho {slip_id}")
    if row["branch_id"] != user.branch_id:
        raise AppError(ErrorCode.FORBIDDEN, "Phiếu kho thuộc chi nhánh khác", rule="K-01")
    return row


async def list_slips(
    conn: asyncpg.Connection, user: CurrentUser, status: SlipStatus | None
) -> list[StockSlip]:
    rows = await conn.fetch(
        "SELECT * FROM stock_slips WHERE branch_id = $1 AND ($2::text IS NULL OR status = $2)"
        " ORDER BY created_at DESC, slip_id DESC",
        user.branch_id,
        status,
    )
    return await _load(conn, rows)


async def get_slip(conn: asyncpg.Connection, slip_id: str, user: CurrentUser) -> StockSlip:
    return (await _load(conn, [await _owned_slip(conn, slip_id, user)]))[0]


# ---------------------------------------------------------------- 4.2 Nhập từ kho tổng, NCC


async def create_inbound(
    conn: asyncpg.Connection, body: InboundSlipCreate, user: CurrentUser
) -> StockSlip:
    """TK-02: ghi nhận ngay khi lưu; bộ (bên giao, số phiếu giao, chi nhánh) không ghi hai lần."""
    lines = _validate_lines(body.items)
    async with conn.transaction():
        branch_status = await conn.fetchval(
            "SELECT status FROM branches WHERE branch_id = $1", user.branch_id
        )
        if branch_status != BranchStatus.ACTIVE:
            raise AppError(
                ErrorCode.RULE_VIOLATION, "Chi nhánh Ngừng hoạt động không nhập hàng", rule="TK-02"
            )
        await _ensure_products(conn, lines)
        duplicate = AppError(
            ErrorCode.DUPLICATE,
            f"Phiếu giao {body.delivery_no} của {body.counterparty} đã được ghi nhận",
            rule="TK-02",
        )
        if await conn.fetchval(
            "SELECT 1 FROM stock_slips WHERE branch_id = $1 AND counterparty = $2"
            " AND delivery_no = $3 AND type = ANY($4::text[])",
            user.branch_id,
            body.counterparty,
            body.delivery_no,
            [SlipType.IN_WAREHOUSE, SlipType.IN_SUPPLIER],
        ):
            raise duplicate
        try:
            slip_id = await _insert_slip(
                conn,
                user.branch_id or "",
                body.type,
                SlipStatus.POSTED,
                clock.now(),
                lines,
                created_by=user.employee_id,
                counterparty=body.counterparty,
                delivery_no=body.delivery_no,
            )
        except asyncpg.UniqueViolationError:  # yêu cầu khác vừa ghi cùng phiếu giao
            raise duplicate from None
        await _apply(conn, slip_id, user.branch_id or "", body.type)
    return await get_slip(conn, slip_id, user)


# ---------------------------------------------------------------- 4.2, 4.3 Phiếu cần duyệt


async def create_slip(
    conn: asyncpg.Connection, body: StockSlipCreate, user: CurrentUser
) -> StockSlip:
    """TK-03, TK-04: NV kho lập, có lý do; phiếu xuất chỉ lập khi đủ tồn khả dụng và giữ hàng."""
    lines = _validate_lines(body.items)
    branch_id = user.branch_id or ""
    if body.adjusts_slip_id is not None and body.type not in (
        SlipType.ADJUST_UP,
        SlipType.ADJUST_DOWN,
    ):
        raise AppError(
            ErrorCode.VALIDATION_ERROR, "Chỉ phiếu điều chỉnh tham chiếu phiếu bị sai", rule="TK-04"
        )
    async with conn.transaction():
        await _ensure_products(conn, lines)
        if body.adjusts_slip_id is not None and not await conn.fetchval(
            "SELECT 1 FROM stock_slips WHERE slip_id = $1 AND branch_id = $2",
            body.adjusts_slip_id,
            branch_id,
        ):
            raise AppError(
                ErrorCode.NOT_FOUND,
                f"Không tìm thấy phiếu kho {body.adjusts_slip_id} của chi nhánh",
            )
        if body.type in OUT_TYPES:
            await _lock_and_check(conn, branch_id, lines)
        slip_id = await _insert_slip(
            conn,
            branch_id,
            body.type,
            SlipStatus.PENDING,
            clock.now(),
            lines,
            created_by=user.employee_id,
            reason=body.reason,
            adjusts_slip_id=body.adjusts_slip_id,
        )
    return await get_slip(conn, slip_id, user)


async def decide_slip(
    conn: asyncpg.Connection, slip_id: str, user: CurrentUser, reject_reason: str | None
) -> StockSlip:
    """TK-03: QL duyệt thì Đã ghi nhận, từ chối thì Đã hủy; K-02 người duyệt khác người lập;
    K-03 lưu người, thời điểm, lý do từ chối. Phiếu kho không có duyệt thay."""
    async with conn.transaction():
        row = await _owned_slip(conn, slip_id, user, for_update=True)
        if row["status"] != SlipStatus.PENDING or row["type"] not in APPROVAL_TYPES:
            raise AppError(ErrorCode.INVALID_STATE, f"Phiếu {slip_id} không ở trạng thái chờ duyệt")
        if row["created_by"] == user.employee_id:
            raise AppError(
                ErrorCode.FORBIDDEN, "Người duyệt phải khác người lập phiếu", rule="K-02"
            )
        status = SlipStatus.CANCELLED if reject_reason is not None else SlipStatus.POSTED
        await _finalize(conn, slip_id, status, clock.now(), user.employee_id, reject_reason)
    return await get_slip(conn, slip_id, user)


# ---------------------------------------------------------------- 4.5 Mức tồn tối thiểu


async def set_min_level(
    conn: asyncpg.Connection, product_id: str, min_level: int | None, user: CurrentUser
) -> StockLevel:
    """TK-05: số nguyên ≥ 0 hoặc để trống; đổi ngưỡng không đổi tồn."""
    if min_level is not None and min_level < 0:
        raise AppError(ErrorCode.VALIDATION_ERROR, "Mức tồn tối thiểu phải ≥ 0", rule="TK-05")
    await _ensure_products(conn, [(product_id, 0)])
    await conn.execute(
        "INSERT INTO stock (branch_id, product_id, min_level) VALUES ($1, $2, $3)"
        " ON CONFLICT (branch_id, product_id) DO UPDATE SET min_level = EXCLUDED.min_level",
        user.branch_id,
        product_id,
        min_level,
    )
    row = await conn.fetchrow(
        f"{_LEVEL} WHERE p.product_id = $3", user.branch_id, _out_types(), product_id
    )
    return StockLevel(**row)


# ---------------------------------------------------------------- 4.4 Yêu cầu bổ sung


async def _load_requests(
    conn: asyncpg.Connection, rows: list[asyncpg.Record]
) -> list[ReplenishmentRequest]:
    items = await conn.fetch(
        "SELECT request_id, product_id, quantity FROM replenishment_request_items"
        " WHERE request_id = ANY($1::text[]) ORDER BY product_id",
        [row["request_id"] for row in rows],
    )
    by_request: dict[str, list[StockSlipItem]] = {}
    for item in items:
        by_request.setdefault(item["request_id"], []).append(
            StockSlipItem(product_id=item["product_id"], quantity=item["quantity"])
        )
    return [ReplenishmentRequest(**row, items=by_request[row["request_id"]]) for row in rows]


async def list_replenishments(
    conn: asyncpg.Connection, user: CurrentUser
) -> list[ReplenishmentRequest]:
    rows = await conn.fetch(
        "SELECT * FROM replenishment_requests WHERE branch_id = $1"
        " ORDER BY created_at DESC, request_id DESC",
        user.branch_id,
    )
    return await _load_requests(conn, rows)


async def create_replenishment(
    conn: asyncpg.Connection, body: ReplenishmentCreate, user: CurrentUser
) -> ReplenishmentRequest:
    """TK-06: sản phẩm Đang bán, số lượng > 0, mỗi sản phẩm một dòng; lưu như đã gửi,
    không đổi tồn."""
    lines = _validate_lines(body.items)
    async with conn.transaction():
        await _ensure_products(conn, lines)
        stopped = await conn.fetch(
            "SELECT product_id FROM products WHERE product_id = ANY($1::text[]) AND status <> $2"
            " ORDER BY product_id",
            [product_id for product_id, _ in lines],
            ProductStatus.ON_SALE,
        )
        if stopped:
            names = ", ".join(row["product_id"] for row in stopped)
            raise AppError(ErrorCode.RULE_VIOLATION, f"Sản phẩm {names} đã ngừng bán", rule="TK-06")
        row = await conn.fetchrow(
            "INSERT INTO replenishment_requests"
            " (branch_id, created_by, created_at, type, recipient)"
            " VALUES ($1, $2, $3, $4, $5) RETURNING *",
            user.branch_id,
            user.employee_id,
            clock.now(),
            body.type,
            body.recipient,
        )
        await conn.executemany(
            "INSERT INTO replenishment_request_items (request_id, product_id, quantity)"
            " VALUES ($1, $2, $3)",
            [(row["request_id"], product_id, qty) for product_id, qty in sorted(lines)],
        )
    return (await _load_requests(conn, [row]))[0]


# ---------------------------------------------------------------- Hàm giao cho nhóm 3


async def hold_for_order(
    conn: asyncpg.Connection, order_id: str, branch_id: str, lines: Lines, at: datetime
) -> str:
    """3.2 trước khi tạo giao dịch thu: phiếu Xuất bán Chờ xử lý giữ hàng (TK-03, TT-03)."""
    await _lock_and_check(conn, branch_id, lines)
    try:
        return await _insert_slip(
            conn, branch_id, SlipType.OUT_SALE, SlipStatus.PENDING, at, lines, order_id=order_id
        )
    except asyncpg.UniqueViolationError:  # stock_slips_one_live_sale_per_order
        raise AppError(
            ErrorCode.INVALID_STATE, f"Đơn {order_id} đã có phiếu xuất bán chưa hủy", rule="TK-03"
        ) from None


async def _live_sale(conn: asyncpg.Connection, order_id: str) -> str:
    slip_id = await conn.fetchval(
        "SELECT slip_id FROM stock_slips WHERE order_id = $1 AND type = $2 AND status = $3",
        order_id,
        SlipType.OUT_SALE,
        SlipStatus.PENDING,
    )
    if slip_id is None:
        raise AppError(ErrorCode.INVALID_STATE, f"Đơn {order_id} không có phiếu xuất bán chờ xử lý")
    return slip_id


async def confirm_sale(conn: asyncpg.Connection, order_id: str, at: datetime) -> None:
    """3.2 thu Thành công: phiếu Xuất bán Đã ghi nhận, trừ tồn (TK-03)."""
    await _finalize(conn, await _live_sale(conn, order_id), SlipStatus.POSTED, at)


async def release_hold(conn: asyncpg.Connection, order_id: str, at: datetime) -> None:
    """3.2 thu Thất bại: phiếu Xuất bán Đã hủy, nhả hàng (TK-03)."""
    await _finalize(conn, await _live_sale(conn, order_id), SlipStatus.CANCELLED, at)


async def receive_return(
    conn: asyncpg.Connection, return_id: str, branch_id: str, lines: Lines, at: datetime
) -> str | None:
    """3.4 phiếu trả Đã duyệt: Nhập hàng trả cho hàng tốt, một lần mỗi phiếu trả (TK-02, TH-05)."""
    if await conn.fetchval("SELECT 1 FROM stock_slips WHERE return_id = $1", return_id):
        raise AppError(ErrorCode.DUPLICATE, f"Phiếu trả {return_id} đã được nhập kho", rule="TH-05")
    if not lines:
        return None
    slip_id = await _insert_slip(
        conn, branch_id, SlipType.IN_RETURN, SlipStatus.POSTED, at, lines, return_id=return_id
    )
    await _apply(conn, slip_id, branch_id, SlipType.IN_RETURN)
    return slip_id
