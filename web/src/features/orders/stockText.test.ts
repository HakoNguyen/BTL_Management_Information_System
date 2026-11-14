import { expect, test } from "vitest";
import { stockText } from "./stockText";

const line = { product_id: "A", quantity: 7, available: 5, min_level: 10 };

test("lập đơn, phiếu kho: chỉ hiện tồn khả dụng (4.1 phục vụ 3.1)", () => {
  expect(stockText(line, false)).toBe("khả dụng 5");
  expect(stockText(undefined, false)).toBe("khả dụng ?");
});

test("yêu cầu bổ sung (4.4): hiện tồn và ngưỡng hiện tại (TK-05, TK-06)", () => {
  expect(stockText(line, true)).toBe("tồn 7 · ngưỡng 10");
  expect(stockText({ ...line, min_level: null }, true)).toBe("tồn 7 · ngưỡng Chưa thiết lập");
  expect(stockText({ ...line, min_level: 0 }, true)).toBe("tồn 7 · ngưỡng 0");
  expect(stockText(undefined, true)).toBe("tồn ? · ngưỡng ?");
});
