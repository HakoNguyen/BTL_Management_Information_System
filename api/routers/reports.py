"""Nhóm 5 – Báo cáo (docs/api.md mục 4). Vòng 8: 5.4; vòng 9: 5.1, 5.2, 5.3, 5.5."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from deps import Conn, require_role
from fastapi import APIRouter, Depends, Query
from services import reports

from common.constants import RankBy, Role
from common.models import (
    CurrentUser,
    LowStockReport,
    ProductSalesReport,
    RevenueReport,
    StaffSalesReport,
    StockReport,
)

router = APIRouter(tags=["reports"])
StockWatcher = Annotated[CurrentUser, Depends(require_role(Role.MANAGER, Role.WAREHOUSE))]
SalesViewer = Annotated[CurrentUser, Depends(require_role(Role.HQ, Role.MANAGER))]
StockViewer = Annotated[CurrentUser, Depends(require_role(Role.HQ, Role.MANAGER, Role.WAREHOUSE))]
StaffViewer = Annotated[CurrentUser, Depends(require_role(Role.HQ, Role.MANAGER, Role.SALES))]
From = Annotated[date, Query(alias="from")]
To = Annotated[date, Query(alias="to")]


@router.get("/reports/low-stock")
async def low_stock(user: StockWatcher, conn: Conn) -> LowStockReport:
    return await reports.low_stock(conn, user)


@router.get("/reports/revenue")
async def revenue(
    user: SalesViewer, conn: Conn, from_: From, to: To, branch_id: str | None = None
) -> RevenueReport:
    return await reports.revenue(conn, user, from_, to, branch_id)


@router.get("/reports/products")
async def products(
    user: SalesViewer,
    conn: Conn,
    from_: From,
    to: To,
    branch_id: str | None = None,
    rank_by: RankBy = RankBy.QUANTITY,
) -> ProductSalesReport:
    return await reports.products(conn, user, from_, to, branch_id, rank_by)


@router.get("/reports/stock")
async def stock(
    user: StockViewer, conn: Conn, from_: From, to: To, branch_id: str | None = None
) -> StockReport:
    return await reports.stock(conn, user, from_, to, branch_id)


@router.get("/reports/staff-sales")
async def staff_sales(
    user: StaffViewer, conn: Conn, from_: From, to: To, branch_id: str | None = None
) -> StaffSalesReport:
    return await reports.staff_sales(conn, user, from_, to, branch_id)
