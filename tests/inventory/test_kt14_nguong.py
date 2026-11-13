"""KT-14 Ngưỡng và yêu cầu bổ sung (TK-02, TK-05, TK-06; chức năng 5.4, 4.4, 4.2)."""

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
    WAREHOUSE_ID,
    complete_order,
    login_as,
    open_shift,
    seed_product,
    seed_staff,
    seed_stock,
)

from common import clock
from common.clock import VN_TZ
from common.constants import ReplenishType, SlipType

pytestmark = pytest.mark.db


async def test_kt14_nguong(client: httpx.AsyncClient, conn: asyncpg.Connection) -> None:
    await seed_staff(conn)
    await seed_product(conn, "A")
    await seed_product(conn, "D")
    await seed_stock(conn, BRANCH_1, "A", 3)
    ql = await login_as(client, MANAGER_ID)
    kho = await login_as(client, WAREHOUSE_ID)
    bh = await login_as(client, SALES_ID)
    tn = await login_as(client, CASHIER_ID)

    clock.freeze(datetime(2026, 11, 1, 8, 0, tzinfo=VN_TZ))
    response = await client.put("/stock/A/min-level", json={"min_level": 3}, headers=ql)
    assert response.status_code == 200, response.text

    async def report() -> dict:
        response = await client.get("/reports/low-stock", headers=kho)
        assert response.status_code == 200, response.text
        return response.json()

    async def stock_a() -> int:
        rows = (await client.get("/stock", headers=kho)).json()
        return {row["product_id"]: row["quantity"] for row in rows}["A"]

    # Tồn 3 = ngưỡng: không cảnh báo
    first = await report()
    assert first["below_min"] == []

    # Bán 1 A: tồn 2 < 3, cảnh báo sáng hôm sau
    clock.freeze(datetime(2026, 11, 1, 10, 0, tzinfo=VN_TZ))
    await open_shift(client, tn)
    await complete_order(client, bh, tn, {"A": 1})
    clock.freeze(datetime(2026, 11, 2, 7, 0, tzinfo=VN_TZ))
    second = await report()
    assert [(r["product_id"], r["quantity"], r["min_level"]) for r in second["below_min"]] == [
        ("A", 2, 3)
    ]

    # NV kho lập yêu cầu 20 A gửi kho tổng: tồn vẫn 2
    response = await client.post(
        "/replenishment-requests",
        json={
            "type": ReplenishType.TRANSFER,
            "recipient": "Kho tổng",
            "items": [{"product_id": "A", "quantity": 20}],
        },
        headers=kho,
    )
    assert response.status_code == 201, response.text
    assert await stock_a() == 2

    # Hàng về, kiểm nhận 20: tồn 22
    response = await client.post(
        "/stock-slips/inbound",
        json={
            "type": SlipType.IN_WAREHOUSE,
            "counterparty": "Kho tổng",
            "delivery_no": "PX-001",
            "items": [{"product_id": "A", "quantity": 20}],
        },
        headers=kho,
    )
    assert response.status_code == 201, response.text
    assert await stock_a() == 22

    # D không bị cảnh báo, được liệt kê ở mục Chưa thiết lập
    for result in (first, second, await report()):
        assert "D" not in [r["product_id"] for r in result["below_min"]]
        assert [r["product_id"] for r in result["not_set"]] == ["D"]
