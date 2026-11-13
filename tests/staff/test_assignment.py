"""6.2 Phân công chi nhánh và vai trò (NV-01, NV-02, K-05). Không thuộc 16 tình huống KT."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

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
    seed_order,
    seed_return_slip,
    seed_shift,
    seed_staff,
    seed_stock_slip,
)

from common.constants import (
    EmployeeStatus,
    ErrorCode,
    OrderStatus,
    ReturnStatus,
    Role,
    ShiftStatus,
    SlipStatus,
)

pytestmark = pytest.mark.db


@pytest.fixture
async def hq(client: httpx.AsyncClient, conn: asyncpg.Connection) -> dict[str, str]:
    await seed_staff(conn)
    return await login_as(client, HQ_ID)


async def _assign(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    employee_id: str,
    role: Role,
    branch_id: str | None,
) -> httpx.Response:
    return await client.put(
        f"/employees/{employee_id}/assignment",
        json={"role": role, "branch_id": branch_id},
        headers=headers,
    )


async def _assignment(conn: asyncpg.Connection, employee_id: str) -> tuple[str, str | None]:
    row = await conn.fetchrow(
        "SELECT role, branch_id FROM employees WHERE employee_id = $1", employee_id
    )
    return row["role"], row["branch_id"]


async def test_move_branch(client: httpx.AsyncClient, hq: dict[str, str]) -> None:
    """NV-02, K-01: chuyển chi nhánh có hiệu lực ngay với phiên đang mở."""
    sales_headers = await login_as(client, SALES_ID)
    response = await _assign(client, hq, SALES_ID, Role.SALES, BRANCH_2)
    assert response.status_code == 200
    assert (response.json()["role"], response.json()["branch_id"]) == (Role.SALES, BRANCH_2)
    me = await client.get("/auth/me", headers=sales_headers)
    assert me.json()["branch_id"] == BRANCH_2


@pytest.mark.parametrize(("role", "branch_id"), [(Role.CASHIER, BRANCH_1), (Role.HQ, None)])
async def test_change_role(
    client: httpx.AsyncClient,
    conn: asyncpg.Connection,
    hq: dict[str, str],
    role: Role,
    branch_id: str | None,
) -> None:
    """NV-02: thiếu thu ngân thì trụ sở phân công nhân viên sang vai trò Thu ngân."""
    response = await _assign(client, hq, SALES_ID, role, branch_id)
    assert response.status_code == 200
    assert await _assignment(conn, SALES_ID) == (role, branch_id)


@pytest.mark.parametrize(("role", "branch_id"), [(Role.HQ, BRANCH_1), (Role.SALES, None)])
async def test_role_branch_mismatch(
    client: httpx.AsyncClient,
    conn: asyncpg.Connection,
    hq: dict[str, str],
    role: Role,
    branch_id: str | None,
) -> None:
    """NV-01."""
    response = await _assign(client, hq, SALES_ID, role, branch_id)
    assert response.status_code == 422
    assert response.json()["details"]["rule"] == "NV-01"
    assert await _assignment(conn, SALES_ID) == (Role.SALES, BRANCH_1)


async def test_assign_unknown(client: httpx.AsyncClient, hq: dict[str, str]) -> None:
    assert (await _assign(client, hq, SALES_ID, Role.SALES, "CN9")).status_code == 404
    assert (await _assign(client, hq, "NV-X", Role.SALES, BRANCH_2)).status_code == 404


async def test_assign_to_inactive_branch(
    client: httpx.AsyncClient, conn: asyncpg.Connection, hq: dict[str, str]
) -> None:
    """NV-04: không phân công vào chi nhánh Ngừng hoạt động (quyết định vòng 1)."""
    assert (await client.post(f"/branches/{BRANCH_2}/deactivate", headers=hq)).status_code == 200
    response = await _assign(client, hq, SALES_ID, Role.SALES, BRANCH_2)
    assert response.status_code == 422
    assert response.json()["details"]["rule"] == "NV-04"
    assert await _assignment(conn, SALES_ID) == (Role.SALES, BRANCH_1)


async def test_assign_left_employee(
    client: httpx.AsyncClient, conn: asyncpg.Connection, hq: dict[str, str]
) -> None:
    """Nhân viên Đã nghỉ không được phân công (quyết định vòng 1)."""
    await seed_employee(
        conn, "NV-CU", Role.SALES, BRANCH_1, with_account=False, status=EmployeeStatus.LEFT
    )
    response = await _assign(client, hq, "NV-CU", Role.SALES, BRANCH_2)
    assert response.status_code == 409
    assert response.json()["error_code"] == ErrorCode.INVALID_STATE


async def _open_shift(conn: asyncpg.Connection) -> str:
    await seed_shift(conn, CASHIER_ID)
    return CASHIER_ID


async def _shift_awaiting_confirmation(conn: asyncpg.Connection) -> str:
    await seed_shift(conn, CASHIER_ID, status=ShiftStatus.AWAITING_CONFIRMATION)
    return CASHIER_ID


async def _draft_order(conn: asyncpg.Connection) -> str:
    await seed_order(conn, SALES_ID)
    return SALES_ID


async def _awaiting_payment_order(conn: asyncpg.Connection) -> str:
    await seed_order(conn, SALES_ID, status=OrderStatus.AWAITING_PAYMENT)
    return SALES_ID


async def _pending_return_slip(conn: asyncpg.Connection) -> str:
    order_id = await seed_order(conn, MANAGER_ID, status=OrderStatus.COMPLETED)
    await seed_return_slip(conn, order_id, SALES_ID)
    return SALES_ID


async def _pending_stock_slip(conn: asyncpg.Connection) -> str:
    await seed_stock_slip(conn, BRANCH_1, WAREHOUSE_ID)
    return WAREHOUSE_ID


@pytest.mark.parametrize(
    "setup",
    [
        _open_shift,
        _shift_awaiting_confirmation,
        _draft_order,
        _awaiting_payment_order,
        _pending_return_slip,
        _pending_stock_slip,
    ],
)
async def test_rejected_with_unfinished_documents(
    client: httpx.AsyncClient,
    conn: asyncpg.Connection,
    hq: dict[str, str],
    setup: Callable[[asyncpg.Connection], Awaitable[str]],
) -> None:
    """NV-02: còn ca chưa chốt, đơn dở, phiếu chờ xử lý do mình lập thì từ chối."""
    employee_id = await setup(conn)
    before = await _assignment(conn, employee_id)
    response = await _assign(client, hq, employee_id, before[0], BRANCH_2)
    assert response.status_code == 422
    assert response.json()["error_code"] == ErrorCode.RULE_VIOLATION
    assert response.json()["details"]["rule"] == "NV-02"
    assert await _assignment(conn, employee_id) == before


async def test_not_blocked_by_finished_or_others_documents(
    client: httpx.AsyncClient, conn: asyncpg.Connection, hq: dict[str, str]
) -> None:
    """NV-02 chỉ xét chứng từ chưa kết thúc do chính nhân viên đó lập."""
    await seed_shift(conn, SALES_ID, status=ShiftStatus.SETTLED)
    completed = await seed_order(conn, SALES_ID, status=OrderStatus.COMPLETED)
    await seed_order(conn, SALES_ID, status=OrderStatus.CANCELLED)
    await seed_return_slip(conn, completed, SALES_ID, ReturnStatus.APPROVED, decided_by=MANAGER_ID)
    await seed_stock_slip(conn, BRANCH_1, SALES_ID, SlipStatus.POSTED)
    await seed_order(conn, MANAGER_ID)
    await seed_return_slip(conn, completed, MANAGER_ID)
    await seed_stock_slip(conn, BRANCH_1, WAREHOUSE_ID)
    await seed_shift(conn, CASHIER_ID)

    response = await _assign(client, hq, SALES_ID, Role.SALES, BRANCH_2)
    assert response.status_code == 200


async def test_old_documents_keep_branch_and_creator(
    client: httpx.AsyncClient, conn: asyncpg.Connection, hq: dict[str, str]
) -> None:
    """K-05: chứng từ cũ giữ chi nhánh và người lập gốc."""
    order_id = await seed_order(conn, SALES_ID, status=OrderStatus.COMPLETED)
    assert (await _assign(client, hq, SALES_ID, Role.CASHIER, BRANCH_2)).status_code == 200
    row = await conn.fetchrow(
        "SELECT branch_id, created_by FROM orders WHERE order_id = $1", order_id
    )
    assert (row["branch_id"], row["created_by"]) == (BRANCH_1, SALES_ID)
