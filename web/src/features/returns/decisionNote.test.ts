import { expect, test } from "vitest";
import { decisionNoteRequired } from "./decisionNote";

test("QL duyệt phiếu trả: ghi chú tùy chọn", () => {
  expect(decisionNoteRequired("MANAGER", "approve")).toBe(false);
});

test("HQ duyệt thay luôn phải ghi lý do (K-02)", () => {
  expect(decisionNoteRequired("HQ", "approve")).toBe(true);
});

test("từ chối luôn phải ghi lý do (K-03), dù là QL hay HQ", () => {
  expect(decisionNoteRequired("MANAGER", "reject")).toBe(true);
  expect(decisionNoteRequired("HQ", "reject")).toBe(true);
});
