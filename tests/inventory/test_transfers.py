"""4.6 Điều chuyển hàng giữa chi nhánh (TK-07; lập và duyệt như TK-03, K-02)."""

from __future__ import annotations

import asyncio
from datetime import datetime

import asyncpg
import httpx
import pytest
from fixtures import (
    BRANCH_1,
    BRANCH_2,
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
from common.constants import BranchStatus, ErrorCode, ProductStatus, Role

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 17, 10, 0, tzinfo=VN_TZ)
KHO2_ID = "NV-KHO2"
QL2_ID = "NV-QL2"


def _transfer(quantity: int = 4, to: str | None = BRANCH_2, **extra: object) -> dict:
    body = {
        "type": "OUT_TRANSFER",
        "reason": "Cân đối hàng",
        "counterparty": to,
        "items": [{"product_id": "A", "quantity": quantity}],
    }
    return body | extra


@pytest.fixture
async def world(conn: asyncpg.Connection) -> None:
    await seed_staff(conn)
    await seed_employee(conn, KHO2_ID, Role.WAREHOUSE, BRANCH_2)
    await seed_employee(conn, QL2_ID, Role.MANAGER, BRANCH_2)
    await seed_product(conn, "A")
    await seed_stock(conn, BRANCH_1, "A", 10)
    clock.freeze(NOW)


@pytest.fixture
async def kho(client: httpx.AsyncClient, world: None) -> dict[str, str]:
    return await login_as(client, WAREHOUSE_ID)


@pytest.fixture
async def ql(client: httpx.AsyncClient, world: None) -> dict[str, str]:
    return await login_as(client, MANAGER_ID)


@pytest.fixture
async def kho2(client: httpx.AsyncClient, world: None) -> dict[str, str]:
    return await login_as(client, KHO2_ID)


def _error(response: httpx.Response, status: int, code: ErrorCode, rule: str | None) -> None:
    assert response.status_code == status, response.text
    assert response.json()["error_code"] == code
    assert response.json()["details"].get("rule") == rule


async def _stock_a(client: httpx.AsyncClient, headers: dict[str, str]) -> tuple[int, int]:
    rows = (await client.get("/stock", headers=headers)).json()
    row = next(row for row in rows if row["product_id"] == "A")
    return row["quantity"], row["available"]


async def _posted(client: httpx.AsyncClient, kho: dict[str, str], ql: dict[str, str]) -> str:
    response = await client.post("/stock-slips", json=_transfer(), headers=kho)
    assert response.status_code == 201, response.text
    slip_id = response.json()["slip_id"]
    assert (await client.post(f"/stock-slips/{slip_id}/approve", headers=ql)).status_code == 200
    return slip_id


async def test_out_transfer_holds_then_posts(
    client: httpx.AsyncClient, kho: dict[str, str], ql: dict[str, str], kho2: dict[str, str]
) -> None:
    """TK-07, TK-03: lập thì giữ hàng; duyệt thì tồn CN gửi giảm, hàng đang vận chuyển."""
    response = await client.post("/stock-slips", json=_transfer(), headers=kho)
    assert response.status_code == 201, response.text
    slip = response.json()
    assert (slip["type"], slip["status"], slip["counterparty"]) == (
        "OUT_TRANSFER",
        "PENDING",
        BRANCH_2,
    )
    assert await _stock_a(client, kho) == (10, 6)
    # Chưa duyệt thì CN nhận chưa thấy hàng đến
    assert (await client.get("/stock-slips/incoming-transfers", headers=kho2)).json() == []

    approved = await client.post(f"/stock-slips/{slip['slip_id']}/approve", headers=ql)
    assert approved.json()["status"] == "POSTED"
    assert await _stock_a(client, kho) == (6, 6)
    assert await _stock_a(client, kho2) == (0, 0)
    incoming = (await client.get("/stock-slips/incoming-transfers", headers=kho2)).json()
    assert [s["slip_id"] for s in incoming] == [slip["slip_id"]]


async def test_receive_copies_lines_once(
    client: httpx.AsyncClient, kho: dict[str, str], ql: dict[str, str], kho2: dict[str, str]
) -> None:
    """TK-07: nhận đúng dòng phiếu xuất, ghi nhận ngay, mỗi phiếu xuất một lần."""
    out_id = await _posted(client, kho, ql)
    response = await client.post(f"/stock-slips/{out_id}/receive", headers=kho2)
    assert response.status_code == 201, response.text
    slip = response.json()
    assert (slip["branch_id"], slip["type"], slip["status"]) == (BRANCH_2, "IN_TRANSFER", "POSTED")
    assert (slip["counterparty"], slip["transfer_slip_id"], slip["created_by"]) == (
        BRANCH_1,
        out_id,
        KHO2_ID,
    )
    assert slip["items"] == [{"product_id": "A", "quantity": 4}]
    assert await _stock_a(client, kho2) == (4, 4)
    assert (await client.get("/stock-slips/incoming-transfers", headers=kho2)).json() == []

    again = await client.post(f"/stock-slips/{out_id}/receive", headers=kho2)
    _error(again, 409, ErrorCode.DUPLICATE, "TK-07")
    assert await _stock_a(client, kho2) == (4, 4)


