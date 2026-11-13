# Thiết kế CSDL

Bản hiện thực của đặc tả mục 5 ([spec.md](spec.md)) trên PostgreSQL 16. Schema nằm trong
`db/migrations/001_schema.sql`; file này là bảng đối chiếu tên và là hợp đồng cho mọi code đọc/ghi CSDL.
Khi file này và migration lệch nhau thì đó là lỗi: dừng lại và báo, không tự chọn một bên.

## 1. Quy ước

- Tên bảng, cột, mã trạng thái bằng tiếng Anh; giao diện hiển thị tiếng Việt (`web/src/labels.ts`).
- Tiền: `bigint`, đơn vị VND, số nguyên (G-07). Số lượng: `integer`.
- Thời gian: `timestamptz`. Mốc thời gian nghiệp vụ không có `DEFAULT`; code lấy từ `common/clock.py`
  rồi truyền vào SQL. Giờ đóng cửa (`branches.closing_time`) là giờ Việt Nam (UTC+7).
- Mã do trụ sở nhập: chi nhánh, nhân viên, nhóm sản phẩm, sản phẩm. Mã do hệ thống sinh: tiền tố + 6 chữ số
  tăng dần, sinh bằng `DEFAULT next_code(...)` của cột khóa chính (mục 7).
- Chỉ nhóm sở hữu kho được ghi vào bảng của kho đó (đặc tả 6.1); nhóm khác gọi hàm của nhóm sở hữu
  ([api.md](api.md) mục 5). Đọc thì được `SELECT` trực tiếp theo ma trận 6.1.
- `schema_migrations` là bảng kỹ thuật của `db/migrate.py`, không thuộc 18 bảng nghiệp vụ.

## 2. Đối chiếu 18 bảng

Cột viết theo dạng `tên trong code` = tên trong đặc tả 5.7. **PK** là khóa chính.

### D6 Nhân viên và chi nhánh (nhóm 6 ghi)

| Bảng | Thực thể | Cột |
| --- | --- | --- |
| `branches` | CHI NHÁNH | **`branch_id`** = mã CN; `name` = tên CN; `address` = địa chỉ; `phone` = điện thoại; `closing_time` = giờ đóng cửa; `status` = trạng thái |
| `employees` | NHÂN VIÊN | **`employee_id`** = mã NV; `full_name` = họ tên; `phone` = điện thoại; `role` = vai trò; `branch_id` = mã CN hiện tại (NULL với trụ sở); `hired_on` = ngày vào làm; `status` = trạng thái nhân viên; `username` = tên đăng nhập; `password_hash` = mật khẩu đã mã hóa; `account_status` = trạng thái tài khoản |

### D1 Sản phẩm (nhóm 1 ghi)

| Bảng | Thực thể | Cột |
| --- | --- | --- |
| `product_groups` | NHÓM SẢN PHẨM | **`group_id`** = mã nhóm; `name` = tên nhóm; `description` = mô tả |
| `products` | SẢN PHẨM | **`product_id`** = mã SP; `name` = tên SP; `group_id` = mã nhóm; `unit` = đơn vị tính; `current_price` = giá hiện hành; `description` = mô tả; `status` = trạng thái kinh doanh |
| `price_history` | LỊCH SỬ GIÁ | **`product_id` + `effective_at`** = mã SP + thời điểm hiệu lực; `price` = giá; `changed_by` = mã NV thay đổi |

### D2 Khách hàng (nhóm 2 ghi)

| Bảng | Thực thể | Cột |
| --- | --- | --- |
| `customers` | KHÁCH HÀNG | **`customer_id`** = mã KH; `full_name` = họ tên; `phone` = số điện thoại (duy nhất, NULL với KHLE); `address` = địa chỉ; `registered_on` = ngày đăng ký |

### D3 Đơn hàng và trả hàng (nhóm 3 ghi)

| Bảng | Thực thể | Cột |
| --- | --- | --- |
| `orders` | ĐƠN HÀNG | **`order_id`** = mã đơn; `branch_id` = mã CN; `customer_id` = mã KH; `created_by` = mã NV lập; `created_at` = thời điểm lập; `confirmed_at` = thời điểm chốt; `completed_at` = thời điểm hoàn tất; `status` = trạng thái; `cancelled_at` = thời điểm hủy; `cancelled_by` = mã NV hủy (NULL = Hệ thống); `cancel_reason` = lý do hủy |
| `order_items` | CHI TIẾT ĐƠN | **`order_id` + `product_id`**; `quantity` = số lượng; `unit_price` = đơn giá chốt (NULL khi đơn Đang lập) |
| `return_slips` | PHIẾU TRẢ | **`return_id`** = mã phiếu trả; `order_id` = mã đơn; `created_by` = mã NV lập; `created_at` = thời điểm lập; `reason` = lý do trả; `status` = trạng thái; `decided_by` = mã NV quyết định (NULL = Hệ thống tự từ chối); `decided_at` = thời điểm quyết định; `decision_note` = ghi chú quyết định |
| `return_slip_items` | CHI TIẾT PHIẾU TRẢ | **`return_id` + `product_id`**; `good_qty` = số lượng tốt; `defective_qty` = số lượng lỗi |

