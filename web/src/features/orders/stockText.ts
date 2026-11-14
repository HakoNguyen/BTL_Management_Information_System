// Phần tồn trong nhãn chọn sản phẩm; số liệu nguyên từ GET /stock, giao diện không tự tính.
import type { Schemas } from "../../api/client";

/** Lập đơn, phiếu kho: tồn khả dụng. Yêu cầu bổ sung (4.4): tồn và ngưỡng hiện tại (TK-05). */
export function stockText(line: Schemas["StockLevel"] | undefined, withLevels: boolean) {
  if (!withLevels) return `khả dụng ${line?.available ?? "?"}`;
  const minLevel = line ? (line.min_level ?? "Chưa thiết lập") : "?";
  return `tồn ${line?.quantity ?? "?"} · ngưỡng ${minLevel}`;
}
