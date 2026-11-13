"""1.1 Thêm mới, cập nhật sản phẩm và 1.4 trạng thái kinh doanh (SP-01, SP-02, SP-04)."""

from __future__ import annotations

from datetime import datetime

import asyncpg
import httpx
import pytest
from fixtures import (
    BRANCH_1,
    GROUP_ID,
    HQ_ID,
    SALES_ID,
    WAREHOUSE_ID,
    login_as,
    seed_order,
    seed_order_item,
    seed_product,
    seed_staff,
    seed_stock_slip,
    seed_stock_slip_item,
)

from common import clock
from common.clock import VN_TZ
from common.constants import ErrorCode, ProductStatus

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 13, 10, 0, tzinfo=VN_TZ)


@pytest.fixture
async def hq(client: httpx.AsyncClient, conn: asyncpg.Connection) -> dict[str, str]:
    await seed_staff(conn)
    clock.freeze(NOW)
    headers = await login_as(client, HQ_ID)
    group = {"group_id": GROUP_ID, "name": "Nhóm mẫu"}
    assert (await client.post("/product-groups", json=group, headers=headers)).status_code == 201
    return headers


def _new(product_id: str = "A", **overrides: object) -> dict[str, object]:
    return {
        "product_id": product_id,
        "name": f"Sản phẩm {product_id}",
        "group_id": GROUP_ID,
        "unit": "cái",
        "price": 100_000,
        **overrides,
    }


def _product(product_id: str = "A", **overrides: object) -> dict[str, object]:
    return {
        "product_id": product_id,
        "name": f"Sản phẩm {product_id}",
        "group_id": GROUP_ID,
        "unit": "cái",
        "current_price": 100_000,
        "description": None,
        "status": ProductStatus.ON_SALE,
        **overrides,
    }


async def test_create_product_with_first_price(
    client: httpx.AsyncClient, conn: asyncpg.Connection, hq: dict[str, str]
) -> None:
    """SP-02: tạo sản phẩm Đang bán kèm bản ghi lịch sử giá đầu tiên; SP-04: tồn 0 mọi chi nhánh."""
    response = await client.post("/products", json=_new(description="Hộp 1kg"), headers=hq)
    assert response.status_code == 201
    assert response.json() == _product(description="Hộp 1kg")
    history = await conn.fetch("SELECT effective_at, price, changed_by FROM price_history")
    assert [dict(r) for r in history] == [
        {"effective_at": NOW, "price": 100_000, "changed_by": HQ_ID}
    ]
    assert await conn.fetchval("SELECT count(*) FROM stock WHERE product_id = 'A'") == 0


async def test_create_product_duplicate(client: httpx.AsyncClient, hq: dict[str, str]) -> None:
    """SP-01: mã sản phẩm duy nhất toàn chuỗi."""
    assert (await client.post("/products", json=_new(), headers=hq)).status_code == 201
    response = await client.post("/products", json=_new(name="Khác"), headers=hq)
    assert response.status_code == 409
    assert response.json()["error_code"] == ErrorCode.DUPLICATE
    assert response.json()["details"]["rule"] == "SP-01"


async def test_create_product_group_not_found(
    client: httpx.AsyncClient, conn: asyncpg.Connection, hq: dict[str, str]
) -> None:
    """SP-01: nhóm phải tồn tại."""
    response = await client.post("/products", json=_new(group_id="KHONG"), headers=hq)
    assert response.status_code == 404
    assert response.json()["error_code"] == ErrorCode.NOT_FOUND
    assert await conn.fetchval("SELECT count(*) FROM products") == 0


@pytest.mark.parametrize("price", [0, -1])
async def test_create_product_price_positive(
    client: httpx.AsyncClient, conn: asyncpg.Connection, hq: dict[str, str], price: int
) -> None:
    """SP-02: giá > 0."""
    response = await client.post("/products", json=_new(price=price), headers=hq)
    assert response.status_code == 422
    assert response.json()["error_code"] == ErrorCode.RULE_VIOLATION
    assert response.json()["details"]["rule"] == "SP-02"
    assert await conn.fetchval("SELECT count(*) FROM products") == 0


