"""Dependency dùng chung của mọi router: kết nối CSDL, phiên đăng nhập, kiểm tra vai trò (K-01)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Annotated

import asyncpg
from fastapi import Depends, Request
from services import auth as auth_service

from common import clock
from common.auth import read_token
from common.constants import ErrorCode, Role
from common.errors import AppError
from common.models import CurrentUser


async def get_conn(request: Request) -> AsyncIterator[asyncpg.Connection]:
    async with request.app.state.pool.acquire() as conn:
        yield conn


Conn = Annotated[asyncpg.Connection, Depends(get_conn)]


async def current_user(request: Request, conn: Conn) -> CurrentUser:
    """Đọc lại nhân viên từ CSDL ở mỗi request: tài khoản vừa bị khóa là mất quyền ngay (K-01)."""
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    employee_id = None
    if scheme.lower() == "bearer":
        employee_id = read_token(token, request.app.state.secret_key, clock.now().timestamp())
    employee = await auth_service.get_active_employee(conn, employee_id) if employee_id else None
    if employee is None:
        raise AppError(ErrorCode.UNAUTHORIZED, "Chưa đăng nhập hoặc phiên đã hết hạn")
    return CurrentUser(**employee)


User = Annotated[CurrentUser, Depends(current_user)]


def require_role(*roles: Role) -> Callable[[CurrentUser], Awaitable[CurrentUser]]:
    """Dùng: `user: Annotated[CurrentUser, Depends(require_role(Role.HQ))]` (ma trận 2.2)."""

    async def guard(user: User) -> CurrentUser:
        if user.role not in roles:
            raise AppError(
                ErrorCode.FORBIDDEN,
                "Vai trò hiện tại không được thực hiện chức năng này",
                rule="K-01",
                details={"allowed_roles": list(roles)},
            )
        return user

    return guard
