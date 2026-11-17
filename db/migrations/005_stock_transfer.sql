-- 4.6, TK-07: điều chuyển hàng giữa chi nhánh (duyệt 17/11/2026, docs/plan.md quyết định 16).
-- Hai loại phiếu kho mới; phiếu nhập điều chuyển trỏ về phiếu xuất điều chuyển.
ALTER TABLE stock_slips DROP CONSTRAINT stock_slips_type_check;
ALTER TABLE stock_slips ADD CONSTRAINT stock_slips_type_check CHECK (type IN (
    'IN_WAREHOUSE', 'IN_SUPPLIER', 'IN_RETURN', 'ADJUST_UP',
    'OUT_SALE', 'OUT_DISPOSAL', 'OUT_TO_WAREHOUSE', 'ADJUST_DOWN',
    'OUT_TRANSFER', 'IN_TRANSFER'));

ALTER TABLE stock_slips ADD COLUMN transfer_slip_id text REFERENCES stock_slips;

-- TK-03, TK-07: phiếu cần duyệt bắt buộc lý do (thêm Xuất điều chuyển)
ALTER TABLE stock_slips DROP CONSTRAINT stock_slips_reason_required;
ALTER TABLE stock_slips ADD CONSTRAINT stock_slips_reason_required CHECK (
    type NOT IN ('ADJUST_UP', 'ADJUST_DOWN', 'OUT_DISPOSAL', 'OUT_TO_WAREHOUSE', 'OUT_TRANSFER')
    OR reason IS NOT NULL
);
-- TK-07: xuất điều chuyển có bên nhận (mã chi nhánh nhận)
ALTER TABLE stock_slips ADD CONSTRAINT stock_slips_transfer_counterparty CHECK (
    type <> 'OUT_TRANSFER' OR counterparty IS NOT NULL
);
-- TK-07: nhập điều chuyển bắt buộc có mã phiếu xuất điều chuyển, loại khác không có
ALTER TABLE stock_slips ADD CONSTRAINT stock_slips_transfer_link CHECK (
    (type = 'IN_TRANSFER') = (transfer_slip_id IS NOT NULL)
);
-- TK-07: mỗi phiếu xuất điều chuyển chỉ được nhận một lần
CREATE UNIQUE INDEX stock_slips_one_per_transfer
    ON stock_slips (transfer_slip_id) WHERE transfer_slip_id IS NOT NULL;
