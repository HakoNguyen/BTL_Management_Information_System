import { describe, expect, it } from "vitest";
import { inDateRange, isoWeekRange, vnDate } from "./dateRange";

describe("vnDate", () => {
  it("đổi sang ngày giờ Việt Nam", () => {
    // 17:30 UTC ngày 15 = 00:30 ngày 16 giờ Việt Nam
    expect(vnDate("2026-11-15T17:30:00Z")).toBe("2026-11-16");
    expect(vnDate("2026-11-16T16:59:59Z")).toBe("2026-11-16");
  });
});

describe("inDateRange", () => {
  const range: [string, string] = ["2026-11-10", "2026-11-16"];

  it("không lọc thì khớp mọi dòng, kể cả chưa có thời điểm", () => {
    expect(inDateRange(null, null)).toBe(true);
    expect(inDateRange("2020-01-01T00:00:00Z", null)).toBe(true);
  });

  it("tính cả hai đầu theo giờ Việt Nam", () => {
    expect(inDateRange("2026-11-09T17:00:00Z", range)).toBe(true); // 00:00 ngày 10
    expect(inDateRange("2026-11-09T16:59:59Z", range)).toBe(false); // 23:59 ngày 9
    expect(inDateRange("2026-11-16T16:59:59Z", range)).toBe(true); // 23:59 ngày 16
    expect(inDateRange("2026-11-16T17:00:00Z", range)).toBe(false); // 00:00 ngày 17
  });

  it("chưa có thời điểm thì không khớp khi đang lọc", () => {
    expect(inDateRange(null, range)).toBe(false);
  });
});

describe("isoWeekRange", () => {
  it("trả thứ Hai đến Chủ nhật của tuần, kể cả tuần vắt qua năm", () => {
    expect(isoWeekRange("2026-W47")).toEqual(["2026-11-16", "2026-11-22"]);
    expect(isoWeekRange("2026-W01")).toEqual(["2025-12-29", "2026-01-04"]);
    expect(isoWeekRange("2020-W53")).toEqual(["2020-12-28", "2021-01-03"]);
  });

  it("chuỗi rỗng (xóa ô tuần) thì null", () => {
    expect(isoWeekRange("")).toBeNull();
  });
});
