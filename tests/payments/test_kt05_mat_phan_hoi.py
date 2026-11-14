"""KT-05 Mất phản hồi, phản hồi lặp (TT-02, TT-03, BH-05, CA-02, CA-03).

Chức năng 3.2, 4.3, 3.3, 3.5. Ý "đơn không bị hủy kể cả lúc đóng cửa" kiểm cả hủy tay (BH-04) lẫn
tác vụ giờ đóng cửa `run_closing` (BH-05).
"""

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
    bank_callback,
    create_awaiting_order,
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
from common.constants import (
    ErrorCode,
    OrderStatus,
    ShiftStatus,
    SlipStatus,
    TxnMethod,
    TxnStatus,
)

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 13, 10, 0, tzinfo=VN_TZ)
CLOSING = datetime(2026, 11, 13, 22, 0, tzinfo=VN_TZ)  # giờ đóng cửa mặc định của seed_branch


async def _counts(conn: asyncpg.Connection, order_id: str) -> tuple[int, int, int]:
    return (
        await conn.fetchval(
            "SELECT count(*) FROM transactions WHERE order_id = $1 AND status = $2",
            order_id,
            TxnStatus.SUCCESS,
        ),
        await conn.fetchval(
            "SELECT count(*) FROM stock_slips WHERE order_id = $1 AND status = $2",
            order_id,
            SlipStatus.POSTED,
        ),
        await conn.fetchval("SELECT count(*) FROM invoices WHERE order_id = $1", order_id),
    )


async def test_kt05_mat_phan_hoi(client: httpx.AsyncClient, conn: asyncpg.Connection) -> None:
    await seed_staff(conn)
    await seed_product(conn, "A")
    await seed_stock(conn, BRANCH_1, "A", 5)
    clock.freeze(NOW)
    bh = await login_as(client, SALES_ID)
    tn = await login_as(client, CASHIER_ID)
    ql = await login_as(client, MANAGER_ID)
    shift_id = await open_shift(client, tn)
    order_id = await create_awaiting_order(client, bh, {"A": 3})

    # Chuyển khoản 300.000, ngân hàng không phản hồi (không có BANK_URL: không ai gọi lại)
    txn = await start_payment(client, tn, order_id, TxnMethod.TRANSFER)
    assert txn["amount"] == 300_000

    # Trong lúc chờ: giao dịch Chờ kết quả, hàng vẫn giữ
    detail = (await client.get(f"/shifts/{shift_id}", headers=tn)).json()
    assert [t["txn_id"] for t in detail["pending"]] == [txn["txn_id"]]
    slip_status = await conn.fetchval(
        "SELECT status FROM stock_slips WHERE order_id = $1", order_id
    )
    assert slip_status == SlipStatus.PENDING
    stock = (await client.get("/stock", headers=bh)).json()
    assert [(s["quantity"], s["available"]) for s in stock] == [(5, 2)]
    # không tạo giao dịch mới
    response = await client.post(
        f"/orders/{order_id}/payments", json={"method": TxnMethod.TRANSFER}, headers=tn
    )
    assert response.json()["error_code"] == ErrorCode.INVALID_STATE
    assert response.json()["details"]["rule"] == "TT-02"
    # đơn không bị hủy
    response = await client.post(
        f"/orders/{order_id}/cancel", json={"reason": "Quá hạn"}, headers=bh
    )
    assert response.json()["error_code"] == ErrorCode.INVALID_STATE
    # thu ngân đóng ca được, QL chưa chốt ca được
    response = await client.post(f"/shifts/{shift_id}/close", json={"counted_cash": 0}, headers=tn)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == ShiftStatus.AWAITING_CONFIRMATION
    response = await client.post(f"/shifts/{shift_id}/confirm", headers=ql)
    assert response.json()["error_code"] == ErrorCode.RULE_VIOLATION
    assert response.json()["details"]["rule"] == "CA-03"
    assert await _counts(conn, order_id) == (0, 0, 0)
    # đến giờ đóng cửa (BH-05): đơn vẫn Chờ thanh toán, hàng vẫn giữ
    clock.freeze(CLOSING)
    await run_closing(conn, clock.now())
    # phiên cũ hết hạn sau 12 giờ: đăng nhập lại
    bh = await login_as(client, SALES_ID)
    tn = await login_as(client, CASHIER_ID)
    ql = await login_as(client, MANAGER_ID)
    response = await client.get(f"/orders/{order_id}", headers=bh)
    assert response.status_code == 200, response.text
    order = response.json()
    assert order["status"] == OrderStatus.AWAITING_PAYMENT
    assert order["cancelled_at"] is None
    stock = (await client.get("/stock", headers=bh)).json()
    assert [(s["quantity"], s["available"]) for s in stock] == [(5, 2)]

    # Sau tra soát: ngân hàng xác nhận Thành công mã R1 -> đơn Hoàn tất, xuất bán, hóa đơn
    response = await client.post(
        f"/transactions/{txn['txn_id']}/reconcile",
        json={"result": "SUCCESS", "reference_code": "R1"},
        headers=tn,
    )
    assert response.status_code == 200, response.text
    assert response.json()["reference_code"] == "R1"
    order = (await client.get(f"/orders/{order_id}", headers=bh)).json()
    assert order["status"] == OrderStatus.COMPLETED
    assert await _counts(conn, order_id) == (1, 1, 1)
    # ca chốt được
    response = await client.post(f"/shifts/{shift_id}/confirm", headers=ql)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == ShiftStatus.SETTLED

    # Phản hồi lặp R1 bị bỏ qua: vẫn 1 lần thu, 1 lần xuất, 1 hóa đơn
    response = await bank_callback(client, txn["txn_id"], TxnStatus.SUCCESS, "R1")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == TxnStatus.SUCCESS
    assert await _counts(conn, order_id) == (1, 1, 1)
    stock = (await client.get("/stock", headers=bh)).json()
    assert [(s["quantity"], s["available"]) for s in stock] == [(2, 2)]
