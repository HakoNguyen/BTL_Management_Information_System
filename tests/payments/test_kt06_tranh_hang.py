"""KT-06 Tranh hàng cuối cùng (TK-01, TK-03, TT-03; chức năng 3.2, 4.3).

Hai nhánh kết quả của P (thành công, thất bại) chạy thành hai lần test.
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
    bank_callback,
    create_awaiting_order,
    login_as,
    open_shift,
    seed_employee,
    seed_product,
    seed_staff,
    seed_stock,
    start_payment,
)

from common import clock
from common.clock import VN_TZ
from common.constants import ErrorCode, OrderStatus, Role, SlipStatus, TxnMethod, TxnStatus

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 13, 10, 0, tzinfo=VN_TZ)
CASHIER_2 = "NV-TN2"


async def _stock(client: httpx.AsyncClient, headers: dict[str, str]) -> tuple[int, int]:
    (row,) = (await client.get("/stock", headers=headers)).json()
    return row["quantity"], row["available"]


@pytest.mark.parametrize("p_result", [TxnStatus.SUCCESS, TxnStatus.FAILED])
async def test_kt06_tranh_hang(
    client: httpx.AsyncClient, conn: asyncpg.Connection, p_result: TxnStatus
) -> None:
    await seed_staff(conn)
    await seed_employee(conn, CASHIER_2, Role.CASHIER, BRANCH_1)
    await seed_product(conn, "A")
    await seed_stock(conn, BRANCH_1, "A", 1)
    clock.freeze(NOW)
    bh = await login_as(client, SALES_ID)
    tn1 = await login_as(client, CASHIER_ID)
    tn2 = await login_as(client, CASHIER_2)
    await open_shift(client, tn1)
    await open_shift(client, tn2)
    p = await create_awaiting_order(client, bh, {"A": 1})
    q = await create_awaiting_order(client, bh, {"A": 1})

    # Thu ngân 1 khởi tạo chuyển khoản cho P: P giữ được hàng, tồn khả dụng = 0
    txn_p = await start_payment(client, tn1, p, TxnMethod.TRANSFER)
    assert await _stock(client, bh) == (1, 0)
    # Thu ngân 2 khởi tạo tiền mặt cho Q: bị từ chối giữ hàng, không tạo giao dịch
    response = await client.post(
        f"/orders/{q}/payments", json={"method": TxnMethod.CASH}, headers=tn2
    )
    assert response.json()["error_code"] == ErrorCode.INSUFFICIENT_STOCK
    assert response.json()["details"]["rule"] == "TK-03"
    assert await conn.fetchval("SELECT count(*) FROM transactions WHERE order_id = $1", q) == 0
    assert (await client.get(f"/orders/{q}", headers=bh)).json()["status"] == (
        OrderStatus.AWAITING_PAYMENT
    )

    reference = "REF-P" if p_result == TxnStatus.SUCCESS else None
    response = await bank_callback(client, txn_p["txn_id"], p_result, reference)
    assert response.status_code == 200, response.text
    if p_result == TxnStatus.SUCCESS:
        # P thành công thì tồn = 0
        assert await _stock(client, bh) == (0, 0)
    else:
        # P thất bại thì hàng được giải phóng và Q thu được
        assert await _stock(client, bh) == (1, 1)
        txn_q = await start_payment(client, tn2, q, TxnMethod.CASH)
        response = await client.post(
            f"/transactions/{txn_q['txn_id']}/confirm-cash",
            json={"result": "SUCCESS"},
            headers=tn2,
        )
        assert response.status_code == 200, response.text
        assert await _stock(client, bh) == (0, 0)

    # Không có đơn đã thu tiền mà thiếu hàng; tồn không âm
    paid = await conn.fetch(
        "SELECT order_id FROM transactions WHERE status = $1 ORDER BY order_id", TxnStatus.SUCCESS
    )
    posted = await conn.fetch(
        "SELECT order_id FROM stock_slips WHERE status = $1 ORDER BY order_id", SlipStatus.POSTED
    )
    assert [r["order_id"] for r in paid] == [r["order_id"] for r in posted]
    assert len(paid) == 1
    assert await conn.fetchval("SELECT min(quantity) FROM stock") >= 0
