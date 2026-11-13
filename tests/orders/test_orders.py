"""3.1 lập, sửa, chốt, mở lại đơn và phần hủy đơn của 3.4 (BH-01 đến BH-04, SP-03)."""

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
    login_as,
    seed_employee,
    seed_order,
    seed_product,
    seed_shift,
    seed_staff,
    seed_stock,
    seed_transaction,
)
from services import orders

from common import clock
from common.clock import VN_TZ
from common.constants import (
    BranchStatus,
    ErrorCode,
    OrderStatus,
    ProductStatus,
    Role,
    TxnStatus,
)
from common.errors import AppError

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 13, 10, 0, tzinfo=VN_TZ)
OTHER_SALES_ID = "NV-BH2"


@pytest.fixture
async def world(conn: asyncpg.Connection) -> None:
    await seed_staff(conn)
    await seed_employee(conn, OTHER_SALES_ID, Role.SALES, BRANCH_1)
    await seed_product(conn, "A")
    await seed_product(conn, "B", price=50_000)
    await seed_stock(conn, BRANCH_1, "A", 5)
    await seed_stock(conn, BRANCH_1, "B", 5)
    clock.freeze(NOW)


async def _create(
    client: httpx.AsyncClient, headers: dict[str, str], items: list | None = None
) -> dict:
    body = {"customer_id": "KHLE", "items": items or [{"product_id": "A", "quantity": 2}]}
    response = await client.post("/orders", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _error(response: httpx.Response, code: ErrorCode, rule: str | None = None) -> dict:
    body = response.json()
    assert body["error_code"] == code, response.text
    if rule is not None:
        assert body["details"]["rule"] == rule
    return body


async def test_create_draft(client: httpx.AsyncClient, world: None) -> None:
    """BH-01: đơn Đang lập thuộc chi nhánh và người lập, chưa có đơn giá chốt."""
    order = await _create(client, await login_as(client, SALES_ID))
    assert order["order_id"] == "DH000001"
    assert order["branch_id"] == BRANCH_1
    assert order["created_by"] == SALES_ID
    assert order["customer_id"] == "KHLE"
    assert order["status"] == OrderStatus.DRAFT
    assert order["total"] is None
    assert order["items"] == [{"product_id": "A", "quantity": 2, "unit_price": None}]


async def test_create_validation(client: httpx.AsyncClient, world: None) -> None:
    """BH-01: có ít nhất một dòng, mỗi sản phẩm một dòng, số lượng > 0, khách, sản phẩm có thật."""
    headers = await login_as(client, SALES_ID)
    cases = [
        ({"customer_id": "KHLE", "items": []}, ErrorCode.VALIDATION_ERROR),
        (
            {"customer_id": "KHLE", "items": [{"product_id": "A", "quantity": 0}]},
            ErrorCode.VALIDATION_ERROR,
        ),
        (
            {
                "customer_id": "KHLE",
                "items": [{"product_id": "A", "quantity": 1}, {"product_id": "A", "quantity": 1}],
            },
            ErrorCode.VALIDATION_ERROR,
        ),
        ({"customer_id": "KH999999", "items": [{"product_id": "A", "quantity": 1}]}, "NOT_FOUND"),
        ({"customer_id": "KHLE", "items": [{"product_id": "Z", "quantity": 1}]}, "NOT_FOUND"),
    ]
    for body, code in cases:
        response = await client.post("/orders", json=body, headers=headers)
        _error(response, ErrorCode(code))


async def test_roles(client: httpx.AsyncClient, world: None) -> None:
    """K-01: HQ, thu ngân, NV kho không lập đơn; thu ngân được xem."""
    order = await _create(client, await login_as(client, MANAGER_ID))
    for employee_id in (HQ_ID, CASHIER_ID):
        response = await client.post(
            "/orders",
            json={"customer_id": "KHLE", "items": [{"product_id": "A", "quantity": 1}]},
            headers=await login_as(client, employee_id),
        )
        _error(response, ErrorCode.FORBIDDEN, "K-01")
    cashier = await login_as(client, CASHIER_ID)
    response = await client.get(f"/orders/{order['order_id']}", headers=cashier)
    assert response.status_code == 200
    response = await client.get("/orders?status=DRAFT", headers=cashier)
    assert [o["order_id"] for o in response.json()] == [order["order_id"]]
    response = await client.get("/orders?status=CANCELLED", headers=cashier)
    assert response.json() == []


async def test_other_branch_forbidden(
    client: httpx.AsyncClient, conn: asyncpg.Connection, world: None
) -> None:
    """K-01: đơn của chi nhánh khác không xem, không sửa được."""
    order_id = await seed_order(conn, SALES_ID, branch_id=BRANCH_2)
    headers = await login_as(client, MANAGER_ID)
    _error(await client.get(f"/orders/{order_id}", headers=headers), ErrorCode.FORBIDDEN, "K-01")
    response = await client.post(f"/orders/{order_id}/confirm", headers=headers)
    _error(response, ErrorCode.FORBIDDEN, "K-01")
    assert (await client.get("/orders", headers=headers)).json() == []
    _error(await client.get("/orders/DH999999", headers=headers), ErrorCode.NOT_FOUND)


async def test_edit_items_only_draft(client: httpx.AsyncClient, world: None) -> None:
    """BH-03: chỉ sửa nội dung khi đơn Đang lập; sửa thay toàn bộ dòng."""
    headers = await login_as(client, SALES_ID)
    order = await _create(client, headers)
    url = f"/orders/{order['order_id']}"
    items = [{"product_id": "B", "quantity": 3}, {"product_id": "A", "quantity": 1}]
    response = await client.put(f"{url}/items", json={"items": items}, headers=headers)
    assert response.status_code == 200, response.text
    assert [(i["product_id"], i["quantity"]) for i in response.json()["items"]] == [
        ("A", 1),
        ("B", 3),
    ]
    assert (await client.post(f"{url}/confirm", headers=headers)).status_code == 200
    response = await client.put(f"{url}/items", json={"items": items}, headers=headers)
    _error(response, ErrorCode.INVALID_STATE, "BH-03")


async def test_only_creator_or_manager(client: httpx.AsyncClient, world: None) -> None:
    """BH-03, BH-04: NVBH chỉ thao tác đơn mình lập; QL thao tác mọi đơn của chi nhánh."""
    order = await _create(client, await login_as(client, SALES_ID))
    url = f"/orders/{order['order_id']}"
    other = await login_as(client, OTHER_SALES_ID)
    items = {"items": [{"product_id": "A", "quantity": 1}]}
    _error(
        await client.put(f"{url}/items", json=items, headers=other), ErrorCode.FORBIDDEN, "BH-03"
    )
    _error(await client.post(f"{url}/confirm", headers=other), ErrorCode.FORBIDDEN, "BH-03")
    response = await client.post(f"{url}/cancel", json={"reason": "x"}, headers=other)
    _error(response, ErrorCode.FORBIDDEN, "BH-04")

    manager = await login_as(client, MANAGER_ID)
    assert (await client.post(f"{url}/confirm", headers=manager)).status_code == 200
    _error(await client.post(f"{url}/reopen", headers=other), ErrorCode.FORBIDDEN, "BH-03")
    assert (await client.post(f"{url}/reopen", headers=manager)).status_code == 200
    response = await client.post(f"{url}/cancel", json={"reason": "Khách bỏ"}, headers=manager)
    assert response.status_code == 200
    assert response.json()["cancelled_by"] == MANAGER_ID


async def test_confirm_fixes_price(client: httpx.AsyncClient, world: None) -> None:
    """BH-02, SP-03: chốt chép giá hiện hành, ghi thời điểm chốt; không giữ hàng."""
    headers = await login_as(client, SALES_ID)
    order = await _create(
        client, headers, [{"product_id": "A", "quantity": 2}, {"product_id": "B", "quantity": 1}]
    )
    response = await client.post(f"/orders/{order['order_id']}/confirm", headers=headers)
    assert response.status_code == 200, response.text
    confirmed = response.json()
    assert confirmed["status"] == OrderStatus.AWAITING_PAYMENT
    assert datetime.fromisoformat(confirmed["confirmed_at"]) == NOW
    assert confirmed["total"] == 250_000
    assert [i["unit_price"] for i in confirmed["items"]] == [100_000, 50_000]
    stock = {row["product_id"]: row for row in (await client.get("/stock", headers=headers)).json()}
    assert stock["A"]["available"] == 5  # chốt không giữ hàng
    response = await client.post(f"/orders/{order['order_id']}/confirm", headers=headers)
    _error(response, ErrorCode.INVALID_STATE, "BH-02")


async def test_confirm_insufficient_stock(client: httpx.AsyncClient, world: None) -> None:
    """BH-02: vượt tồn khả dụng thì đơn vẫn Đang lập, kèm dòng thiếu."""
    headers = await login_as(client, SALES_ID)
    order = await _create(client, headers, [{"product_id": "A", "quantity": 6}])
    response = await client.post(f"/orders/{order['order_id']}/confirm", headers=headers)
    body = _error(response, ErrorCode.INSUFFICIENT_STOCK, "BH-02")
    assert body["details"]["lines"] == [{"product_id": "A", "quantity": 6, "available": 5}]
    order = (await client.get(f"/orders/{order['order_id']}", headers=headers)).json()
    assert order["status"] == OrderStatus.DRAFT
    assert order["confirmed_at"] is None


async def test_confirm_discontinued(client: httpx.AsyncClient, world: None) -> None:
    """BH-02: sản phẩm Ngừng bán thì không chốt; ngừng bán sau khi chốt không ảnh hưởng đơn."""
    headers = await login_as(client, SALES_ID)
    first = await _create(client, headers)
    assert (await client.post(f"/orders/{first['order_id']}/confirm", headers=headers)).is_success
    second = await _create(client, headers)
    response = await client.put(
        "/products/A/status",
        json={"status": ProductStatus.DISCONTINUED},
        headers=await login_as(client, HQ_ID),
    )
    assert response.status_code == 200, response.text
    response = await client.post(f"/orders/{second['order_id']}/confirm", headers=headers)
    body = _error(response, ErrorCode.RULE_VIOLATION, "BH-02")
    assert body["details"]["product_ids"] == ["A"]
    first = (await client.get(f"/orders/{first['order_id']}", headers=headers)).json()
    assert first["status"] == OrderStatus.AWAITING_PAYMENT
    assert first["total"] == 200_000


async def test_confirm_inactive_branch(
    client: httpx.AsyncClient, conn: asyncpg.Connection, world: None
) -> None:
    """BH-02: chi nhánh Ngừng hoạt động thì không chốt."""
    headers = await login_as(client, SALES_ID)
    order = await _create(client, headers)
    # 6.4 không đóng chi nhánh còn đơn mở, nên dựng trạng thái này bằng SQL (chốt chặn phòng thủ)
    await conn.execute(
        "UPDATE branches SET status = $1 WHERE branch_id = $2", BranchStatus.INACTIVE, BRANCH_1
    )
    response = await client.post(f"/orders/{order['order_id']}/confirm", headers=headers)
    _error(response, ErrorCode.RULE_VIOLATION, "BH-02")


async def test_reopen_and_cancel_states(
    client: httpx.AsyncClient, conn: asyncpg.Connection, world: None
) -> None:
    """BH-03, BH-04: mở lại chỉ từ Chờ thanh toán; đơn Hoàn tất, Đã hủy không hủy được."""
    headers = await login_as(client, SALES_ID)
    order = await _create(client, headers)
    url = f"/orders/{order['order_id']}"
    _error(await client.post(f"{url}/reopen", headers=headers), ErrorCode.INVALID_STATE, "BH-03")
    response = await client.post(f"{url}/cancel", json={"reason": " "}, headers=headers)
    _error(response, ErrorCode.VALIDATION_ERROR)
    response = await client.post(f"{url}/cancel", json={"reason": "Khách đổi ý"}, headers=headers)
    assert response.status_code == 200, response.text
    cancelled = response.json()
    assert cancelled["status"] == OrderStatus.CANCELLED
    assert cancelled["cancelled_by"] == SALES_ID
    assert cancelled["cancel_reason"] == "Khách đổi ý"
    assert datetime.fromisoformat(cancelled["cancelled_at"]) == NOW
    response = await client.post(f"{url}/cancel", json={"reason": "x"}, headers=headers)
    _error(response, ErrorCode.INVALID_STATE, "BH-04")

    completed = await seed_order(conn, SALES_ID, status=OrderStatus.COMPLETED, completed_at=NOW)
    response = await client.post(
        f"/orders/{completed}/cancel", json={"reason": "x"}, headers=headers
    )
    _error(response, ErrorCode.INVALID_STATE, "BH-04")


async def test_pending_txn_blocks_reopen_and_cancel(
    client: httpx.AsyncClient, conn: asyncpg.Connection, world: None
) -> None:
    """BH-03, BH-04: đơn có giao dịch Chờ kết quả không mở lại, không hủy được."""
    headers = await login_as(client, SALES_ID)
    order = await _create(client, headers)
    url = f"/orders/{order['order_id']}"
    assert (await client.post(f"{url}/confirm", headers=headers)).is_success
    shift_id = await seed_shift(conn, CASHIER_ID)
    await seed_transaction(conn, order["order_id"], shift_id, status=TxnStatus.PENDING)
    _error(await client.post(f"{url}/reopen", headers=headers), ErrorCode.INVALID_STATE, "BH-03")
    response = await client.post(f"{url}/cancel", json={"reason": "x"}, headers=headers)
    _error(response, ErrorCode.INVALID_STATE, "BH-04")


async def test_mark_completed(
    client: httpx.AsyncClient, conn: asyncpg.Connection, world: None
) -> None:
    """Hàm giao cho 3.2: Chờ thanh toán sang Hoàn tất, ghi thời điểm; trạng thái khác thì lỗi."""
    headers = await login_as(client, SALES_ID)
    order = await _create(client, headers)
    with pytest.raises(AppError) as error:
        await orders.mark_completed(conn, order["order_id"], NOW)
    assert error.value.error_code == ErrorCode.INVALID_STATE
    assert (await client.post(f"/orders/{order['order_id']}/confirm", headers=headers)).is_success
    await orders.mark_completed(conn, order["order_id"], NOW)
    row = await conn.fetchrow(
        "SELECT status, completed_at FROM orders WHERE order_id = $1", order["order_id"]
    )
    assert row["status"] == OrderStatus.COMPLETED
    assert row["completed_at"] == NOW
