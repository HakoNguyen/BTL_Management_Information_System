"""Model Pydantic v2 cho request/response của API (docs/api.md).

Mỗi vòng nghiệp vụ thêm model của mình vào đây, theo đúng tên trường đã chốt trong docs/api.md.
Giao diện sinh kiểu TypeScript từ các model này (make gen-api), không tự gõ lại tên trường.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from common.constants import Role


class HealthResponse(BaseModel):
    status: Literal["ok"]


class CurrentUser(BaseModel):
    """Thông tin phiên đăng nhập: dùng để kiểm tra quyền theo vai trò và chi nhánh (K-01)."""

    employee_id: str
    full_name: str
    role: Role
    branch_id: str | None  # None với nhân viên trụ sở (NV-01)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    token: str
    user: CurrentUser
