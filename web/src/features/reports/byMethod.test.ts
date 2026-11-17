import { describe, expect, it } from "vitest";
import { byMethod } from "./byMethod";

describe("byMethod", () => {
  it("gom thu và hoàn của cùng phương thức vào một dòng, bỏ phương thức không phát sinh", () => {
    expect(
      byMethod([
        { type: "COLLECT", method: "CASH", amount: 300_000 },
        { type: "REFUND", method: "CASH", amount: 100_000 },
        { type: "COLLECT", method: "CARD", amount: 200_000 },
      ]),
    ).toEqual([
      { method: "Tiền mặt", COLLECT: 300_000, REFUND: 100_000 },
      { method: "Thẻ", COLLECT: 200_000 },
    ]);
  });

  it("không có giao dịch thì không có dòng nào", () => {
    expect(byMethod([])).toEqual([]);
  });
});
