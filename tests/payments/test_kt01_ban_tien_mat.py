"""KT-01 Bán tiền mặt (BH-02, TT-01 đến TT-04, TK-03; chức năng 3.1, 4.1, 3.2, 4.3, 3.3).

Doanh thu gộp tính ở báo cáo 5.1 (vòng 9); ở đây kiểm bằng tổng của đơn Hoàn tất.
"""

from __future__ import annotations

from datetime import datetime

import asyncpg
import httpx
import pytest
from fixtures import (
    BRANCH_1,
    CASHIER_ID,
    SALES_ID,
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
from common.constants import OrderStatus, SlipStatus, SlipType, TxnMethod, TxnStatus, TxnType

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 13, 10, 0, tzinfo=VN_TZ)


async def test_kt01_ban_tien_mat(client: httpx.AsyncClient, conn: asyncpg.Connection) -> None:
    await seed_staff(conn)
    await seed_product(conn, "A")
    await seed_stock(conn, BRANCH_1, "A", 5)
    clock.freeze(NOW)
    bh = await login_as(client, SALES_ID)
    tn = await login_as(client, CASHIER_ID)
    shift_id = await open_shift(client, tn, 500_000)

    order_id = await create_awaiting_order(client, bh, {"A": 2})
    txn = await start_payment(client, tn, order_id, TxnMethod.CASH)
    assert txn["amount"] == 200_000
    assert txn["type"] == TxnType.COLLECT
    assert txn["shift_id"] == shift_id
    assert txn["status"] == TxnStatus.PENDING
    response = await client.post(
        f"/transactions/{txn['txn_id']}/confirm-cash", json={"result": "SUCCESS"}, headers=tn
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == TxnStatus.SUCCESS

    # Đơn Hoàn tất 200.000
    order = (await client.get(f"/orders/{order_id}", headers=bh)).json()
    assert order["status"] == OrderStatus.COMPLETED
    assert order["total"] == 200_000
    assert order["completed_at"] is not None
    # Một phiếu xuất bán Đã ghi nhận, tồn = 3
    slips = await conn.fetch("SELECT type, status FROM stock_slips WHERE order_id = $1", order_id)
    assert [(s["type"], s["status"]) for s in slips] == [(SlipType.OUT_SALE, SlipStatus.POSTED)]
    stock = (await client.get("/stock", headers=bh)).json()
    assert [(s["product_id"], s["quantity"]) for s in stock] == [("A", 3)]
    # Một giao dịch thu Thành công
    rows = await conn.fetch("SELECT type, status FROM transactions WHERE order_id = $1", order_id)
    assert [(r["type"], r["status"]) for r in rows] == [(TxnType.COLLECT, TxnStatus.SUCCESS)]
    # Một hóa đơn
    assert await conn.fetchval("SELECT count(*) FROM invoices WHERE order_id = $1", order_id) == 1
    invoice = (await client.get(f"/orders/{order_id}/invoice", headers=tn)).json()
    assert invoice["total"] == 200_000
    assert invoice["method"] == TxnMethod.CASH
    # Doanh thu gộp +200.000
    revenue = await conn.fetchval(
        "SELECT sum(i.quantity * i.unit_price) FROM order_items i JOIN orders o USING (order_id)"
        " WHERE o.status = $1",
        OrderStatus.COMPLETED,
    )
    assert revenue == 200_000
    # Tiền mặt kỳ vọng của ca +200.000
    shift = (await client.get(f"/shifts/{shift_id}", headers=tn)).json()
    assert shift["expected_cash"] == 500_000 + 200_000
