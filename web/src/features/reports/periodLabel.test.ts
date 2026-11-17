import { describe, expect, it } from "vitest";
import { periodLabel } from "./periodLabel";

describe("periodLabel", () => {
  it("hiện nhãn theo độ chi tiết", () => {
    expect(periodLabel("2026-11-16", "DAY")).toBe("16/11");
    expect(periodLabel("2026-11-01", "MONTH")).toBe("11/2026");
    expect(periodLabel("2026-01-01", "QUARTER")).toBe("Q1/2026");
    expect(periodLabel("2026-10-01", "QUARTER")).toBe("Q4/2026");
    expect(periodLabel("2026-01-01", "YEAR")).toBe("2026");
  });
});
