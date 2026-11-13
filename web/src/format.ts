// Định dạng số liệu lấy từ API để hiển thị; không tính toán nghiệp vụ ở giao diện.

/** Tiền VND (số nguyên). null: API báo không có số liệu (vd giá trị đơn trung bình khi không có đơn). */
export const money = (value: number | null) =>
  value === null ? "Không có dữ liệu" : value.toLocaleString("vi-VN");

/** Thời điểm ISO 8601 hiện theo giờ Việt Nam. */
export const dateTime = (value: string | null) =>
  value ? new Date(value).toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" }) : "";
