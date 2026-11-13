"""Nhóm 5 – Báo cáo (docs/api.md mục 4). Vòng 8: 5.4; vòng 9: 5.1, 5.2, 5.3, 5.5."""

from __future__ import annotations

from typing import Annotated

from deps import Conn, require_role
from fastapi import APIRouter, Depends
from services import reports

from common.constants import Role
from common.models import CurrentUser, LowStockReport

router = APIRouter(tags=["reports"])
StockWatcher = Annotated[CurrentUser, Depends(require_role(Role.MANAGER, Role.WAREHOUSE))]


@router.get("/reports/low-stock")
async def low_stock(user: StockWatcher, conn: Conn) -> LowStockReport:
    return await reports.low_stock(conn, user)
