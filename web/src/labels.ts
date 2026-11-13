// Nhãn tiếng Việt cho các mã lưu trong CSDL (docs/db.md mục 3). Giao diện không hiển thị mã thô.
// Kiểu Record<...> buộc khai báo đủ nhãn: API thêm giá trị mới mà thiếu nhãn là lỗi biên dịch.
import type { Role } from "./api/client";

export const ROLE_LABEL: Record<Role, string> = {
  HQ: "Trụ sở",
  MANAGER: "Quản lý cửa hàng",
  SALES: "Nhân viên bán hàng",
  CASHIER: "Thu ngân",
  WAREHOUSE: "Nhân viên kho",
};
