"""1.2 Phân loại sản phẩm (SP-01). Không thuộc 16 tình huống KT."""

from __future__ import annotations

import asyncpg
import httpx
import pytest
from fixtures import GROUP_ID, HQ_ID, MANAGER_ID, SALES_ID, login_as, seed_product, seed_staff

from common.constants import ErrorCode, ProductStatus

pytestmark = pytest.mark.db


@pytest.fixture
async def hq(client: httpx.AsyncClient, conn: asyncpg.Connection) -> dict[str, str]:
    await seed_staff(conn)
    return await login_as(client, HQ_ID)


def _group(group_id: str, **overrides: object) -> dict[str, object]:
    return {"group_id": group_id, "name": f"Nhóm {group_id}", "description": None, **overrides}


async def test_create_and_list_groups_any_role(
    client: httpx.AsyncClient, hq: dict[str, str]
) -> None:
    """SP-01."""
    response = await client.post("/product-groups", json=_group("N2"), headers=hq)
    assert response.status_code == 201
    assert response.json() == _group("N2")
    await client.post("/product-groups", json=_group("N1", description="Đồ uống"), headers=hq)
    response = await client.get("/product-groups", headers=await login_as(client, SALES_ID))
    assert response.status_code == 200
    assert response.json() == [_group("N1", description="Đồ uống"), _group("N2")]


async def test_create_group_duplicate(client: httpx.AsyncClient, hq: dict[str, str]) -> None:
    """SP-01: mã nhóm duy nhất."""
    assert (await client.post("/product-groups", json=_group("N1"), headers=hq)).status_code == 201
    response = await client.post("/product-groups", json=_group("N1", name="Khác"), headers=hq)
    assert response.status_code == 409
    assert response.json()["error_code"] == ErrorCode.DUPLICATE
    assert response.json()["details"]["rule"] == "SP-01"


async def test_update_group(client: httpx.AsyncClient, hq: dict[str, str]) -> None:
    """SP-01: chỉ đổi tên, mô tả; mã giữ nguyên."""
    await client.post("/product-groups", json=_group("N1"), headers=hq)
    response = await client.patch(
        "/product-groups/N1", json={"name": "Bánh kẹo", "group_id": "N9"}, headers=hq
    )
    assert response.status_code == 200
    assert response.json() == _group("N1", name="Bánh kẹo")
    response = await client.patch("/product-groups/KHONG", json={"name": "X"}, headers=hq)
    assert response.json()["error_code"] == ErrorCode.NOT_FOUND


async def test_delete_empty_group(client: httpx.AsyncClient, hq: dict[str, str]) -> None:
    await client.post("/product-groups", json=_group("N1"), headers=hq)
    response = await client.delete("/product-groups/N1", headers=hq)
    assert response.status_code == 200
    assert response.json() == _group("N1")
    assert (await client.get("/product-groups", headers=hq)).json() == []
    response = await client.delete("/product-groups/N1", headers=hq)
    assert response.json()["error_code"] == ErrorCode.NOT_FOUND


async def test_delete_group_with_products_rejected(
    client: httpx.AsyncClient, conn: asyncpg.Connection, hq: dict[str, str]
) -> None:
    """SP-01: không xóa nhóm còn sản phẩm, kể cả sản phẩm Ngừng bán."""
    await seed_product(conn, "A")
    await client.put("/products/A/status", json={"status": ProductStatus.DISCONTINUED}, headers=hq)
    response = await client.delete(f"/product-groups/{GROUP_ID}", headers=hq)
    assert response.status_code == 422
    assert response.json()["error_code"] == ErrorCode.RULE_VIOLATION
    assert response.json()["details"]["rule"] == "SP-01"
    assert await conn.fetchval("SELECT 1 FROM product_groups WHERE group_id = $1", GROUP_ID)


async def test_change_product_group(
    client: httpx.AsyncClient, conn: asyncpg.Connection, hq: dict[str, str]
) -> None:
    """SP-01: mỗi sản phẩm thuộc đúng một nhóm; gán sang nhóm khác rồi nhóm cũ xóa được."""
    await seed_product(conn, "A")
    await client.post("/product-groups", json=_group("N2"), headers=hq)
    response = await client.put("/products/A/group", json={"group_id": "N2"}, headers=hq)
    assert response.status_code == 200
    assert response.json()["group_id"] == "N2"
    assert (await client.delete(f"/product-groups/{GROUP_ID}", headers=hq)).status_code == 200


async def test_change_product_group_not_found(
    client: httpx.AsyncClient, conn: asyncpg.Connection, hq: dict[str, str]
) -> None:
    await seed_product(conn, "A")
    response = await client.put("/products/A/group", json={"group_id": "KHONG"}, headers=hq)
    assert response.status_code == 404
    response = await client.put("/products/KHONG/group", json={"group_id": GROUP_ID}, headers=hq)
    assert response.status_code == 404


async def test_group_writes_hq_only(
    client: httpx.AsyncClient, conn: asyncpg.Connection, hq: dict[str, str]
) -> None:
    """K-01: chỉ Trụ sở ghi danh mục."""
    await seed_product(conn, "A")
    manager = await login_as(client, MANAGER_ID)
    for response in (
        await client.post("/product-groups", json=_group("N2"), headers=manager),
        await client.patch(f"/product-groups/{GROUP_ID}", json={"name": "X"}, headers=manager),
        await client.delete(f"/product-groups/{GROUP_ID}", headers=manager),
        await client.put("/products/A/group", json={"group_id": GROUP_ID}, headers=manager),
    ):
        assert response.status_code == 403
        assert response.json()["error_code"] == ErrorCode.FORBIDDEN
