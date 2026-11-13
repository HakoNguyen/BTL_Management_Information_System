"""2.1 Ghi nhận, 2.2 cập nhật, 2.3 tra cứu khách hàng (KH-01, KH-02, KH-03)."""

from __future__ import annotations

from datetime import date, datetime

import asyncpg
import httpx
import pytest
from fixtures import (
    BRANCH_2,
    CASHIER_ID,
    HQ_ID,
    MANAGER_ID,
    SALES_ID,
    WAREHOUSE_ID,
    login_as,
    seed_employee,
    seed_order,
    seed_staff,
)

from common import clock
from common.clock import VN_TZ
from common.constants import ErrorCode, OrderStatus, Role

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 13, 10, 0, tzinfo=VN_TZ)
AN = {"full_name": "Nguyễn Văn An", "phone": "0901 234.567", "address": "Hà Nội"}


@pytest.fixture
async def sales(client: httpx.AsyncClient, conn: asyncpg.Connection) -> dict[str, str]:
    await seed_staff(conn)
    clock.freeze(NOW)
    return await login_as(client, SALES_ID)


def _error(response: httpx.Response, status: int, code: ErrorCode, rule: str | None) -> None:
    assert response.status_code == status, response.text
    body = response.json()
    assert body["error_code"] == code
    assert body["details"].get("rule") == rule


# ---------------------------------------------------------------- 2.1 Ghi nhận khách mới


async def test_create_customer(client: httpx.AsyncClient, sales: dict[str, str]) -> None:
    """KH-01: tạo mã mới, chuẩn hóa số điện thoại, ghi ngày đăng ký."""
    response = await client.post("/customers", json=AN, headers=sales)
    assert response.status_code == 201, response.text
    assert response.json() == {
        "customer_id": "KH000001",
        "full_name": "Nguyễn Văn An",
        "phone": "0901234567",
        "address": "Hà Nội",
        "registered_on": "2026-11-13",
    }


async def test_create_without_address(client: httpx.AsyncClient, sales: dict[str, str]) -> None:
    """KH-01: địa chỉ không bắt buộc."""
    body = {"full_name": "Bình", "phone": "+84 912-345-678"}
    response = await client.post("/customers", json=body, headers=sales)
    assert response.status_code == 201, response.text
    assert response.json()["phone"] == "0912345678"
    assert response.json()["address"] is None


async def test_create_duplicate_phone_returns_existing(
    client: httpx.AsyncClient, sales: dict[str, str], conn: asyncpg.Connection
) -> None:
    """KH-01: số đã có (sau chuẩn hóa) thì trả hồ sơ có sẵn, không tạo mới, không đổi hồ sơ."""
    created = (await client.post("/customers", json=AN, headers=sales)).json()
    clock.freeze(datetime(2026, 11, 20, 10, 0, tzinfo=VN_TZ))
    sales = await login_as(client, SALES_ID)  # đổi ngày làm token cũ hết hạn
    again = {"full_name": "Tên khác", "phone": "(+84) 901-234-567"}
    response = await client.post("/customers", json=again, headers=sales)
    assert response.status_code == 200, response.text
    assert response.json() == created
    assert await conn.fetchval("SELECT count(*) FROM customers WHERE customer_id <> 'KHLE'") == 1


@pytest.mark.parametrize(
    "body",
    [
        {"phone": "0901234567"},
        {"full_name": "  ", "phone": "0901234567"},
        {"full_name": "An"},
        {"full_name": "An", "phone": ""},
    ],
)
async def test_create_requires_name_and_phone(
    client: httpx.AsyncClient, sales: dict[str, str], body: dict[str, str]
) -> None:
    """KH-01: họ tên và số điện thoại bắt buộc."""
    response = await client.post("/customers", json=body, headers=sales)
    assert response.status_code == 400
    assert response.json()["error_code"] == ErrorCode.VALIDATION_ERROR


@pytest.mark.parametrize("phone", ["090123", "09012345678901", "1901234567", "09012a4567"])
async def test_create_invalid_phone(
    client: httpx.AsyncClient, sales: dict[str, str], phone: str
) -> None:
    """KH-01: số sau chuẩn hóa phải là 0 và 9 hoặc 10 chữ số."""
    response = await client.post(
        "/customers", json={"full_name": "An", "phone": phone}, headers=sales
    )
    _error(response, 400, ErrorCode.VALIDATION_ERROR, "KH-01")


