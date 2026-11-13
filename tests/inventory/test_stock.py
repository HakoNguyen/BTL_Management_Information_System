"""4.1 Tra cứu tồn theo chi nhánh, 4.5 mức tồn tối thiểu (TK-01, TK-05)."""

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
    seed_product,
    seed_staff,
    seed_stock,
    seed_stock_slip,
    seed_stock_slip_item,
)

from common import clock
from common.clock import VN_TZ
from common.constants import ErrorCode

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 13, 10, 0, tzinfo=VN_TZ)


@pytest.fixture
async def world(conn: asyncpg.Connection) -> None:
    await seed_staff(conn)
    await seed_product(conn, "A")
    await seed_product(conn, "B")
    await seed_stock(conn, BRANCH_1, "A", 10)
    await seed_stock(conn, BRANCH_2, "A", 99)
    clock.freeze(NOW)


def _error(response: httpx.Response, status: int, code: ErrorCode, rule: str | None) -> None:
    assert response.status_code == status, response.text
    assert response.json()["error_code"] == code
    assert response.json()["details"].get("rule") == rule


async def test_stock_lists_own_branch_with_available(
    client: httpx.AsyncClient, conn: asyncpg.Connection, world: None
) -> None:
    """TK-01: tồn khả dụng = tồn − phiếu xuất Chờ xử lý; cặp chưa có bản ghi là tồn 0."""
    slip = await seed_stock_slip(conn, BRANCH_1, WAREHOUSE_ID)  # ADJUST_DOWN PENDING
    await seed_stock_slip_item(conn, slip, "A", 3)
    for employee_id in (MANAGER_ID, SALES_ID, WAREHOUSE_ID):
        response = await client.get("/stock", headers=await login_as(client, employee_id))
        assert response.status_code == 200, response.text
        assert response.json() == [
            {"product_id": "A", "quantity": 10, "available": 7, "min_level": None},
            {"product_id": "B", "quantity": 0, "available": 0, "min_level": None},
        ]


async def test_stock_forbidden_roles(client: httpx.AsyncClient, world: None) -> None:
    """K-01: Thu ngân, Trụ sở không xem tồn qua 4.1."""
    for employee_id in (CASHIER_ID, HQ_ID):
        response = await client.get("/stock", headers=await login_as(client, employee_id))
        _error(response, 403, ErrorCode.FORBIDDEN, "K-01")


async def test_set_min_level(client: httpx.AsyncClient, world: None) -> None:
    """TK-05: đặt, đặt 0, để trống; không đổi tồn; cặp chưa có bản ghi vẫn đặt được."""
    ql = await login_as(client, MANAGER_ID)
    response = await client.put("/stock/A/min-level", json={"min_level": 5}, headers=ql)
    assert response.status_code == 200, response.text
    assert response.json() == {"product_id": "A", "quantity": 10, "available": 10, "min_level": 5}
    response = await client.put("/stock/B/min-level", json={"min_level": 0}, headers=ql)
    assert response.json() == {"product_id": "B", "quantity": 0, "available": 0, "min_level": 0}
    response = await client.put("/stock/A/min-level", json={"min_level": None}, headers=ql)
    assert response.json()["min_level"] is None
    assert response.json()["quantity"] == 10


async def test_set_min_level_rejects_negative(client: httpx.AsyncClient, world: None) -> None:
    """TK-05: ngưỡng âm bị từ chối."""
    ql = await login_as(client, MANAGER_ID)
    response = await client.put("/stock/A/min-level", json={"min_level": -1}, headers=ql)
    _error(response, 400, ErrorCode.VALIDATION_ERROR, "TK-05")


async def test_set_min_level_unknown_product(client: httpx.AsyncClient, world: None) -> None:
    ql = await login_as(client, MANAGER_ID)
    response = await client.put("/stock/ZZ/min-level", json={"min_level": 1}, headers=ql)
    _error(response, 404, ErrorCode.NOT_FOUND, None)


async def test_set_min_level_only_manager(client: httpx.AsyncClient, world: None) -> None:
    """K-01: chỉ QL đặt ngưỡng."""
    for employee_id in (WAREHOUSE_ID, SALES_ID, HQ_ID):
        headers = await login_as(client, employee_id)
        response = await client.put("/stock/A/min-level", json={"min_level": 1}, headers=headers)
        _error(response, 403, ErrorCode.FORBIDDEN, "K-01")