### D4 Thanh toán, hóa đơn và ca (nhóm 3 ghi)

| Bảng | Thực thể | Cột |
| --- | --- | --- |
| `transactions` | GIAO DỊCH | **`txn_id`** = mã GD; `order_id` = mã đơn; `return_id` = mã phiếu trả (chỉ giao dịch Hoàn); `shift_id` = mã ca; `type` = loại; `method` = phương thức; `amount` = số tiền; `status` = trạng thái; `created_at` = thời điểm tạo; `resolved_at` = thời điểm có kết quả; `reference_code` = mã tham chiếu; `cash_refund_approved_by` = mã NV duyệt hoàn tiền mặt thay thế; `cash_refund_reason` = lý do hoàn tiền mặt |
| `invoices` | HÓA ĐƠN | **`invoice_no`** = số hóa đơn; `order_id` = mã đơn (duy nhất); `issued_at` = thời điểm phát hành; `print_count` = số lần in |
| `shifts` | CA THU NGÂN | **`shift_id`** = mã ca; `branch_id` = mã CN; `cashier_id` = mã thu ngân; `opened_at`, `closed_at`, `settled_at` = thời điểm mở, đóng, chốt; `opening_cash` = tiền đầu ca; `counted_cash` = tiền kiểm đếm; `variance_reason` = lý do chênh lệch; `status` = trạng thái; `proxy_closed_by` = mã NV đóng thay; `witness_id` = mã NV làm chứng; `proxy_reason` = lý do đóng thay; `confirmed_by` = mã NV xác nhận chốt |

### D5 Tồn kho (nhóm 4 ghi)

| Bảng | Thực thể | Cột |
| --- | --- | --- |
| `stock` | TỒN KHO | **`branch_id` + `product_id`**; `quantity` = số lượng tồn; `min_level` = mức tồn tối thiểu (NULL = Chưa thiết lập) |
| `stock_slips` | PHIẾU KHO | **`slip_id`** = mã phiếu kho; `branch_id` = mã CN; `type` = loại phiếu; `status` = trạng thái; `created_at` = thời điểm lập; `created_by` = mã NV lập (NULL nếu tự động); `reason` = lý do; `counterparty` = bên giao / bên nhận; `delivery_no` = số phiếu giao; `order_id` = mã đơn (xuất bán); `return_id` = mã phiếu trả (nhập hàng trả); `adjusts_slip_id` = mã phiếu kho bị điều chỉnh; `approved_by` = mã NV duyệt; `finalized_at` = thời điểm ghi nhận hoặc hủy |
| `stock_slip_items` | CHI TIẾT PHIẾU KHO | **`slip_id` + `product_id`**; `quantity` = số lượng |
| `replenishment_requests` | YÊU CẦU BỔ SUNG | **`request_id`** = mã yêu cầu; `branch_id` = mã CN; `created_by` = mã NV lập; `created_at` = thời điểm lập; `type` = loại yêu cầu; `recipient` = nơi nhận |
| `replenishment_request_items` | CHI TIẾT YÊU CẦU | **`request_id` + `product_id`**; `quantity` = số lượng đề nghị |

## 3. Mã trạng thái và loại

Giá trị lưu trong CSDL trùng với enum trong `common/constants.py`; `tests/db/test_schema.py` kiểm tra hai bên khớp.
Code dùng enum, không viết chuỗi trực tiếp.

