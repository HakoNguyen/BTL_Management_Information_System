"""KT-09 Hoàn thẻ thất bại (TH-04, CA-02; chức năng 3.4, 3.5)."""

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
    TxnMethod,
    TxnStatus,
    TxnType,
)

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 13, 10, 0, tzinfo=VN_TZ)


async def test_kt09_hoan_the_that_bai(client: httpx.AsyncClient, conn: asyncpg.Connection) -> None:
    await seed_staff(conn)
    await seed_product(conn, "A")
    await seed_stock(conn, BRANCH_1, "A", 10)
    clock.freeze(NOW)
    bh = await login_as(client, SALES_ID)
    tn = await login_as(client, CASHIER_ID)
    ql = await login_as(client, MANAGER_ID)
    shift_id = await open_shift(client, tn, 500_000)

    # Phiếu trả 200.000 của đơn thanh toán thẻ
    order_id = await complete_order(client, bh, tn, {"A": 2}, TxnMethod.CARD)
    return_id = (await create_return(client, bh, order_id, {"A": (2, 0)})).json()["return_id"]
    response = await client.post(f"/returns/{return_id}/approve", json={}, headers=ql)
    assert response.status_code == 200, response.text
    assert response.json()["value"] == 200_000

    async def stock_a() -> int:
        rows = (await client.get("/stock", headers=ql)).json()
        return {row["product_id"]: row["quantity"] for row in rows}["A"]

    stock_after_approval = await stock_a()
    assert stock_after_approval == 10

    # Lần hoàn thẻ đầu tiên bị ngân hàng từ chối vì thẻ đã hủy
    first = (await client.post(f"/returns/{return_id}/refunds", headers=tn)).json()
    assert first["method"] == TxnMethod.CARD
    first = await resolve_txn(client, tn, first, TxnStatus.FAILED)

    # Phiếu vẫn Đã duyệt, tình trạng hoàn Chưa hoàn; tồn và doanh thu không bị đảo
    slip = (await client.get(f"/returns/{return_id}", headers=ql)).json()
    assert slip["status"] == ReturnStatus.APPROVED
    assert slip["refund_status"] == RefundStatus.NOT_REFUNDED
    assert await stock_a() == stock_after_approval
    order = (await client.get(f"/orders/{order_id}", headers=bh)).json()
    assert order["status"] == OrderStatus.FULLY_RETURNED
    assert order["total"] == 200_000

    # QL duyệt hoàn tiền mặt, ghi lý do
    response = await client.post(
        f"/transactions/{first['txn_id']}/approve-cash-refund",
        json={"reason": "Thẻ của khách đã hủy"},
        headers=ql,
    )
    assert response.status_code == 200, response.text

    # Giao dịch hoàn tiền mặt 200.000 Thành công
    response = await client.post(f"/returns/{return_id}/refunds", headers=tn)
    assert response.status_code == 201, response.text
    cash = await resolve_txn(client, tn, response.json(), TxnStatus.SUCCESS)
    assert (cash["method"], cash["amount"], cash["status"]) == (
        TxnMethod.CASH,
        200_000,
        TxnStatus.SUCCESS,
    )
    assert cash["cash_refund_approved_by"] == MANAGER_ID
    assert cash["cash_refund_reason"] == "Thẻ của khách đã hủy"

    # Tiền mặt kỳ vọng của ca −200.000
    shift = (await client.get(f"/shifts/{shift_id}", headers=tn)).json()
    assert shift["expected_cash"] == 500_000 - 200_000

    # Tổng hoàn Thành công = 200.000, không vượt giá trị phiếu
    refunded = await conn.fetchval(
        "SELECT sum(amount) FROM transactions WHERE return_id = $1 AND type = $2 AND status = $3",
        return_id,
        TxnType.REFUND,
        TxnStatus.SUCCESS,
    )
    assert refunded == 200_000
    response = await client.post(f"/returns/{return_id}/refunds", headers=tn)
    assert response.status_code == 409, response.text
    assert response.json()["details"]["rule"] == "TH-04"
