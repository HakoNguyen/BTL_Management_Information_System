"""KT-12 Nhập nhầm và nhập trùng (TK-01 đến TK-04; chức năng 4.2, 4.3)."""

from __future__ import annotations

from datetime import datetime

import asyncpg
import httpx
import pytest
from fixtures import (
    BRANCH_1,
    MANAGER_ID,
    WAREHOUSE_ID,
    login_as,
    seed_product,
    seed_staff,
    seed_stock,
)

from common import clock
from common.clock import VN_TZ
from common.constants import ErrorCode, SlipStatus

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 13, 10, 0, tzinfo=VN_TZ)


async def _stock_a(client: httpx.AsyncClient, headers: dict[str, str]) -> dict:
    response = await client.get("/stock", headers=headers)
    assert response.status_code == 200, response.text
    return next(row for row in response.json() if row["product_id"] == "A")


async def test_kt12_nhap_nham_va_nhap_trung(
    client: httpx.AsyncClient, conn: asyncpg.Connection
) -> None:
    await seed_staff(conn)
    await seed_product(conn, "A")
    await seed_stock(conn, BRANCH_1, "A", 2)
    clock.freeze(NOW)
    kho = await login_as(client, WAREHOUSE_ID)
    ql = await login_as(client, MANAGER_ID)

    # Phiếu giao PG-0815 ghi 5 A; NV kho nhập nhầm 50 -> tồn = 52
    inbound = {
        "type": "IN_WAREHOUSE",
        "counterparty": "Kho tổng",
        "delivery_no": "PG-0815",
        "items": [{"product_id": "A", "quantity": 50}],
    }
    response = await client.post("/stock-slips/inbound", json=inbound, headers=kho)
    assert response.status_code == 201, response.text
    original = response.json()
    assert original["status"] == SlipStatus.POSTED
    assert (await _stock_a(client, kho))["quantity"] == 52

    # Nhập lại PG-0815 bị từ chối vì trùng; tồn giữ 52
    response = await client.post("/stock-slips/inbound", json=inbound, headers=kho)
    assert response.status_code == 409, response.text
    assert response.json()["error_code"] == ErrorCode.DUPLICATE
    assert response.json()["details"]["rule"] == "TK-02"
    assert (await _stock_a(client, kho))["quantity"] == 52

    # Điều chỉnh giảm 45 tham chiếu phiếu nhập sai; chờ duyệt thì tồn khả dụng = 7
    adjust = {
        "type": "ADJUST_DOWN",
        "reason": "Nhập nhầm số lượng PG-0815",
        "adjusts_slip_id": original["slip_id"],
        "items": [{"product_id": "A", "quantity": 45}],
    }
    response = await client.post("/stock-slips", json=adjust, headers=kho)
    assert response.status_code == 201, response.text
    slip = response.json()
    assert slip["status"] == SlipStatus.PENDING
    assert slip["adjusts_slip_id"] == original["slip_id"]
    assert await _stock_a(client, kho) == {
        "product_id": "A", "quantity": 52, "available": 7, "min_level": None,
    }  # fmt: skip

    # QL duyệt thì tồn = 7
    response = await client.post(f"/stock-slips/{slip['slip_id']}/approve", headers=ql)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == SlipStatus.POSTED
    assert response.json()["approved_by"] == MANAGER_ID
    stock = await _stock_a(client, kho)
    assert (stock["quantity"], stock["available"]) == (7, 7)

    # Phiếu nhập gốc không bị sửa hay xóa
    response = await client.get(f"/stock-slips/{original['slip_id']}", headers=ql)
    assert response.status_code == 200, response.text
    assert response.json() == original
