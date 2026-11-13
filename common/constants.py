"""Hằng số dùng chung: vai trò, trạng thái, loại chứng từ, mã lỗi.

Giá trị của mỗi enum là giá trị lưu trong CSDL (docs/db.md mục 3) và trả qua API (docs/api.md).
Code không viết chuỗi trực tiếp như "PENDING"; luôn dùng các enum dưới đây.
"""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    HQ = "HQ"  # Trụ sở
    MANAGER = "MANAGER"  # Quản lý cửa hàng (QL)
    SALES = "SALES"  # Nhân viên bán hàng (NVBH)
    CASHIER = "CASHIER"  # Thu ngân
    WAREHOUSE = "WAREHOUSE"  # Nhân viên kho


class EmployeeStatus(StrEnum):
    WORKING = "WORKING"  # Đang làm
    LEFT = "LEFT"  # Đã nghỉ


class AccountStatus(StrEnum):
    ACTIVE = "ACTIVE"  # Hoạt động
    LOCKED = "LOCKED"  # Bị khóa


class BranchStatus(StrEnum):
    ACTIVE = "ACTIVE"  # Hoạt động
    INACTIVE = "INACTIVE"  # Ngừng hoạt động


class ProductStatus(StrEnum):
    ON_SALE = "ON_SALE"  # Đang bán
    DISCONTINUED = "DISCONTINUED"  # Ngừng bán


class OrderStatus(StrEnum):
    DRAFT = "DRAFT"  # Đang lập
    AWAITING_PAYMENT = "AWAITING_PAYMENT"  # Chờ thanh toán
    COMPLETED = "COMPLETED"  # Hoàn tất
    PARTIALLY_RETURNED = "PARTIALLY_RETURNED"  # Đã trả một phần
    FULLY_RETURNED = "FULLY_RETURNED"  # Đã trả toàn bộ
    CANCELLED = "CANCELLED"  # Đã hủy


class ReturnStatus(StrEnum):
    PENDING = "PENDING"  # Chờ duyệt
    APPROVED = "APPROVED"  # Đã duyệt
    REJECTED = "REJECTED"  # Từ chối


class TxnType(StrEnum):
    COLLECT = "COLLECT"  # Thu
    REFUND = "REFUND"  # Hoàn


class TxnMethod(StrEnum):
    CASH = "CASH"  # Tiền mặt
    TRANSFER = "TRANSFER"  # Chuyển khoản
    CARD = "CARD"  # Thẻ


class TxnStatus(StrEnum):
    PENDING = "PENDING"  # Chờ kết quả
    SUCCESS = "SUCCESS"  # Thành công
    FAILED = "FAILED"  # Thất bại


class ShiftStatus(StrEnum):
    OPEN = "OPEN"  # Đang mở
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"  # Chờ xác nhận
    SETTLED = "SETTLED"  # Đã chốt


class SlipType(StrEnum):
    IN_WAREHOUSE = "IN_WAREHOUSE"  # Nhập từ kho tổng
    IN_SUPPLIER = "IN_SUPPLIER"  # Nhập từ NCC
    IN_RETURN = "IN_RETURN"  # Nhập hàng trả
    ADJUST_UP = "ADJUST_UP"  # Điều chỉnh tăng
    OUT_SALE = "OUT_SALE"  # Xuất bán
    OUT_DISPOSAL = "OUT_DISPOSAL"  # Xuất hủy
    OUT_TO_WAREHOUSE = "OUT_TO_WAREHOUSE"  # Xuất trả kho tổng
    ADJUST_DOWN = "ADJUST_DOWN"  # Điều chỉnh giảm


class SlipStatus(StrEnum):
    PENDING = "PENDING"  # Chờ xử lý
    POSTED = "POSTED"  # Đã ghi nhận
    CANCELLED = "CANCELLED"  # Đã hủy


class ReplenishType(StrEnum):
    TRANSFER = "TRANSFER"  # Điều chuyển (gửi kho tổng)
    SUPPLIER = "SUPPLIER"  # Nhập NCC (giao thẳng)


class ErrorCode(StrEnum):
    VALIDATION_ERROR = "VALIDATION_ERROR"  # dữ liệu vào sai định dạng
    UNAUTHORIZED = "UNAUTHORIZED"  # chưa đăng nhập, sai mật khẩu, phiên hết hạn
    FORBIDDEN = "FORBIDDEN"  # sai vai trò, sai chi nhánh, tài khoản bị khóa, K-02
    NOT_FOUND = "NOT_FOUND"
    DUPLICATE = "DUPLICATE"  # trùng mã, số điện thoại, phiếu giao
    INVALID_STATE = "INVALID_STATE"  # chứng từ không ở trạng thái cho phép thao tác
    INSUFFICIENT_STOCK = "INSUFFICIENT_STOCK"  # vượt tồn khả dụng (TK-01, TK-03)
    RULE_VIOLATION = "RULE_VIOLATION"  # vi phạm quy tắc nghiệp vụ khác; details.rule ghi mã quy tắc
    INTERNAL_ERROR = "INTERNAL_ERROR"


ERROR_HTTP_STATUS: dict[ErrorCode, int] = {
    ErrorCode.VALIDATION_ERROR: 400,
    ErrorCode.UNAUTHORIZED: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.DUPLICATE: 409,
    ErrorCode.INVALID_STATE: 409,
    ErrorCode.INSUFFICIENT_STOCK: 409,
    ErrorCode.RULE_VIOLATION: 422,
    ErrorCode.INTERNAL_ERROR: 500,
}

# Khách lẻ (KH-02): mã khách mặc định, tạo sẵn trong db/migrations/002_seed.sql
WALK_IN_CUSTOMER_ID = "KHLE"
# Hạn trả hàng tính từ thời điểm đơn Hoàn tất (G-06, TH-01)
RETURN_WINDOW_DAYS = 7
# Lý do do Hệ thống ghi lúc giờ đóng cửa (BH-05, TH-03)
OVERDUE_CANCEL_REASON = "Quá hạn"
OVERDUE_REJECT_REASON = "Quá hạn duyệt"

# Phiên đăng nhập
TOKEN_TTL_SECONDS = 12 * 3600

# Tên biến môi trường (.env.example, infra/compose.yml)
ENV_DB_URL = "DB_URL"
ENV_SECRET_KEY = "SECRET_KEY"
ENV_ADMIN_USERNAME = "ADMIN_USERNAME"
ENV_ADMIN_PASSWORD = "ADMIN_PASSWORD"
# Mã nhân viên của tài khoản trụ sở đầu tiên, tạo khi API khởi động
BOOTSTRAP_ADMIN_ID = "NV000"
