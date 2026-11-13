"""Sự kiện giờ đóng cửa: `workers.closing.run_closing` (BH-05, TH-03, G-08, quyết định 9)."""

from __future__ import annotations

from datetime import datetime, time

import asyncpg
import httpx
import pytest
from fixtures import (
    BRANCH_1,
    BRANCH_2,
    CASHIER_ID,
    HQ_ID,
    MANAGER_ID,
    SALES_ID,
    complete_order,
    create_return,
    login_as,
    open_shift,
    seed_employee,
    seed_product,
    seed_staff,
    seed_stock,
)
from workers.closing import run_closing

from common import clock
from common.clock import VN_TZ
from common.constants import OrderStatus, ReturnStatus, Role

pytestmark = pytest.mark.db

SALES_2 = "NV-BH2"


def _at(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 11, day, hour, minute, tzinfo=VN_TZ)


async def _draft(client: httpx.AsyncClient, headers: dict[str, str]) -> str:
    response = await client.post(
        "/orders",
        json={"customer_id": "KHLE", "items": [{"product_id": "A", "quantity": 1}]},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["order_id"]


async def _status(client: httpx.AsyncClient, path: str) -> dict:
    headers = await login_as(client, MANAGER_ID)
    return (await client.get(path, headers=headers)).json()


@pytest.fixture
async def ready(conn: asyncpg.Connection) -> None:
    await seed_staff(conn)
    await seed_product(conn, "A")
    await seed_stock(conn, BRANCH_1, "A", 10)


async def test_documents_after_closing_wait_for_next_closing(
    client: httpx.AsyncClient, conn: asyncpg.Connection, ready: None
) -> None:
    """BH-05, TH-03, quyết định 9: chứng từ lập sau giờ đóng cửa chờ lần đóng cửa kế tiếp."""
    bh = await login_as(client, SALES_ID)
    tn = await login_as(client, CASHIER_ID)
    clock.freeze(_at(1, 10))
    await open_shift(client, tn)
    sold = await complete_order(client, bh, tn, {"A": 1})

    clock.freeze(_at(1, 22, 30))
    order_id = await _draft(client, bh)
    return_id = (await create_return(client, bh, sold, {"A": (1, 0)})).json()["return_id"]
    await run_closing(conn, clock.now())
    assert (await _status(client, f"/orders/{order_id}"))["status"] == OrderStatus.DRAFT
    assert (await _status(client, f"/returns/{return_id}"))["status"] == ReturnStatus.PENDING

    await run_closing(conn, _at(2, 21, 59))
    assert (await _status(client, f"/orders/{order_id}"))["status"] == OrderStatus.DRAFT

    await run_closing(conn, _at(2, 22))
    order = await _status(client, f"/orders/{order_id}")
    assert order["status"] == OrderStatus.CANCELLED
    assert (await _status(client, f"/returns/{return_id}"))["status"] == ReturnStatus.REJECTED
    # đơn Hoàn tất không bị đụng tới
    assert (await _status(client, f"/orders/{sold}"))["status"] == OrderStatus.COMPLETED

    # chạy lại không đổi kết quả đã ghi
    await run_closing(conn, _at(2, 22, 5))
    again = await _status(client, f"/orders/{order_id}")
    assert again["cancelled_at"] == order["cancelled_at"]


async def test_each_branch_closes_at_its_own_time(
    client: httpx.AsyncClient, conn: asyncpg.Connection, ready: None
) -> None:
    """G-08, BH-05: CN2 đóng 20:00, CN1 đóng 22:00; lúc 21:00 chỉ đơn CN2 bị hủy."""
    await seed_employee(conn, SALES_2, Role.SALES, BRANCH_2)
    await seed_stock(conn, BRANCH_2, "A", 10)
    hq = await login_as(client, HQ_ID)
    response = await client.patch(
        f"/branches/{BRANCH_2}", json={"closing_time": time(20, 0).isoformat()}, headers=hq
    )
    assert response.status_code == 200, response.text

    clock.freeze(_at(1, 10))
    bh1, bh2 = await login_as(client, SALES_ID), await login_as(client, SALES_2)
    first, second = await _draft(client, bh1), await _draft(client, bh2)

    await run_closing(conn, _at(1, 21))
    assert (await client.get(f"/orders/{first}", headers=bh1)).json()["status"] == OrderStatus.DRAFT
    order = (await client.get(f"/orders/{second}", headers=bh2)).json()
    assert order["status"] == OrderStatus.CANCELLED
    assert order["cancel_reason"] == "Quá hạn"
