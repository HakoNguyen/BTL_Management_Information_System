"""KT-13 Ngừng bán và đóng chi nhánh (SP-04, TK-03, NV-04; chức năng 1.4, 4.3, 6.4, 5.3)."""

from __future__ import annotations

from datetime import datetime

import asyncpg
import httpx
import pytest
from fixtures import (
    BRANCH_2,
    HQ_ID,
    complete_order,
    create_return,
    login_as,
    open_shift,
    resolve_txn,
    seed_employee,
    seed_product,
    seed_staff,
    seed_stock,
)

from common import clock
from common.clock import VN_TZ
from common.constants import BranchStatus, ErrorCode, ProductStatus, Role, SlipType, TxnStatus

pytestmark = pytest.mark.db

QL2, BH2, TN2, KHO2 = "NV-QL2", "NV-BH2", "NV-TN2", "NV-KHO2"


async def test_kt13_dong_chi_nhanh(client: httpx.AsyncClient, conn: asyncpg.Connection) -> None:
    await seed_staff(conn)
    for employee_id, role in (
        (QL2, Role.MANAGER),
        (BH2, Role.SALES),
        (TN2, Role.CASHIER),
        (KHO2, Role.WAREHOUSE),
    ):
        await seed_employee(conn, employee_id, role, BRANCH_2)
    for product_id, quantity in (("B", 12), ("C", 3), ("D", 1)):
        await seed_product(conn, product_id)
        await seed_stock(conn, BRANCH_2, product_id, quantity)
    clock.freeze(datetime(2026, 11, 1, 9, 0, tzinfo=VN_TZ))
    hq = await login_as(client, HQ_ID)
    ql = await login_as(client, QL2)
    bh = await login_as(client, BH2)
    tn = await login_as(client, TN2)
    kho = await login_as(client, KHO2)
    response = await client.put("/stock/B/min-level", json={"min_level": 20}, headers=ql)
    assert response.status_code == 200, response.text

    # Ca của CN2 còn mở; một phiếu trả (hàng lỗi) Đã duyệt chưa hoàn tiền
    shift_id = await open_shift(client, tn)
    order_id = await complete_order(client, bh, tn, {"D": 1})
    return_id = (await create_return(client, bh, order_id, {"D": (0, 1)})).json()["return_id"]
    assert (await client.post(f"/returns/{return_id}/approve", json={}, headers=ql)).is_success

    # Sản phẩm B chuyển Ngừng bán
    response = await client.put(
        "/products/B/status", json={"status": ProductStatus.DISCONTINUED}, headers=hq
    )
    assert response.status_code == 200, response.text

    # B không được chốt vào đơn mới
    response = await client.post(
        "/orders",
        json={"customer_id": "KHLE", "items": [{"product_id": "B", "quantity": 1}]},
        headers=bh,
    )
    assert response.status_code == 201, response.text
    draft_id = response.json()["order_id"]
    response = await client.post(f"/orders/{draft_id}/confirm", headers=bh)
    assert response.status_code == 422, response.text
    assert response.json()["details"]["rule"] == "BH-02"
    assert (
        await client.post(f"/orders/{draft_id}/cancel", json={"reason": "Ngừng bán"}, headers=bh)
    ).is_success

    # B không bị cảnh báo dù tồn 12 < ngưỡng 20
    alert = (await client.get("/reports/low-stock", headers=ql)).json()
    assert "B" not in [x["product_id"] for x in alert["below_min"] + alert["not_set"]]

    # NV kho lập Xuất trả kho tổng 12 B và Xuất hủy 3 C; QL duyệt thì tồn = 0
    for type_, product_id, quantity, reason in (
        (SlipType.OUT_TO_WAREHOUSE, "B", 12, "Đóng chi nhánh"),
        (SlipType.OUT_DISPOSAL, "C", 3, "Hàng hỏng"),
    ):
        body = {
            "type": type_,
            "reason": reason,
            "items": [{"product_id": product_id, "quantity": quantity}],
        }
        response = await client.post("/stock-slips", json=body, headers=kho)
        assert response.status_code == 201, response.text
        slip_id = response.json()["slip_id"]
        response = await client.post(f"/stock-slips/{slip_id}/approve", headers=ql)
        assert response.status_code == 200, response.text
    params = {"from": "2026-11-01", "to": "2026-11-01", "branch_id": BRANCH_2}
    report = (await client.get("/reports/stock", params=params, headers=hq)).json()
    assert {x["product_id"]: x["quantity"] for x in report["lines"]} == {"B": 0, "C": 0, "D": 0}
    assert [(m["type"], m["product_id"], m["quantity"]) for m in report["movements"]] == [
        (SlipType.OUT_DISPOSAL, "C", 3)
    ]

    # Quá 7 ngày từ đơn hoàn tất gần nhất, nhưng còn ca chưa chốt và phiếu trả chưa hoàn xong
    clock.freeze(datetime(2026, 11, 9, 9, 0, tzinfo=VN_TZ))
    hq, ql, tn = [await login_as(client, x) for x in (HQ_ID, QL2, TN2)]
    response = await client.post(f"/branches/{BRANCH_2}/deactivate", headers=hq)
    assert response.status_code == 422, response.text
    body = response.json()
    assert (body["error_code"], body["details"]["rule"]) == (ErrorCode.RULE_VIOLATION, "NV-04")
    assert "ca chưa chốt" in body["message"]
    assert "phiếu trả Đã duyệt chưa hoàn tiền xong" in body["message"]

    # Hoàn tiền xong, đóng và chốt ca thì CN2 chuyển Ngừng hoạt động
    refund = (await client.post(f"/returns/{return_id}/refunds", headers=tn)).json()
    await resolve_txn(client, tn, refund, TxnStatus.SUCCESS)
    response = await client.post(f"/shifts/{shift_id}/close", json={"counted_cash": 0}, headers=tn)
    assert response.status_code == 200, response.text
    assert (await client.post(f"/shifts/{shift_id}/confirm", headers=ql)).is_success
    response = await client.post(f"/branches/{BRANCH_2}/deactivate", headers=hq)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == BranchStatus.INACTIVE
