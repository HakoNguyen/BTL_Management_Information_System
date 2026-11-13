import { expect, test } from "vitest";
import { dateTime, money } from "./format";

test("tiền là số nguyên VND, phân cách hàng nghìn theo vi-VN, giữ dấu âm", () => {
  expect(money(1234567)).toBe("1.234.567");
  expect(money(0)).toBe("0");
  expect(money(-50000)).toBe("-50.000");
});

test("không có số liệu (vd giá trị đơn trung bình khi không có đơn) hiện 'Không có dữ liệu'", () => {
  expect(money(null)).toBe("Không có dữ liệu");
});

test("thời điểm ISO hiện theo giờ Việt Nam", () => {
  expect(dateTime("2026-11-13T03:04:05Z")).toBe("10:04:05 13/11/2026");
  expect(dateTime(null)).toBe("");
});
