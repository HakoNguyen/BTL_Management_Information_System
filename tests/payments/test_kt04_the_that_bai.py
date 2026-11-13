"""KT-04 Thẻ thất bại rồi thành công (TT-02, TT-03, TK-03; chức năng 3.2, 4.3, 3.3)."""

from __future__ import annotations

from datetime import datetime

import asyncpg
import httpx
import pytest
from fixtures import (
    BRANCH_1,
    CASHIER_ID,
    SALES_ID,
    bank_callback,
    create_awaiting_order,
    login_as,
    open_shift,
    seed_product,
    seed_staff,
    seed_stock,
    start_payment,
)

from common import clock
from common.clock import VN_TZ
from common.constants import OrderStatus, SlipStatus, TxnMethod, TxnStatus

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 13, 10, 0, tzinfo=VN_TZ)


async def test_kt04_the_that_bai(client: httpx.AsyncClient, conn: asyncpg.Connection) -> None:
    await seed_staff(conn)
    await seed_product(conn, "A")
    await seed_stock(conn, BRANCH_1, "A", 10)
    clock.freeze(NOW)
    bh = await login_as(client, SALES_ID)
    tn = await login_as(client, CASHIER_ID)
    shift_id = await open_shift(client, tn, 300_000)
    order_id = await create_awaiting_order(client, bh, {"A": 5})

    # Lần 1: thẻ bị từ chối -> giao dịch Thất bại, phiếu xuất bán Đã hủy, đơn vẫn Chờ thanh toán
    first = await start_payment(client, tn, order_id, TxnMethod.CARD)
    assert first["amount"] == 500_000
    response = await bank_callback(client, first["txn_id"], TxnStatus.FAILED)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == TxnStatus.FAILED
    slip_status = await conn.fetchval(
        "SELECT status FROM stock_slips WHERE order_id = $1", order_id
    )
    assert slip_status == SlipStatus.CANCELLED
    order = (await client.get(f"/orders/{order_id}", headers=bh)).json()
    assert order["status"] == OrderStatus.AWAITING_PAYMENT

    # Lần 2: thành công -> Hoàn tất
    second = await start_payment(client, tn, order_id, TxnMethod.CARD)
    response = await bank_callback(client, second["txn_id"], TxnStatus.SUCCESS, "REF-THE-2")
    assert response.status_code == 200, response.text
    order = (await client.get(f"/orders/{order_id}", headers=bh)).json()
    assert order["status"] == OrderStatus.COMPLETED

    # Đơn có 2 giao dịch (1 Thất bại, 1 Thành công), 1 hóa đơn, doanh thu 500.000
    statuses = await conn.fetch(
        "SELECT status FROM transactions WHERE order_id = $1 ORDER BY txn_id", order_id
    )
    assert [r["status"] for r in statuses] == [TxnStatus.FAILED, TxnStatus.SUCCESS]
    assert await conn.fetchval("SELECT count(*) FROM invoices WHERE order_id = $1", order_id) == 1
    assert order["total"] == 500_000
    # Tiền mặt ca không đổi
    shift = (await client.get(f"/shifts/{shift_id}", headers=tn)).json()
    assert shift["expected_cash"] == 300_000
