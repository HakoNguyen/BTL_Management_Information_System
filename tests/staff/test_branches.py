"""6.4 Cập nhật thông tin chi nhánh (NV-04, K-05). Không thuộc 16 tình huống KT."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

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
    seed_order,
    seed_product,
    seed_return_slip,
    seed_shift,
    seed_staff,
    seed_stock,
    seed_stock_slip,
    seed_transaction,
)

from common import clock
from common.clock import VN_TZ
from common.constants import (
    BranchStatus,
    ErrorCode,
    OrderStatus,
    ReturnStatus,
    ShiftStatus,
    SlipStatus,
    TxnStatus,
)

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 13, 10, 0, tzinfo=VN_TZ)
LONG_AGO = NOW - timedelta(days=30)


@pytest.fixture
async def hq(client: httpx.AsyncClient, conn: asyncpg.Connection) -> dict[str, str]:
    await seed_staff(conn)
    clock.freeze(NOW)
    return await login_as(client, HQ_ID)


def _branch(branch_id: str, **overrides: object) -> dict[str, object]:
    return {
        "branch_id": branch_id,
        "name": f"Chi nhánh {branch_id}",
        "address": None,
        "phone": None,
        "closing_time": "22:00:00",
        "status": BranchStatus.ACTIVE,
        **overrides,
    }


async def _branch_status(conn: asyncpg.Connection, branch_id: str) -> str:
    return await conn.fetchval("SELECT status FROM branches WHERE branch_id = $1", branch_id)


async def test_list_branches_any_role(
    client: httpx.AsyncClient, conn: asyncpg.Connection, hq: dict[str, str]
) -> None:
    assert (await client.post(f"/branches/{BRANCH_2}/deactivate", headers=hq)).status_code == 200
    response = await client.get("/branches", headers=await login_as(client, SALES_ID))
    assert response.status_code == 200
    assert response.json() == [_branch(BRANCH_1), _branch(BRANCH_2, status=BranchStatus.INACTIVE)]


async def test_create_branch(client: httpx.AsyncClient, hq: dict[str, str]) -> None:
    body = {
        "branch_id": "CN3",
        "name": "Chi nhánh 3",
        "address": "1 Lê Lợi",
        "phone": "028123",
        "closing_time": "21:30",
    }
    response = await client.post("/branches", json=body, headers=hq)
    assert response.status_code == 201
    expected = {**body, "closing_time": "21:30:00", "status": BranchStatus.ACTIVE}
    assert response.json() == expected
    listed = (await client.get("/branches", headers=hq)).json()
    assert expected in listed


async def test_create_branch_duplicate(
    client: httpx.AsyncClient, conn: asyncpg.Connection, hq: dict[str, str]
) -> None:
    """NV-04: mã chi nhánh duy nhất."""
    response = await client.post(
        "/branches",
        json={"branch_id": BRANCH_1, "name": "Trùng", "closing_time": "20:00"},
        headers=hq,
    )
    assert response.status_code == 409
    assert response.json()["error_code"] == ErrorCode.DUPLICATE
    assert response.json()["details"]["rule"] == "NV-04"
    assert await conn.fetchval("SELECT name FROM branches WHERE branch_id = $1", BRANCH_1) == (
        f"Chi nhánh {BRANCH_1}"
    )


async def test_create_branch_requires_closing_time(
    client: httpx.AsyncClient, hq: dict[str, str]
) -> None:
    """NV-04, G-08: giờ đóng cửa bắt buộc."""
    response = await client.post("/branches", json={"branch_id": "CN3", "name": "X"}, headers=hq)
    assert response.status_code == 400
    assert response.json()["error_code"] == ErrorCode.VALIDATION_ERROR


async def test_update_branch(client: httpx.AsyncClient, hq: dict[str, str]) -> None:
    response = await client.patch(
        f"/branches/{BRANCH_1}", json={"name": "Tên mới", "closing_time": "21:00"}, headers=hq
    )
    assert response.status_code == 200
    assert response.json() == _branch(BRANCH_1, name="Tên mới", closing_time="21:00:00")

    response = await client.patch(f"/branches/{BRANCH_1}", json={"address": "2 Hai Bà"}, headers=hq)
    assert response.json() == _branch(
        BRANCH_1, name="Tên mới", closing_time="21:00:00", address="2 Hai Bà"
    )

    response = await client.patch(f"/branches/{BRANCH_1}", json={"address": None}, headers=hq)
    assert response.json()["address"] is None

    # NV-04: mã chi nhánh không đổi; trường branch_id gửi kèm bị bỏ qua
    response = await client.patch(f"/branches/{BRANCH_1}", json={"branch_id": "CN7"}, headers=hq)
    assert response.json()["branch_id"] == BRANCH_1
    assert [row["branch_id"] for row in (await client.get("/branches", headers=hq)).json()] == [
        BRANCH_1,
        BRANCH_2,
    ]


@pytest.mark.parametrize("body", [{"closing_time": None}, {"name": None}])
async def test_update_branch_rejects_null_required(
    client: httpx.AsyncClient, hq: dict[str, str], body: dict[str, object]
) -> None:
    """NV-04: giờ đóng cửa bắt buộc; tên bắt buộc."""
    response = await client.patch(f"/branches/{BRANCH_1}", json=body, headers=hq)
    assert response.status_code == 400
    assert response.json()["error_code"] == ErrorCode.VALIDATION_ERROR


async def test_update_branch_not_found(client: httpx.AsyncClient, hq: dict[str, str]) -> None:
    response = await client.patch("/branches/CN9", json={"name": "X"}, headers=hq)
    assert response.status_code == 404
    assert response.json()["error_code"] == ErrorCode.NOT_FOUND


async def _completed_order(conn: asyncpg.Connection, completed_at: datetime = LONG_AGO) -> str:
    return await seed_order(conn, SALES_ID, BRANCH_1, OrderStatus.COMPLETED, completed_at)


async def _approved_return(conn: asyncpg.Connection) -> tuple[str, str]:
    order_id = await _completed_order(conn)
    return_id = await seed_return_slip(
        conn, order_id, SALES_ID, ReturnStatus.APPROVED, decided_by=MANAGER_ID
    )
    return order_id, return_id


async def test_deactivate_branch(
    client: httpx.AsyncClient, conn: asyncpg.Connection, hq: dict[str, str]
) -> None:
    """NV-04: lịch sử đã kết thúc hết thì chi nhánh chuyển Ngừng hoạt động."""
    await seed_product(conn)
    await seed_stock(conn, BRANCH_1, "A", 0)
    shift_id = await seed_shift(conn, CASHIER_ID, status=ShiftStatus.SETTLED)
    await seed_order(conn, SALES_ID, BRANCH_1, OrderStatus.CANCELLED)
    order_id, return_id = await _approved_return(conn)
    await seed_transaction(conn, order_id, shift_id)
    await seed_transaction(conn, order_id, shift_id, TxnStatus.FAILED, return_id=return_id)
    await seed_transaction(conn, order_id, shift_id, TxnStatus.SUCCESS, return_id=return_id)
    await seed_return_slip(conn, order_id, SALES_ID, ReturnStatus.REJECTED, decided_by=MANAGER_ID)
    await seed_stock_slip(conn, BRANCH_1, WAREHOUSE_ID, SlipStatus.POSTED)
    await _completed_order(conn, NOW - timedelta(days=7, seconds=1))

    response = await client.post(f"/branches/{BRANCH_1}/deactivate", headers=hq)
    assert response.status_code == 200
    assert response.json() == _branch(BRANCH_1, status=BranchStatus.INACTIVE)
    assert await _branch_status(conn, BRANCH_1) == BranchStatus.INACTIVE


async def _stock_left(conn: asyncpg.Connection) -> None:
    await seed_product(conn)
    await seed_stock(conn, BRANCH_1, "A", 5)


async def _open_shift(conn: asyncpg.Connection) -> None:
    await seed_shift(conn, CASHIER_ID)


async def _shift_awaiting_confirmation(conn: asyncpg.Connection) -> None:
    await seed_shift(conn, CASHIER_ID, status=ShiftStatus.AWAITING_CONFIRMATION)


async def _draft_order(conn: asyncpg.Connection) -> None:
    await seed_order(conn, SALES_ID)


async def _awaiting_payment_order(conn: asyncpg.Connection) -> None:
    await seed_order(conn, SALES_ID, status=OrderStatus.AWAITING_PAYMENT)


async def _pending_stock_slip(conn: asyncpg.Connection) -> None:
    await seed_stock_slip(conn, BRANCH_1, WAREHOUSE_ID)


async def _pending_return_slip(conn: asyncpg.Connection) -> None:
    await seed_return_slip(conn, await _completed_order(conn), SALES_ID)


async def _approved_return_not_refunded(conn: asyncpg.Connection) -> None:
    await _approved_return(conn)


async def _approved_return_refund_failed(conn: asyncpg.Connection) -> None:
    order_id, return_id = await _approved_return(conn)
    shift_id = await seed_shift(conn, CASHIER_ID, status=ShiftStatus.SETTLED)
    await seed_transaction(conn, order_id, shift_id, TxnStatus.FAILED, return_id=return_id)


async def _approved_return_refund_pending(conn: asyncpg.Connection) -> None:
    order_id, return_id = await _approved_return(conn)
    shift_id = await seed_shift(conn, CASHIER_ID, status=ShiftStatus.SETTLED)
    await seed_transaction(conn, order_id, shift_id, TxnStatus.PENDING, return_id=return_id)


async def _completed_within_7_days(conn: asyncpg.Connection) -> None:
    await _completed_order(conn, NOW - timedelta(days=7))


@pytest.mark.parametrize(
    "setup",
    [
        _stock_left,
        _open_shift,
        _shift_awaiting_confirmation,
        _draft_order,
        _awaiting_payment_order,
        _pending_stock_slip,
        _pending_return_slip,
        _approved_return_not_refunded,
        _approved_return_refund_failed,
        _approved_return_refund_pending,
        _completed_within_7_days,
    ],
)
async def test_deactivate_rejected(
    client: httpx.AsyncClient,
    conn: asyncpg.Connection,
    hq: dict[str, str],
    setup: Callable[[asyncpg.Connection], Awaitable[None]],
) -> None:
    """NV-04: thiếu bất kỳ điều kiện nào thì từ chối, chi nhánh vẫn Hoạt động."""
    await setup(conn)
    response = await client.post(f"/branches/{BRANCH_1}/deactivate", headers=hq)
    assert response.status_code == 422
    assert response.json()["error_code"] == ErrorCode.RULE_VIOLATION
    assert response.json()["details"]["rule"] == "NV-04"
    assert await _branch_status(conn, BRANCH_1) == BranchStatus.ACTIVE


async def test_deactivate_twice_and_not_found(
    client: httpx.AsyncClient, hq: dict[str, str]
) -> None:
    assert (await client.post(f"/branches/{BRANCH_2}/deactivate", headers=hq)).status_code == 200
    again = await client.post(f"/branches/{BRANCH_2}/deactivate", headers=hq)
    assert again.status_code == 409
    assert again.json()["error_code"] == ErrorCode.INVALID_STATE
    missing = await client.post("/branches/CN9/deactivate", headers=hq)
    assert missing.status_code == 404


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("POST", "/branches", {"branch_id": "CN3", "name": "X", "closing_time": "20:00"}),
        ("PATCH", f"/branches/{BRANCH_1}", {"name": "X"}),
        ("POST", f"/branches/{BRANCH_2}/deactivate", None),
    ],
)
async def test_branch_writes_require_hq(
    client: httpx.AsyncClient,
    hq: dict[str, str],
    method: str,
    path: str,
    body: dict[str, object] | None,
) -> None:
    """K-01: chỉ Trụ sở ghi chi nhánh (ma trận 2.2)."""
    headers = await login_as(client, MANAGER_ID)
    response = await client.request(method, path, json=body, headers=headers)
    assert response.status_code == 403
    assert response.json()["details"]["rule"] == "K-01"


async def test_branch_cannot_be_deleted(client: httpx.AsyncClient, hq: dict[str, str]) -> None:
    """NV-04, K-05: không có thao tác xóa chi nhánh."""
    assert (await client.delete(f"/branches/{BRANCH_1}", headers=hq)).status_code == 405