# ---------------------------------------------------------------- 2.2 Cập nhật


async def test_update_customer(
    client: httpx.AsyncClient, sales: dict[str, str], conn: asyncpg.Connection
) -> None:
    """KH-01, KH-03: cập nhật hồ sơ; mã khách và đơn cũ không đổi."""
    await client.post("/customers", json=AN, headers=sales)
    order_id = await seed_order(
        conn, SALES_ID, status=OrderStatus.COMPLETED, completed_at=NOW, customer_id="KH000001"
    )
    body = {"full_name": "Nguyễn Văn Ân", "phone": "0987 654 321", "address": None}
    response = await client.patch("/customers/KH000001", json=body, headers=sales)
    assert response.status_code == 200, response.text
    assert response.json() == {
        "customer_id": "KH000001",
        "full_name": "Nguyễn Văn Ân",
        "phone": "0987654321",
        "address": None,
        "registered_on": "2026-11-13",
    }
    order = await conn.fetchrow(
        "SELECT customer_id, status FROM orders WHERE order_id = $1", order_id
    )
    assert dict(order) == {"customer_id": "KH000001", "status": OrderStatus.COMPLETED}


async def test_update_partial_keeps_other_fields(
    client: httpx.AsyncClient, sales: dict[str, str]
) -> None:
    """KH-01: trường không gửi thì giữ nguyên; gửi lại chính số của mình không bị coi là trùng."""
    await client.post("/customers", json=AN, headers=sales)
    response = await client.patch(
        "/customers/KH000001", json={"address": "Huế", "phone": "0901234567"}, headers=sales
    )
    assert response.status_code == 200, response.text
    assert response.json()["full_name"] == "Nguyễn Văn An"
    assert response.json()["address"] == "Huế"


async def test_update_phone_of_another_customer(
    client: httpx.AsyncClient, sales: dict[str, str]
) -> None:
    """KH-01: số mới thuộc hồ sơ khác thì từ chối."""
    await client.post("/customers", json=AN, headers=sales)
    await client.post(
        "/customers", json={"full_name": "Bình", "phone": "0912345678"}, headers=sales
    )
    response = await client.patch(
        "/customers/KH000002", json={"phone": "+84901234567"}, headers=sales
    )
    _error(response, 409, ErrorCode.DUPLICATE, "KH-01")


@pytest.mark.parametrize("body", [{"full_name": None}, {"phone": None}, {"full_name": " "}])
async def test_update_rejects_blank_required(
    client: httpx.AsyncClient, sales: dict[str, str], body: dict[str, str | None]
) -> None:
    """KH-01: họ tên, số điện thoại không được xóa."""
    await client.post("/customers", json=AN, headers=sales)
    response = await client.patch("/customers/KH000001", json=body, headers=sales)
    assert response.status_code == 400
    assert response.json()["error_code"] == ErrorCode.VALIDATION_ERROR


async def test_update_invalid_phone(client: httpx.AsyncClient, sales: dict[str, str]) -> None:
    """KH-01."""
    await client.post("/customers", json=AN, headers=sales)
    response = await client.patch("/customers/KH000001", json={"phone": "12345"}, headers=sales)
    _error(response, 400, ErrorCode.VALIDATION_ERROR, "KH-01")


async def test_update_walk_in_rejected(client: httpx.AsyncClient, sales: dict[str, str]) -> None:
    """KH-02: không sửa KHLE."""
    response = await client.patch("/customers/KHLE", json={"phone": "0901234567"}, headers=sales)
    _error(response, 422, ErrorCode.RULE_VIOLATION, "KH-02")


async def test_update_not_found(client: httpx.AsyncClient, sales: dict[str, str]) -> None:
    response = await client.patch("/customers/KH999999", json={"address": "X"}, headers=sales)
    _error(response, 404, ErrorCode.NOT_FOUND, None)


async def test_no_delete_endpoint(client: httpx.AsyncClient, sales: dict[str, str]) -> None:
    """KH-03: không có chức năng xóa khách."""
    await client.post("/customers", json=AN, headers=sales)
    response = await client.delete("/customers/KH000001", headers=sales)
    assert response.status_code == 405


# ---------------------------------------------------------------- 2.3 Tra cứu


