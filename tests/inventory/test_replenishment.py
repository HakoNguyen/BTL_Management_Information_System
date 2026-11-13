"""4.4 Yêu cầu bổ sung (TK-06)."""

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
from common.constants import ErrorCode, ProductStatus, ReplenishType, Role

pytestmark = pytest.mark.db

AT = datetime(2026, 11, 2, 8, 0, tzinfo=VN_TZ)


def _body(items: list[dict], type_: ReplenishType = ReplenishType.TRANSFER) -> dict:
    return {"type": type_, "recipient": "Kho tổng", "items": items}


@pytest.fixture
async def ready(conn: asyncpg.Connection) -> None:
    await seed_staff(conn)
    await seed_product(conn, "A")
    await seed_product(conn, "B")
    await seed_stock(conn, BRANCH_1, "A", 2)
    clock.freeze(AT)


@pytest.mark.parametrize("type_", list(ReplenishType))
async def test_create_request_keeps_stock(
    client: httpx.AsyncClient, ready: None, type_: ReplenishType
) -> None:
    """TK-06: lưu như đã gửi, mỗi sản phẩm một dòng, không làm tăng tồn."""
    kho = await login_as(client, WAREHOUSE_ID)
    items = [{"product_id": "B", "quantity": 5}, {"product_id": "A", "quantity": 20}]
    response = await client.post("/replenishment-requests", json=_body(items, type_), headers=kho)
    assert response.status_code == 201, response.text
    request = response.json()
    assert request["request_id"] == "YC000001"
    assert request["branch_id"] == BRANCH_1
    assert request["created_by"] == WAREHOUSE_ID
    assert datetime.fromisoformat(request["created_at"]) == AT
    assert request["type"] == type_
    assert request["recipient"] == "Kho tổng"
    assert request["items"] == sorted(items, key=lambda i: i["product_id"])

    stock = {
        row["product_id"]: row["quantity"]
        for row in (await client.get("/stock", headers=kho)).json()
    }
    assert stock == {"A": 2, "B": 0}

    ql = await login_as(client, MANAGER_ID)
    listed = (await client.get("/replenishment-requests", headers=ql)).json()
    assert listed == [request]


async def test_discontinued_product_rejected(client: httpx.AsyncClient, ready: None) -> None:
    """TK-06: chỉ sản phẩm Đang bán."""
    hq = await login_as(client, HQ_ID)
    response = await client.put(
        "/products/B/status", json={"status": ProductStatus.DISCONTINUED}, headers=hq
    )
    assert response.status_code == 200, response.text
    kho = await login_as(client, WAREHOUSE_ID)
    response = await client.post(
        "/replenishment-requests", json=_body([{"product_id": "B", "quantity": 1}]), headers=kho
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == ErrorCode.RULE_VIOLATION
    assert response.json()["details"]["rule"] == "TK-06"


@pytest.mark.parametrize(
    ("items", "status", "code"),
    [
        ([{"product_id": "A", "quantity": 0}], 400, ErrorCode.VALIDATION_ERROR),
        ([], 400, ErrorCode.VALIDATION_ERROR),
        (
            [{"product_id": "A", "quantity": 1}, {"product_id": "A", "quantity": 2}],
            400,
            ErrorCode.VALIDATION_ERROR,
        ),
        ([{"product_id": "ZZ", "quantity": 1}], 404, ErrorCode.NOT_FOUND),
    ],
)
async def test_invalid_lines(
    client: httpx.AsyncClient, ready: None, items: list[dict], status: int, code: ErrorCode
) -> None:
    """TK-06: số lượng > 0, mỗi sản phẩm một dòng, có ít nhất một dòng, sản phẩm phải có."""
    kho = await login_as(client, WAREHOUSE_ID)
    response = await client.post("/replenishment-requests", json=_body(items), headers=kho)
    assert response.status_code == status
    assert response.json()["error_code"] == code
    listed = (await client.get("/replenishment-requests", headers=kho)).json()
    assert listed == []


@pytest.mark.parametrize("employee_id", [SALES_ID, MANAGER_ID, CASHIER_ID, HQ_ID])
async def test_only_warehouse_creates(
    client: httpx.AsyncClient, ready: None, employee_id: str
) -> None:
    """K-01: chỉ NV kho lập yêu cầu."""
    headers = await login_as(client, employee_id)
    response = await client.post(
        "/replenishment-requests",
        json=_body([{"product_id": "A", "quantity": 1}]),
        headers=headers,
    )
    assert response.status_code == 403
    assert response.json()["error_code"] == ErrorCode.FORBIDDEN


@pytest.mark.parametrize("employee_id", [SALES_ID, CASHIER_ID, HQ_ID])
async def test_viewers(client: httpx.AsyncClient, ready: None, employee_id: str) -> None:
    """K-01: chỉ QL, NV kho xem yêu cầu."""
    headers = await login_as(client, employee_id)
    response = await client.get("/replenishment-requests", headers=headers)
    assert response.status_code == 403


async def test_other_branch_does_not_see_requests(
    client: httpx.AsyncClient, conn: asyncpg.Connection, ready: None
) -> None:
    """K-01: chỉ thấy yêu cầu của chi nhánh mình."""
    await seed_employee(conn, "NV-KHO2", Role.WAREHOUSE, BRANCH_2)
    kho = await login_as(client, WAREHOUSE_ID)
    response = await client.post(
        "/replenishment-requests", json=_body([{"product_id": "A", "quantity": 1}]), headers=kho
    )
    assert response.status_code == 201
    kho2 = await login_as(client, "NV-KHO2")
    assert (await client.get("/replenishment-requests", headers=kho2)).json() == []
