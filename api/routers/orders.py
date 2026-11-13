"""Nhóm 3 – Đơn hàng (docs/api.md mục 4): 3.1 và phần hủy đơn của 3.4."""

from __future__ import annotations

from typing import Annotated

from deps import Conn, require_role
from fastapi import APIRouter, Depends
from services import orders

from common.constants import OrderStatus, Role
from common.models import CurrentUser, Order, OrderCancel, OrderCreate, OrderItemsChange

router = APIRouter(tags=["orders"])
SalesUser = Annotated[CurrentUser, Depends(require_role(Role.MANAGER, Role.SALES))]
OrderViewer = Annotated[CurrentUser, Depends(require_role(Role.MANAGER, Role.SALES, Role.CASHIER))]


@router.post("/orders", status_code=201)
async def create_order(body: OrderCreate, user: SalesUser, conn: Conn) -> Order:
    return await orders.create_order(conn, body, user)


@router.get("/orders")
async def list_orders(
    user: OrderViewer, conn: Conn, status: OrderStatus | None = None
) -> list[Order]:
    return await orders.list_orders(conn, user, status)


@router.get("/orders/{order_id}")
async def get_order(order_id: str, user: OrderViewer, conn: Conn) -> Order:
    return await orders.get_order(conn, order_id, user)


@router.put("/orders/{order_id}/items")
async def update_items(order_id: str, body: OrderItemsChange, user: SalesUser, conn: Conn) -> Order:
    return await orders.update_items(conn, order_id, body.items, user)


@router.post("/orders/{order_id}/confirm")
async def confirm_order(order_id: str, user: SalesUser, conn: Conn) -> Order:
    return await orders.confirm_order(conn, order_id, user)


@router.post("/orders/{order_id}/reopen")
async def reopen_order(order_id: str, user: SalesUser, conn: Conn) -> Order:
    return await orders.reopen_order(conn, order_id, user)


@router.post("/orders/{order_id}/cancel")
async def cancel_order(order_id: str, body: OrderCancel, user: SalesUser, conn: Conn) -> Order:
    return await orders.cancel_order(conn, order_id, body.reason, user)
