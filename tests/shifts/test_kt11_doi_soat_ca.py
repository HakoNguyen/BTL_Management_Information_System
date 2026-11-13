"""KT-11 Đối soát ca (CA-02, CA-03; chức năng 3.5).

Giao dịch hoàn tiền mặt chèn bằng SQL vì 3.4 hoàn tiền chưa có API (vòng 7).
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
    seed_return_slip,
    seed_staff,
    seed_stock,
    seed_transaction,
    start_payment,
)

from common import clock
from common.clock import VN_TZ
from common.constants import (
    ErrorCode,
    ReturnStatus,
    ShiftStatus,
    TxnMethod,
    TxnStatus,
    TxnType,
)

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 13, 10, 0, tzinfo=VN_TZ)


async def test_kt11_doi_soat_ca(client: httpx.AsyncClient, conn: asyncpg.Connection) -> None:
    await seed_staff(conn)
    await seed_product(conn, "A")
    await seed_stock(conn, BRANCH_1, "A", 100)
    clock.freeze(NOW)
    bh = await login_as(client, SALES_ID)
    tn = await login_as(client, CASHIER_ID)
    ql = await login_as(client, MANAGER_ID)
    # Tiền đầu ca 500.000
    shift_id = await open_shift(client, tn, 500_000)

    # Thu tiền mặt Thành công 2.000.000
    cash_order = await create_awaiting_order(client, bh, {"A": 20})
    txn = await start_payment(client, tn, cash_order, TxnMethod.CASH)
    response = await client.post(
        f"/transactions/{txn['txn_id']}/confirm-cash", json={"result": "SUCCESS"}, headers=tn
    )
    assert response.status_code == 200, response.text
    # Hoàn tiền mặt Thành công 200.000
    return_id = await seed_return_slip(
        conn, cash_order, SALES_ID, ReturnStatus.APPROVED, decided_by=MANAGER_ID
    )
    await seed_transaction(conn, cash_order, shift_id, return_id=return_id, amount=200_000)
    # Thu thẻ Thành công 1.000.000
    card_order = await create_awaiting_order(client, bh, {"A": 10})
    txn = await start_payment(client, tn, card_order, TxnMethod.CARD)
    assert (await bank_callback(client, txn["txn_id"], TxnStatus.SUCCESS, "REF-THE")).is_success
    # Thu chuyển khoản Thất bại 300.000
    transfer_order = await create_awaiting_order(client, bh, {"A": 3})
    failed = await start_payment(client, tn, transfer_order, TxnMethod.TRANSFER)
    assert (await bank_callback(client, failed["txn_id"], TxnStatus.FAILED)).is_success

    # Tiền kiểm đếm 2.290.000: chênh lệch -10.000, thu ngân phải nhập lý do
    response = await client.post(
        f"/shifts/{shift_id}/close", json={"counted_cash": 2_290_000}, headers=tn
    )
    assert response.json()["error_code"] == ErrorCode.RULE_VIOLATION
    assert response.json()["details"]["rule"] == "CA-02"
    response = await client.post(
        f"/shifts/{shift_id}/close",
        json={"counted_cash": 2_290_000, "variance_reason": "Thối nhầm"},
        headers=tn,
    )
    assert response.status_code == 200, response.text
    shift = response.json()
    assert shift["status"] == ShiftStatus.AWAITING_CONFIRMATION
    # Tiền mặt kỳ vọng = 500.000 + 2.000.000 - 200.000 = 2.300.000; chênh lệch = -10.000
    assert shift["expected_cash"] == 2_300_000
    assert shift["variance"] == -10_000
    # Thẻ và giao dịch thất bại không tính vào tiền mặt
    assert shift["cash_collected"] == 2_000_000
    assert shift["cash_refunded"] == 200_000
    assert shift["electronic"] == [
        {"type": TxnType.COLLECT, "method": TxnMethod.CARD, "count": 1, "amount": 1_000_000}
    ]
    assert [(t["txn_id"], t["amount"]) for t in shift["failed"]] == [(failed["txn_id"], 300_000)]
    assert shift["pending"] == []

    # QL xác nhận thì ca Đã chốt
    response = await client.post(f"/shifts/{shift_id}/confirm", headers=ql)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == ShiftStatus.SETTLED
    assert response.json()["confirmed_by"] == MANAGER_ID
