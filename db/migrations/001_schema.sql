-- 18 bảng nghiệp vụ theo docs/db.md (đặc tả mục 5.7) và ràng buộc mục 5.3.
-- KHÔNG sửa file này sau khi đã chạy; đổi schema = thêm file migration mới, đánh số tiếp theo.
--
-- Quy ước:
--   * Tiền: bigint, đơn vị VND (G-07). Số lượng: integer.
--   * Mốc thời gian nghiệp vụ không có DEFAULT: code truyền vào từ common/clock.py.
--   * Giá trị trạng thái/loại khớp với enum trong common/constants.py (test_schema kiểm tra).
--   * Chưa tạo index phụ ngoài index của khóa và ràng buộc; thêm bằng migration mới khi cần.

CREATE FUNCTION next_code(prefix text, seq regclass) RETURNS text
LANGUAGE sql AS $$ SELECT prefix || lpad(nextval(seq)::text, 6, '0') $$;

CREATE SEQUENCE customer_seq;
CREATE SEQUENCE order_seq;
CREATE SEQUENCE return_seq;
CREATE SEQUENCE txn_seq;
CREATE SEQUENCE invoice_seq;
CREATE SEQUENCE shift_seq;
CREATE SEQUENCE stock_slip_seq;
CREATE SEQUENCE replenishment_seq;

-- ============================================================ D6 Nhân viên và chi nhánh (nhóm 6)

CREATE TABLE branches (
    branch_id     text PRIMARY KEY,                       -- NV-04: duy nhất, không đổi
    name          text NOT NULL,
    address       text,
    phone         text,
    closing_time  time NOT NULL,                          -- G-08: "cuối ngày" của chi nhánh
    status        text NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'INACTIVE'))
);

CREATE TABLE employees (
    employee_id     text PRIMARY KEY,
    full_name       text NOT NULL,
    phone           text,
    role            text NOT NULL
                    CHECK (role IN ('HQ', 'MANAGER', 'SALES', 'CASHIER', 'WAREHOUSE')),
    branch_id       text REFERENCES branches,             -- chi nhánh hiện tại; NULL với trụ sở
    hired_on        date NOT NULL,
    status          text NOT NULL DEFAULT 'WORKING' CHECK (status IN ('WORKING', 'LEFT')),
    username        text UNIQUE,                          -- NV-03: không tái sử dụng
    password_hash   text,
    account_status  text CHECK (account_status IN ('ACTIVE', 'LOCKED')),
    -- NV-01: nhân viên trụ sở không thuộc chi nhánh, nhân viên cửa hàng thuộc đúng một chi nhánh
    CONSTRAINT employees_hq_has_no_branch CHECK ((role = 'HQ') = (branch_id IS NULL)),
    -- Chưa cấp tài khoản thì cả ba cột tài khoản đều rỗng
    CONSTRAINT employees_account_all_or_none CHECK (
        (username IS NULL) = (password_hash IS NULL)
        AND (username IS NULL) = (account_status IS NULL)
    )
);

-- ============================================================ D1 Sản phẩm (nhóm 1)

CREATE TABLE product_groups (
    group_id     text PRIMARY KEY,                        -- SP-01
    name         text NOT NULL,
    description  text
);

CREATE TABLE products (
    product_id     text PRIMARY KEY,                      -- SP-01
    name           text NOT NULL,
    group_id       text NOT NULL REFERENCES product_groups,
    unit           text NOT NULL,                         -- đơn vị tính
    current_price  bigint NOT NULL CHECK (current_price > 0),   -- SP-02, đã gồm VAT (G-02)
    description    text,
    status         text NOT NULL DEFAULT 'ON_SALE' CHECK (status IN ('ON_SALE', 'DISCONTINUED'))
);

CREATE TABLE price_history (
    product_id    text NOT NULL REFERENCES products,
    effective_at  timestamptz NOT NULL,
    price         bigint NOT NULL CHECK (price > 0),
    changed_by    text NOT NULL REFERENCES employees,
    PRIMARY KEY (product_id, effective_at)
);

-- ============================================================ D2 Khách hàng (nhóm 2)

CREATE TABLE customers (
    customer_id    text PRIMARY KEY DEFAULT next_code('KH', 'customer_seq'),
    full_name      text NOT NULL,
    phone          text UNIQUE,                           -- KH-01: duy nhất toàn chuỗi (đã chuẩn hóa)
    address        text,
    registered_on  date NOT NULL,
    -- KH-01, KH-02: chỉ khách lẻ KHLE không có số điện thoại
    CONSTRAINT customers_phone_except_walk_in CHECK ((customer_id = 'KHLE') = (phone IS NULL))
);
ALTER SEQUENCE customer_seq OWNED BY customers.customer_id;

