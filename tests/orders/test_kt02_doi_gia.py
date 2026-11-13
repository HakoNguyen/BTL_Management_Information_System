"""KT-02 Đổi giá (SP-02, SP-03, BH-02, BH-03; chức năng 1.3, 3.1).

Ý "trả 1 A của X được hoàn 100.000" (TH-04) bổ sung ở vòng 7.
"""

from __future__ import annotations

from datetime import datetime

import asyncpg
import httpx
import pytest
from fixtures import BRANCH_1, HQ_ID, SALES_ID, login_as, seed_product, seed_staff, seed_stock

from common import clock
from common.clock import VN_TZ

pytestmark = pytest.mark.db


def _at(hour: int, minute: int) -> datetime:
    return datetime(2026, 11, 13, hour, minute, tzinfo=VN_TZ)


async def test_kt02_doi_gia(client: httpx.AsyncClient, conn: asyncpg.Connection) -> None:
    await seed_staff(conn)
    await seed_product(conn, "A")
    await seed_stock(conn, BRANCH_1, "A", 10)
    bh = await login_as(client, SALES_ID)
    hq = await login_as(client, HQ_ID)

    async def order(quantity: int) -> str:
        body = {"customer_id": "KHLE", "items": [{"product_id": "A", "quantity": quantity}]}
        response = await client.post("/orders", json=body, headers=bh)
        assert response.status_code == 201, response.text
        return response.json()["order_id"]

    async def confirm(order_id: str) -> dict:
        response = await client.post(f"/orders/{order_id}/confirm", headers=bh)
        assert response.status_code == 200, response.text
        return response.json()

    # 9:00 chốt X: 2 A giá 100.000
    clock.freeze(_at(9, 0))
    x = await order(2)
    assert (await confirm(x))["total"] == 200_000

    # 9:30 trụ sở đổi giá thành 110.000: lịch sử giá có thêm một bản ghi
    clock.freeze(_at(9, 30))
    response = await client.put("/products/A/price", json={"price": 110_000}, headers=hq)
    assert response.status_code == 200, response.text
    history = (await client.get("/products/A/price-history", headers=hq)).json()
    assert [entry["price"] for entry in history] == [100_000, 110_000]

    # 9:45 chốt Y: 1 A dùng giá 110.000
    clock.freeze(_at(9, 45))
    y = await confirm(await order(1))
    assert y["items"][0]["unit_price"] == 110_000
    assert y["total"] == 110_000

    # X vẫn 200.000
    x_now = (await client.get(f"/orders/{x}", headers=bh)).json()
    assert x_now["items"][0]["unit_price"] == 100_000
    assert x_now["total"] == 200_000

    # X mở lại và chốt lại sau 9:30 thì thành 220.000
    clock.freeze(_at(10, 0))
    response = await client.post(f"/orders/{x}/reopen", headers=bh)
    assert response.status_code == 200, response.text
    assert response.json()["total"] is None
    x_again = await confirm(x)
    assert x_again["items"][0]["unit_price"] == 110_000
    assert x_again["total"] == 220_000
    assert datetime.fromisoformat(x_again["confirmed_at"]) == _at(10, 0)
