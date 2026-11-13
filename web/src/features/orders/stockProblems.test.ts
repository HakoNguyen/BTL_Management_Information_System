import { expect, test } from "vitest";
import { ApiError } from "../../api/client";
import { stockProblems } from "./stockProblems";

const names = new Map([
  ["SP001", "Áo thun"],
  ["SP002", "Quần jean"],
]);

test("thiếu tồn (BH-02): mỗi dòng thiếu một câu kèm số cần và số khả dụng", () => {
  const error = new ApiError(409, {
    error_code: "INSUFFICIENT_STOCK",
    message: "Không đủ tồn khả dụng",
    details: {
      rule: "BH-02",
      lines: [
        { product_id: "SP001", quantity: 5, available: 2 },
        { product_id: "SP009", quantity: 1, available: 0 },
      ],
    },
  });
  expect(stockProblems(error, names)).toEqual([
    "SP001 – Áo thun: cần 5, tồn khả dụng 2",
    "SP009: cần 1, tồn khả dụng 0",
  ]);
});

test("sản phẩm Ngừng bán (BH-02): liệt kê từng sản phẩm", () => {
  const error = new ApiError(422, {
    error_code: "RULE_VIOLATION",
    message: "Sản phẩm đã ngừng bán",
    details: { rule: "BH-02", product_ids: ["SP002"] },
  });
  expect(stockProblems(error, names)).toEqual(["SP002 – Quần jean: đã ngừng bán"]);
});

test("phiếu xuất vượt tồn khả dụng (TK-03): cùng dạng dòng như chốt đơn", () => {
  const error = new ApiError(409, {
    error_code: "INSUFFICIENT_STOCK",
    message: "Phiếu xuất vượt tồn khả dụng",
    details: { rule: "TK-03", lines: [{ product_id: "SP002", quantity: 4, available: 1 }] },
  });
  expect(stockProblems(error, names)).toEqual(["SP002 – Quần jean: cần 4, tồn khả dụng 1"]);
});

test("lỗi khác: không có dòng nào", () => {
  const error = new ApiError(409, { error_code: "INVALID_STATE", message: "x", details: {} });
  expect(stockProblems(error, names)).toEqual([]);
  expect(stockProblems(new Error("mạng"), names)).toEqual([]);
});
