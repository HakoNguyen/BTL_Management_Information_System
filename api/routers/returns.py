"""Nhóm 3 – Phiếu trả (docs/api.md mục 4): phần phiếu trả của 3.4."""

from __future__ import annotations

from typing import Annotated

from deps import Conn, require_role
from fastapi import APIRouter, Depends
from services import returns

from common.constants import RefundStatus, ReturnStatus, Role
from common.models import CurrentUser, ReturnCreate, ReturnDecision, ReturnSlip

router = APIRouter(tags=["returns"])
Creator = Annotated[CurrentUser, Depends(require_role(Role.MANAGER, Role.SALES))]
Viewer = Annotated[
    CurrentUser, Depends(require_role(Role.MANAGER, Role.SALES, Role.CASHIER, Role.HQ))
]
# QL duyệt; HQ duyệt thay (K-02, docs/plan.md quyết định 15)
Approver = Annotated[CurrentUser, Depends(require_role(Role.MANAGER, Role.HQ))]


@router.post("/returns", status_code=201)
async def create_return(body: ReturnCreate, user: Creator, conn: Conn) -> ReturnSlip:
    return await returns.create_return(conn, body, user)


@router.get("/returns")
async def list_returns(
    user: Viewer,
    conn: Conn,
    status: ReturnStatus | None = None,
    refund_status: RefundStatus | None = None,
) -> list[ReturnSlip]:
    return await returns.list_returns(conn, user, status, refund_status)


@router.get("/returns/{return_id}")
async def get_return(return_id: str, user: Viewer, conn: Conn) -> ReturnSlip:
    return await returns.get_return(conn, return_id, user)


@router.post("/returns/{return_id}/approve")
async def approve_return(
    return_id: str, body: ReturnDecision, user: Approver, conn: Conn
) -> ReturnSlip:
    return await returns.approve_return(conn, return_id, body, user)


@router.post("/returns/{return_id}/reject")
async def reject_return(
    return_id: str, body: ReturnDecision, user: Approver, conn: Conn
) -> ReturnSlip:
    return await returns.reject_return(conn, return_id, body, user)