| Cột | Enum | Giá trị = nghĩa trong đặc tả 5.4 |
| --- | --- | --- |
| `employees.role` | `Role` | `HQ` = Trụ sở; `MANAGER` = Quản lý cửa hàng; `SALES` = Nhân viên bán hàng; `CASHIER` = Thu ngân; `WAREHOUSE` = Nhân viên kho |
| `employees.status` | `EmployeeStatus` | `WORKING` = Đang làm; `LEFT` = Đã nghỉ |
| `employees.account_status` | `AccountStatus` | `ACTIVE` = Hoạt động; `LOCKED` = Bị khóa; NULL = chưa cấp tài khoản |
| `branches.status` | `BranchStatus` | `ACTIVE` = Hoạt động; `INACTIVE` = Ngừng hoạt động |
| `products.status` | `ProductStatus` | `ON_SALE` = Đang bán; `DISCONTINUED` = Ngừng bán |
| `orders.status` | `OrderStatus` | `DRAFT` = Đang lập; `AWAITING_PAYMENT` = Chờ thanh toán; `COMPLETED` = Hoàn tất; `PARTIALLY_RETURNED` = Đã trả một phần; `FULLY_RETURNED` = Đã trả toàn bộ; `CANCELLED` = Đã hủy |
| `return_slips.status` | `ReturnStatus` | `PENDING` = Chờ duyệt; `APPROVED` = Đã duyệt; `REJECTED` = Từ chối |
| `transactions.type` | `TxnType` | `COLLECT` = Thu; `REFUND` = Hoàn |
| `transactions.method` | `TxnMethod` | `CASH` = Tiền mặt; `TRANSFER` = Chuyển khoản; `CARD` = Thẻ |
| `transactions.status` | `TxnStatus` | `PENDING` = Chờ kết quả; `SUCCESS` = Thành công; `FAILED` = Thất bại |
| `shifts.status` | `ShiftStatus` | `OPEN` = Đang mở; `AWAITING_CONFIRMATION` = Chờ xác nhận; `SETTLED` = Đã chốt |
| `stock_slips.type` | `SlipType` | `IN_WAREHOUSE` = Nhập từ kho tổng; `IN_SUPPLIER` = Nhập từ NCC; `IN_RETURN` = Nhập hàng trả; `ADJUST_UP` = Điều chỉnh tăng; `OUT_SALE` = Xuất bán; `OUT_DISPOSAL` = Xuất hủy; `OUT_TO_WAREHOUSE` = Xuất trả kho tổng; `ADJUST_DOWN` = Điều chỉnh giảm |
| `stock_slips.status` | `SlipStatus` | `PENDING` = Chờ xử lý; `POSTED` = Đã ghi nhận; `CANCELLED` = Đã hủy |
| `replenishment_requests.type` | `ReplenishType` | `TRANSFER` = Điều chuyển (kho tổng); `SUPPLIER` = Nhập NCC |

Trạng thái chỉ đi tới theo đặc tả 5.4 và sơ đồ vòng đời đơn hàng (mục 4.3). Cập nhật trạng thái luôn có điều kiện
trạng thái liền trước: `UPDATE … SET status = $mới WHERE … AND status = $cũ`, rồi kiểm tra số dòng bị ảnh hưởng.

## 4. Ràng buộc ép ở CSDL

Các ràng buộc dưới đây là chốt chặn cuối. Service vẫn phải kiểm tra trước để trả lỗi có mã quy tắc rõ ràng,
không để lỗi CSDL lọt ra thành lỗi 500.

| Quy tắc | Ràng buộc |
| --- | --- |
| NV-01: trụ sở không thuộc chi nhánh, nhân viên cửa hàng thuộc đúng một chi nhánh | `employees_hq_has_no_branch` |
| NV-03: tên đăng nhập duy nhất; chưa cấp tài khoản thì ba cột tài khoản đều NULL | `UNIQUE (username)`, `employees_account_all_or_none` |
| SP-02: giá > 0 | `CHECK` trên `products.current_price`, `price_history.price` |
| KH-01, KH-02: số điện thoại duy nhất; chỉ KHLE không có số | `UNIQUE (phone)`, `customers_phone_except_walk_in` |
| BH-01: mỗi sản phẩm một dòng, số lượng > 0 | khóa chính `order_items`, `CHECK (quantity > 0)` |
| K-03: đơn Đã hủy có thời điểm và lý do | `orders_cancel_info` |
| K-02: người quyết định phiếu trả khác người lập | `return_slips_decider_differs` |
| TH-02: mỗi sản phẩm một dòng; tốt, lỗi ≥ 0; tổng > 0 | khóa chính `return_slip_items`, `return_slip_items_total_positive` |
| 5.3: giao dịch Hoàn gắn phiếu trả cùng mã đơn; giao dịch Thu không gắn phiếu | khóa ngoại ghép `(return_id, order_id)`, `transactions_refund_has_slip` |
| 5.3: mỗi đơn tối đa một giao dịch Chờ kết quả | `transactions_one_pending_per_order` |
| 5.3, TT-03: mỗi đơn tối đa một giao dịch Thu Thành công | `transactions_one_collect_success_per_order` |
| 5.3, TH-04: mỗi phiếu trả tối đa một giao dịch Hoàn Thành công | `transactions_one_refund_success_per_slip` |
| TT-02: một mã tham chiếu không gắn cho hai giao dịch | `transactions_reference_code_unique` |
| TT-04: mỗi đơn đúng một hóa đơn | `UNIQUE (order_id)` trên `invoices` |
| CA-01: mỗi thu ngân tối đa một ca Đang mở | `shifts_one_open_per_cashier` |
| CA-04: thông tin đóng ca thay đủ cả ba hoặc không có | `shifts_proxy_all_or_none` |
| K-02: người xác nhận chốt ca khác thu ngân và khác người đóng thay | `shifts_confirmer_differs` |
| TK-01: tồn ≥ 0 | `CHECK (quantity >= 0)` trên `stock` |
| 5.3: Xuất bán có mã đơn; Nhập hàng trả có mã phiếu trả | `stock_slips_sale_has_order`, `stock_slips_return_has_slip` |
| TK-02: nhập kho tổng/NCC có bên giao và số phiếu giao, không ghi hai lần | `stock_slips_delivery_note`, `stock_slips_delivery_note_unique` |
| TK-03: mỗi đơn tối đa một phiếu xuất bán chưa hủy | `stock_slips_one_live_sale_per_order` |
| TK-02, TH-05: mỗi phiếu trả tối đa một phiếu nhập hàng trả | `stock_slips_one_per_return` |
| TK-03, TK-04: phiếu cần duyệt bắt buộc lý do | `stock_slips_reason_required` |
| K-02: người duyệt phiếu kho khác người lập | `stock_slips_approver_differs` |

