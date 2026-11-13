"""1.3 Thiết lập và cập nhật giá bán (SP-02)."""

from __future__ import annotations

from datetime import datetime

import asyncpg
import httpx
import pytest
from fixtures import HQ_ID, SEED_AT, login_as, seed_employee, seed_product, seed_staff

from common import clock
from common.clock import VN_TZ
from common.constants import ErrorCode, Role

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 13, 9, 30, tzinfo=VN_TZ)
HQ_2 = "NV-TS2"


@pytest.fixture
async def hq(client: httpx.AsyncClient, conn: asyncpg.Connection) -> dict[str, str]:
    await seed_staff(conn)
    await seed_product(conn, "A")
    clock.freeze(NOW)
    return await login_as(client, HQ_ID)


async def test_change_price_records_history(
    client: httpx.AsyncClient, conn: asyncpg.Connection, hq: dict[str, str]
) -> None:
    """SP-02: giá mới có hiệu lực ngay; mỗi lần đổi ghi giá, thời điểm, người đổi."""
    response = await client.put("/products/A/price", json={"price": 110_000}, headers=hq)
    assert response.status_code == 200
    assert response.json()["current_price"] == 110_000
    await seed_employee(conn, HQ_2, Role.HQ)
    later = datetime(2026, 11, 13, 11, 0, tzinfo=VN_TZ)
    clock.freeze(later)
    hq2 = await login_as(client, HQ_2)
    assert (
        await client.put("/products/A/price", json={"price": 90_000}, headers=hq2)
    ).status_code == 200
    response = await client.get("/products/A/price-history", headers=hq)
    assert response.status_code == 200
    history = [
        (datetime.fromisoformat(e["effective_at"]), e["price"], e["changed_by"])
        for e in response.json()
    ]
    assert history == [(SEED_AT, 100_000, HQ_ID), (NOW, 110_000, HQ_ID), (later, 90_000, HQ_2)]
    assert (await client.get("/products/A", headers=hq)).json()["current_price"] == 90_000


@pytest.mark.parametrize("price", [100_000, 0, -5])
async def test_change_price_rejected(
    client: httpx.AsyncClient, conn: asyncpg.Connection, hq: dict[str, str], price: int
) -> None:
    """SP-02: giá mới > 0 và khác giá hiện hành."""
    response = await client.put("/products/A/price", json={"price": price}, headers=hq)
    assert response.status_code == 422
    assert response.json()["error_code"] == ErrorCode.RULE_VIOLATION
    assert response.json()["details"]["rule"] == "SP-02"
    assert await conn.fetchval("SELECT count(*) FROM price_history") == 1
    assert await conn.fetchval("SELECT current_price FROM products") == 100_000


async def test_price_not_found(client: httpx.AsyncClient, hq: dict[str, str]) -> None:
    response = await client.put("/products/KHONG/price", json={"price": 1}, headers=hq)
    assert response.status_code == 404
    response = await client.get("/products/KHONG/price-history", headers=hq)
    assert response.status_code == 404
