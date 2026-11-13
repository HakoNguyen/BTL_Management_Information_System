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
    LevelStatus,
    OrderStatus,
    ProductStatus,
    RankBy,
    RefundStatus,
    ReplenishType,
    ReturnStatus,
    Role,
    ShiftStatus,
    SlipStatus,
    SlipType,
    TxnMethod,
    TxnStatus,
    TxnType,
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


class ReplenishmentCreate(BaseModel):
    type: ReplenishType
    recipient: NonBlank  # kho tổng hoặc tên NCC
    items: list[StockSlipItem] = Field(min_length=1)  # TK-06


class ReplenishmentRequest(BaseModel):
    request_id: str
    branch_id: str
    created_by: str
    created_at: datetime
    type: ReplenishType
    recipient: str
    items: list[StockSlipItem]


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


# ---------------------------------------------------------------- Ca, thu tiền, hóa đơn (vòng 6)

TxnResult = Literal[TxnStatus.SUCCESS, TxnStatus.FAILED]


class ShiftOpen(BaseModel):
    opening_cash: int  # âm thì service trả VALIDATION_ERROR CA-01


class ShiftClose(BaseModel):
    counted_cash: int  # âm thì service trả VALIDATION_ERROR CA-02
    variance_reason: str | None = None  # bắt buộc khi chênh lệch khác 0 (CA-02)


class ShiftProxyClose(ShiftClose):
    witness_id: NonBlank  # CA-04
    proxy_reason: NonBlank


class Shift(BaseModel):
    shift_id: str
    branch_id: str
    cashier_id: str
    status: ShiftStatus
    opened_at: datetime
    closed_at: datetime | None
    settled_at: datetime | None
    opening_cash: int
    counted_cash: int | None
    variance_reason: str | None
    proxy_closed_by: str | None
    witness_id: str | None
    proxy_reason: str | None
    confirmed_by: str | None
    expected_cash: int  # dẫn xuất (CA-02)
    variance: int | None  # tiền kiểm đếm − tiền mặt kỳ vọng; null khi chưa kiểm đếm


class Transaction(BaseModel):
    txn_id: str
    order_id: str
    return_id: str | None
    shift_id: str
    type: TxnType
    method: TxnMethod
    amount: int
    status: TxnStatus
    created_at: datetime
    resolved_at: datetime | None
    reference_code: str | None
    cash_refund_approved_by: str | None
    cash_refund_reason: str | None


class ShiftMethodTotal(BaseModel):
    type: TxnType
    method: TxnMethod
    count: int
    amount: int


class ShiftDetail(Shift):
    """Ca kèm kết quả đối soát (CA-03)."""

    cash_collected: int
    cash_refunded: int
    electronic: list[ShiftMethodTotal]
    failed: list[Transaction]
    pending: list[Transaction]


class PaymentCreate(BaseModel):
    method: TxnMethod


class CashConfirm(BaseModel):
    result: TxnResult  # FAILED = khách không đưa tiền


class Reconcile(BaseModel):
    result: TxnResult
    reference_code: str | None = None  # bắt buộc khi SUCCESS (TT-02)


class BankCallback(Reconcile):
    txn_id: NonBlank


class InvoiceLine(BaseModel):
    product_id: str
    name: str
    quantity: int
    unit_price: int
    amount: int


class Invoice(BaseModel):
    invoice_no: str
    order_id: str
    branch_id: str
    issued_at: datetime
    print_count: int
    method: TxnMethod
    total: int
    items: list[InvoiceLine]


# ---------------------------------------------------------------- Trả hàng, hoàn tiền (vòng 7)


class ReturnItemInput(BaseModel):
    product_id: NonBlank
    good_qty: int = Field(ge=0)
    defective_qty: int = Field(ge=0)  # tổng tốt + lỗi > 0 do service kiểm tra (TH-02)


class ReturnCreate(BaseModel):
    order_id: NonBlank
    reason: NonBlank  # TH-02
    items: list[ReturnItemInput] = Field(min_length=1)


class ReturnItem(BaseModel):
    product_id: str
    good_qty: int
    defective_qty: int
    unit_price: int  # đơn giá chốt trên đơn gốc
    amount: int  # (tốt + lỗi) × đơn giá chốt


