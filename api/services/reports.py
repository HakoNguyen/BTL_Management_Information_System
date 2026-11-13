"""Nhóm 5 – Báo cáo: chỉ đọc (đặc tả 6.1), tính lúc gọi, không lưu kết quả (docs/db.md mục 6).

Ba mốc thời gian không trộn (đặc tả 4.5): bán theo `orders.completed_at`; hàng trả theo `decided_at`
của phiếu Đã duyệt; tiền thu, hoàn theo `resolved_at` của giao dịch Thành công. Doanh thu, hàng trả,
đơn hủy ghi cho chi nhánh và người lập của đơn gốc (DT-05). Kỳ là [start, end) theo giờ Việt Nam.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta

import asyncpg

from common import clock
from common.clock import VN_TZ
from common.constants import (
    WALK_IN_CUSTOMER_ID,
    ErrorCode,
    LevelStatus,
    OrderStatus,
    ProductStatus,
    RankBy,
    ReturnStatus,
    Role,
    SlipStatus,
    SlipType,
    TxnStatus,
    TxnType,
)
from common.errors import AppError
from common.models import (
    CountByReason,
    CurrentUser,
    GroupSalesLine,
    LowStockLine,
    LowStockReport,
    MoneyByMethod,
    ProductSalesLine,
    ProductSalesReport,
    RevenueReport,
    RevenueSummary,
    SlowMovingLine,
    StaffSalesLine,
    StaffSalesReport,
    StockMovementLine,
    StockReport,
    StockReportLine,
)
from services import inventory, shifts

# ---------------------------------------------------------------- 5.4 Cảnh báo dưới ngưỡng


async def low_stock(conn: asyncpg.Connection, user: CurrentUser) -> LowStockReport:
    """TK-05: sản phẩm Đang bán có tồn < ngưỡng; Chưa thiết lập (null, khác 0) liệt kê riêng."""
    rows = await conn.fetch(
        "SELECT p.product_id, p.name, COALESCE(s.quantity, 0) AS quantity, s.min_level"
        " FROM products p LEFT JOIN stock s ON s.product_id = p.product_id AND s.branch_id = $1"
        " WHERE p.status = $2 AND (s.min_level IS NULL OR COALESCE(s.quantity, 0) < s.min_level)"
        " ORDER BY p.product_id",
        user.branch_id,
        ProductStatus.ON_SALE,
    )
    lines = [LowStockLine(**row) for row in rows]
    return LowStockReport(
        branch_id=user.branch_id or "",
        generated_at=clock.now(),
        below_min=[line for line in lines if line.min_level is not None],
        not_set=[line for line in lines if line.min_level is None],
    )


# ---------------------------------------------------------------- Kỳ, phạm vi

# Truy vấn dưới đây: $1 chi nhánh (NULL = toàn chuỗi); $2, $3 đầu kỳ, cuối kỳ (không gồm)
_SCOPE = "($1::text IS NULL OR o.branch_id = $1)"
# Hàng trả của phiếu Đã duyệt, giá trị theo đơn giá chốt trên đơn gốc (TH-04)
_RETURN_ITEMS = f"""
    FROM return_slips r JOIN orders o USING (order_id)
    JOIN return_slip_items i USING (return_id)
    JOIN order_items oi ON oi.order_id = r.order_id AND oi.product_id = i.product_id
    WHERE {_SCOPE} AND r.status = '{ReturnStatus.APPROVED}'