async def test_concurrent_receive_counts_once(
    client: httpx.AsyncClient, kho: dict[str, str], ql: dict[str, str], kho2: dict[str, str]
) -> None:
    """TK-07: hai lần nhận cùng lúc chỉ một lần qua."""
    out_id = await _posted(client, kho, ql)
    results = await asyncio.gather(
        client.post(f"/stock-slips/{out_id}/receive", headers=kho2),
        client.post(f"/stock-slips/{out_id}/receive", headers=kho2),
    )
    assert sorted(r.status_code for r in results) == [201, 409]
    assert await _stock_a(client, kho2) == (4, 4)


async def test_receive_wrong_branch_or_state(
    client: httpx.AsyncClient, kho: dict[str, str], ql: dict[str, str], kho2: dict[str, str]
) -> None:
    """TK-07: chỉ chi nhánh nhận được nhận, và chỉ khi phiếu xuất đã ghi nhận."""
    response = await client.post("/stock-slips", json=_transfer(), headers=kho)
    pending_id = response.json()["slip_id"]
    _error(
        await client.post(f"/stock-slips/{pending_id}/receive", headers=kho2),
        409,
        ErrorCode.INVALID_STATE,
        "TK-07",
    )
    # Chi nhánh gửi không tự nhận phiếu của mình
    _error(
        await client.post(f"/stock-slips/{pending_id}/receive", headers=kho),
        404,
        ErrorCode.NOT_FOUND,
        None,
    )
    # Phiếu không phải xuất điều chuyển
    other = await client.post(
        "/stock-slips",
        json={
            "type": "OUT_DISPOSAL",
            "reason": "Hỏng",
            "items": [{"product_id": "A", "quantity": 1}],
        },
        headers=kho,
    )
    _error(
        await client.post(f"/stock-slips/{other.json()['slip_id']}/receive", headers=kho2),
        404,
        ErrorCode.NOT_FOUND,
        None,
    )


async def test_rejected_transfer_releases_hold(
    client: httpx.AsyncClient, kho: dict[str, str], ql: dict[str, str], kho2: dict[str, str]
) -> None:
    """TK-03: QL từ chối thì Đã hủy, nhả hàng; không thành hàng đang vận chuyển."""
    slip_id = (await client.post("/stock-slips", json=_transfer(), headers=kho)).json()["slip_id"]
    response = await client.post(
        f"/stock-slips/{slip_id}/reject", json={"reason": "Không cần"}, headers=ql
    )
    assert response.json()["status"] == "CANCELLED"
    assert await _stock_a(client, kho) == (10, 10)
    assert (await client.get("/stock-slips/incoming-transfers", headers=kho2)).json() == []


async def test_out_transfer_validation(
    client: httpx.AsyncClient, conn: asyncpg.Connection, kho: dict[str, str]
) -> None:
    """TK-07: chi nhánh nhận bắt buộc, khác mình, tồn tại, Hoạt động; sản phẩm Đang bán; đủ tồn."""
    _error(
        await client.post("/stock-slips", json=_transfer(to=None), headers=kho),
        400,
        ErrorCode.VALIDATION_ERROR,
        "TK-07",
    )
    disposal = _transfer(type="OUT_DISPOSAL")
    _error(
        await client.post("/stock-slips", json=disposal, headers=kho),
        400,
        ErrorCode.VALIDATION_ERROR,
        "TK-07",
    )
    _error(
        await client.post("/stock-slips", json=_transfer(to=BRANCH_1), headers=kho),
        422,
        ErrorCode.RULE_VIOLATION,
        "TK-07",
    )
    _error(
        await client.post("/stock-slips", json=_transfer(to="CN9"), headers=kho),
        404,
        ErrorCode.NOT_FOUND,
        None,
    )
    _error(
        await client.post("/stock-slips", json=_transfer(quantity=11), headers=kho),
        409,
        ErrorCode.INSUFFICIENT_STOCK,
        "TK-03",
    )
    await conn.execute(
        "UPDATE products SET status = $1 WHERE product_id = 'A'", ProductStatus.DISCONTINUED
    )
    _error(
        await client.post("/stock-slips", json=_transfer(), headers=kho),
        422,
        ErrorCode.RULE_VIOLATION,
        "TK-07",
    )
    await conn.execute(
        "UPDATE products SET status = $1 WHERE product_id = 'A'", ProductStatus.ON_SALE
    )
    await conn.execute(
        "UPDATE branches SET status = $1 WHERE branch_id = $2", BranchStatus.INACTIVE, BRANCH_2
    )
    _error(
        await client.post("/stock-slips", json=_transfer(), headers=kho),
        422,
        ErrorCode.RULE_VIOLATION,
        "TK-07",
    )
    assert await _stock_a(client, kho) == (10, 10)


async def test_transfer_roles(client: httpx.AsyncClient, world: None) -> None:
    """K-01: chỉ NV kho lập và nhận; QL, NV kho xem hàng đến."""
    for employee_id in (MANAGER_ID, SALES_ID, HQ_ID):
        headers = await login_as(client, employee_id)
        _error(
            await client.post("/stock-slips", json=_transfer(), headers=headers),
            403,
            ErrorCode.FORBIDDEN,
            "K-01",
        )
        _error(
            await client.post("/stock-slips/PK000001/receive", headers=headers),
            403,
            ErrorCode.FORBIDDEN,
            "K-01",
        )
    ql2 = await login_as(client, QL2_ID)
    assert (await client.get("/stock-slips/incoming-transfers", headers=ql2)).status_code == 200
