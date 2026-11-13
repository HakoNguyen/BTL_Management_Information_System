"""Model Pydantic v2 cho request/response của API (docs/api.md).

Mỗi vòng nghiệp vụ thêm model của mình vào đây, theo đúng tên trường đã chốt trong docs/api.md.
Giao diện sinh kiểu TypeScript từ các model này (make gen-api), không tự gõ lại tên trường.
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from common.constants import (
    AccountStatus,
    BranchStatus,
    EmployeeStatus,
    OrderStatus,
    ProductStatus,
    Role,
    SlipStatus,
    SlipType,
)

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


# ---------------------------------------------------------------- Nhóm 1 (vòng 2)


class ProductGroup(BaseModel):
    group_id: str
    name: str
    description: str | None


class ProductGroupCreate(BaseModel):
    group_id: NonBlank
    name: NonBlank
    description: str | None = None


class ProductGroupUpdate(BaseModel):
    name: NonBlank = None  # type: ignore[assignment]
    description: str | None = None


class Product(BaseModel):
    product_id: str
    name: str
    group_id: str
    unit: str
    current_price: int  # VND, đã gồm VAT
    description: str | None
    status: ProductStatus


class ProductCreate(BaseModel):
    product_id: NonBlank
    name: NonBlank
    group_id: NonBlank
    unit: NonBlank
    description: str | None = None
    price: int  # giá ban đầu; > 0 kiểm tra ở service (SP-02)


class ProductUpdate(BaseModel):
    # Mã không đổi (SP-01); nhóm, giá, trạng thái đổi qua endpoint riêng
    name: NonBlank = None  # type: ignore[assignment]
    description: str | None = None
    unit: NonBlank = None  # type: ignore[assignment]


class ProductGroupChange(BaseModel):
    group_id: NonBlank


class PriceChange(BaseModel):
    price: int


class PriceHistoryEntry(BaseModel):
    effective_at: datetime
    price: int
    changed_by: str


class ProductStatusChange(BaseModel):
    status: ProductStatus


# ---------------------------------------------------------------- Nhóm 2 (vòng 3)
# Số điện thoại chuẩn hóa và kiểm tra ở service (KH-01), dùng chung cho tạo, cập nhật, tra cứu.


class Customer(BaseModel):
    customer_id: str
    full_name: str
    phone: str | None  # chỉ KHLE không có số (KH-02)
    address: str | None
    registered_on: date


class CustomerCreate(BaseModel):
    full_name: NonBlank
    phone: NonBlank
    address: str | None = None


class CustomerUpdate(BaseModel):
    # Mã khách không đổi (KH-03)
    full_name: NonBlank = None  # type: ignore[assignment]
    phone: NonBlank = None  # type: ignore[assignment]
    address: str | None = None


# ---------------------------------------------------------------- Nhóm 4 (vòng 4)


class StockLevel(BaseModel):
    product_id: str
    quantity: int
    available: int  # tồn khả dụng, dẫn xuất (TK-01)
    min_level: int | None  # null = Chưa thiết lập (TK-05)


class StockSlipItem(BaseModel):
    product_id: NonBlank
    quantity: int = Field(gt=0)


class StockSlip(BaseModel):
    slip_id: str
    branch_id: str
    type: SlipType
    status: SlipStatus
    created_at: datetime
    created_by: str | None
    reason: str | None
    counterparty: str | None
    delivery_no: str | None
    order_id: str | None
    return_id: str | None
    adjusts_slip_id: str | None
    approved_by: str | None  # người quyết định, cả khi từ chối
    decision_reason: str | None
    finalized_at: datetime | None
    items: list[StockSlipItem]


class InboundSlipCreate(BaseModel):
    type: Literal[SlipType.IN_WAREHOUSE, SlipType.IN_SUPPLIER]
    counterparty: NonBlank
    delivery_no: NonBlank
    items: list[StockSlipItem] = Field(min_length=1)


class StockSlipCreate(BaseModel):
    type: Literal[
        SlipType.ADJUST_UP, SlipType.OUT_DISPOSAL, SlipType.OUT_TO_WAREHOUSE, SlipType.ADJUST_DOWN
    ]
    reason: NonBlank
    adjusts_slip_id: str | None = None
    items: list[StockSlipItem] = Field(min_length=1)


class StockSlipReject(BaseModel):
    reason: NonBlank  # K-03


class MinLevelChange(BaseModel):
    min_level: int | None  # âm thì service trả VALIDATION_ERROR TK-05


# ---------------------------------------------------------------- Nhóm 3 – Đơn hàng (vòng 5)


class OrderItemInput(BaseModel):
    product_id: NonBlank
    quantity: int = Field(gt=0)  # BH-01


class OrderItem(BaseModel):
    product_id: str
    quantity: int
    unit_price: int | None  # đơn giá chốt; null khi đơn Đang lập (BH-02)


class Order(BaseModel):
    order_id: str
    branch_id: str
    customer_id: str
    created_by: str
    created_at: datetime
    status: OrderStatus
    confirmed_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    cancelled_by: str | None  # null = Hệ thống (BH-05)
    cancel_reason: str | None
    total: int | None  # Σ số lượng × đơn giá chốt, dẫn xuất; null khi Đang lập (BH-01)
    items: list[OrderItem]


class OrderCreate(BaseModel):
    customer_id: NonBlank  # KHLE cho khách lẻ (KH-02)
    items: list[OrderItemInput] = Field(min_length=1)


class OrderItemsChange(BaseModel):
    items: list[OrderItemInput] = Field(min_length=1)


class OrderCancel(BaseModel):
    reason: NonBlank  # K-03
