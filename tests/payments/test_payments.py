"""3.2 Thu tiền và 3.3 hóa đơn (TT-01 đến TT-04, K-01), cổng thanh toán (docs/api.md mục 6)."""

from __future__ import annotations

from datetime import datetime

import asyncpg
import httpx
import pytest
from fixtures import (
    BRANCH_1,
    BRANCH_2,
    CASHIER_ID,
    MANAGER_ID,
    SALES_ID,
    bank_callback,
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
from common.constants import (
    ENV_BANK_URL,
    ErrorCode,
    OrderStatus,
    Role,
    SlipStatus,
    TxnMethod,
    TxnStatus,
)

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 13, 10, 0, tzinfo=VN_TZ)
CASHIER_CN2 = "NV-TN-CN2"


@pytest.fixture
async def ready(client: httpx.AsyncClient, conn: asyncpg.Connection) -> dict:
    """CN1: A giá 100.000 tồn 10, B giá 50.000 tồn 10; thu ngân đã mở ca; một đơn Chờ thanh toán."""
    await seed_staff(conn)
    await seed_employee(conn, CASHIER_CN2, Role.CASHIER, BRANCH_2)
    await seed_product(conn, "A")
    await seed_product(conn, "B", 50_000)
    await seed_stock(conn, BRANCH_1, "A", 10)
    await seed_stock(conn, BRANCH_1, "B", 10)
    clock.freeze(NOW)
    bh = await login_as(client, SALES_ID)
    tn = await login_as(client, CASHIER_ID)
    shift_id = await open_shift(client, tn)
    order_id = await create_awaiting_order(client, bh, {"A": 2, "B": 1})
    return {"bh": bh, "tn": tn, "shift_id": shift_id, "order_id": order_id}


def _error(response: httpx.Response, code: ErrorCode, rule: str) -> None:
    body = response.json()
    assert body["error_code"] == code, body
    assert body["details"]["rule"] == rule, body


async def _pay(client: httpx.AsyncClient, ready: dict, method: TxnMethod) -> httpx.Response:
    return await client.post(
        f"/orders/{ready['order_id']}/payments", json={"method": method}, headers=ready["tn"]
    )


async def _confirm_cash(
    client: httpx.AsyncClient, headers: dict[str, str], txn_id: str, result: str = "SUCCESS"
) -> httpx.Response:
    return await client.post(
        f"/transactions/{txn_id}/confirm-cash", json={"result": result}, headers=headers
    )


# ---------------------------------------------------------------- TT-01, TT-03 Khởi tạo thu


async def test_start_payment(client: httpx.AsyncClient, conn: asyncpg.Connection, ready: dict):
    """TT-01, TT-02, TT-03: số tiền bằng tổng đơn, gắn ca Đang mở, Chờ kết quả; giữ hàng trước."""
    response = await _pay(client, ready, TxnMethod.TRANSFER)
    assert response.status_code == 201, response.text
    txn = response.json()
    assert txn["txn_id"] == "GD000001"
    assert (txn["order_id"], txn["shift_id"], txn["amount"]) == (
        ready["order_id"],
        ready["shift_id"],
        250_000,
    )
    assert (txn["type"], txn["method"], txn["status"]) == ("COLLECT", "TRANSFER", "PENDING")
    assert datetime.fromisoformat(txn["created_at"]) == NOW
    assert txn["resolved_at"] is None
    slip = await conn.fetchrow("SELECT type, status FROM stock_slips")
    assert (slip["type"], slip["status"]) == ("OUT_SALE", SlipStatus.PENDING)


async def test_start_payment_order_not_awaiting(client: httpx.AsyncClient, ready: dict) -> None:
    """TT-01: chỉ thu đơn Chờ thanh toán."""
    await client.post(f"/orders/{ready['order_id']}/reopen", headers=ready["bh"])
    _error(await _pay(client, ready, TxnMethod.CASH), ErrorCode.INVALID_STATE, "TT-01")


async def test_start_payment_completed_order(client: httpx.AsyncClient, ready: dict) -> None:
    """TT-03: đơn Hoàn tất không nhận thêm giao dịch thu."""
    txn = (await _pay(client, ready, TxnMethod.CASH)).json()
    await _confirm_cash(client, ready["tn"], txn["txn_id"])
    _error(await _pay(client, ready, TxnMethod.CASH), ErrorCode.INVALID_STATE, "TT-01")


async def test_start_payment_without_open_shift(client: httpx.AsyncClient, ready: dict) -> None:
    """TT-01: thu ngân phải có ca Đang mở."""
    await client.post(
        f"/shifts/{ready['shift_id']}/close", json={"counted_cash": 0}, headers=ready["tn"]
    )
    _error(await _pay(client, ready, TxnMethod.CASH), ErrorCode.RULE_VIOLATION, "TT-01")


async def test_start_payment_while_pending(client: httpx.AsyncClient, ready: dict) -> None:
    """TT-02: chỉ tạo lần thử mới khi lần trước đã Thất bại."""
    await _pay(client, ready, TxnMethod.CARD)
    _error(await _pay(client, ready, TxnMethod.CASH), ErrorCode.INVALID_STATE, "TT-02")


