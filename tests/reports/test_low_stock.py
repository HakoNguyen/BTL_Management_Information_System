"""5.4 Cảnh báo hàng dưới mức tồn tối thiểu (TK-05)."""

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
    WAREHOUSE_ID,
    login_as,
    seed_employee,
    seed_product,
    seed_staff,
    seed_stock,
)

from common import clock
from common.clock import VN_TZ
from common.constants import ErrorCode, ProductStatus, Role

pytestmark = pytest.mark.db

AT = datetime(2026, 11, 2, 7, 0, tzinfo=VN_TZ)


async def test_low_stock_report(client: httpx.AsyncClient, conn: asyncpg.Connection) -> None:
    """TK-05: Đang bán, tồn < ngưỡng; Chưa thiết lập liệt kê riêng; Ngừng bán bỏ qua."""
    await seed_staff(conn)
    await seed_employee(conn, "NV-QL2", Role.MANAGER, BRANCH_2)
    for product_id in "ABCDEF":
        await seed_product(conn, product_id)
    await seed_stock(conn, BRANCH_1, "A", 2)
    await seed_stock(conn, BRANCH_1, "B", 3)
    ql = await login_as(client, MANAGER_ID)
    for product_id, level in (("A", 3), ("B", 3), ("C", 1), ("E", 5), ("F", 0)):
        response = await client.put(
            f"/stock/{product_id}/min-level", json={"min_level": level}, headers=ql
        )
        assert response.status_code == 200, response.text
    hq = await login_as(client, HQ_ID)
    response = await client.put(
        "/products/E/status", json={"status": ProductStatus.DISCONTINUED}, headers=hq
    )
    assert response.status_code == 200, response.text
    # chi nhánh khác đặt ngưỡng cho D: không ảnh hưởng CN1
    ql2 = await login_as(client, "NV-QL2")
    await client.put("/stock/D/min-level", json={"min_level": 9}, headers=ql2)

    clock.freeze(AT)
    for employee_id in (MANAGER_ID, WAREHOUSE_ID):
        response = await client.get(
            "/reports/low-stock", headers=await login_as(client, employee_id)
        )
        assert response.status_code == 200, response.text
        report = response.json()
        assert report["branch_id"] == BRANCH_1
        assert datetime.fromisoformat(report["generated_at"]) == AT
        assert report["below_min"] == [
            {"product_id": "A", "name": "Sản phẩm A", "quantity": 2, "min_level": 3},
            {"product_id": "C", "name": "Sản phẩm C", "quantity": 0, "min_level": 1},
        ]
        assert report["not_set"] == [
            {"product_id": "D", "name": "Sản phẩm D", "quantity": 0, "min_level": None},
        ]

    report = (await client.get("/reports/low-stock", headers=ql2)).json()
    assert report["branch_id"] == BRANCH_2
    assert [r["product_id"] for r in report["below_min"]] == ["D"]
    assert [r["product_id"] for r in report["not_set"]] == ["A", "B", "C", "F"]


@pytest.mark.parametrize("employee_id", [SALES_ID, CASHIER_ID, HQ_ID])
async def test_low_stock_roles(
    client: httpx.AsyncClient, conn: asyncpg.Connection, employee_id: str
) -> None:
    """K-01: chỉ QL, NV kho xem cảnh báo 5.4."""
    await seed_staff(conn)
    response = await client.get("/reports/low-stock", headers=await login_as(client, employee_id))
    assert response.status_code == 403
    assert response.json()["error_code"] == ErrorCode.FORBIDDEN
