"""Nhóm 6 – Nhân viên và chi nhánh (docs/api.md mục 4). Trụ sở ghi; mọi vai trò xem chi nhánh."""

from __future__ import annotations

from typing import Annotated

from deps import Conn, User, require_role
from fastapi import APIRouter, Depends
from services import staff

from common.constants import AccountStatus, Role
from common.models import (
    AccountCreate,
    AccountIssued,
    AssignmentRequest,
    Branch,
    BranchCreate,
    BranchUpdate,
    CurrentUser,
    Employee,
    EmployeeCreate,
    EmployeeUpdate,
)

router = APIRouter(tags=["staff"])
HqUser = Annotated[CurrentUser, Depends(require_role(Role.HQ))]


@router.get("/branches")
async def list_branches(_: User, conn: Conn) -> list[Branch]:
    return await staff.list_branches(conn)


@router.post("/branches", status_code=201)
async def create_branch(body: BranchCreate, _: HqUser, conn: Conn) -> Branch:
    return await staff.create_branch(conn, body)


@router.patch("/branches/{branch_id}")
async def update_branch(branch_id: str, body: BranchUpdate, _: HqUser, conn: Conn) -> Branch:
    return await staff.update_branch(conn, branch_id, body)


@router.post("/branches/{branch_id}/deactivate")
async def deactivate_branch(branch_id: str, _: HqUser, conn: Conn) -> Branch:
    return await staff.deactivate_branch(conn, branch_id)


@router.get("/employees")
async def list_employees(_: HqUser, conn: Conn) -> list[Employee]:
    return await staff.list_employees(conn)


@router.post("/employees", status_code=201)
async def create_employee(body: EmployeeCreate, _: HqUser, conn: Conn) -> Employee:
    return await staff.create_employee(conn, body)


@router.patch("/employees/{employee_id}")
async def update_employee(
    employee_id: str, body: EmployeeUpdate, _: HqUser, conn: Conn
) -> Employee:
    return await staff.update_employee(conn, employee_id, body)


@router.post("/employees/{employee_id}/leave")
async def leave_employee(employee_id: str, _: HqUser, conn: Conn) -> Employee:
    return await staff.leave_employee(conn, employee_id)


@router.put("/employees/{employee_id}/assignment")
async def assign_employee(
    employee_id: str, body: AssignmentRequest, _: HqUser, conn: Conn
) -> Employee:
    return await staff.assign_employee(conn, employee_id, body)


@router.post("/employees/{employee_id}/account", status_code=201)
async def issue_account(
    employee_id: str, body: AccountCreate, _: HqUser, conn: Conn
) -> AccountIssued:
    return await staff.issue_account(conn, employee_id, body.username)


@router.post("/employees/{employee_id}/account/lock")
async def lock_account(employee_id: str, _: HqUser, conn: Conn) -> Employee:
    return await staff.set_account_status(conn, employee_id, AccountStatus.LOCKED)


@router.post("/employees/{employee_id}/account/unlock")
async def unlock_account(employee_id: str, _: HqUser, conn: Conn) -> Employee:
    return await staff.set_account_status(conn, employee_id, AccountStatus.ACTIVE)