class ReturnSlip(BaseModel):
    return_id: str
    order_id: str
    branch_id: str
    created_by: str
    created_at: datetime
    reason: str
    status: ReturnStatus
    decided_by: str | None  # null = Hệ thống tự từ chối
    decided_at: datetime | None
    decision_note: str | None
    value: int  # giá trị phiếu, dẫn xuất (TH-04)
    refund_status: RefundStatus | None  # dẫn xuất; null khi phiếu chưa Đã duyệt
    items: list[ReturnItem]


class ReturnDecision(BaseModel):
    decision_note: str | None = None  # bắt buộc khi HQ duyệt (K-02) và khi từ chối (K-03)


class CashRefundApproval(BaseModel):
    reason: NonBlank  # TH-04


class CustomerHistory(BaseModel):
    """2.4: lịch sử mua và trả của khách sau khi xác minh số điện thoại (KH-04)."""

    customer: Customer
    orders: list[Order]
    returns: list[ReturnSlip]


class LowStockLine(BaseModel):
    product_id: str
    name: str
    quantity: int
    min_level: int | None  # null = Chưa thiết lập


class LowStockReport(BaseModel):
    """5.4: tính lúc gọi, không lưu (TK-05)."""

    branch_id: str
    generated_at: datetime
    below_min: list[LowStockLine]
    not_set: list[LowStockLine]


# ---------------------------------------------------------------- Nhóm 5 (vòng 9)
# Tính lúc gọi từ chứng từ gốc, không lưu (docs/db.md mục 6). Doanh thu, hàng trả ghi cho chi nhánh
# và người lập của đơn gốc (DT-05).


class ReportHeader(BaseModel):
    branch_id: str | None  # null = toàn chuỗi
    from_date: date
    to_date: date
    generated_at: datetime


class MoneyByMethod(BaseModel):
    type: TxnType
    method: TxnMethod
    amount: int


class CountByReason(BaseModel):
    reason: str
    count: int


class RevenueSummary(BaseModel):
    branch_id: str | None  # null ở dòng tổng
    order_count: int
    gross_revenue: int  # DT-01
    returns_value: int  # DT-02
    net_revenue: int  # DT-03, có thể âm
    average_order_value: int | None  # null = Không có dữ liệu
    registered_revenue: int
    walk_in_revenue: int
    cancellations: list[CountByReason]
    shift_variance: int  # CA-02
    payments: list[MoneyByMethod]  # DT-04
    outstanding_refunds: int  # số còn phải hoàn lúc cuối kỳ (DT-04)


class RevenueReport(ReportHeader):
    branches: list[RevenueSummary]
    total: RevenueSummary
    previous: RevenueSummary


class ProductSalesLine(BaseModel):
    product_id: str
    name: str
    group_id: str  # nhóm hiện tại trong D1 (DT-05)
    sold_qty: int
    returned_qty: int
    net_qty: int
    net_value: int
    rank: int
    previous_rank: int | None


class GroupSalesLine(BaseModel):
    group_id: str
    name: str
    sold_qty: int
    returned_qty: int
    net_qty: int
    net_value: int


class SlowMovingLine(BaseModel):
    branch_id: str
    product_id: str
    name: str
    quantity: int


class ProductSalesReport(ReportHeader):
    rank_by: RankBy
    products: list[ProductSalesLine]  # sắp theo rank; top 10 là 10 dòng đầu
    groups: list[GroupSalesLine]
    slow_moving: list[SlowMovingLine]


class StockReportLine(BaseModel):
    branch_id: str
    product_id: str
    name: str
    quantity: int
    available: int  # TK-01
    min_level: int | None
    level_status: LevelStatus  # TK-05


class StockMovementLine(BaseModel):
    branch_id: str
    type: SlipType
    reason: str
    product_id: str
    quantity: int


class StockReport(ReportHeader):
    lines: list[StockReportLine]
    movements: list[StockMovementLine]


class StaffSalesLine(BaseModel):
    branch_id: str
    employee_id: str
    full_name: str
    order_count: int
    gross_revenue: int
    returns_value: int
    net_revenue: int
    cancelled_count: int
    rank: int  # trong chi nhánh theo net_revenue
    previous_net_revenue: int


class StaffSalesReport(ReportHeader):
    lines: list[StaffSalesLine]
