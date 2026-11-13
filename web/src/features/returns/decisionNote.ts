import type { Role } from "../../api/client";

/** Ghi chú quyết định phiếu trả: bắt buộc khi từ chối (K-03) và khi HQ duyệt thay (K-02). */
export const decisionNoteRequired = (role: Role, decision: "approve" | "reject") =>
  decision === "reject" || role === "HQ";
