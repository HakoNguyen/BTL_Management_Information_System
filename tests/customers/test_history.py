"""2.4 Tra cứu lịch sử mua và trả hàng – KH-04, KH-02."""

from __future__ import annotations

from datetime import datetime, timedelta

import asyncpg
import httpx
import pytest
from fixtures import (
    BRANCH_1,
    CASHIER_ID,
    MANAGER_ID,
    SALES_ID,
    create_awaiting_order,
    create_return,
    login_as,
    open_shift,
    resolve_txn,
    seed_product,
    seed_staff,
    seed_stock,
    start_payment,
)

from common import clock
from common.clock import VN_TZ
from common.constants import OrderStatus, ReturnStatus, TxnMethod, TxnStatus

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 13, 10, 0, tzinfo=VN_TZ)
PHONE = "0901234567"


@pytest.fixture
async def world(client: httpx.AsyncClient, conn: asyncpg.Connection) -> dict:
    """Khách KH000001 có 2 đơn Hoàn tất (10:00, 11:00), 1 đơn Đang lập; đơn thứ hai có phiếu trả."""
    await seed_staff(conn)
    await seed_product(conn, "A")
    await seed_stock(conn, BRANCH_1, "A", 10)
    clock.freeze(NOW)
    bh = await login_as(client, SALES_ID)
    tn = await login_as(client, CASHIER_ID)
    ql = await login_as(client, MANAGER_ID)
    await open_shift(client, tn)
    response = await client.post(
        "/customers", json={"full_name": "Nguyễn Văn A", "phone": PHONE}, headers=bh
    )
    customer_id = response.json()["customer_id"]

    async def completed(at: datetime) -> str:
        clock.freeze(at)
        body = {"customer_id": customer_id, "items": [{"product_id": "A", "quantity": 1}]}
        order_id = (await client.post("/orders", json=body, headers=bh)).json()["order_id"]
        await client.post(f"/orders/{order_id}/confirm", headers=bh)
        txn = await start_payment(client, tn, order_id, TxnMethod.CASH)
        await resolve_txn(client, tn, txn, TxnStatus.SUCCESS)
        return order_id

    first = await completed(NOW)
    second = await completed(NOW + timedelta(hours=1))
    await client.post(
        "/orders",
        json={"customer_id": customer_id, "items": [{"product_id": "A", "quantity": 1}]},
        headers=bh,
    )
    await create_awaiting_order(client, bh, {"A": 1})  # đơn KHLE, không thuộc khách
    clock.freeze(NOW + timedelta(hours=2))
    slip = (await create_return(client, bh, second, {"A": (1, 0)})).json()
    await client.post(f"/returns/{slip['return_id']}/approve", json={}, headers=ql)
    return {
        "bh": bh,
        "tn": tn,
        "ql": ql,
        "customer_id": customer_id,
        "orders": [first, second],
        "return_id": slip["return_id"],
    }


async def _history(
    client: httpx.AsyncClient, world: dict, customer_id: str, phone: str, who: str = "bh"
):
    return await client.get(
        f"/customers/{customer_id}/history", params={"phone": phone}, headers=world[who]
    )


async def test_history(client: httpx.AsyncClient, world: dict) -> None:
    """2.4: đơn từng Hoàn tất (kể cả đã trả) và phiếu trả kèm trạng thái, mới nhất trước."""
    response = await _history(client, world, world["customer_id"], "090 123 4567")
    assert response.status_code == 200, response.text
    history = response.json()
    assert history["customer"]["customer_id"] == world["customer_id"]
    first, second = world["orders"]
    assert [o["order_id"] for o in history["orders"]] == [second, first]
    assert [o["status"] for o in history["orders"]] == [
        OrderStatus.FULLY_RETURNED,
        OrderStatus.COMPLETED,
    ]
    assert [(r["return_id"], r["status"]) for r in history["returns"]] == [
        (world["return_id"], ReturnStatus.APPROVED)
    ]


async def test_phone_must_match(client: httpx.AsyncClient, world: dict) -> None:
    """KH-04: chỉ cung cấp cho đúng khách sau khi xác minh số điện thoại."""
    response = await _history(client, world, world["customer_id"], "0909999999")
    assert response.status_code == 422, response.text
    assert response.json()["details"]["rule"] == "KH-04"
    response = await _history(client, world, world["customer_id"], "12")
    assert response.status_code == 400, response.text
    assert response.json()["details"]["rule"] == "KH-01"


async def test_walk_in_and_missing(client: httpx.AsyncClient, world: dict) -> None:
    """KH-02: không tra lịch sử cá nhân cho KHLE."""
    response = await _history(client, world, "KHLE", PHONE)
    assert response.status_code == 422, response.text
    assert response.json()["details"]["rule"] == "KH-02"
    response = await _history(client, world, "KH999999", PHONE)
    assert response.status_code == 404, response.text


async def test_history_roles(client: httpx.AsyncClient, world: dict) -> None:
    """Ma trận 2.2: chỉ NVBH tra lịch sử cho khách."""
    for who in ("tn", "ql"):
        response = await _history(client, world, world["customer_id"], PHONE, who)
        assert response.status_code == 403, response.text
        assert response.json()["details"]["rule"] == "K-01"
