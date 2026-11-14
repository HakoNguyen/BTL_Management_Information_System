"""3.5 Ca thu ngân: mở, đóng, đóng thay, xác nhận chốt, xem (CA-01 đến CA-04, K-01, K-02)."""

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
    create_awaiting_order,
    login_as,
    open_shift,
    seed_employee,
    seed_product,
    seed_staff,
    seed_stock,
    start_payment,
)

from common import clock
from common.clock import VN_TZ
from common.constants import BranchStatus, EmployeeStatus, ErrorCode, Role, ShiftStatus, TxnMethod

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 13, 10, 0, tzinfo=VN_TZ)
CASHIER_2 = "NV-TN2"
MANAGER_2 = "NV-QL2"
CASHIER_CN2 = "NV-TN-CN2"


@pytest.fixture
async def staff(conn: asyncpg.Connection) -> None:
    await seed_staff(conn)
    await seed_employee(conn, CASHIER_2, Role.CASHIER, BRANCH_1)
    await seed_employee(conn, MANAGER_2, Role.MANAGER, BRANCH_2)
    await seed_employee(conn, CASHIER_CN2, Role.CASHIER, BRANCH_2)
    clock.freeze(NOW)


def _error(response: httpx.Response, code: ErrorCode, rule: str) -> None:
    body = response.json()
    assert body["error_code"] == code, body
    assert body["details"]["rule"] == rule, body


# ---------------------------------------------------------------- CA-01 Mở ca


async def test_open_shift(client: httpx.AsyncClient, staff: None) -> None:
    """CA-01: ca Đang mở gắn thu ngân và chi nhánh lúc mở, ghi tiền đầu ca."""
    tn = await login_as(client, CASHIER_ID)
    assert (await client.get("/shifts/current", headers=tn)).json() is None
    response = await client.post("/shifts", json={"opening_cash": 500_000}, headers=tn)
    assert response.status_code == 201, response.text
    shift = response.json()
    assert shift["shift_id"] == "CA000001"
    assert (shift["status"], shift["branch_id"], shift["cashier_id"]) == (
        ShiftStatus.OPEN,
        BRANCH_1,
        CASHIER_ID,
    )
    assert shift["opening_cash"] == 500_000
    assert shift["expected_cash"] == 500_000
    assert shift["variance"] is None
    assert datetime.fromisoformat(shift["opened_at"]) == NOW
    current = (await client.get("/shifts/current", headers=tn)).json()
    assert current["shift_id"] == shift["shift_id"]


async def test_open_shift_zero_cash(client: httpx.AsyncClient, staff: None) -> None:
    """CA-01: tiền đầu ca = 0 hợp lệ."""
    tn = await login_as(client, CASHIER_ID)
    await open_shift(client, tn, 0)


async def test_open_shift_negative_cash(client: httpx.AsyncClient, staff: None) -> None:
    """CA-01: tiền đầu ca âm."""
    tn = await login_as(client, CASHIER_ID)
    response = await client.post("/shifts", json={"opening_cash": -1}, headers=tn)
    _error(response, ErrorCode.VALIDATION_ERROR, "CA-01")


async def test_open_second_shift(client: httpx.AsyncClient, staff: None) -> None:
    """CA-01: mỗi thu ngân tối đa một ca Đang mở."""
    tn = await login_as(client, CASHIER_ID)
    await open_shift(client, tn)
    response = await client.post("/shifts", json={"opening_cash": 0}, headers=tn)
    _error(response, ErrorCode.INVALID_STATE, "CA-01")


async def test_open_shift_inactive_branch(
    client: httpx.AsyncClient, conn: asyncpg.Connection, staff: None
) -> None:
    """CA-01: chi nhánh phải Hoạt động."""
    await conn.execute(
        "UPDATE branches SET status = $1 WHERE branch_id = $2", BranchStatus.INACTIVE, BRANCH_1
    )
    tn = await login_as(client, CASHIER_ID)
    response = await client.post("/shifts", json={"opening_cash": 0}, headers=tn)
    _error(response, ErrorCode.RULE_VIOLATION, "CA-01")


@pytest.mark.parametrize("employee_id", [MANAGER_ID, SALES_ID, WAREHOUSE_ID, HQ_ID])
async def test_open_shift_forbidden(
    client: httpx.AsyncClient, staff: None, employee_id: str
) -> None:
    """K-01: chỉ thu ngân mở ca."""
    headers = await login_as(client, employee_id)
    response = await client.post("/shifts", json={"opening_cash": 0}, headers=headers)
    _error(response, ErrorCode.FORBIDDEN, "K-01")


