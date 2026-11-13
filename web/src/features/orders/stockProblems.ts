// Đọc lỗi chốt đơn (BH-02) thành từng dòng để chỉ rõ sản phẩm nào không đạt; số liệu lấy nguyên từ API.
import { ApiError } from "../../api/client";

type ShortLine = { product_id: string; quantity: number; available: number };

export function stockProblems(error: unknown, names: Map<string, string>): string[] {
  if (!(error instanceof ApiError)) return [];
  const label = (id: string) => (names.has(id) ? `${id} – ${names.get(id)}` : id);
  const lines = (error.details.lines ?? []) as ShortLine[];
  const discontinued = (error.details.product_ids ?? []) as string[];
  return [
    ...lines.map(
      (line) =>
        `${label(line.product_id)}: cần ${line.quantity}, tồn khả dụng ${line.available}`,
    ),
    ...discontinued.map((id) => `${label(id)}: đã ngừng bán`),
  ];
}
