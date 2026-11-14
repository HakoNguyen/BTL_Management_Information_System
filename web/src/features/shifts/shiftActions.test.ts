import { expect, test } from "vitest";
import type { Schemas } from "../../api/client";
import { canApproveCashRefund, canReconcile, shiftActions } from "./shiftActions";

const shift = (status: Schemas["ShiftStatus"], proxy_closed_by: string | null = null) => ({
  status,
  proxy_closed_by,
});

test("ca Đang mở: chỉ QL được đóng ca thay (CA-04)", () => {
  expect(shiftActions(shift("OPEN"), "MANAGER")).toEqual(["proxy-close"]);
  expect(shiftActions(shift("OPEN"), "HQ")).toEqual([]);
  expect(shiftActions(shift("OPEN"), "CASHIER")).toEqual([]);
});

test("ca thu ngân tự đóng: QL xác nhận, HQ duyệt thay kèm lý do (2.2, K-02, quyết định 14)", () => {
  expect(shiftActions(shift("AWAITING_CONFIRMATION"), "MANAGER")).toEqual(["confirm"]);
  expect(shiftActions(shift("AWAITING_CONFIRMATION"), "HQ")).toEqual(["confirm"]);
  expect(shiftActions(shift("AWAITING_CONFIRMATION"), "CASHIER")).toEqual([]);
});

test("ca QL đóng thay: chỉ HQ xác nhận (CA-04)", () => {
  expect(shiftActions(shift("AWAITING_CONFIRMATION", "NV-QL1"), "HQ")).toEqual(["confirm"]);
  expect(shiftActions(shift("AWAITING_CONFIRMATION", "NV-QL1"), "MANAGER")).toEqual([]);
});

test("ca Đã chốt: không còn thao tác", () => {
  expect(shiftActions(shift("SETTLED"), "MANAGER")).toEqual([]);
  expect(shiftActions(shift("SETTLED", "NV-QL1"), "HQ")).toEqual([]);
});

const txn = (over: Partial<Schemas["Transaction"]>) =>
  ({
    type: "REFUND",
    method: "TRANSFER",
    status: "FAILED",
    cash_refund_approved_by: null,
    ...over,
  }) as Schemas["Transaction"];

test("duyệt hoàn tiền mặt chỉ cho giao dịch hoàn điện tử Thất bại chưa được duyệt (TH-04)", () => {
  expect(canApproveCashRefund(txn({}), "MANAGER")).toBe(true);
  expect(canApproveCashRefund(txn({ method: "CARD" }), "HQ")).toBe(true);
  expect(canApproveCashRefund(txn({ type: "COLLECT" }), "MANAGER")).toBe(false);
  expect(canApproveCashRefund(txn({ method: "CASH" }), "MANAGER")).toBe(false);
  expect(canApproveCashRefund(txn({ status: "SUCCESS" }), "MANAGER")).toBe(false);
  expect(canApproveCashRefund(txn({ cash_refund_approved_by: "NV-QL1" }), "MANAGER")).toBe(false);
  expect(canApproveCashRefund(txn({}), "CASHIER")).toBe(false);
});

test("tra soát giao dịch điện tử Chờ kết quả trong ca Chờ xác nhận, chỉ thu ngân (TT-02, CA-03)", () => {
  const pending = txn({ type: "COLLECT", status: "PENDING" });
  expect(canReconcile(shift("AWAITING_CONFIRMATION"), pending, "CASHIER")).toBe(true);
  expect(canReconcile(shift("AWAITING_CONFIRMATION"), pending, "MANAGER")).toBe(false);
  expect(canReconcile(shift("OPEN"), pending, "CASHIER")).toBe(false);
  expect(canReconcile(shift("SETTLED"), pending, "CASHIER")).toBe(false);
  expect(canReconcile(shift("AWAITING_CONFIRMATION"), { ...pending, method: "CASH" }, "CASHIER")).toBe(
    false,
  );
});
