"""Nhóm 3 – Ca thu ngân (docs/api.md mục 4): chức năng 3.5."""

from __future__ import annotations

from typing import Annotated

from deps import Conn, require_role
from fastapi import APIRouter, Depends
from services import shifts

from common.constants import Role, ShiftStatus
from common.models import CurrentUser, Shift, ShiftClose, ShiftDetail, ShiftOpen, ShiftProxyClose

router = APIRouter(tags=["shifts"])
Cashier = Annotated[CurrentUser, Depends(require_role(Role.CASHIER))]
Manager = Annotated[CurrentUser, Depends(require_role(Role.MANAGER))]
Confirmer = Annotated[CurrentUser, Depends(require_role(Role.MANAGER, Role.HQ))]
Viewer = Annotated[CurrentUser, Depends(require_role(Role.MANAGER, Role.HQ, Role.CASHIER))]


@router.post("/shifts", status_code=201)
async def open_shift(body: ShiftOpen, user: Cashier, conn: Conn) -> ShiftDetail:
    return await shifts.open_shift(conn, body, user)


@router.get("/shifts/current")
async def current_shift(user: Cashier, conn: Conn) -> ShiftDetail | None:
    return await shifts.current_shift(conn, user)


@router.get("/shifts")
async def list_shifts(user: Viewer, conn: Conn, status: ShiftStatus | None = None) -> list[Shift]:
    return await shifts.list_shifts(conn, user, status)


@router.get("/shifts/{shift_id}")
async def get_shift(shift_id: str, user: Viewer, conn: Conn) -> ShiftDetail:
    return await shifts.get_shift(conn, shift_id, user)


@router.post("/shifts/{shift_id}/close")
async def close_shift(shift_id: str, body: ShiftClose, user: Cashier, conn: Conn) -> ShiftDetail:
    return await shifts.close_shift(conn, shift_id, body, user)


@router.post("/shifts/{shift_id}/proxy-close")
async def proxy_close(
    shift_id: str, body: ShiftProxyClose, user: Manager, conn: Conn
) -> ShiftDetail:
    return await shifts.proxy_close(conn, shift_id, body, user)


@router.post("/shifts/{shift_id}/confirm")
async def confirm_shift(shift_id: str, user: Confirmer, conn: Conn) -> ShiftDetail:
    return await shifts.confirm_shift(conn, shift_id, user)
