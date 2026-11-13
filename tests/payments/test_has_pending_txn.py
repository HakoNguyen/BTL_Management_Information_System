"""Hàm giao payments.has_pending_txn cho 3.1 mở lại và 3.4 hủy đơn (BH-03, BH-04)."""

from __future__ import annotations

import asyncpg
import pytest
from fixtures import CASHIER_ID, SALES_ID, seed_order, seed_shift, seed_staff, seed_transaction
from services import payments

from common.constants import OrderStatus, TxnStatus

pytestmark = pytest.mark.db


async def test_has_pending_txn(conn: asyncpg.Connection) -> None:
    """BH-03, BH-04: chỉ giao dịch Chờ kết quả của đúng đơn đó được tính."""
    await seed_staff(conn)
    shift_id = await seed_shift(conn, CASHIER_ID)
    order_id = await seed_order(conn, SALES_ID, status=OrderStatus.AWAITING_PAYMENT)
    other_id = await seed_order(conn, SALES_ID, status=OrderStatus.AWAITING_PAYMENT)
    assert await payments.has_pending_txn(conn, order_id) is False
    await seed_transaction(conn, order_id, shift_id, status=TxnStatus.FAILED)
    assert await payments.has_pending_txn(conn, order_id) is False
    await seed_transaction(conn, order_id, shift_id, status=TxnStatus.PENDING)
    assert await payments.has_pending_txn(conn, order_id) is True
    assert await payments.has_pending_txn(conn, other_id) is False
