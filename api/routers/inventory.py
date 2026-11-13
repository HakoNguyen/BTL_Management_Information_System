"""Nhóm 4 – Tồn kho (docs/api.md mục 4). NV kho lập phiếu, yêu cầu bổ sung; QL duyệt phiếu."""

from __future__ import annotations

from typing import Annotated

from deps import Conn, require_role
from fastapi import APIRouter, Depends
from services import inventory

from common.constants import Role, SlipStatus
from common.models import (
    CurrentUser,
    InboundSlipCreate,
    MinLevelChange,
    ReplenishmentCreate,
    ReplenishmentRequest,
    StockLevel,
    StockSlip,
    StockSlipCreate,
    StockSlipReject,
)

router = APIRouter(tags=["inventory"])
StockViewer = Annotated[
    CurrentUser, Depends(require_role(Role.MANAGER, Role.SALES, Role.WAREHOUSE))
]
SlipViewer = Annotated[CurrentUser, Depends(require_role(Role.MANAGER, Role.WAREHOUSE))]
WarehouseUser = Annotated[CurrentUser, Depends(require_role(Role.WAREHOUSE))]
ManagerUser = Annotated[CurrentUser, Depends(require_role(Role.MANAGER))]


@router.get("/stock")
async def list_stock(user: StockViewer, conn: Conn) -> list[StockLevel]:
    return await inventory.list_stock(conn, user.branch_id or "")


@router.put("/stock/{product_id}/min-level")
async def set_min_level(
    product_id: str, body: MinLevelChange, user: ManagerUser, conn: Conn
) -> StockLevel:
    return await inventory.set_min_level(conn, product_id, body.min_level, user)


@router.post("/stock-slips/inbound", status_code=201)
async def create_inbound(body: InboundSlipCreate, user: WarehouseUser, conn: Conn) -> StockSlip:
    return await inventory.create_inbound(conn, body, user)


@router.post("/stock-slips", status_code=201)
async def create_slip(body: StockSlipCreate, user: WarehouseUser, conn: Conn) -> StockSlip:
    return await inventory.create_slip(conn, body, user)


@router.get("/stock-slips")
async def list_slips(
    user: SlipViewer, conn: Conn, status: SlipStatus | None = None
) -> list[StockSlip]:
    return await inventory.list_slips(conn, user, status)


@router.get("/stock-slips/{slip_id}")
async def get_slip(slip_id: str, user: SlipViewer, conn: Conn) -> StockSlip:
    return await inventory.get_slip(conn, slip_id, user)


@router.post("/stock-slips/{slip_id}/approve")
async def approve_slip(slip_id: str, user: ManagerUser, conn: Conn) -> StockSlip:
    return await inventory.decide_slip(conn, slip_id, user, None)


@router.post("/stock-slips/{slip_id}/reject")
async def reject_slip(
    slip_id: str, body: StockSlipReject, user: ManagerUser, conn: Conn
) -> StockSlip:
    return await inventory.decide_slip(conn, slip_id, user, body.reason)


@router.post("/replenishment-requests", status_code=201)
async def create_replenishment(
    body: ReplenishmentCreate, user: WarehouseUser, conn: Conn
) -> ReplenishmentRequest:
    return await inventory.create_replenishment(conn, body, user)


@router.get("/replenishment-requests")
async def list_replenishments(user: SlipViewer, conn: Conn) -> list[ReplenishmentRequest]:
    return await inventory.list_replenishments(conn, user)