# ---------------------------------------------------------------- CA-02 Đóng ca


async def test_close_shift_no_variance(client: httpx.AsyncClient, staff: None) -> None:
    """CA-02: chênh lệch 0 không cần lý do; ca Chờ xác nhận, ghi thời điểm đóng."""
    tn = await login_as(client, CASHIER_ID)
    shift_id = await open_shift(client, tn, 200_000)
    response = await client.post(
        f"/shifts/{shift_id}/close", json={"counted_cash": 200_000}, headers=tn
    )
    assert response.status_code == 200, response.text
    shift = response.json()
    assert shift["status"] == ShiftStatus.AWAITING_CONFIRMATION
    assert shift["variance"] == 0
    assert datetime.fromisoformat(shift["closed_at"]) == NOW
    assert (await client.get("/shifts/current", headers=tn)).json() is None


async def test_close_shift_variance_needs_reason(client: httpx.AsyncClient, staff: None) -> None:
    """CA-02: chênh lệch khác 0 phải có lý do."""
    tn = await login_as(client, CASHIER_ID)
    shift_id = await open_shift(client, tn, 200_000)
    for body in ({"counted_cash": 210_000}, {"counted_cash": 210_000, "variance_reason": " "}):
        response = await client.post(f"/shifts/{shift_id}/close", json=body, headers=tn)
        _error(response, ErrorCode.RULE_VIOLATION, "CA-02")
    body = {"counted_cash": 210_000, "variance_reason": "Khách gửi lại tiền thừa"}
    response = await client.post(f"/shifts/{shift_id}/close", json=body, headers=tn)
    assert response.json()["variance"] == 10_000
    assert response.json()["variance_reason"] == "Khách gửi lại tiền thừa"


async def test_close_shift_negative_count(client: httpx.AsyncClient, staff: None) -> None:
    """CA-02: tiền kiểm đếm âm."""
    tn = await login_as(client, CASHIER_ID)
    shift_id = await open_shift(client, tn)
    response = await client.post(f"/shifts/{shift_id}/close", json={"counted_cash": -5}, headers=tn)
    _error(response, ErrorCode.VALIDATION_ERROR, "CA-02")


async def test_close_shift_twice(client: httpx.AsyncClient, staff: None) -> None:
    """CA-02: chỉ đóng ca Đang mở."""
    tn = await login_as(client, CASHIER_ID)
    shift_id = await open_shift(client, tn)
    await client.post(f"/shifts/{shift_id}/close", json={"counted_cash": 0}, headers=tn)
    response = await client.post(f"/shifts/{shift_id}/close", json={"counted_cash": 0}, headers=tn)
    _error(response, ErrorCode.INVALID_STATE, "CA-02")


async def test_close_shift_pending_cash(
    client: httpx.AsyncClient, conn: asyncpg.Connection, staff: None
) -> None:
    """CA-02: không đóng được khi còn giao dịch tiền mặt Chờ kết quả; ca đóng thì ngừng nhận
    giao dịch mới (TT-01)."""
    await seed_product(conn, "A")
    await seed_stock(conn, BRANCH_1, "A", 5)
    bh = await login_as(client, SALES_ID)
    tn = await login_as(client, CASHIER_ID)
    shift_id = await open_shift(client, tn)
    order_id = await create_awaiting_order(client, bh, {"A": 1})
    txn = await start_payment(client, tn, order_id, TxnMethod.CASH)
    response = await client.post(f"/shifts/{shift_id}/close", json={"counted_cash": 0}, headers=tn)
    _error(response, ErrorCode.RULE_VIOLATION, "CA-02")

    await client.post(
        f"/transactions/{txn['txn_id']}/confirm-cash", json={"result": "FAILED"}, headers=tn
    )
    response = await client.post(f"/shifts/{shift_id}/close", json={"counted_cash": 0}, headers=tn)
    assert response.status_code == 200, response.text
    response = await client.post(
        f"/orders/{order_id}/payments", json={"method": TxnMethod.CASH}, headers=tn
    )
    _error(response, ErrorCode.RULE_VIOLATION, "TT-01")


