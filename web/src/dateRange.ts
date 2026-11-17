// Lọc danh sách chứng từ theo khoảng ngày (giờ Việt Nam) ngay trên trình duyệt.

/** Khoảng ngày "YYYY-MM-DD", tính cả hai đầu; null = mọi ngày. */
export type DateRange = [string, string] | null;

/** Ngày theo giờ Việt Nam của một thời điểm ISO 8601, dạng YYYY-MM-DD. */
export const vnDate = (iso: string) =>
  new Date(iso).toLocaleDateString("en-CA", { timeZone: "Asia/Ho_Chi_Minh" });

/** Thời điểm nằm trong khoảng ngày; chưa có thời điểm (null) thì chỉ khớp khi không lọc. */
export const inDateRange = (iso: string | null | undefined, range: DateRange) => {
  if (!range) return true;
  if (!iso) return false;
  const day = vnDate(iso);
  return range[0] <= day && day <= range[1];
};
