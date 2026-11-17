import type { Schemas } from "../../api/client";
import { TXN_METHOD_LABEL } from "../../labels";

export type MethodRow = { method: string } & Partial<Record<Schemas["TxnType"], number>>;

/**
 * Xoay danh sách (loại, phương thức, số tiền) của DT-04 thành mỗi phương thức một dòng để vẽ biểu đồ.
 * Chỉ sắp xếp lại số liệu API trả về, không cộng gộp; phương thức không phát sinh thì bỏ.
 */
export const byMethod = (payments: Schemas["MoneyByMethod"][]): MethodRow[] =>
  (Object.keys(TXN_METHOD_LABEL) as Schemas["TxnMethod"][])
    .map((method) => ({
      method: TXN_METHOD_LABEL[method],
      ...Object.fromEntries(
        payments.filter((p) => p.method === method).map((p) => [p.type, p.amount]),
      ),
    }))
    .filter((row) => Object.keys(row).length > 1);