-- ============================================================ D3 Đơn hàng và trả hàng (nhóm 3)

CREATE TABLE orders (
    order_id       text PRIMARY KEY DEFAULT next_code('DH', 'order_seq'),
    branch_id      text NOT NULL REFERENCES branches,     -- chi nhánh lúc lập, không đổi (K-05)
    customer_id    text NOT NULL REFERENCES customers,    -- BH-01: có thể là KHLE
    created_by     text NOT NULL REFERENCES employees,    -- doanh số ghi cho người lập
    created_at     timestamptz NOT NULL,
    confirmed_at   timestamptz,                           -- thời điểm chốt (BH-02)
    completed_at   timestamptz,                           -- thời điểm hoàn tất (TT-03)
    status         text NOT NULL DEFAULT 'DRAFT' CHECK (status IN (
                       'DRAFT', 'AWAITING_PAYMENT', 'COMPLETED',
                       'PARTIALLY_RETURNED', 'FULLY_RETURNED', 'CANCELLED')),
    cancelled_at   timestamptz,
    cancelled_by   text REFERENCES employees,             -- NULL = Hệ thống tự hủy (BH-05)
    cancel_reason  text,
    -- K-03: đơn Đã hủy luôn có thời điểm và lý do
    CONSTRAINT orders_cancel_info CHECK (
        (status = 'CANCELLED') = (cancelled_at IS NOT NULL)
        AND (status = 'CANCELLED') = (cancel_reason IS NOT NULL)
    )
);
ALTER SEQUENCE order_seq OWNED BY orders.order_id;

CREATE TABLE order_items (
    order_id    text NOT NULL REFERENCES orders,
    product_id  text NOT NULL REFERENCES products,
    quantity    integer NOT NULL CHECK (quantity > 0),
    unit_price  bigint CHECK (unit_price > 0),            -- đơn giá chốt; NULL khi đơn Đang lập
    PRIMARY KEY (order_id, product_id)                    -- BH-01: mỗi sản phẩm một dòng
);

CREATE TABLE return_slips (
    return_id      text PRIMARY KEY DEFAULT next_code('PT', 'return_seq'),
    order_id       text NOT NULL REFERENCES orders,
    created_by     text NOT NULL REFERENCES employees,
    created_at     timestamptz NOT NULL,
    reason         text NOT NULL,                         -- TH-02
    status         text NOT NULL DEFAULT 'PENDING'
                   CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED')),
    decided_by     text REFERENCES employees,             -- NULL = Hệ thống tự từ chối (TH-03)
    decided_at     timestamptz,
    decision_note  text,
    UNIQUE (return_id, order_id),                         -- đích cho khóa ngoại ghép của transactions
    -- K-02: người quyết định khác người lập
    CONSTRAINT return_slips_decider_differs CHECK (decided_by IS DISTINCT FROM created_by),
    CONSTRAINT return_slips_decision_time CHECK ((status = 'PENDING') = (decided_at IS NULL))
);
ALTER SEQUENCE return_seq OWNED BY return_slips.return_id;

CREATE TABLE return_slip_items (
    return_id      text NOT NULL REFERENCES return_slips,
    product_id     text NOT NULL REFERENCES products,
    good_qty       integer NOT NULL CHECK (good_qty >= 0),
    defective_qty  integer NOT NULL CHECK (defective_qty >= 0),
    PRIMARY KEY (return_id, product_id),                  -- TH-02: mỗi sản phẩm một dòng
    CONSTRAINT return_slip_items_total_positive CHECK (good_qty + defective_qty > 0)
);

-- ============================================================ D4 Thanh toán, hóa đơn và ca (nhóm 3)

CREATE TABLE shifts (
    shift_id         text PRIMARY KEY DEFAULT next_code('CA', 'shift_seq'),
    branch_id        text NOT NULL REFERENCES branches,   -- cố định từ lúc mở (CA-01)
    cashier_id       text NOT NULL REFERENCES employees,
    opened_at        timestamptz NOT NULL,
    closed_at        timestamptz,
    settled_at       timestamptz,                         -- thời điểm chốt
    opening_cash     bigint NOT NULL CHECK (opening_cash >= 0),
    counted_cash     bigint CHECK (counted_cash >= 0),    -- tiền kiểm đếm
    variance_reason  text,                                -- lý do chênh lệch (CA-02)
    status           text NOT NULL DEFAULT 'OPEN'
                     CHECK (status IN ('OPEN', 'AWAITING_CONFIRMATION', 'SETTLED')),
    proxy_closed_by  text REFERENCES employees,           -- QL đóng ca thay (CA-04)
    witness_id       text REFERENCES employees,
    proxy_reason     text,
    confirmed_by     text REFERENCES employees,           -- người xác nhận chốt
    CONSTRAINT shifts_proxy_all_or_none CHECK (
        (proxy_closed_by IS NULL) = (witness_id IS NULL)
        AND (proxy_closed_by IS NULL) = (proxy_reason IS NULL)
    ),
    -- K-02: người xác nhận chốt khác thu ngân và khác người đóng ca thay
    CONSTRAINT shifts_confirmer_differs CHECK (
        confirmed_by IS NULL
        OR (confirmed_by <> cashier_id AND confirmed_by IS DISTINCT FROM proxy_closed_by)
    )
);
ALTER SEQUENCE shift_seq OWNED BY shifts.shift_id;
-- CA-01: mỗi thu ngân tối đa một ca Đang mở
CREATE UNIQUE INDEX shifts_one_open_per_cashier ON shifts (cashier_id) WHERE status = 'OPEN';

