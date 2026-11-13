"""Đăng nhập và thông tin phiên (docs/api.md mục 3)."""

from __future__ import annotations

from deps import Conn, User
from fastapi import APIRouter, Request
from services import auth as auth_service

from common import clock
from common.auth import make_token
from common.models import CurrentUser, LoginRequest, LoginResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
async def login(body: LoginRequest, request: Request, conn: Conn) -> LoginResponse:
    employee = await auth_service.login(conn, body.username, body.password)
    token = make_token(
        employee["employee_id"], request.app.state.secret_key, clock.now().timestamp()
    )
    return LoginResponse(token=token, user=CurrentUser(**employee))


@router.get("/me")
async def me(user: User) -> CurrentUser:
    return user
