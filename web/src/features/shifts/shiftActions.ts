// Nút thao tác trên ca theo vai trò (ma trận 2.2, CA-03, CA-04, quyết định 14). Chỉ để tiện dùng; API kiểm tra lại.
import type { Role, Schemas } from "../../api/client";

export type ShiftAction = "confirm" | "proxy-close";

export function shiftActions(
  shift: Pick<Schemas["Shift"], "status" | "proxy_closed_by">,
  role: Role,
): ShiftAction[] {
  if (shift.status === "OPEN") return role === "MANAGER" ? ["proxy-close"] : [];
  if (shift.status !== "AWAITING_CONFIRMATION") return [];
  // Ca QL đóng thay chỉ HQ xác nhận; ca thu ngân tự đóng chỉ QL xác nhận
  const confirmer: Role = shift.proxy_closed_by ? "HQ" : "MANAGER";
  return role === confirmer ? ["confirm"] : [];
}

/** TH-04: giao dịch hoàn điện tử Thất bại chưa được duyệt hoàn tiền mặt; QL hoặc HQ duyệt thay. */
export const canApproveCashRefund = (txn: Schemas["Transaction"], role: Role) =>
  (role === "MANAGER" || role === "HQ") &&
  txn.type === "REFUND" &&
  txn.method !== "CASH" &&
  txn.status === "FAILED" &&
  !txn.cash_refund_approved_by;
