"""KT-10 Bán, trả, hoàn khác ngày (DT-01 đến DT-04; chức năng 5.1)."""

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
from common.constants import TxnMethod, TxnStatus, TxnType

pytestmark = pytest.mark.db


def _at(day: int) -> datetime:
    return datetime(2026, 11, day, 10, 0, tzinfo=VN_TZ)


async def test_kt10_khac_ngay(client: httpx.AsyncClient, conn: asyncpg.Connection) -> None:
    await seed_staff(conn)
    await seed_product(conn, "A")
    await seed_stock(conn, BRANCH_1, "A", 20)
    clock.freeze(_at(10))
    bh = await login_as(client, SALES_ID)
    tn = await login_as(client, CASHIER_ID)
    ql = await login_as(client, MANAGER_ID)
    await open_shift(client, tn)

    # 10/11: đơn 1.000.000 Hoàn tất, thanh toán chuyển khoản
    order_id = await complete_order(client, bh, tn, {"A": 10}, TxnMethod.TRANSFER)

    # 12/11: phiếu trả 200.000 được duyệt; hoàn chuyển khoản thất bại
    clock.freeze(_at(12))
    bh, tn, ql = [await login_as(client, x) for x in (SALES_ID, CASHIER_ID, MANAGER_ID)]
    return_id = (await create_return(client, bh, order_id, {"A": (2, 0)})).json()["return_id"]
    response = await client.post(f"/returns/{return_id}/approve", json={}, headers=ql)
    assert response.status_code == 200, response.text
    failed = (await client.post(f"/returns/{return_id}/refunds", headers=tn)).json()
    await resolve_txn(client, tn, failed, TxnStatus.FAILED)

    # 13/11: hoàn chuyển khoản thành công
    clock.freeze(_at(13))
    tn, ql = [await login_as(client, x) for x in (CASHIER_ID, MANAGER_ID)]
    retry = (await client.post(f"/returns/{return_id}/refunds", headers=tn)).json()
    await resolve_txn(client, tn, retry, TxnStatus.SUCCESS)

    async def day(d: int) -> dict:
        date = f"2026-11-{d:02d}"
        response = await client.get(
            "/reports/revenue", params={"from": date, "to": date}, headers=ql
        )
        assert response.status_code == 200, response.text
        return response.json()["total"]

    # Ngày 10/11: doanh thu gộp +1.000.000
    d10 = await day(10)
    assert (d10["order_count"], d10["gross_revenue"], d10["returns_value"]) == (1, 1_000_000, 0)
    assert d10["net_revenue"] == 1_000_000
    assert d10["payments"] == [
        {"type": TxnType.COLLECT, "method": TxnMethod.TRANSFER, "amount": 1_000_000}
    ]

    # Ngày 12/11: hàng bán bị trả 200.000, doanh thu thuần âm; còn phải hoàn cuối ngày 200.000
    d12 = await day(12)
    assert (d12["gross_revenue"], d12["returns_value"], d12["net_revenue"]) == (
        0,
        200_000,
        -200_000,
    )
    assert d12["average_order_value"] is None
    assert d12["payments"] == []  # hoàn Thất bại không tính
    assert d12["outstanding_refunds"] == 200_000

    # Ngày 13/11: tiền hoàn 200.000, doanh thu không giảm lần hai; còn phải hoàn = 0
    d13 = await day(13)
    assert (d13["gross_revenue"], d13["returns_value"], d13["net_revenue"]) == (0, 0, 0)
    assert d13["payments"] == [
        {"type": TxnType.REFUND, "method": TxnMethod.TRANSFER, "amount": 200_000}
    ]
    assert d13["outstanding_refunds"] == 0
