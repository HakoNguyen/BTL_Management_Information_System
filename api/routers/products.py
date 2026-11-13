"""Nhóm 1 – Sản phẩm (docs/api.md mục 4). Trụ sở ghi; mọi vai trò xem danh mục."""

from __future__ import annotations

from typing import Annotated

from deps import Conn, User, require_role
from fastapi import APIRouter, Depends
from services import products

from common.constants import Role
from common.models import (
    CurrentUser,
    PriceChange,
    PriceHistoryEntry,
    Product,
    ProductCreate,
    ProductGroup,
    ProductGroupChange,
    ProductGroupCreate,
    ProductGroupUpdate,
    ProductStatusChange,
    ProductUpdate,
)

router = APIRouter(tags=["products"])
HqUser = Annotated[CurrentUser, Depends(require_role(Role.HQ))]


@router.get("/product-groups")
async def list_groups(_: User, conn: Conn) -> list[ProductGroup]:
    return await products.list_groups(conn)


@router.post("/product-groups", status_code=201)
async def create_group(body: ProductGroupCreate, _: HqUser, conn: Conn) -> ProductGroup:
    return await products.create_group(conn, body)


@router.patch("/product-groups/{group_id}")
async def update_group(
    group_id: str, body: ProductGroupUpdate, _: HqUser, conn: Conn
) -> ProductGroup:
    return await products.update_group(conn, group_id, body)


@router.delete("/product-groups/{group_id}")
async def delete_group(group_id: str, _: HqUser, conn: Conn) -> ProductGroup:
    return await products.delete_group(conn, group_id)


@router.put("/products/{product_id}/group")
async def change_group(product_id: str, body: ProductGroupChange, _: HqUser, conn: Conn) -> Product:
    return await products.change_group(conn, product_id, body.group_id)


@router.get("/products")
async def list_products(_: User, conn: Conn) -> list[Product]:
    return await products.list_products(conn)


@router.get("/products/{product_id}")
async def get_product(product_id: str, _: User, conn: Conn) -> Product:
    return await products.get_product(conn, product_id)


@router.post("/products", status_code=201)
async def create_product(body: ProductCreate, user: HqUser, conn: Conn) -> Product:
    return await products.create_product(conn, body, user.employee_id)


@router.patch("/products/{product_id}")
async def update_product(product_id: str, body: ProductUpdate, _: HqUser, conn: Conn) -> Product:
    return await products.update_product(conn, product_id, body)


@router.put("/products/{product_id}/price")
async def change_price(product_id: str, body: PriceChange, user: HqUser, conn: Conn) -> Product:
    return await products.change_price(conn, product_id, body.price, user.employee_id)


@router.get("/products/{product_id}/price-history")
async def price_history(product_id: str, _: HqUser, conn: Conn) -> list[PriceHistoryEntry]:
    return await products.price_history(conn, product_id)


@router.put("/products/{product_id}/status")
async def set_status(product_id: str, body: ProductStatusChange, _: HqUser, conn: Conn) -> Product:
    return await products.set_status(conn, product_id, body.status)