## 5. Ràng buộc ép ở service

CSDL không tự ép được các điều dưới đây; service của nhóm sở hữu phải kiểm tra trong cùng transaction với thao tác ghi.

- Ca của giao dịch cùng chi nhánh với đơn (5.3).
- Sản phẩm trên phiếu trả phải có trong đơn gốc; tổng lượng trả đã duyệt và đang chờ duyệt ≤ lượng mua (TH-02, 5.3).
- Phương thức của giao dịch Hoàn bằng phương thức của giao dịch Thu Thành công, trừ khi đã duyệt hoàn tiền mặt (TH-04).
- Số tiền giao dịch Thu = tổng đơn; số tiền giao dịch Hoàn = giá trị phiếu trả (TT-01, TH-04).
- Số lượng trên phiếu xuất không vượt tồn khả dụng (TK-03): khóa dòng `stock` bằng `SELECT … FOR UPDATE`
  theo thứ tự `product_id` tăng dần trước khi tính, để hai giao dịch tranh hàng không cùng qua được (KT-06).
- Tồn chỉ đổi khi một phiếu kho chuyển `POSTED` (TK-01): không có câu `UPDATE stock SET quantity` nào nằm ngoài
  `api/services/inventory.py`.
- Không sửa, xóa chứng từ đã có hiệu lực (K-04) và không xóa danh mục đã phát sinh nghiệp vụ (K-05).

## 6. Dữ liệu dẫn xuất

Theo đặc tả 5.5, các số dưới đây **không lưu thành cột**; luôn tính bằng truy vấn từ dữ liệu gốc.

| Dữ liệu | Cách tính |
| --- | --- |
| Tổng tiền đơn | Σ `quantity × unit_price` của `order_items` |
| Lượng đã trả của một dòng đơn | Σ `good_qty + defective_qty` trên các phiếu trả `APPROVED` của đơn, cùng sản phẩm |
| Giá trị phiếu trả | Σ `(good_qty + defective_qty) × unit_price` của dòng đơn gốc (TH-04) |
| Tình trạng hoàn tiền của phiếu | Đã hoàn nếu có giao dịch Hoàn `SUCCESS`; Đang chờ kết quả nếu có giao dịch `PENDING`; còn lại Chưa hoàn |
| Tồn khả dụng | `stock.quantity` − Σ số lượng trên các phiếu xuất `PENDING` của cùng chi nhánh và sản phẩm (TK-01) |
| Tiền mặt kỳ vọng, chênh lệch ca | Theo CA-02 |
| Chỉ tiêu doanh thu | Theo DT-01 đến DT-05 |

## 7. Mã chứng từ do hệ thống sinh

| Chứng từ | Cột | Tiền tố | Ví dụ |
| --- | --- | --- | --- |
| Khách hàng | `customers.customer_id` | `KH` | `KH000001` (riêng khách lẻ là `KHLE`) |
| Đơn hàng | `orders.order_id` | `DH` | `DH000001` |
| Phiếu trả | `return_slips.return_id` | `PT` | `PT000001` |
| Giao dịch | `transactions.txn_id` | `GD` | `GD000001` |
| Hóa đơn | `invoices.invoice_no` | `HD` | `HD000001` |
| Ca thu ngân | `shifts.shift_id` | `CA` | `CA000001` |
| Phiếu kho | `stock_slips.slip_id` | `PK` | `PK000001` |
| Yêu cầu bổ sung | `replenishment_requests.request_id` | `YC` | `YC000001` |

Code không tự ghép mã: `INSERT … RETURNING <cột mã>` để lấy mã vừa sinh.
