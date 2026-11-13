"""KT-16 Thu ngân vắng đột xuất (CA-04, K-02, NV-02; chức năng 3.5, 6.2)."""

from __future__ import annotations

from datetime import datetime

import asyncpg
import httpx
import pytest
from fixtures import (
    BRANCH_2,
    CASHIER_ID,
    HQ_ID,
    MANAGER_ID,
    SALES_ID,
    login_as,
    open_shift,
    seed_staff,
)

from common import clock
from common.clock import VN_TZ
from common.constants import ErrorCode, Role, ShiftStatus

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 13, 10, 0, tzinfo=VN_TZ)


async def test_kt16_thu_ngan_vang(client: httpx.AsyncClient, conn: asyncpg.Connection) -> None:
    await seed_staff(conn)
    clock.freeze(NOW)
    # Ca C7 của thu ngân Bình đang mở
    binh = await login_as(client, CASHIER_ID)
    ql = await login_as(client, MANAGER_ID)
    hq = await login_as(client, HQ_ID)
    c7 = await open_shift(client, binh, 500_000)
    transfer = {"role": Role.CASHIER, "branch_id": BRANCH_2}

    # QL kiểm đếm cùng một NVBH làm chứng, đóng ca thay, ghi lý do: ca Chờ xác nhận
    response = await client.post(
        f"/shifts/{c7}/proxy-close",
        json={
            "counted_cash": 500_000,
            "witness_id": SALES_ID,
            "proxy_reason": "Thu ngân nghỉ đột xuất",
        },
        headers=ql,
    )
    assert response.status_code == 200, response.text
    shift = response.json()
    assert shift["status"] == ShiftStatus.AWAITING_CONFIRMATION
    assert shift["proxy_closed_by"] == MANAGER_ID
    assert shift["witness_id"] == SALES_ID
    assert shift["proxy_reason"] == "Thu ngân nghỉ đột xuất"
    assert shift["counted_cash"] == 500_000

    # Yêu cầu chuyển chi nhánh của Bình bị từ chối cho đến khi C7 Đã chốt
    response = await client.put(f"/employees/{CASHIER_ID}/assignment", json=transfer, headers=hq)
    assert response.json()["error_code"] == ErrorCode.RULE_VIOLATION
    assert response.json()["details"]["rule"] == "NV-02"

    # Trụ sở xác nhận chốt vì QL là người đóng; QL không tự xác nhận được
    response = await client.post(f"/shifts/{c7}/confirm", headers=ql)
    assert response.json()["error_code"] == ErrorCode.FORBIDDEN
    assert response.json()["details"]["rule"] == "CA-04"
    response = await client.post(f"/shifts/{c7}/confirm", headers=hq)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == ShiftStatus.SETTLED
    assert response.json()["confirmed_by"] == HQ_ID

    response = await client.put(f"/employees/{CASHIER_ID}/assignment", json=transfer, headers=hq)
    assert response.status_code == 200, response.text
    assert response.json()["branch_id"] == BRANCH_2