async def test_list_and_get_products_any_role(
    client: httpx.AsyncClient, hq: dict[str, str]
) -> None:
    await client.post("/products", json=_new("B"), headers=hq)
    await client.post("/products", json=_new("A"), headers=hq)
    await client.put("/products/B/status", json={"status": ProductStatus.DISCONTINUED}, headers=hq)
    sales = await login_as(client, SALES_ID)
    response = await client.get("/products", headers=sales)
    assert response.status_code == 200
    assert response.json() == [_product("A"), _product("B", status=ProductStatus.DISCONTINUED)]
    response = await client.get("/products/A", headers=sales)
    assert response.json() == _product("A")
    response = await client.get("/products/KHONG", headers=sales)
    assert response.status_code == 404


async def test_update_product_info(client: httpx.AsyncClient, hq: dict[str, str]) -> None:
    """1.1: sửa tên, mô tả, đơn vị tính khi chưa có chứng từ; mã, giá không đổi (SP-01)."""
    await client.post("/products", json=_new(), headers=hq)
    response = await client.patch(
        "/products/A",
        json={
            "name": "Bánh quy",
            "description": "Hộp",
            "unit": "hộp",
            "product_id": "Z",
            "current_price": 1,
        },
        headers=hq,
    )
    assert response.status_code == 200
    assert response.json() == _product(name="Bánh quy", description="Hộp", unit="hộp")
    response = await client.patch("/products/KHONG", json={"name": "X"}, headers=hq)
    assert response.status_code == 404


async def test_unit_locked_after_order(
    client: httpx.AsyncClient, conn: asyncpg.Connection, hq: dict[str, str]
) -> None:
    """SP-04: sản phẩm đã có trên đơn thì không đổi đơn vị tính; tên vẫn đổi được."""
    await client.post("/products", json=_new(), headers=hq)
    await seed_order_item(conn, await seed_order(conn, SALES_ID), "A")
    response = await client.patch("/products/A", json={"unit": "hộp"}, headers=hq)
    assert response.status_code == 422
    assert response.json()["error_code"] == ErrorCode.RULE_VIOLATION
    assert response.json()["details"]["rule"] == "SP-04"
    response = await client.patch("/products/A", json={"name": "Mới", "unit": "cái"}, headers=hq)
    assert response.status_code == 200
    assert response.json() == _product(name="Mới")


async def test_unit_locked_after_stock_slip(
    client: httpx.AsyncClient, conn: asyncpg.Connection, hq: dict[str, str]
) -> None:
    """SP-04: sản phẩm đã có trên phiếu kho thì không đổi đơn vị tính."""
    await client.post("/products", json=_new(), headers=hq)
    await seed_stock_slip_item(conn, await seed_stock_slip(conn, BRANCH_1, WAREHOUSE_ID), "A")
    response = await client.patch("/products/A", json={"unit": "hộp"}, headers=hq)
    assert response.status_code == 422
    assert response.json()["details"]["rule"] == "SP-04"


async def test_change_status_both_ways(
    client: httpx.AsyncClient, conn: asyncpg.Connection, hq: dict[str, str]
) -> None:
    """1.4, SP-04: Đang bán ↔ Ngừng bán; không có endpoint xóa sản phẩm."""
    await seed_product(conn, "A")
    for target in (ProductStatus.DISCONTINUED, ProductStatus.ON_SALE):
        response = await client.put("/products/A/status", json={"status": target}, headers=hq)
        assert response.status_code == 200
        assert response.json()["status"] == target
    response = await client.put(
        "/products/A/status", json={"status": ProductStatus.ON_SALE}, headers=hq
    )
    assert response.status_code == 409
    assert response.json()["error_code"] == ErrorCode.INVALID_STATE
    response = await client.put(
        "/products/KHONG/status", json={"status": ProductStatus.ON_SALE}, headers=hq
    )
    assert response.status_code == 404
    assert (await client.delete("/products/A", headers=hq)).status_code == 405


async def test_product_writes_hq_only(
    client: httpx.AsyncClient, conn: asyncpg.Connection, hq: dict[str, str]
) -> None:
    """K-01, SP-02: chỉ Trụ sở ghi sản phẩm và giá."""
    await seed_product(conn, "A")
    sales = await login_as(client, SALES_ID)
    for response in (
        await client.post("/products", json=_new("B"), headers=sales),
        await client.patch("/products/A", json={"name": "X"}, headers=sales),
        await client.put("/products/A/price", json={"price": 1}, headers=sales),
        await client.get("/products/A/price-history", headers=sales),
        await client.put(
            "/products/A/status", json={"status": ProductStatus.DISCONTINUED}, headers=sales
        ),
    ):
        assert response.status_code == 403
        assert response.json()["error_code"] == ErrorCode.FORBIDDEN
