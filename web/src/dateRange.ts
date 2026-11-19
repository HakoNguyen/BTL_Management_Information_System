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

/** Tuần ISO "YYYY-Www" (giá trị của <input type="week">) → [thứ Hai, Chủ nhật]; sai dạng thì null. */
export function isoWeekRange(week: string): [string, string] | null {
  const match = /^(\d{4})-W(\d{2})$/.exec(week);
  if (!match) return null;
  // Ngày 4/1 luôn thuộc tuần 1: lùi về thứ Hai của tuần đó rồi cộng số tuần
  const monday = new Date(Date.UTC(Number(match[1]), 0, 4));
  monday.setUTCDate(4 - ((monday.getUTCDay() + 6) % 7) + (Number(match[2]) - 1) * 7);
  const sunday = new Date(monday);
  sunday.setUTCDate(monday.getUTCDate() + 6);
  const day = (date: Date) => date.toISOString().slice(0, 10);
  return [day(monday), day(sunday)];
}
