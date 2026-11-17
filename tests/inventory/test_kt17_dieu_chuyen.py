"""KT-17 Điều chuyển giữa hai chi nhánh (TK-01, TK-03, TK-07, NV-04, K-02; chức năng 4.6, 6.4)."""

from __future__ import annotations

from datetime import datetime

import asyncpg
import httpx
import pytest
from fixtures import (
    BRANCH_1,
    BRANCH_2,
    HQ_ID,
    MANAGER_ID,
    WAREHOUSE_ID,
    login_as,
    seed_employee,
    seed_product,
    seed_staff,
    seed_stock,
)

from common import clock
from common.clock import VN_TZ
from common.constants import ErrorCode, Role, SlipStatus, SlipType

pytestmark = pytest.mark.db

KHO2 = "NV-KHO2"


async def _stock_a(client: httpx.AsyncClient, headers: dict[str, str]) -> tuple[int, int]:
    rows = (await client.get("/stock", headers=headers)).json()
    row = next(row for row in rows if row["product_id"] == "A")
    return row["quantity"], row["available"]


async def test_kt17_dieu_chuyen(client: httpx.AsyncClient, conn: asyncpg.Connection) -> None:
    await seed_staff(conn)
    await seed_employee(conn, KHO2, Role.WAREHOUSE, BRANCH_2)
    await seed_product(conn, "A")
    await seed_stock(conn, BRANCH_1, "A", 10)
    clock.freeze(datetime(2026, 11, 17, 9, 0, tzinfo=VN_TZ))
    kho1 = await login_as(client, WAREHOUSE_ID)
    ql1 = await login_as(client, MANAGER_ID)
    kho2 = await login_as(client, KHO2)
    hq = await login_as(client, HQ_ID)
    body = {
        "type": SlipType.OUT_TRANSFER,
        "reason": "Cân đối hàng",
        "counterparty": BRANCH_2,
        "items": [{"product_id": "A", "quantity": 4}],
    }

    # Lập phiếu gửi tới chính CN1 bị từ chối
    response = await client.post(
        "/stock-slips", json=body | {"counterparty": BRANCH_1}, headers=kho1
    )
    assert response.status_code == 422, response.text
    assert response.json()["details"]["rule"] == "TK-07"

    # Chờ duyệt: tồn CN1 = 10, tồn khả dụng = 6
    response = await client.post("/stock-slips", json=body, headers=kho1)
    assert response.status_code == 201, response.text
    out_id = response.json()["slip_id"]
    assert response.json()["status"] == SlipStatus.PENDING
    assert await _stock_a(client, kho1) == (10, 6)

    # QL CN1 duyệt (khác người lập): tồn CN1 = 6, đang vận chuyển 4 A, tồn CN2 = 0
    response = await client.post(f"/stock-slips/{out_id}/approve", headers=ql1)
    assert response.json()["status"] == SlipStatus.POSTED
    assert response.json()["approved_by"] == MANAGER_ID
    assert await _stock_a(client, kho1) == (6, 6)
    assert await _stock_a(client, kho2) == (0, 0)
    incoming = (await client.get("/stock-slips/incoming-transfers", headers=kho2)).json()
    assert [(s["slip_id"], s["items"]) for s in incoming] == [
        (out_id, [{"product_id": "A", "quantity": 4}])
    ]

    # Trụ sở không cho CN2 ngừng hoạt động khi hàng đang chuyển đến
    response = await client.post(f"/branches/{BRANCH_2}/deactivate", headers=hq)
    assert response.status_code == 422, response.text
    assert response.json()["error_code"] == ErrorCode.RULE_VIOLATION
    assert response.json()["details"]["rule"] == "NV-04"
    assert "hàng điều chuyển đang chuyển đến" in response.json()["message"]

    # NV kho CN2 ghi nhận: tồn CN2 = 4, không còn hàng đang vận chuyển
    response = await client.post(f"/stock-slips/{out_id}/receive", headers=kho2)
    assert response.status_code == 201, response.text
    assert (response.json()["type"], response.json()["status"]) == (
        SlipType.IN_TRANSFER,
        SlipStatus.POSTED,
    )
    assert await _stock_a(client, kho2) == (4, 4)
    assert await _stock_a(client, kho1) == (6, 6)
    assert (await client.get("/stock-slips/incoming-transfers", headers=kho2)).json() == []

    # Ghi nhận lần hai bị từ chối
    response = await client.post(f"/stock-slips/{out_id}/receive", headers=kho2)
    assert response.status_code == 409, response.text
    assert response.json()["error_code"] == ErrorCode.DUPLICATE
    assert response.json()["details"]["rule"] == "TK-07"
    assert await _stock_a(client, kho2) == (4, 4)