CREATE TABLE transactions (
    txn_id                   text PRIMARY KEY DEFAULT next_code('GD', 'txn_seq'),
    order_id                 text NOT NULL REFERENCES orders,
    return_id                text,                        -- chỉ với giao dịch Hoàn
    shift_id                 text NOT NULL REFERENCES shifts,   -- ca Đang mở lúc khởi tạo (TT-02)
    type                     text NOT NULL CHECK (type IN ('COLLECT', 'REFUND')),
    method                   text NOT NULL CHECK (method IN ('CASH', 'TRANSFER', 'CARD')),
    amount                   bigint NOT NULL CHECK (amount > 0),
    status                   text NOT NULL DEFAULT 'PENDING'
                             CHECK (status IN ('PENDING', 'SUCCESS', 'FAILED')),
    created_at               timestamptz NOT NULL,
    resolved_at              timestamptz,                 -- thời điểm có kết quả
    reference_code           text,                        -- mã tham chiếu của ngân hàng
    cash_refund_approved_by  text REFERENCES employees,   -- duyệt hoàn tiền mặt thay thế (TH-04)
    cash_refund_reason       text,
    -- 5.3: giao dịch Hoàn gắn phiếu trả có cùng mã đơn; giao dịch Thu không gắn phiếu
    FOREIGN KEY (return_id, order_id) REFERENCES return_slips (return_id, order_id),
    CONSTRAINT transactions_refund_has_slip CHECK ((type = 'REFUND') = (return_id IS NOT NULL)),
    CONSTRAINT transactions_resolved_time CHECK ((status = 'PENDING') = (resolved_at IS NULL)),
    CONSTRAINT transactions_cash_refund_all_or_none CHECK (
        (cash_refund_approved_by IS NULL) = (cash_refund_reason IS NULL)
    )
);
ALTER SEQUENCE txn_seq OWNED BY transactions.txn_id;
-- 5.3: mỗi đơn tối đa một giao dịch Chờ kết quả và một giao dịch Thu Thành công
CREATE UNIQUE INDEX transactions_one_pending_per_order
    ON transactions (order_id) WHERE status = 'PENDING';
CREATE UNIQUE INDEX transactions_one_collect_success_per_order
    ON transactions (order_id) WHERE type = 'COLLECT' AND status = 'SUCCESS';
-- 5.3, TH-04: mỗi phiếu trả tối đa một giao dịch Hoàn Thành công
CREATE UNIQUE INDEX transactions_one_refund_success_per_slip
    ON transactions (return_id) WHERE type = 'REFUND' AND status = 'SUCCESS';
-- TT-02: một mã tham chiếu không gắn cho hai giao dịch
CREATE UNIQUE INDEX transactions_reference_code_unique
    ON transactions (reference_code) WHERE reference_code IS NOT NULL;

CREATE TABLE invoices (
    invoice_no   text PRIMARY KEY DEFAULT next_code('HD', 'invoice_seq'),
    order_id     text NOT NULL UNIQUE REFERENCES orders,  -- TT-04: đúng một hóa đơn mỗi đơn
    issued_at    timestamptz NOT NULL,
    print_count  integer NOT NULL DEFAULT 0 CHECK (print_count >= 0)
);
ALTER SEQUENCE invoice_seq OWNED BY invoices.invoice_no;

-- ============================================================ D5 Tồn kho (nhóm 4)

CREATE TABLE stock (
    branch_id   text NOT NULL REFERENCES branches,
    product_id  text NOT NULL REFERENCES products,
    quantity    integer NOT NULL DEFAULT 0 CHECK (quantity >= 0),   -- TK-01: không âm
    min_level   integer CHECK (min_level >= 0),           -- NULL = Chưa thiết lập (TK-05)
    PRIMARY KEY (branch_id, product_id)
);

