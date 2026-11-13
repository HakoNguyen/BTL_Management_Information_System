"""Hoàn tiền (3.4): giao dịch Hoàn và duyệt hoàn tiền mặt thay thế – TH-04, TT-02, K-01."""

from __future__ import annotations

from datetime import datetime

import asyncpg
import httpx
import pytest
from fixtures import (
    BRANCH_2,
    CASHIER_ID,
    HQ_ID,
    MANAGER_ID,
    SALES_ID,
    complete_order,
    create_return,
    login_as,
    open_shift,
    resolve_txn,
    seed_employee,
    seed_product,
    seed_staff,
    seed_stock,
)

from common import clock
from common.clock import VN_TZ
from common.constants import RefundStatus, Role, TxnMethod, TxnStatus, TxnType

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 13, 10, 0, tzinfo=VN_TZ)
CASHIER_2 = "NV-TN2"
MANAGER_2 = "NV-QL2"


@pytest.fixture
async def world(client: httpx.AsyncClient, conn: asyncpg.Connection) -> dict:
    """CN1: tồn A = 10; `slip(method)` dựng đơn 2 A thu bằng `method` và phiếu trả 2 A Đã duyệt."""
    await seed_staff(conn)
    await seed_employee(conn, CASHIER_2, Role.CASHIER, BRANCH_2)
    await seed_employee(conn, MANAGER_2, Role.MANAGER, BRANCH_2)
    await seed_product(conn, "A")
    await seed_stock(conn, "CN1", "A", 10)
    clock.freeze(NOW)
    users = {
        "bh": await login_as(client, SALES_ID),
        "tn": await login_as(client, CASHIER_ID),
        "ql": await login_as(client, MANAGER_ID),
        "hq": await login_as(client, HQ_ID),
        "tn2": await login_as(client, CASHIER_2),
        "ql2": await login_as(client, MANAGER_2),
    }
    users["shift_id"] = await open_shift(client, users["tn"], 500_000)

    async def slip(method: TxnMethod, approve: bool = True) -> str:
        order_id = await complete_order(client, users["bh"], users["tn"], {"A": 2}, method)
        response = await create_return(client, users["bh"], order_id, {"A": (1, 1)})
        assert response.status_code == 201, response.text
        return_id = response.json()["return_id"]
        if approve:
            response = await client.post(
                f"/returns/{return_id}/approve", json={}, headers=users["ql"]
            )
            assert response.status_code == 200, response.text
        return return_id

    users["slip"] = slip
    return users


def _error(response: httpx.Response, status: int, code: str, rule: str | None) -> None:
    assert response.status_code == status, response.text
    body = response.json()
    assert body["error_code"] == code
    assert body["details"].get("rule") == rule


async def _refund(client: httpx.AsyncClient, headers: dict, return_id: str) -> httpx.Response:
    return await client.post(f"/returns/{return_id}/refunds", headers=headers)


async def _approve_cash(
    client: httpx.AsyncClient, headers: dict, txn_id: str, reason: str = "Thẻ đã hủy"
) -> httpx.Response:
    return await client.post(
        f"/transactions/{txn_id}/approve-cash-refund", json={"reason": reason}, headers=headers
    )


async def test_refund_uses_collect_method_and_slip_value(
    client: httpx.AsyncClient, world: dict
) -> None:
    """TH-04: số tiền = giá trị phiếu, phương thức = phương thức thu, gắn ca Đang mở."""
    return_id = await world["slip"](TxnMethod.TRANSFER)
    response = await _refund(client, world["tn"], return_id)
    assert response.status_code == 201, response.text
    txn = response.json()
    assert txn["type"] == TxnType.REFUND
    assert txn["return_id"] == return_id
    assert txn["method"] == TxnMethod.TRANSFER
    assert txn["amount"] == 200_000
    assert txn["status"] == TxnStatus.PENDING
    assert txn["shift_id"] == world["shift_id"]
    assert txn["cash_refund_approved_by"] is None
    slip = (await client.get(f"/returns/{return_id}", headers=world["tn"])).json()
    assert slip["refund_status"] == RefundStatus.PENDING

    # TT-02: còn giao dịch Chờ kết quả thì không tạo lần mới
    _error(await _refund(client, world["tn"], return_id), 409, "INVALID_STATE", "TT-02")

    await resolve_txn(client, world["tn"], txn, TxnStatus.SUCCESS)
    slip = (await client.get(f"/returns/{return_id}", headers=world["tn"])).json()
    assert slip["refund_status"] == RefundStatus.REFUNDED
    # TH-04: mỗi phiếu tối đa một giao dịch Hoàn Thành công
    _error(await _refund(client, world["tn"], return_id), 409, "INVALID_STATE", "TH-04")


async def test_cash_refund_lowers_expected_cash(client: httpx.AsyncClient, world: dict) -> None:
    """TH-04, CA-02: hoàn tiền mặt Thành công trừ vào tiền mặt kỳ vọng của ca."""
    return_id = await world["slip"](TxnMethod.CASH)
    txn = (await _refund(client, world["tn"], return_id)).json()
    assert txn["method"] == TxnMethod.CASH
    await resolve_txn(client, world["tn"], txn, TxnStatus.SUCCESS)
    shift = (await client.get(f"/shifts/{world['shift_id']}", headers=world["tn"])).json()
    assert shift["expected_cash"] == 500_000 + 200_000 - 200_000
    assert shift["cash_refunded"] == 200_000