async def test_search_by_phone_and_code(client: httpx.AsyncClient, sales: dict[str, str]) -> None:
    """2.3: tra theo số (đã chuẩn hóa) hoặc mã khách."""
    created = (await client.post("/customers", json=AN, headers=sales)).json()
    by_phone = await client.get("/customers", params={"phone": "+84 901 234 567"}, headers=sales)
    by_code = await client.get("/customers", params={"customer_id": "KH000001"}, headers=sales)
    assert by_phone.status_code == by_code.status_code == 200
    assert by_phone.json() == by_code.json() == [created]


async def test_search_not_found(client: httpx.AsyncClient, sales: dict[str, str]) -> None:
    """2.3: không khớp thì trả danh sách rỗng ("Không tìm thấy")."""
    by_phone = await client.get("/customers", params={"phone": "0999999999"}, headers=sales)
    by_code = await client.get("/customers", params={"customer_id": "KH000009"}, headers=sales)
    assert by_phone.json() == by_code.json() == []


@pytest.mark.parametrize("params", [{}, {"phone": "0901234567", "customer_id": "KH000001"}])
async def test_search_needs_exactly_one_criterion(
    client: httpx.AsyncClient, sales: dict[str, str], params: dict[str, str]
) -> None:
    response = await client.get("/customers", params=params, headers=sales)
    assert response.status_code == 400
    assert response.json()["error_code"] == ErrorCode.VALIDATION_ERROR


async def test_search_walk_in_rejected(client: httpx.AsyncClient, sales: dict[str, str]) -> None:
    """KH-02: không tra cứu KHLE."""
    response = await client.get("/customers", params={"customer_id": "KHLE"}, headers=sales)
    _error(response, 422, ErrorCode.RULE_VIOLATION, "KH-02")


async def test_search_invalid_phone(client: httpx.AsyncClient, sales: dict[str, str]) -> None:
    """KH-01: số tra cứu cũng chuẩn hóa; sai định dạng thì báo lỗi."""
    response = await client.get("/customers", params={"phone": "abc"}, headers=sales)
    _error(response, 400, ErrorCode.VALIDATION_ERROR, "KH-01")


# ---------------------------------------------------------------- Phân quyền


async def test_shared_across_branches(
    client: httpx.AsyncClient, sales: dict[str, str], conn: asyncpg.Connection
) -> None:
    """G-06: khách dùng chung toàn chuỗi; NVBH chi nhánh khác tra cứu và cập nhật được."""
    await client.post("/customers", json=AN, headers=sales)
    await seed_employee(conn, "NV-BH2", Role.SALES, BRANCH_2)
    other = await login_as(client, "NV-BH2")
    found = await client.get("/customers", params={"phone": "0901234567"}, headers=other)
    assert [c["customer_id"] for c in found.json()] == ["KH000001"]
    updated = await client.patch("/customers/KH000001", json={"address": "Huế"}, headers=other)
    assert updated.status_code == 200


@pytest.mark.parametrize("employee_id", [HQ_ID, MANAGER_ID, CASHIER_ID, WAREHOUSE_ID])
async def test_only_sales_allowed(
    client: httpx.AsyncClient, sales: dict[str, str], employee_id: str
) -> None:
    """Ma trận 2.2: chỉ NVBH thao tác nhóm 2."""
    await client.post("/customers", json=AN, headers=sales)
    headers = await login_as(client, employee_id)
    for response in (
        await client.post(
            "/customers", json={"full_name": "B", "phone": "0912345678"}, headers=headers
        ),
        await client.patch("/customers/KH000001", json={"address": "X"}, headers=headers),
        await client.get("/customers", params={"customer_id": "KH000001"}, headers=headers),
    ):
        assert response.status_code == 403
        assert response.json()["error_code"] == ErrorCode.FORBIDDEN


async def test_registered_on_uses_vietnam_date(
    client: httpx.AsyncClient, sales: dict[str, str]
) -> None:
    """2.1: ngày đăng ký theo giờ Việt Nam (00:30 ngày 14 giờ VN là 17:30 ngày 13 UTC)."""
    clock.freeze(datetime(2026, 11, 14, 0, 30, tzinfo=VN_TZ))
    sales = await login_as(client, SALES_ID)  # đổi ngày làm token cũ hết hạn
    response = await client.post("/customers", json=AN, headers=sales)
    assert response.json()["registered_on"] == date(2026, 11, 14).isoformat()
