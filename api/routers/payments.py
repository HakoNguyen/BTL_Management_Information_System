"""Nhóm 3 – Thu tiền, hóa đơn, hoàn tiền (docs/api.md mục 4, 6): 3.2, 3.3 và hoàn tiền của 3.4."""

from __future__ import annotations

from typing import Annotated

from deps import Conn, require_role
from fastapi import APIRouter, Depends, Header
from services import payments

from common.constants import Role
from common.models import (
    BankCallback,
    CashConfirm,
    CashRefundApproval,
    CurrentUser,
    Invoice,
    PaymentCreate,
    Reconcile,
    Transaction,
)

router = APIRouter(tags=["payments"])
Cashier = Annotated[CurrentUser, Depends(require_role(Role.CASHIER))]
# QL duyệt; HQ duyệt thay (K-02, docs/plan.md quyết định 15)
Approver = Annotated[CurrentUser, Depends(require_role(Role.MANAGER, Role.HQ))]


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


@router.post("/returns/{return_id}/refunds", status_code=201)
async def start_refund(return_id: str, user: Cashier, conn: Conn) -> Transaction:
    return await payments.start_refund(conn, return_id, user)


@router.post("/transactions/{txn_id}/approve-cash-refund")
async def approve_cash_refund(
    txn_id: str, body: CashRefundApproval, user: Approver, conn: Conn
) -> Transaction:
    return await payments.approve_cash_refund(conn, txn_id, body.reason, user)
