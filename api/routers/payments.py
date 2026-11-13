"""Nhóm 3 – Thu tiền và hóa đơn (docs/api.md mục 4, 6): chức năng 3.2, 3.3."""

from __future__ import annotations

from typing import Annotated

from deps import Conn, require_role
from fastapi import APIRouter, Depends, Header
from services import payments

from common.constants import Role
from common.models import (
    BankCallback,
    CashConfirm,
    CurrentUser,
    Invoice,
    PaymentCreate,
    Reconcile,
    Transaction,
)

router = APIRouter(tags=["payments"])
Cashier = Annotated[CurrentUser, Depends(require_role(Role.CASHIER))]


@router.post("/orders/{order_id}/payments", status_code=201)
async def start_payment(
    order_id: str, body: PaymentCreate, user: Cashier, conn: Conn
) -> Transaction:
    return await payments.start_payment(conn, order_id, body.method, user)


@router.post("/transactions/{txn_id}/confirm-cash")
async def confirm_cash(txn_id: str, body: CashConfirm, user: Cashier, conn: Conn) -> Transaction:
    return await payments.confirm_cash(conn, txn_id, body.result, user)


@router.post("/transactions/{txn_id}/reconcile")
async def reconcile(txn_id: str, body: Reconcile, user: Cashier, conn: Conn) -> Transaction:
    return await payments.reconcile(conn, txn_id, body, user)


# Cổng gọi lại: không có phiên đăng nhập, xác thực bằng header X-Bank-Key (docs/api.md mục 6)
@router.post("/bank/callback")
async def bank_callback(
    body: BankCallback, conn: Conn, x_bank_key: Annotated[str | None, Header()] = None
) -> Transaction:
    return await payments.bank_callback(conn, body, x_bank_key)


@router.get("/orders/{order_id}/invoice")
async def get_invoice(order_id: str, user: Cashier, conn: Conn) -> Invoice:
    return await payments.get_invoice(conn, order_id, user)


@router.post("/invoices/{invoice_no}/print")
async def print_invoice(invoice_no: str, user: Cashier, conn: Conn) -> Invoice:
    return await payments.print_invoice(conn, invoice_no, user)
