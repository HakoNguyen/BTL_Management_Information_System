"""Model Pydantic v2 cho request/response của API (docs/api.md).

Mỗi vòng nghiệp vụ thêm model của mình vào đây, theo đúng tên trường đã chốt trong docs/api.md.
Giao diện sinh kiểu TypeScript từ các model này (make gen-api), không tự gõ lại tên trường.
"""

from __future__ import annotations

from datetime import date, time
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from common.constants import AccountStatus, BranchStatus, EmployeeStatus, Role

# Chuỗi bắt buộc: bỏ khoảng trắng hai đầu, không rỗng
NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


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


# ---------------------------------------------------------------- Nhóm 6 (vòng 1)
# Model PATCH: trường không gửi thì giữ nguyên (service dùng model_dump(exclude_unset=True)).
# Trường bắt buộc có kiểu không nhận None nhưng mặc định None: được bỏ trống, gửi null thì 400.


class Branch(BaseModel):
    branch_id: str
    name: str
    address: str | None
    phone: str | None
    closing_time: time  # giờ Việt Nam (G-08)
    status: BranchStatus


class BranchCreate(BaseModel):
    branch_id: NonBlank
    name: NonBlank
    address: str | None = None
    phone: str | None = None
    closing_time: time  # NV-04: bắt buộc


class BranchUpdate(BaseModel):
    name: NonBlank = None  # type: ignore[assignment]
    address: str | None = None
    phone: str | None = None
    closing_time: time = None  # type: ignore[assignment]


class Employee(BaseModel):
    employee_id: str
    full_name: str
    phone: str | None
    role: Role
    branch_id: str | None  # None với nhân viên trụ sở (NV-01)
    hired_on: date
    status: EmployeeStatus
    username: str | None  # None khi chưa cấp tài khoản
    account_status: AccountStatus | None


class EmployeeCreate(BaseModel):
    employee_id: NonBlank
    full_name: NonBlank
    phone: str | None = None
    hired_on: date
    role: Role
    branch_id: str | None = None


class EmployeeUpdate(BaseModel):
    full_name: NonBlank = None  # type: ignore[assignment]
    phone: str | None = None
    hired_on: date = None  # type: ignore[assignment]


class AssignmentRequest(BaseModel):
    role: Role
    branch_id: str | None = None


class AccountCreate(BaseModel):
    username: NonBlank


class AccountIssued(BaseModel):
    employee_id: str
    username: str
    temporary_password: str  # chỉ trả một lần, lúc cấp (6.3)
    account_status: AccountStatus