CREATE TABLE stock_slips (
    slip_id          text PRIMARY KEY DEFAULT next_code('PK', 'stock_slip_seq'),
    branch_id        text NOT NULL REFERENCES branches,
    type             text NOT NULL CHECK (type IN (
                         'IN_WAREHOUSE', 'IN_SUPPLIER', 'IN_RETURN', 'ADJUST_UP',
                         'OUT_SALE', 'OUT_DISPOSAL', 'OUT_TO_WAREHOUSE', 'ADJUST_DOWN')),
    status           text NOT NULL CHECK (status IN ('PENDING', 'POSTED', 'CANCELLED')),
    created_at       timestamptz NOT NULL,
    created_by       text REFERENCES employees,           -- NULL nếu tự động (xuất bán, nhập hàng trả)
    reason           text,
    counterparty     text,                                -- bên giao / bên nhận
    delivery_no      text,                                -- số phiếu giao
    order_id         text REFERENCES orders,              -- chỉ phiếu Xuất bán
    return_id        text REFERENCES return_slips,        -- chỉ phiếu Nhập hàng trả
    adjusts_slip_id  text REFERENCES stock_slips,         -- phiếu kho bị điều chỉnh (TK-04)
    approved_by      text REFERENCES employees,
    finalized_at     timestamptz,                         -- thời điểm ghi nhận hoặc hủy
    -- 5.3: Xuất bán bắt buộc có mã đơn; Nhập hàng trả bắt buộc có mã phiếu trả
    CONSTRAINT stock_slips_sale_has_order CHECK ((type = 'OUT_SALE') = (order_id IS NOT NULL)),
    CONSTRAINT stock_slips_return_has_slip CHECK ((type = 'IN_RETURN') = (return_id IS NOT NULL)),
    -- TK-02: nhập từ kho tổng/NCC bắt buộc có bên giao và số phiếu giao
    CONSTRAINT stock_slips_delivery_note CHECK (
        type NOT IN ('IN_WAREHOUSE', 'IN_SUPPLIER')
        OR (counterparty IS NOT NULL AND delivery_no IS NOT NULL)
    ),
    -- TK-03, TK-04: phiếu do NV kho lập và cần duyệt thì bắt buộc lý do
    CONSTRAINT stock_slips_reason_required CHECK (
        type NOT IN ('ADJUST_UP', 'ADJUST_DOWN', 'OUT_DISPOSAL', 'OUT_TO_WAREHOUSE')
        OR reason IS NOT NULL
    ),
    CONSTRAINT stock_slips_finalized_time CHECK ((status = 'PENDING') = (finalized_at IS NULL)),
    -- K-02: người duyệt khác người lập
    CONSTRAINT stock_slips_approver_differs CHECK (
        approved_by IS NULL OR approved_by IS DISTINCT FROM created_by
    )
);
ALTER SEQUENCE stock_slip_seq OWNED BY stock_slips.slip_id;
-- TK-02: bộ (bên giao, số phiếu giao, chi nhánh) không được ghi hai lần
CREATE UNIQUE INDEX stock_slips_delivery_note_unique
    ON stock_slips (branch_id, counterparty, delivery_no)
    WHERE type IN ('IN_WAREHOUSE', 'IN_SUPPLIER');
-- TK-03: mỗi đơn tối đa một phiếu xuất bán chưa bị hủy
CREATE UNIQUE INDEX stock_slips_one_live_sale_per_order
    ON stock_slips (order_id) WHERE type = 'OUT_SALE' AND status <> 'CANCELLED';
-- TK-02, TH-05: tối đa một phiếu nhập hàng trả cho mỗi phiếu trả
CREATE UNIQUE INDEX stock_slips_one_per_return
    ON stock_slips (return_id) WHERE return_id IS NOT NULL;

CREATE TABLE stock_slip_items (
    slip_id     text NOT NULL REFERENCES stock_slips,
    product_id  text NOT NULL REFERENCES products,
    quantity    integer NOT NULL CHECK (quantity > 0),
    PRIMARY KEY (slip_id, product_id)
);

CREATE TABLE replenishment_requests (
    request_id  text PRIMARY KEY DEFAULT next_code('YC', 'replenishment_seq'),
    branch_id   text NOT NULL REFERENCES branches,
    created_by  text NOT NULL REFERENCES employees,
    created_at  timestamptz NOT NULL,
    type        text NOT NULL CHECK (type IN ('TRANSFER', 'SUPPLIER')),
    recipient   text NOT NULL                             -- nơi nhận: kho tổng hoặc tên NCC
);
ALTER SEQUENCE replenishment_seq OWNED BY replenishment_requests.request_id;

CREATE TABLE replenishment_request_items (
    request_id  text NOT NULL REFERENCES replenishment_requests,
    product_id  text NOT NULL REFERENCES products,
    quantity    integer NOT NULL CHECK (quantity > 0),    -- số lượng đề nghị (TK-06)
    PRIMARY KEY (request_id, product_id)
);
