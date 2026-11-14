-- K-02, K-03: lý do khi trụ sở duyệt thay xác nhận chốt ca (đặc tả 2.2; duyệt 14/11/2026, docs/plan.md quyết định 14)
ALTER TABLE shifts ADD COLUMN confirm_reason text;
