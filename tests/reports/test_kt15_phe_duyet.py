"""KT-15 Phê duyệt và lịch sử (K-02, K-05, NV-02, DT-05; chức năng 3.4, 6.2, 5.5)."""

from __future__ import annotations

from datetime import datetime

import asyncpg
import httpx
import pytest
from fixtures import (
    BRANCH_1,
    BRANCH_2,
    CASHIER_ID,
    HQ_ID,
    MANAGER_ID,
    SALES_ID,
    complete_order,
    create_return,
    login_as,
    open_shift,
    seed_product,
    seed_staff,
    seed_stock,
)

from common import clock
from common.clock import VN_TZ
from common.constants import ErrorCode, ReturnStatus, Role

pytestmark = pytest.mark.db

AN = SALES_ID  # NVBH An


async def _staff_sales(client: httpx.AsyncClient, headers: dict, month: int) -> list[dict]:
    last = 31 if month == 10 else 30
    params = {"from": f"2026-{month:02d}-01", "to": f"2026-{month:02d}-{last}"}
    response = await client.get("/reports/staff-sales", params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["lines"]


async def _revenue(client: httpx.AsyncClient, headers: dict) -> dict[str, dict]:
    params = {"from": "2026-11-01", "to": "2026-11-30"}
    response = await client.get("/reports/revenue", params=params, headers=headers)
    assert response.status_code == 200, response.text
    return {line["branch_id"]: line for line in response.json()["branches"]}


async def test_kt15_phe_duyet(client: httpx.AsyncClient, conn: asyncpg.Connection) -> None:
    await seed_staff(conn)
    await seed_product(conn, "A", price=200_000)
    await seed_stock(conn, BRANCH_1, "A", 10)

    # Tháng 10: An bán đơn 1.000.000 tại CN1
    clock.freeze(datetime(2026, 10, 30, 10, 0, tzinfo=VN_TZ))
    tn = await login_as(client, CASHIER_ID)
    an = await login_as(client, AN)
    await open_shift(client, tn)
    order_id = await complete_order(client, an, tn, {"A": 5})

    # 01/11: An chuyển sang CN2 khi không còn đơn dở
    clock.freeze(datetime(2026, 11, 1, 8, 0, tzinfo=VN_TZ))
    hq, ql, an = [await login_as(client, x) for x in (HQ_ID, MANAGER_ID, AN)]
    response = await client.put(
        f"/employees/{AN}/assignment",
        json={"role": Role.SALES, "branch_id": BRANCH_2},
        headers=hq,
    )
    assert response.status_code == 200, response.text

    # QL CN1 tự lập phiếu trả 200.000 của đơn đó: không tự duyệt được
    return_id = (await create_return(client, ql, order_id, {"A": (1, 0)})).json()["return_id"]
    response = await client.post(f"/returns/{return_id}/approve", json={}, headers=ql)
    assert response.status_code == 403, response.text
    assert response.json()["error_code"] == ErrorCode.FORBIDDEN
    assert response.json()["details"]["rule"] == "K-02"

    # Trụ sở duyệt thay, ghi lý do
    response = await client.post(
        f"/returns/{return_id}/approve",
        json={"decision_note": "QL lập phiếu, trụ sở duyệt thay"},
        headers=hq,
    )
    assert response.status_code == 200, response.text
    slip = response.json()
    assert (slip["status"], slip["decided_by"], slip["value"]) == (
        ReturnStatus.APPROVED,
        HQ_ID,
        200_000,
    )
    assert slip["decision_note"] == "QL lập phiếu, trụ sở duyệt thay"

    # Tháng 10: doanh số 1.000.000 thuộc An tại CN1
    october = await _staff_sales(client, hq, 10)
    assert [(x["branch_id"], x["employee_id"]) for x in october] == [(BRANCH_1, AN)]
    assert (october[0]["gross_revenue"], october[0]["net_revenue"]) == (1_000_000, 1_000_000)

    # Tháng 11: hàng bán bị trả 200.000 trừ vào An tại CN1, không vào CN2
    november = await _staff_sales(client, hq, 11)
    assert [(x["branch_id"], x["employee_id"]) for x in november] == [(BRANCH_1, AN)]
    line = november[0]
    assert (line["gross_revenue"], line["returns_value"], line["net_revenue"]) == (
        0,
        200_000,
        -200_000,
    )
    assert line["previous_net_revenue"] == 1_000_000
    branches = await _revenue(client, hq)
    assert branches[BRANCH_1]["returns_value"] == 200_000
    assert branches[BRANCH_2]["returns_value"] == 0

    # An xem doanh số của mình: vẫn là dòng CN1
    assert [(x["branch_id"], x["returns_value"]) for x in await _staff_sales(client, an, 11)] == [
        (BRANCH_1, 200_000)
    ]

    # Đơn cũ vẫn mang CN1 và tên An
    order = (await client.get(f"/orders/{order_id}", headers=ql)).json()
    assert (order["branch_id"], order["created_by"]) == (BRANCH_1, AN)
