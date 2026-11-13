"""KT-07 Cuối ngày (BH-05, TH-03; chức năng 3.4, sự kiện giờ đóng cửa)."""

from __future__ import annotations

from datetime import datetime

import asyncpg
import httpx
import pytest
from fixtures import (
    BRANCH_1,
    CASHIER_ID,
    MANAGER_ID,
    SALES_ID,
    complete_order,
    create_awaiting_order,
    create_return,
    login_as,
    open_shift,
    seed_product,
    seed_staff,
    seed_stock,
    start_payment,
)
from workers.closing import run_closing

from common import clock
from common.clock import VN_TZ
from common.constants import OrderStatus, ReturnStatus, TxnMethod, TxnStatus

pytestmark = pytest.mark.db


async def test_kt07_cuoi_ngay(client: httpx.AsyncClient, conn: asyncpg.Connection) -> None:
    # CN1 đóng cửa 22:00 (seed_branch)
    await seed_staff(conn)
    await seed_product(conn, "A")
    await seed_stock(conn, BRANCH_1, "A", 10)
    bh = await login_as(client, SALES_ID)
    tn = await login_as(client, CASHIER_ID)
    ql = await login_as(client, MANAGER_ID)

    clock.freeze(datetime(2026, 11, 1, 10, 0, tzinfo=VN_TZ))
    shift_id = await open_shift(client, tn)
    sold = await complete_order(client, bh, tn, {"A": 1})
    response = await create_return(client, bh, sold, {"A": (1, 0)})
    assert response.status_code == 201, response.text
    r = response.json()["return_id"]

    clock.freeze(datetime(2026, 11, 1, 15, 0, tzinfo=VN_TZ))
    response = await client.post(
        "/orders",
        json={"customer_id": "KHLE", "items": [{"product_id": "A", "quantity": 1}]},
        headers=bh,
    )
    m = response.json()["order_id"]
    n = await create_awaiting_order(client, bh, {"A": 1})
    o = await create_awaiting_order(client, bh, {"A": 1})
    pending = await start_payment(client, tn, o, TxnMethod.TRANSFER)
    assert pending["status"] == TxnStatus.PENDING

    closing_at = datetime(2026, 11, 1, 22, 0, tzinfo=VN_TZ)
    clock.freeze(closing_at)
    await run_closing(conn, clock.now())

    # M, N chuyển Đã hủy, lý do Quá hạn, người hủy Hệ thống
    for order_id in (m, n):
        order = (await client.get(f"/orders/{order_id}", headers=ql)).json()
        assert order["status"] == OrderStatus.CANCELLED
        assert order["cancel_reason"] == "Quá hạn"
        assert order["cancelled_by"] is None
        assert datetime.fromisoformat(order["cancelled_at"]) == closing_at

    # O giữ nguyên, nằm trong danh sách tra soát của ca
    order = (await client.get(f"/orders/{o}", headers=ql)).json()
    assert order["status"] == OrderStatus.AWAITING_PAYMENT
    shift = (await client.get(f"/shifts/{shift_id}", headers=ql)).json()
    assert [t["txn_id"] for t in shift["pending"]] == [pending["txn_id"]]
    assert shift["pending"][0]["order_id"] == o

    # R chuyển Từ chối, lý do Quá hạn duyệt
    slip = (await client.get(f"/returns/{r}", headers=ql)).json()
    assert slip["status"] == ReturnStatus.REJECTED
    assert slip["decision_note"] == "Quá hạn duyệt"
    assert slip["decided_by"] is None
