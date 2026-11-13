"""KT-08 Trả hàng tốt và lỗi (TH-01 đến TH-05, TK-02; chức năng 3.4, 4.2)."""

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
    create_return,
    login_as,
    open_shift,
    resolve_txn,
    seed_product,
    seed_staff,
    seed_stock,
)

from common import clock
from common.clock import VN_TZ
from common.constants import (
    OrderStatus,
    RefundStatus,
    ReturnStatus,
    SlipStatus,
    SlipType,
    TxnMethod,
    TxnStatus,
)

pytestmark = pytest.mark.db


def _day(day: int, hour: int = 10) -> datetime:
    return datetime(2026, 11, day, hour, 0, tzinfo=VN_TZ)


async def test_kt08_tra_hang(client: httpx.AsyncClient, conn: asyncpg.Connection) -> None:
    await seed_staff(conn)
    await seed_product(conn, "A")
    await seed_stock(conn, BRANCH_1, "A", 10)
    bh = await login_as(client, SALES_ID)
    tn = await login_as(client, CASHIER_ID)
    ql = await login_as(client, MANAGER_ID)

    # Đơn 3 A giá 100.000, thanh toán thẻ, Hoàn tất 10:00 ngày 01/11
    clock.freeze(_day(1))
    await open_shift(client, tn)
    order_id = await complete_order(client, bh, tn, {"A": 3}, TxnMethod.CARD)

    async def stock_a() -> int:
        rows = (await client.get("/stock", headers=ql)).json()
        return {row["product_id"]: row["quantity"] for row in rows}["A"]

    assert await stock_a() == 7

    # Ngày 04/11 khách trả 1 tốt, 1 lỗi; QL duyệt
    clock.freeze(_day(4))
    response = await create_return(client, bh, order_id, {"A": (1, 1)})
    assert response.status_code == 201, response.text
    return_id = response.json()["return_id"]
    # Phiếu trả giá trị 200.000
    assert response.json()["value"] == 200_000
    response = await client.post(f"/returns/{return_id}/approve", json={}, headers=ql)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == ReturnStatus.APPROVED

    # Phiếu nhập hàng trả 1 A, tồn +1; hàng lỗi không vào tồn
    slips = await conn.fetch(
        "SELECT s.type, s.status, i.product_id, i.quantity FROM stock_slips s"
        " JOIN stock_slip_items i USING (slip_id) WHERE s.return_id = $1",
        return_id,
    )
    assert [(r["type"], r["status"], r["product_id"], r["quantity"]) for r in slips] == [
        (SlipType.IN_RETURN, SlipStatus.POSTED, "A", 1)
    ]
    assert await stock_a() == 8

    # Đơn Đã trả một phần
    order = (await client.get(f"/orders/{order_id}", headers=bh)).json()
    assert order["status"] == OrderStatus.PARTIALLY_RETURNED

    # Thu ngân hoàn thẻ 200.000
    response = await client.post(f"/returns/{return_id}/refunds", headers=tn)
    assert response.status_code == 201, response.text
    refund = response.json()
    assert (refund["method"], refund["amount"]) == (TxnMethod.CARD, 200_000)
    refund = await resolve_txn(client, tn, refund, TxnStatus.SUCCESS)
    assert refund["status"] == TxnStatus.SUCCESS
    slip = (await client.get(f"/returns/{return_id}", headers=ql)).json()
    assert slip["refund_status"] == RefundStatus.REFUNDED

    # Ngày 06/11 còn trong hạn và còn 1 A nên được lập phiếu
    clock.freeze(_day(6))
    response = await create_return(client, bh, order_id, {"A": (1, 0)})
    assert response.status_code == 201, response.text

    # Ngày 09/11 đã quá 10:00 ngày 08/11 nên bị từ chối
    clock.freeze(_day(9))
    response = await create_return(client, bh, order_id, {"A": (1, 0)})
    assert response.status_code == 422, response.text
    assert response.json()["error_code"] == "RULE_VIOLATION"
    assert response.json()["details"]["rule"] == "TH-01"
