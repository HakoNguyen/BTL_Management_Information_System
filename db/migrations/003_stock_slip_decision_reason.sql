-- K-03: lưu lý do khi QL từ chối phiếu kho (duyệt 13/11/2026, docs/plan.md mục 7 ý 13)
ALTER TABLE stock_slips ADD COLUMN decision_reason text;
