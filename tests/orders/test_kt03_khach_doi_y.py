"""KT-03 Khách đổi ý (BH-03, BH-04; chức năng 3.1, 3.4)."""

from __future__ import annotations

from datetime import datetime

import asyncpg
import httpx
import pytest
from fixtures import (
    BRANCH_1,
    CASHIER_ID,
    SALES_ID,
    login_as,
    open_shift,
    seed_product,
    seed_staff,
    seed_stock,
    start_payment,
)

from common import clock
from common.clock import VN_TZ
from common.constants import ErrorCode, OrderStatus, TxnMethod

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 13, 10, 0, tzinfo=VN_TZ)


async def _stock(client: httpx.AsyncClient, headers: dict[str, str]) -> list[dict]:
    response = await client.get("/stock", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def _new_awaiting(client: httpx.AsyncClient, headers: dict[str, str]) -> str:
    body = {"customer_id": "KHLE", "items": [{"product_id": "A", "quantity": 1}]}
    response = await client.post("/orders", json=body, headers=headers)
    assert response.status_code == 201, response.text
    order_id = response.json()["order_id"]
    response = await client.post(f"/orders/{order_id}/confirm", headers=headers)
    assert response.json()["status"] == OrderStatus.AWAITING_PAYMENT
    return order_id


async def test_kt03_khach_doi_y(client: httpx.AsyncClient, conn: asyncpg.Connection) -> None:
    await seed_staff(conn)
    await seed_product(conn, "A")
    await seed_product(conn, "B")
    await seed_stock(conn, BRANCH_1, "A", 5)
    await seed_stock(conn, BRANCH_1, "B", 5)
    clock.freeze(NOW)
    bh = await login_as(client, SALES_ID)
    stock_before = await _stock(client, bh)

    # Z Chờ thanh toán, chưa có giao dịch; khách muốn thêm 1 B: mở lại, thêm B, chốt lại
    z = await _new_awaiting(client, bh)
    response = await client.post(f"/orders/{z}/reopen", headers=bh)
    assert response.json()["status"] == OrderStatus.DRAFT
    items = [{"product_id": "A", "quantity": 1}, {"product_id": "B", "quantity": 1}]
    response = await client.put(f"/orders/{z}/items", json={"items": items}, headers=bh)
    assert response.status_code == 200, response.text
    response = await client.post(f"/orders/{z}/confirm", headers=bh)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == OrderStatus.AWAITING_PAYMENT
    assert response.json()["total"] == 200_000

    # Khách bỏ về: NVBH hủy Z, ghi lý do; tồn và doanh thu không đổi, không có hoàn tiền
    response = await client.post(f"/orders/{z}/cancel", json={"reason": "Khách bỏ về"}, headers=bh)
    assert response.status_code == 200, response.text
    cancelled = response.json()
    assert cancelled["status"] == OrderStatus.CANCELLED
    assert cancelled["cancel_reason"] == "Khách bỏ về"
    assert cancelled["cancelled_by"] == SALES_ID
    assert await _stock(client, bh) == stock_before
    assert await conn.fetchval("SELECT count(*) FROM transactions") == 0
    assert await conn.fetchval("SELECT count(*) FROM stock_slips") == 0

    # Z đang có giao dịch Chờ kết quả thì không mở lại hay hủy được
    z2 = await _new_awaiting(client, bh)
    tn = await login_as(client, CASHIER_ID)
    await open_shift(client, tn)
    await start_payment(client, tn, z2, TxnMethod.TRANSFER)
    for response in (
        await client.post(f"/orders/{z2}/reopen", headers=bh),
        await client.post(f"/orders/{z2}/cancel", json={"reason": "Khách bỏ về"}, headers=bh),
    ):
        assert response.json()["error_code"] == ErrorCode.INVALID_STATE
    order = (await client.get(f"/orders/{z2}", headers=bh)).json()
    assert order["status"] == OrderStatus.AWAITING_PAYMENT