"""
_RETURN_QTY = "(i.good_qty + i.defective_qty)"
_RETURN_VALUE = f"{_RETURN_QTY} * oi.unit_price"
_SOLD_IN_PERIOD = f"{_SCOPE} AND o.completed_at >= $2 AND o.completed_at < $3"

Period = tuple[datetime, datetime]


def _period(from_date: date, to_date: date) -> Period:
    if from_date > to_date:
        raise AppError(ErrorCode.VALIDATION_ERROR, "Ngày đầu kỳ sau ngày cuối kỳ")
    start = datetime.combine(from_date, time(), VN_TZ)
    return start, datetime.combine(to_date + timedelta(days=1), time(), VN_TZ)


def _previous(period: Period) -> Period:
    """Kỳ trước: cùng số ngày, liền ngay trước kỳ đang xem."""
    start, end = period
    return start - (end - start), start


def _branch(user: CurrentUser, branch_id: str | None) -> str | None:
    """K-01: HQ chọn chi nhánh hoặc toàn chuỗi; vai trò khác luôn là chi nhánh mình."""
    if user.role == Role.HQ:
        return branch_id
    if branch_id is not None and branch_id != user.branch_id:
        raise AppError(ErrorCode.FORBIDDEN, "Chỉ xem báo cáo của chi nhánh mình", rule="K-01")
    return user.branch_id


def _header(branch_id: str | None, from_date: date, to_date: date) -> dict:
    return {
        "branch_id": branch_id,
        "from_date": from_date,
        "to_date": to_date,
        "generated_at": clock.now(),
    }


# ---------------------------------------------------------------- Số liệu theo người lập (DT-05)


def _empty_seller() -> dict[str, int]:
    return dict.fromkeys(
        ("order_count", "gross_revenue", "walk_in_revenue", "returns_value", "cancelled_count"), 0
    )


async def _by_seller(
    conn: asyncpg.Connection, branch_id: str | None, period: Period
) -> tuple[dict[tuple[str, str], dict[str, int]], list[asyncpg.Record]]:
    """Chỉ tiêu theo (chi nhánh, người lập) của đơn gốc, kèm các dòng đơn hủy theo lý do."""
    facts: dict[tuple[str, str], dict[str, int]] = defaultdict(_empty_seller)
    sales = await conn.fetch(
        f"""
        SELECT o.branch_id, o.created_by, count(*) AS n, sum(v.total)::bigint AS gross,
               coalesce(sum(v.total) FILTER (WHERE o.customer_id = $4), 0)::bigint AS walk_in
        FROM orders o CROSS JOIN LATERAL (
            SELECT sum(quantity * unit_price) AS total FROM order_items WHERE order_id = o.order_id
        ) v
        WHERE {_SOLD_IN_PERIOD}
        GROUP BY 1, 2
        """,
        branch_id,
        *period,
        WALK_IN_CUSTOMER_ID,
    )
    for row in sales:
        fact = facts[(row["branch_id"], row["created_by"])]
        fact["order_count"] = row["n"]
        fact["gross_revenue"] = row["gross"]
        fact["walk_in_revenue"] = row["walk_in"]
    returned = await conn.fetch(
        f"SELECT o.branch_id, o.created_by, sum({_RETURN_VALUE})::bigint AS value {_RETURN_ITEMS}"
        " AND r.decided_at >= $2 AND r.decided_at < $3 GROUP BY 1, 2",
        branch_id,
        *period,
    )
    for row in returned:
        facts[(row["branch_id"], row["created_by"])]["returns_value"] = row["value"]
    cancels = await conn.fetch(
        f"SELECT o.branch_id, o.created_by, o.cancel_reason AS reason, count(*) AS n FROM orders o"
        f" WHERE {_SCOPE} AND o.status = $4 AND o.cancelled_at >= $2 AND o.cancelled_at < $3"
        " GROUP BY 1, 2, 3",
        branch_id,
        *period,
        OrderStatus.CANCELLED,
    )
    for row in cancels:
        facts[(row["branch_id"], row["created_by"])]["cancelled_count"] += row["n"]
    return facts, cancels


# ---------------------------------------------------------------- 5.1 Tổng hợp doanh thu


def _summary(
    branch_id: str | None,
    fact: dict[str, int],
    cancellations: dict[str, int],
    shift_variance: int,
    payments: dict[tuple[str, str], int],
    outstanding_refunds: int,
) -> RevenueSummary:
    count, gross, returns = fact["order_count"], fact["gross_revenue"], fact["returns_value"]
    return RevenueSummary(
        branch_id=branch_id,
        order_count=count,
        gross_revenue=gross,
        returns_value=returns,
        net_revenue=gross - returns,  # DT-03
        average_order_value=gross // count if count else None,  # DT-01
        registered_revenue=gross - fact["walk_in_revenue"],
        walk_in_revenue=fact["walk_in_revenue"],
        cancellations=[CountByReason(reason=r, count=n) for r, n in sorted(cancellations.items())],
        shift_variance=shift_variance,
        payments=[
            MoneyByMethod(type=t, method=m, amount=a) for (t, m), a in sorted(payments.items())
        ],
        outstanding_refunds=outstanding_refunds,
    )


def _total(lines: list[RevenueSummary]) -> RevenueSummary:
    """DT-05: dòng tổng = Σ các dòng chi nhánh."""
    fact = _empty_seller()
    cancellations: dict[str, int] = defaultdict(int)
    payments: dict[tuple[str, str], int] = defaultdict(int)
    for line in lines:
        for key in ("order_count", "gross_revenue", "walk_in_revenue", "returns_value"):
            fact[key] += getattr(line, key)
        for c in line.cancellations:
            cancellations[c.reason] += c.count
        for p in line.payments:
            payments[(p.type, p.method)] += p.amount
    return _summary(
        None,
        fact,
        cancellations,
        sum(line.shift_variance for line in lines),
        payments,
        sum(line.outstanding_refunds for line in lines),
    )


async def _revenue_lines(
    conn: asyncpg.Connection, branch_id: str | None, period: Period
) -> list[RevenueSummary]:
    branch_ids = await conn.fetch(
        "SELECT branch_id FROM branches WHERE ($1::text IS NULL OR branch_id = $1)"
        " ORDER BY branch_id",
        branch_id,
    )
    sellers, cancels = await _by_seller(conn, branch_id, period)
    facts: dict[str, dict[str, int]] = defaultdict(_empty_seller)
    for (branch, _), fact in sellers.items():
        for key, value in fact.items():
            facts[branch][key] += value
    cancellations: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in cancels:
        cancellations[row["branch_id"]][row["reason"]] += row["n"]
    # DT-04: giao dịch Thành công theo thời điểm có kết quả
    payments: dict[str, dict[tuple[str, str], int]] = defaultdict(dict)
    for row in await conn.fetch(
        f"SELECT o.branch_id, t.type, t.method, sum(t.amount)::bigint AS amount"
        f" FROM transactions t JOIN orders o USING (order_id)"
        f" WHERE {_SCOPE} AND t.status = $4 AND t.resolved_at >= $2 AND t.resolved_at < $3"
        " GROUP BY 1, 2, 3",
        branch_id,
        *period,
        TxnStatus.SUCCESS,
    ):
        payments[row["branch_id"]][(row["type"], row["method"])] = row["amount"]
    # DT-04: số còn phải hoàn lúc cuối kỳ
    outstanding = dict(
        await conn.fetch(
            f"SELECT o.branch_id, sum({_RETURN_VALUE})::bigint {_RETURN_ITEMS}"
            " AND r.decided_at < $2"
            " AND NOT EXISTS (SELECT 1 FROM transactions t WHERE t.return_id = r.return_id"
            "   AND t.type = $3 AND t.status = $4 AND t.resolved_at < $2)"
            " GROUP BY 1",
            branch_id,
            period[1],
            TxnType.REFUND,
            TxnStatus.SUCCESS,
        )
    )
    variances = await shifts.variance_by_branch(conn, branch_id, *period)
    return [
        _summary(
            branch,
            facts[branch],
            cancellations[branch],
            variances.get(branch, 0),
            payments[branch],
            outstanding.get(branch, 0),
        )
        for (branch,) in branch_ids
    ]


async def revenue(
    conn: asyncpg.Connection,
    user: CurrentUser,
    from_date: date,
    to_date: date,
    branch_id: str | None,
) -> RevenueReport:
    """5.1: DT-01 đến DT-05, theo chi nhánh, kèm tổng và tổng kỳ trước."""
    period = _period(from_date, to_date)
    branch_id = _branch(user, branch_id)
    lines = await _revenue_lines(conn, branch_id, period)
    return RevenueReport(
        **_header(branch_id, from_date, to_date),
        branches=lines,
        total=_total(lines),
        previous=_total(await _revenue_lines(conn, branch_id, _previous(period))),
    )


# ---------------------------------------------------------------- 5.2 Thống kê sản phẩm bán


async def _product_lines(
    conn: asyncpg.Connection, branch_id: str | None, period: Period, rank_by: RankBy
) -> list[ProductSalesLine]:
    """Sản phẩm có bán hoặc trả trong kỳ, xếp hạng theo tiêu chí, bằng nhau thì theo mã."""
    rows = await conn.fetch(
        f"""
        WITH sold AS (
            SELECT oi.product_id, sum(oi.quantity) AS qty, sum(oi.quantity * oi.unit_price) AS value
            FROM orders o JOIN order_items oi USING (order_id)
            WHERE {_SOLD_IN_PERIOD} GROUP BY 1
        ), ret AS (
            SELECT i.product_id, sum({_RETURN_QTY}) AS qty, sum({_RETURN_VALUE}) AS value
            {_RETURN_ITEMS} AND r.decided_at >= $2 AND r.decided_at < $3 GROUP BY 1
        )
        SELECT p.product_id, p.name, p.group_id,
               coalesce(sold.qty, 0)::int AS sold_qty, coalesce(ret.qty, 0)::int AS returned_qty,
               (coalesce(sold.value, 0) - coalesce(ret.value, 0))::bigint AS net_value
        FROM products p LEFT JOIN sold USING (product_id) LEFT JOIN ret USING (product_id)
        WHERE sold.product_id IS NOT NULL OR ret.product_id IS NOT NULL
        """,
        branch_id,
        *period,
    )
    field = "net_value" if rank_by == RankBy.VALUE else "net_qty"
    lines = sorted(
        ({**row, "net_qty": row["sold_qty"] - row["returned_qty"]} for row in rows),
        key=lambda x: (-x[field], x["product_id"]),
    )
    return [
        ProductSalesLine(**{**line, "rank": n, "previous_rank": None})
        for n, line in enumerate(lines, 1)
    ]


async def products(
    conn: asyncpg.Connection,
    user: CurrentUser,
    from_date: date,
    to_date: date,
    branch_id: str | None,
    rank_by: RankBy,
) -> ProductSalesReport:
    """5.2: lượng bán gộp, trả, thuần theo sản phẩm và nhóm hiện tại (DT-05); chậm bán."""
    period = _period(from_date, to_date)
    branch_id = _branch(user, branch_id)
    lines = await _product_lines(conn, branch_id, period, rank_by)
    previous = {
        x.product_id: x.rank
        for x in await _product_lines(conn, branch_id, _previous(period), rank_by)
    }
    for line in lines:
        line.previous_rank = previous.get(line.product_id)
    group_names = dict(await conn.fetch("SELECT group_id, name FROM product_groups"))
    groups: dict[str, dict[str, int]] = defaultdict(
        lambda: dict.fromkeys(("sold_qty", "returned_qty", "net_qty", "net_value"), 0)
    )
    for line in lines:
        for key in groups[line.group_id]:
            groups[line.group_id][key] += getattr(line, key)
    slow = await conn.fetch(
        """
        SELECT s.branch_id, p.product_id, p.name, s.quantity
        FROM stock s JOIN products p USING (product_id)
        WHERE ($1::text IS NULL OR s.branch_id = $1) AND p.status = $4 AND s.quantity > 0
          AND NOT EXISTS (
            SELECT 1 FROM orders o JOIN order_items oi USING (order_id)
            WHERE o.branch_id = s.branch_id AND oi.product_id = s.product_id
              AND o.completed_at >= $2 AND o.completed_at < $3)
        ORDER BY 1, 2
        """,
        branch_id,
        *period,
        ProductStatus.ON_SALE,
    )
    return ProductSalesReport(
        **_header(branch_id, from_date, to_date),
        rank_by=rank_by,
        products=lines,
        groups=[
            GroupSalesLine(group_id=g, name=group_names[g], **totals)
            for g, totals in sorted(groups.items())
        ],
        slow_moving=[SlowMovingLine(**row) for row in slow],
    )


# ---------------------------------------------------------------- 5.3 Lập báo cáo tồn kho


def _level_status(quantity: int, min_level: int | None) -> LevelStatus:
    if min_level is None:
        return LevelStatus.NOT_SET
    return LevelStatus.BELOW_MIN if quantity < min_level else LevelStatus.OK


async def stock(
    conn: asyncpg.Connection,
    user: CurrentUser,
    from_date: date,
    to_date: date,
    branch_id: str | None,
) -> StockReport:
    """5.3: tồn, tồn khả dụng (TK-01), so ngưỡng (TK-05) lúc lập; xuất hủy, điều chỉnh trong kỳ."""
    period = _period(from_date, to_date)
    branch_id = _branch(user, branch_id)
    names = dict(await conn.fetch("SELECT product_id, name FROM products"))
    branch_ids = await conn.fetch(
        "SELECT branch_id FROM branches WHERE ($1::text IS NULL OR branch_id = $1)"
        " ORDER BY branch_id",
        branch_id,
    )
    lines = [
        StockReportLine(
            branch_id=branch,
            name=names[level.product_id],
            level_status=_level_status(level.quantity, level.min_level),
            **level.model_dump(),
        )
        for (branch,) in branch_ids
        for level in await inventory.list_stock(conn, branch)
    ]
    movements = await conn.fetch(
        """
        SELECT k.branch_id, k.type, k.reason, i.product_id, sum(i.quantity)::int AS quantity
        FROM stock_slips k JOIN stock_slip_items i USING (slip_id)
        WHERE ($1::text IS NULL OR k.branch_id = $1) AND k.status = $4 AND k.type = ANY($5::text[])
          AND k.finalized_at >= $2 AND k.finalized_at < $3
        GROUP BY 1, 2, 3, 4 ORDER BY 1, 2, 3, 4
        """,
        branch_id,
        *period,
        SlipStatus.POSTED,
        [SlipType.OUT_DISPOSAL, SlipType.ADJUST_UP, SlipType.ADJUST_DOWN],
    )
    return StockReport(
        **_header(branch_id, from_date, to_date),
        lines=lines,
        movements=[StockMovementLine(**row) for row in movements],
    )


# ---------------------------------------------------------------- 5.5 Doanh số nhân viên


async def staff_sales(
    conn: asyncpg.Connection,
    user: CurrentUser,
    from_date: date,
    to_date: date,
    branch_id: str | None,
) -> StaffSalesReport:
    """5.5: theo người lập đơn (DT-05), xếp hạng trong chi nhánh; NVBH chỉ thấy dòng của mình."""
    period = _period(from_date, to_date)
    # NVBH: dòng của mình ở mọi chi nhánh từng bán (DT-05), hạng vẫn tính trong cả chi nhánh
    branch_id = None if user.role == Role.SALES else _branch(user, branch_id)
    facts, _ = await _by_seller(conn, branch_id, period)
    previous, _ = await _by_seller(conn, branch_id, _previous(period))
    names = dict(await conn.fetch("SELECT employee_id, full_name FROM employees"))
    net = {key: f["gross_revenue"] - f["returns_value"] for key, f in facts.items()}
    ranked = sorted(facts, key=lambda k: (k[0], -net[k], k[1]))
    lines: list[StaffSalesLine] = []
    rank, last_branch = 0, None
    for key in ranked:
        branch, employee_id = key
        rank = 1 if branch != last_branch else rank + 1
        last_branch = branch
        if user.role == Role.SALES and employee_id != user.employee_id:
            continue
        fact = facts[key]
        before = previous.get(key)
        lines.append(
            StaffSalesLine(
                branch_id=branch,
                employee_id=employee_id,
                full_name=names[employee_id],
                order_count=fact["order_count"],
                gross_revenue=fact["gross_revenue"],
                returns_value=fact["returns_value"],
                net_revenue=net[key],
                cancelled_count=fact["cancelled_count"],
                rank=rank,
                previous_net_revenue=(
                    before["gross_revenue"] - before["returns_value"] if before else 0
                ),
            )
        )
    return StaffSalesReport(**_header(branch_id, from_date, to_date), lines=lines)
