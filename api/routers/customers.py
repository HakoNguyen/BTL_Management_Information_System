"""Nhóm 2 – Khách hàng (docs/api.md mục 4). Chỉ NVBH (ma trận 2.2)."""

from __future__ import annotations

from typing import Annotated

from deps import Conn, require_role
from fastapi import APIRouter, Depends, Response
from services import customers

from common.constants import Role
from common.models import CurrentUser, Customer, CustomerCreate, CustomerUpdate

router = APIRouter(tags=["customers"])
SalesUser = Annotated[CurrentUser, Depends(require_role(Role.SALES))]


@router.post("/customers", status_code=201, responses={200: {"model": Customer}})
async def create_customer(
    body: CustomerCreate, response: Response, _: SalesUser, conn: Conn
) -> Customer:
    customer, created = await customers.create_customer(conn, body)
    if not created:
        response.status_code = 200  # số đã có hồ sơ: trả hồ sơ có sẵn (2.1)
    return customer


@router.patch("/customers/{customer_id}")
async def update_customer(
    customer_id: str, body: CustomerUpdate, _: SalesUser, conn: Conn
) -> Customer:
    return await customers.update_customer(conn, customer_id, body)


@router.get("/customers")
async def search_customers(
    _: SalesUser, conn: Conn, phone: str | None = None, customer_id: str | None = None
) -> list[Customer]:
    return await customers.search_customers(conn, phone, customer_id)