async def test_refund_requires_approved_slip(client: httpx.AsyncClient, world: dict) -> None:
    """TH-04: chỉ hoàn cho phiếu Đã duyệt."""
    return_id = await world["slip"](TxnMethod.CASH, approve=False)
    _error(await _refund(client, world["tn"], return_id), 409, "INVALID_STATE", "TH-04")


async def test_refund_requires_open_shift(client: httpx.AsyncClient, world: dict) -> None:
    """TH-04: thu ngân phải có ca Đang mở tại chi nhánh của phiếu."""
    return_id = await world["slip"](TxnMethod.CASH)
    response = await client.post(
        f"/shifts/{world['shift_id']}/close",
        json={"counted_cash": 700_000},  # 500.000 đầu ca + 200.000 thu
        headers=world["tn"],
    )
    assert response.status_code == 200, response.text
    _error(await _refund(client, world["tn"], return_id), 422, "RULE_VIOLATION", "TH-04")


async def test_refund_forbidden(client: httpx.AsyncClient, world: dict) -> None:
    """K-01: chỉ thu ngân hoàn tiền; thu ngân chi nhánh khác không hoàn phiếu CN1."""
    return_id = await world["slip"](TxnMethod.CASH)
    for who in ("bh", "ql", "hq"):
        _error(await _refund(client, world[who], return_id), 403, "FORBIDDEN", "K-01")
    _error(await _refund(client, world["tn2"], return_id), 403, "FORBIDDEN", "K-01")
    _error(await _refund(client, world["tn"], "PT999999"), 404, "NOT_FOUND", None)


async def test_cash_refund_approval(client: httpx.AsyncClient, world: dict) -> None:
    """TH-04: sau một lần hoàn điện tử Thất bại, QL duyệt hoàn tiền mặt; lần hoàn sau là tiền mặt,
    mang người duyệt và lý do."""
    return_id = await world["slip"](TxnMethod.CARD)
    failed = (await _refund(client, world["tn"], return_id)).json()

    # Chưa Thất bại thì chưa duyệt được
    _error(
        await _approve_cash(client, world["ql"], failed["txn_id"]), 422, "RULE_VIOLATION", "TH-04"
    )
    failed = await resolve_txn(client, world["tn"], failed, TxnStatus.FAILED)

    response = await _approve_cash(client, world["ql"], failed["txn_id"])
    assert response.status_code == 200, response.text
    approved = response.json()
    assert approved["status"] == TxnStatus.FAILED
    assert approved["amount"] == 200_000
    assert approved["cash_refund_approved_by"] == MANAGER_ID
    assert approved["cash_refund_reason"] == "Thẻ đã hủy"
    # Đã duyệt thì không duyệt lại
    _error(
        await _approve_cash(client, world["ql"], failed["txn_id"]), 409, "INVALID_STATE", "TH-04"
    )

    cash = (await _refund(client, world["tn"], return_id)).json()
    assert cash["method"] == TxnMethod.CASH
    assert cash["amount"] == 200_000
    assert cash["cash_refund_approved_by"] == MANAGER_ID
    assert cash["cash_refund_reason"] == "Thẻ đã hủy"


async def test_hq_approves_cash_refund(client: httpx.AsyncClient, world: dict) -> None:
    """TH-04, K-02: trụ sở duyệt thay, bắt buộc lý do."""
    return_id = await world["slip"](TxnMethod.CARD)
    failed = (await _refund(client, world["tn"], return_id)).json()
    failed = await resolve_txn(client, world["tn"], failed, TxnStatus.FAILED)
    response = await _approve_cash(client, world["hq"], failed["txn_id"], " ")
    _error(response, 400, "VALIDATION_ERROR", None)
    response = await _approve_cash(client, world["hq"], failed["txn_id"], "QL vắng")
    assert response.status_code == 200, response.text
    assert response.json()["cash_refund_approved_by"] == HQ_ID


async def test_cash_refund_approval_rules(client: httpx.AsyncClient, world: dict) -> None:
    """TH-04: chỉ duyệt trên giao dịch Hoàn điện tử Thất bại; phiếu đã hoàn xong thì không duyệt;
    K-01: chỉ QL chi nhánh hoặc HQ."""
    return_id = await world["slip"](TxnMethod.CASH)
    cash = (await _refund(client, world["tn"], return_id)).json()
    cash = await resolve_txn(client, world["tn"], cash, TxnStatus.FAILED)
    _error(await _approve_cash(client, world["ql"], cash["txn_id"]), 422, "RULE_VIOLATION", "TH-04")
    # GD000001 là giao dịch thu của đơn đầu tiên (mã chứng từ bắt đầu lại mỗi test)
    _error(await _approve_cash(client, world["ql"], "GD000001"), 422, "RULE_VIOLATION", "TH-04")

    card_slip = await world["slip"](TxnMethod.CARD)
    first = await resolve_txn(
        client,
        world["tn"],
        (await _refund(client, world["tn"], card_slip)).json(),
        TxnStatus.FAILED,
    )
    for who in ("tn", "bh"):
        _error(await _approve_cash(client, world[who], first["txn_id"]), 403, "FORBIDDEN", "K-01")
    _error(await _approve_cash(client, world["ql2"], first["txn_id"]), 403, "FORBIDDEN", "K-01")
    _error(await _approve_cash(client, world["ql"], "GD999999"), 404, "NOT_FOUND", None)

    second = (await _refund(client, world["tn"], card_slip)).json()
    await resolve_txn(client, world["tn"], second, TxnStatus.SUCCESS)
    _error(await _approve_cash(client, world["ql"], first["txn_id"]), 409, "INVALID_STATE", "TH-04")