async def test_start_payment_forbidden(client: httpx.AsyncClient, ready: dict) -> None:
    """K-01: chỉ thu ngân cùng chi nhánh thu tiền."""
    tn2 = await login_as(client, CASHIER_CN2)
    await open_shift(client, tn2)
    path = f"/orders/{ready['order_id']}/payments"
    for headers in (tn2, ready["bh"], await login_as(client, MANAGER_ID)):
        response = await client.post(path, json={"method": "CASH"}, headers=headers)
        _error(response, ErrorCode.FORBIDDEN, "K-01")
    response = await client.post(
        "/orders/DH999999/payments", json={"method": "CASH"}, headers=ready["tn"]
    )
    assert response.json()["error_code"] == ErrorCode.NOT_FOUND


async def test_bank_unreachable_keeps_pending(
    client: httpx.AsyncClient, ready: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TT-02: gọi cổng lỗi thì giao dịch vẫn Chờ kết quả, không coi là thất bại."""
    monkeypatch.setenv(ENV_BANK_URL, "http://127.0.0.1:9")
    response = await _pay(client, ready, TxnMethod.CARD)
    assert response.status_code == 201, response.text
    assert response.json()["status"] == TxnStatus.PENDING


# ---------------------------------------------------------------- TT-02 Kết quả giao dịch


async def test_cash_failed_releases_hold(
    client: httpx.AsyncClient, conn: asyncpg.Connection, ready: dict
) -> None:
    """TT-02, TT-03: khách không đưa tiền: Thất bại, nhả hàng, đơn chờ thu, thu lại được."""
    txn = (await _pay(client, ready, TxnMethod.CASH)).json()
    response = await _confirm_cash(client, ready["tn"], txn["txn_id"], "FAILED")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == TxnStatus.FAILED
    assert datetime.fromisoformat(response.json()["resolved_at"]) == NOW
    assert await conn.fetchval("SELECT status FROM stock_slips") == SlipStatus.CANCELLED
    order = (await client.get(f"/orders/{ready['order_id']}", headers=ready["bh"])).json()
    assert order["status"] == OrderStatus.AWAITING_PAYMENT
    assert (await _pay(client, ready, TxnMethod.CASH)).status_code == 201


async def test_confirm_cash_rules(client: httpx.AsyncClient, ready: dict) -> None:
    """TT-02: chỉ xác nhận giao dịch tiền mặt, đúng một lần."""
    txn = (await _pay(client, ready, TxnMethod.CARD)).json()
    response = await _confirm_cash(client, ready["tn"], txn["txn_id"])
    _error(response, ErrorCode.RULE_VIOLATION, "TT-02")
    await bank_callback(client, txn["txn_id"], TxnStatus.FAILED)
    cash = (await _pay(client, ready, TxnMethod.CASH)).json()
    await _confirm_cash(client, ready["tn"], cash["txn_id"])
    response = await _confirm_cash(client, ready["tn"], cash["txn_id"], "FAILED")
    _error(response, ErrorCode.INVALID_STATE, "TT-02")


async def test_confirm_cash_forbidden(client: httpx.AsyncClient, ready: dict) -> None:
    """K-01: thu ngân chi nhánh khác, vai trò khác không xác nhận được."""
    txn = (await _pay(client, ready, TxnMethod.CASH)).json()
    for headers in (await login_as(client, CASHIER_CN2), ready["bh"]):
        response = await _confirm_cash(client, headers, txn["txn_id"])
        _error(response, ErrorCode.FORBIDDEN, "K-01")
    response = await _confirm_cash(client, ready["tn"], "GD999999")
    assert response.json()["error_code"] == ErrorCode.NOT_FOUND


async def test_reconcile_rules(client: httpx.AsyncClient, ready: dict) -> None:
    """TT-02: tra soát chỉ cho giao dịch điện tử; Thành công phải có mã tham chiếu."""
    cash = (await _pay(client, ready, TxnMethod.CASH)).json()
    path = f"/transactions/{cash['txn_id']}/reconcile"
    body = {"result": "SUCCESS", "reference_code": "R1"}
    response = await client.post(path, json=body, headers=ready["tn"])
    _error(response, ErrorCode.RULE_VIOLATION, "TT-02")
    await _confirm_cash(client, ready["tn"], cash["txn_id"], "FAILED")

    card = (await _pay(client, ready, TxnMethod.CARD)).json()
    path = f"/transactions/{card['txn_id']}/reconcile"
    for missing in ({"result": "SUCCESS"}, {"result": "SUCCESS", "reference_code": " "}):
        response = await client.post(path, json=missing, headers=ready["tn"])
        _error(response, ErrorCode.VALIDATION_ERROR, "TT-02")
    response = await client.post(path, json={"result": "FAILED"}, headers=ready["tn"])
    assert response.json()["status"] == TxnStatus.FAILED
    response = await client.post(path, json=body, headers=ready["tn"])
    _error(response, ErrorCode.INVALID_STATE, "TT-02")


async def test_reference_code_unique(
    client: httpx.AsyncClient, conn: asyncpg.Connection, ready: dict
) -> None:
    """TT-02: một mã tham chiếu không gắn cho hai giao dịch."""
    first = (await _pay(client, ready, TxnMethod.CARD)).json()
    await bank_callback(client, first["txn_id"], TxnStatus.SUCCESS, "R1")
    other = await create_awaiting_order(client, ready["bh"], {"A": 1})
    txn = await start_payment(client, ready["tn"], other, TxnMethod.TRANSFER)
    _error(
        await bank_callback(client, txn["txn_id"], TxnStatus.SUCCESS, "R1"),
        ErrorCode.DUPLICATE,
        "TT-02",
    )
    response = await client.post(
        f"/transactions/{txn['txn_id']}/reconcile",
        json={"result": "SUCCESS", "reference_code": "R1"},
        headers=ready["tn"],
    )
    _error(response, ErrorCode.DUPLICATE, "TT-02")
    status = await conn.fetchval("SELECT status FROM transactions WHERE txn_id = $1", txn["txn_id"])
    assert status == TxnStatus.PENDING


async def test_bank_callback_auth(client: httpx.AsyncClient, ready: dict) -> None:
    """Callback sai khóa bị từ chối; mã giao dịch không có thì NOT_FOUND."""
    txn = (await _pay(client, ready, TxnMethod.CARD)).json()
    response = await bank_callback(client, txn["txn_id"], TxnStatus.SUCCESS, "R1", key="sai")
    assert response.json()["error_code"] == ErrorCode.UNAUTHORIZED
    response = await bank_callback(client, "GD999999", TxnStatus.FAILED)
    assert response.json()["error_code"] == ErrorCode.NOT_FOUND
    response = await bank_callback(client, txn["txn_id"], TxnStatus.SUCCESS)
    _error(response, ErrorCode.VALIDATION_ERROR, "TT-02")


async def test_bank_callback_on_cash(client: httpx.AsyncClient, ready: dict) -> None:
    """TT-02: giao dịch tiền mặt do thu ngân xác nhận, không nhận kết quả từ cổng."""
    txn = (await _pay(client, ready, TxnMethod.CASH)).json()
    response = await bank_callback(client, txn["txn_id"], TxnStatus.SUCCESS, "R1")
    _error(response, ErrorCode.RULE_VIOLATION, "TT-02")


# ---------------------------------------------------------------- TT-04 Hóa đơn


async def test_invoice(client: httpx.AsyncClient, ready: dict) -> None:
    """TT-04: một hóa đơn cho đơn Hoàn tất, đủ nội dung; in lại dùng số cũ và tăng số lần in."""
    order_id = ready["order_id"]
    response = await client.get(f"/orders/{order_id}/invoice", headers=ready["tn"])
    assert response.json()["error_code"] == ErrorCode.NOT_FOUND
    txn = (await _pay(client, ready, TxnMethod.CARD)).json()
    await bank_callback(client, txn["txn_id"], TxnStatus.SUCCESS, "R1")

    response = await client.get(f"/orders/{order_id}/invoice", headers=ready["tn"])
    assert response.status_code == 200, response.text
    invoice = response.json()
    assert invoice["invoice_no"] == "HD000001"
    assert (invoice["order_id"], invoice["branch_id"]) == (order_id, BRANCH_1)
    assert datetime.fromisoformat(invoice["issued_at"]) == NOW
    assert (invoice["method"], invoice["total"], invoice["print_count"]) == ("CARD", 250_000, 0)
    assert invoice["items"] == [
        {
            "product_id": "A",
            "name": "Sản phẩm A",
            "quantity": 2,
            "unit_price": 100_000,
            "amount": 200_000,
        },
        {
            "product_id": "B",
            "name": "Sản phẩm B",
            "quantity": 1,
            "unit_price": 50_000,
            "amount": 50_000,
        },
    ]
    for count in (1, 2):
        response = await client.post("/invoices/HD000001/print", headers=ready["tn"])
        assert response.status_code == 200, response.text
        assert (response.json()["invoice_no"], response.json()["print_count"]) == (
            "HD000001",
            count,
        )


async def test_invoice_forbidden(client: httpx.AsyncClient, ready: dict) -> None:
    """K-01: hóa đơn chi nhánh khác; vai trò khác thu ngân."""
    txn = (await _pay(client, ready, TxnMethod.CASH)).json()
    await _confirm_cash(client, ready["tn"], txn["txn_id"])
    for headers in (await login_as(client, CASHIER_CN2), ready["bh"]):
        response = await client.get(f"/orders/{ready['order_id']}/invoice", headers=headers)
        _error(response, ErrorCode.FORBIDDEN, "K-01")
        response = await client.post("/invoices/HD000001/print", headers=headers)
        _error(response, ErrorCode.FORBIDDEN, "K-01")
    response = await client.post("/invoices/HD999999/print", headers=ready["tn"])
    assert response.json()["error_code"] == ErrorCode.NOT_FOUND