async def test_close_other_cashier_shift(client: httpx.AsyncClient, staff: None) -> None:
    """K-01: thu ngân chỉ đóng ca của mình."""
    shift_id = await open_shift(client, await login_as(client, CASHIER_ID))
    other = await login_as(client, CASHIER_2)
    response = await client.post(
        f"/shifts/{shift_id}/close", json={"counted_cash": 0}, headers=other
    )
    _error(response, ErrorCode.FORBIDDEN, "K-01")


# ---------------------------------------------------------------- CA-04 Đóng ca thay


def _proxy(witness_id: str, counted_cash: int = 0) -> dict:
    return {"counted_cash": counted_cash, "witness_id": witness_id, "proxy_reason": "Vắng đột xuất"}


@pytest.mark.parametrize("witness_id", [CASHIER_ID, MANAGER_ID, CASHIER_CN2, "NV-NGHI", "NV-X"])
async def test_proxy_close_bad_witness(
    client: httpx.AsyncClient, conn: asyncpg.Connection, staff: None, witness_id: str
) -> None:
    """CA-04: người làm chứng là nhân viên Đang làm cùng chi nhánh, khác QL và thu ngân của ca."""
    await seed_employee(conn, "NV-NGHI", Role.SALES, BRANCH_1, status=EmployeeStatus.LEFT)
    shift_id = await open_shift(client, await login_as(client, CASHIER_ID))
    ql = await login_as(client, MANAGER_ID)
    response = await client.post(
        f"/shifts/{shift_id}/proxy-close", json=_proxy(witness_id), headers=ql
    )
    _error(response, ErrorCode.RULE_VIOLATION, "CA-04")


async def test_proxy_close_variance_needs_reason(client: httpx.AsyncClient, staff: None) -> None:
    """CA-02, CA-04: đóng thay cũng phải có lý do khi chênh lệch."""
    shift_id = await open_shift(client, await login_as(client, CASHIER_ID))
    ql = await login_as(client, MANAGER_ID)
    response = await client.post(
        f"/shifts/{shift_id}/proxy-close", json=_proxy(SALES_ID, 1_000), headers=ql
    )
    _error(response, ErrorCode.RULE_VIOLATION, "CA-02")


async def test_proxy_close_forbidden(client: httpx.AsyncClient, staff: None) -> None:
    """K-01: chỉ QL cùng chi nhánh đóng thay."""
    shift_id = await open_shift(client, await login_as(client, CASHIER_ID))
    for employee_id, rule in ((MANAGER_2, "K-01"), (CASHIER_2, "K-01"), (HQ_ID, "K-01")):
        headers = await login_as(client, employee_id)
        response = await client.post(
            f"/shifts/{shift_id}/proxy-close", json=_proxy(SALES_ID), headers=headers
        )
        _error(response, ErrorCode.FORBIDDEN, rule)


async def test_proxy_close_not_open(client: httpx.AsyncClient, staff: None) -> None:
    """CA-02: chỉ đóng thay ca Đang mở."""
    tn = await login_as(client, CASHIER_ID)
    shift_id = await open_shift(client, tn)
    await client.post(f"/shifts/{shift_id}/close", json={"counted_cash": 0}, headers=tn)
    ql = await login_as(client, MANAGER_ID)
    response = await client.post(
        f"/shifts/{shift_id}/proxy-close", json=_proxy(SALES_ID), headers=ql
    )
    _error(response, ErrorCode.INVALID_STATE, "CA-02")


# ---------------------------------------------------------------- CA-03 Xác nhận chốt


async def _closed(client: httpx.AsyncClient) -> str:
    tn = await login_as(client, CASHIER_ID)
    shift_id = await open_shift(client, tn)
    response = await client.post(f"/shifts/{shift_id}/close", json={"counted_cash": 0}, headers=tn)
    assert response.status_code == 200, response.text
    return shift_id


async def test_confirm_shift(client: httpx.AsyncClient, staff: None) -> None:
    """CA-03: QL xác nhận ca thu ngân tự đóng; ghi người, thời điểm chốt; không chốt lại."""
    shift_id = await _closed(client)
    ql = await login_as(client, MANAGER_ID)
    response = await client.post(f"/shifts/{shift_id}/confirm", headers=ql)
    assert response.status_code == 200, response.text
    shift = response.json()
    assert shift["status"] == ShiftStatus.SETTLED
    assert shift["confirmed_by"] == MANAGER_ID
    assert datetime.fromisoformat(shift["settled_at"]) == NOW
    assert shift["confirm_reason"] is None
    response = await client.post(f"/shifts/{shift_id}/confirm", headers=ql)
    _error(response, ErrorCode.INVALID_STATE, "CA-03")


