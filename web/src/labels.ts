// Nhãn tiếng Việt cho các mã lưu trong CSDL (docs/db.md mục 3). Giao diện không hiển thị mã thô.
// Kiểu Record<...> buộc khai báo đủ nhãn: API thêm giá trị mới mà thiếu nhãn là lỗi biên dịch.
import type { Role, Schemas } from "./api/client";

export const ROLE_LABEL: Record<Role, string> = {
  HQ: "Trụ sở",
  MANAGER: "Quản lý cửa hàng",
  SALES: "Nhân viên bán hàng",
  CASHIER: "Thu ngân",
  WAREHOUSE: "Nhân viên kho",
};

export const BRANCH_STATUS_LABEL: Record<Schemas["BranchStatus"], string> = {
  ACTIVE: "Hoạt động",
  INACTIVE: "Ngừng hoạt động",
};

export const EMPLOYEE_STATUS_LABEL: Record<Schemas["EmployeeStatus"], string> = {
  WORKING: "Đang làm",
  LEFT: "Đã nghỉ",
};

export const ACCOUNT_STATUS_LABEL: Record<Schemas["AccountStatus"], string> = {
  ACTIVE: "Hoạt động",
  LOCKED: "Bị khóa",
};

export const PRODUCT_STATUS_LABEL: Record<Schemas["ProductStatus"], string> = {
  ON_SALE: "Đang bán",
  DISCONTINUED: "Ngừng bán",
};

export const LEVEL_STATUS_LABEL: Record<Schemas["LevelStatus"], string> = {
  BELOW_MIN: "Dưới ngưỡng",
  OK: "Đủ",
  NOT_SET: "Chưa thiết lập",
};

export const RANK_BY_LABEL: Record<Schemas["RankBy"], string> = {
  QUANTITY: "Theo số lượng",
  VALUE: "Theo giá trị",
};

export const TXN_TYPE_LABEL: Record<Schemas["TxnType"], string> = {
  COLLECT: "Thu",
  REFUND: "Hoàn",
};

export const TXN_METHOD_LABEL: Record<Schemas["TxnMethod"], string> = {
  CASH: "Tiền mặt",
  TRANSFER: "Chuyển khoản",
  CARD: "Thẻ",
};

export const SLIP_TYPE_LABEL: Record<Schemas["SlipType"], string> = {
  IN_WAREHOUSE: "Nhập từ kho tổng",
  IN_SUPPLIER: "Nhập từ NCC",
  IN_RETURN: "Nhập hàng trả",
  ADJUST_UP: "Điều chỉnh tăng",
  OUT_SALE: "Xuất bán",
  OUT_DISPOSAL: "Xuất hủy",
  OUT_TO_WAREHOUSE: "Xuất trả kho tổng",
  ADJUST_DOWN: "Điều chỉnh giảm",
};

export const ORDER_STATUS_LABEL: Record<Schemas["OrderStatus"], string> = {
  DRAFT: "Đang lập",
  AWAITING_PAYMENT: "Chờ thanh toán",
  COMPLETED: "Hoàn tất",
  PARTIALLY_RETURNED: "Đã trả một phần",
  FULLY_RETURNED: "Đã trả toàn bộ",
  CANCELLED: "Đã hủy",
};

export const RETURN_STATUS_LABEL: Record<Schemas["ReturnStatus"], string> = {
  PENDING: "Chờ duyệt",
  APPROVED: "Đã duyệt",
  REJECTED: "Từ chối",
};

export const REFUND_STATUS_LABEL: Record<Schemas["RefundStatus"], string> = {
  NOT_REFUNDED: "Chưa hoàn",
  PENDING: "Đang chờ kết quả",
  REFUNDED: "Đã hoàn",
};

/** Danh sách lựa chọn cho Select từ một bảng nhãn. */
export const optionsOf = <K extends string>(labels: Record<K, string>) =>
  (Object.keys(labels) as K[]).map((value) => ({ value, label: labels[value] }));
