"""Nhóm 5 – Báo cáo: chỉ đọc (đặc tả 6.1), tính lúc gọi, không lưu kết quả (docs/db.md mục 6)."""

from __future__ import annotations

import asyncpg

from common import clock
from common.constants import ProductStatus
from common.models import CurrentUser, LowStockLine, LowStockReport

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