async def test_confirm_open_shift(client: httpx.AsyncClient, staff: None) -> None:
    """CA-03: ca Đang mở chưa xác nhận được."""
    shift_id = await open_shift(client, await login_as(client, CASHIER_ID))
    response = await client.post(
        f"/shifts/{shift_id}/confirm", headers=await login_as(client, MANAGER_ID)
    )
    _error(response, ErrorCode.INVALID_STATE, "CA-03")


async def test_confirm_shift_forbidden(client: httpx.AsyncClient, staff: None) -> None:
    """K-01: QL chi nhánh khác, thu ngân không xác nhận chốt ca."""
    shift_id = await _closed(client)
    for employee_id, rule in ((MANAGER_2, "K-01"), (CASHIER_ID, "K-01")):
        response = await client.post(
            f"/shifts/{shift_id}/confirm", headers=await login_as(client, employee_id)
        )
        _error(response, ErrorCode.FORBIDDEN, rule)


async def test_hq_confirm_requires_reason(client: httpx.AsyncClient, staff: None) -> None:
    """2.2, K-02, K-03: trụ sở duyệt thay xác nhận chốt ca thu ngân tự đóng, bắt buộc lý do."""
    shift_id = await _closed(client)
    hq = await login_as(client, HQ_ID)
    for body in (None, {}, {"confirm_reason": "   "}):
        response = await client.post(f"/shifts/{shift_id}/confirm", json=body, headers=hq)
        _error(response, ErrorCode.VALIDATION_ERROR, "K-02")
    response = await client.post(
        f"/shifts/{shift_id}/confirm", json={"confirm_reason": "QL nghỉ phép"}, headers=hq
    )
    assert response.status_code == 200, response.text
    shift = response.json()
    assert shift["status"] == ShiftStatus.SETTLED
    assert shift["confirmed_by"] == HQ_ID
    assert shift["confirm_reason"] == "QL nghỉ phép"
    assert shift["settled_at"] is not None


async def test_manager_confirm_reason_optional(client: httpx.AsyncClient, staff: None) -> None:
    """K-03: QL xác nhận chốt ghi lý do nếu có (không có thì để trống, xem test_confirm_shift)."""
    shift_id = await _closed(client)
    response = await client.post(
        f"/shifts/{shift_id}/confirm",
        json={"confirm_reason": "Đã nhận tiền"},
        headers=await login_as(client, MANAGER_ID),
    )
    assert response.status_code == 200, response.text
    assert response.json()["confirm_reason"] == "Đã nhận tiền"


# ---------------------------------------------------------------- Xem ca


async def test_list_and_get_shifts(client: httpx.AsyncClient, staff: None) -> None:
    """K-01: TN xem ca của mình, QL ca của chi nhánh, HQ mọi chi nhánh."""
    s1 = await open_shift(client, await login_as(client, CASHIER_ID))
    s2 = await open_shift(client, await login_as(client, CASHIER_2))
    s3 = await open_shift(client, await login_as(client, CASHIER_CN2))

    async def ids(employee_id: str, query: str = "") -> list[str]:
        headers = await login_as(client, employee_id)
        response = await client.get(f"/shifts{query}", headers=headers)
        assert response.status_code == 200, response.text
        return [s["shift_id"] for s in response.json()]

    assert await ids(CASHIER_ID) == [s1]
    assert await ids(MANAGER_ID) == [s2, s1]
    assert await ids(HQ_ID) == [s3, s2, s1]
    assert await ids(HQ_ID, f"?status={ShiftStatus.AWAITING_CONFIRMATION}") == []

    tn = await login_as(client, CASHIER_ID)
    detail = (await client.get(f"/shifts/{s1}", headers=tn)).json()
    assert detail["shift_id"] == s1
    assert detail["electronic"] == [] and detail["pending"] == [] and detail["failed"] == []
    _error(await client.get(f"/shifts/{s2}", headers=tn), ErrorCode.FORBIDDEN, "K-01")
    ql = await login_as(client, MANAGER_ID)
    _error(await client.get(f"/shifts/{s3}", headers=ql), ErrorCode.FORBIDDEN, "K-01")
    response = await client.get("/shifts/CA999999", headers=ql)
    assert response.json()["error_code"] == ErrorCode.NOT_FOUND
    bh = await login_as(client, SALES_ID)
    _error(await client.get("/shifts", headers=bh), ErrorCode.FORBIDDEN, "K-01")
