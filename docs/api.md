# Hợp đồng API

Một ứng dụng FastAPI (`api/`) phục vụ cả 6 nhóm chức năng. Giao diện (`web/`) gọi qua tiền tố `/api`
(nginx và vite dev chuyển `/api/*` sang api và bỏ tiền tố), nên các đường dẫn dưới đây không có `/api`.

Tài liệu này chốt **tên endpoint, vai trò được gọi và hàm giao giữa các module**. Tên trường request/response
của từng endpoint được chốt trong bước `/plan-task` của vòng tương ứng: bổ sung vào file này TRƯỚC, rồi mới viết
model trong `common/models.py`. Không tự thêm endpoint ngoài danh sách; cần thêm thì dừng và hỏi.

## 1. Quy ước chung

- JSON, UTF-8. Tiền là số nguyên VND. Thời gian theo ISO 8601 có múi giờ.
- Đăng nhập: gửi `Authorization: Bearer <token>` ở mọi request trừ `/health`, `/auth/login`, `/bank/callback`.
- Quyền kiểm tra ở mỗi request theo vai trò và chi nhánh hiện tại của nhân viên (K-01), bằng
  `require_role(...)` trong `api/deps.py`. QL, NVBH, Thu ngân, NV kho chỉ thao tác trong chi nhánh của mình;
  service so `user.branch_id` với chi nhánh của chứng từ.
- Router mỏng: kiểm tra vai trò, gọi một hàm service, trả model. SQL và quy tắc nghiệp vụ nằm trong `api/services/`.
- Thành công: `200` kèm model, hoặc `201` khi tạo mới. Danh sách trả mảng JSON.

## 2. Lỗi

Mọi lỗi trả cùng một dạng:

```json
{ "error_code": "RULE_VIOLATION", "message": "Sản phẩm đã ngừng bán", "details": { "rule": "BH-02" } }
```

| `error_code` | HTTP | Dùng khi |
| --- | --- | --- |
| `VALIDATION_ERROR` | 400 | Dữ liệu gửi lên sai định dạng, thiếu trường |
| `UNAUTHORIZED` | 401 | Chưa đăng nhập, sai mật khẩu, phiên hết hạn, tài khoản vừa bị khóa |
| `FORBIDDEN` | 403 | Sai vai trò, sai chi nhánh, tài khoản bị khóa lúc đăng nhập, người duyệt trùng người lập (K-02) |
| `NOT_FOUND` | 404 | Không có bản ghi với mã đã cho |
| `DUPLICATE` | 409 | Trùng mã, số điện thoại, tên đăng nhập, phiếu giao |
| `INVALID_STATE` | 409 | Chứng từ không ở trạng thái cho phép thao tác |
| `INSUFFICIENT_STOCK` | 409 | Vượt tồn khả dụng (TK-01, TK-03) |
| `RULE_VIOLATION` | 422 | Vi phạm quy tắc nghiệp vụ khác |
| `INTERNAL_ERROR` | 500 | Lỗi không lường trước |

Code ném `AppError(ErrorCode.X, "thông báo tiếng Việt", rule="BH-02", details={...})` (`common/errors.py`).
Lỗi do quy tắc nghiệp vụ luôn kèm `rule` là mã quy tắc trong đặc tả; test assert theo `error_code` và `details.rule`.

## 3. Endpoint đã có (vòng 0)

| Method, đường dẫn | Vai trò | Nội dung |
| --- | --- | --- |
| `GET /health` | không cần đăng nhập | `{"status": "ok"}` |
| `POST /auth/login` | không cần đăng nhập | Nhận `username`, `password`; trả `token` và `user` (`employee_id`, `full_name`, `role`, `branch_id`). Sai thông tin: `UNAUTHORIZED`. Tài khoản Bị khóa hoặc nhân viên Đã nghỉ: `FORBIDDEN`, `rule` = K-01 |
| `GET /auth/me` | đã đăng nhập | Trả `user` của phiên hiện tại |

## 4. Endpoint theo nhóm chức năng (khung)

Viết tắt vai trò: HQ = Trụ sở, QL = `MANAGER`, BH = `SALES`, TN = `CASHIER`, KHO = `WAREHOUSE`.
"Mọi vai trò" nghĩa là mọi nhân viên đã đăng nhập.

### Nhóm 6 – Nhân viên và chi nhánh (vòng 1)

| Chức năng | Method, đường dẫn | Vai trò | Quy tắc |
| --- | --- | --- | --- |
| 6.4 | `GET /branches` | Mọi vai trò | |
| 6.4 | `POST /branches`, `PATCH /branches/{branch_id}` | HQ | NV-04 |
| 6.4 | `POST /branches/{branch_id}/deactivate` | HQ | NV-04 |
| 6.1 | `GET /employees`, `POST /employees`, `PATCH /employees/{employee_id}` | HQ | NV-01 |
| 6.1 | `POST /employees/{employee_id}/leave` | HQ | NV-03 |
| 6.2 | `PUT /employees/{employee_id}/assignment` | HQ | NV-02 |
| 6.3 | `POST /employees/{employee_id}/account` | HQ | NV-03 |
| 6.3 | `POST /employees/{employee_id}/account/lock`, `…/account/unlock` | HQ | NV-03 |

### Nhóm 1 – Sản phẩm (vòng 2)

| Chức năng | Method, đường dẫn | Vai trò | Quy tắc |
| --- | --- | --- | --- |
| 1.2 | `GET /product-groups` | Mọi vai trò | |
| 1.2 | `POST /product-groups`, `PATCH /product-groups/{group_id}`, `DELETE /product-groups/{group_id}` | HQ | SP-01 |
| 1.2 | `PUT /products/{product_id}/group` | HQ | SP-01 |
| 1.1 | `GET /products`, `GET /products/{product_id}` | Mọi vai trò | |
| 1.1 | `POST /products`, `PATCH /products/{product_id}` | HQ | SP-01, SP-04 |
| 1.3 | `PUT /products/{product_id}/price`, `GET /products/{product_id}/price-history` | HQ | SP-02 |
| 1.4 | `PUT /products/{product_id}/status` | HQ | SP-04 |

### Nhóm 2 – Khách hàng (vòng 3; 2.4 ở vòng 7)

| Chức năng | Method, đường dẫn | Vai trò | Quy tắc |
| --- | --- | --- | --- |
| 2.1 | `POST /customers` | BH | KH-01 |
| 2.2 | `PATCH /customers/{customer_id}` | BH | KH-01, KH-03 |
| 2.3 | `GET /customers` (lọc theo `phone` hoặc `customer_id`) | BH | KH-02 |
| 2.4 | `GET /customers/{customer_id}/history` (kèm `phone` để xác minh) | BH | KH-04 |

### Nhóm 4 – Tồn kho (vòng 4; 4.4 ở vòng 8)

| Chức năng | Method, đường dẫn | Vai trò | Quy tắc |
| --- | --- | --- | --- |
| 4.1 | `GET /stock` (tồn, tồn khả dụng, ngưỡng của chi nhánh mình) | QL, BH, KHO | TK-01 |
| 4.2 | `POST /stock-slips/inbound` (nhập từ kho tổng, NCC) | KHO | TK-02 |
| 4.2, 4.3 | `POST /stock-slips` (điều chỉnh tăng/giảm, xuất hủy, xuất trả kho tổng) | KHO | TK-03, TK-04 |
| 4.2, 4.3 | `GET /stock-slips`, `GET /stock-slips/{slip_id}` | QL, KHO | |
| 4.2, 4.3 | `POST /stock-slips/{slip_id}/approve`, `…/reject` | QL | TK-03, K-02 |
| 4.5 | `PUT /stock/{product_id}/min-level` | QL | TK-05 |
| 4.4 | `POST /replenishment-requests`, `GET /replenishment-requests` | KHO (xem: QL, KHO) | TK-06 |

### Nhóm 3 – Bán hàng và thanh toán (vòng 5, 6, 7)

| Chức năng | Method, đường dẫn | Vai trò | Quy tắc | Vòng |
| --- | --- | --- | --- | --- |
| 3.1 | `POST /orders`, `GET /orders`, `GET /orders/{order_id}` | QL, BH (xem: thêm TN) | BH-01 | 5 |
| 3.1 | `PUT /orders/{order_id}/items` | QL, BH (đơn mình lập) | BH-03 | 5 |
| 3.1 | `POST /orders/{order_id}/confirm`, `…/reopen` | QL, BH (đơn mình lập) | BH-02, BH-03 | 5 |
| 3.4 | `POST /orders/{order_id}/cancel` | QL, BH (đơn mình lập) | BH-04 | 5 |
| 3.5 | `POST /shifts`, `GET /shifts/current`, `POST /shifts/{shift_id}/close` | TN | CA-01, CA-02 | 6 |
| 3.5 | `GET /shifts`, `GET /shifts/{shift_id}` (kèm kết quả đối soát) | QL, HQ, TN (ca của mình) | CA-03 | 6 |
| 3.5 | `POST /shifts/{shift_id}/proxy-close` | QL | CA-04 | 6 |
| 3.5 | `POST /shifts/{shift_id}/confirm` | QL; HQ khi duyệt thay | CA-03, CA-04, K-02 | 6 |
| 3.2 | `POST /orders/{order_id}/payments` (khởi tạo thu) | TN | TT-01, TT-02, TT-03 | 6 |
| 3.2, 3.4 | `POST /transactions/{txn_id}/confirm-cash` (đã nhận hoặc đã chi đủ tiền mặt) | TN | TT-02 | 6 |
| 3.2, 3.4 | `POST /transactions/{txn_id}/reconcile` (cập nhật kết quả tra soát) | TN | TT-02 | 6 |
| 3.2, 3.4 | `POST /bank/callback` | cổng thanh toán (mục 6) | TT-02 | 6 |
| 3.3 | `GET /orders/{order_id}/invoice`, `POST /invoices/{invoice_no}/print` | TN | TT-04 | 6 |
| 3.4 | `POST /returns`, `GET /returns`, `GET /returns/{return_id}` | QL, BH (xem: thêm TN, HQ) | TH-01, TH-02 | 7 |
| 3.4 | `POST /returns/{return_id}/approve`, `…/reject` | QL; HQ khi duyệt thay | TH-03, TH-05, K-02 | 7 |
| 3.4 | `POST /returns/{return_id}/refunds` (khởi tạo hoàn) | TN | TH-04 | 7 |
| 3.4 | `POST /transactions/{txn_id}/approve-cash-refund` | QL; HQ khi duyệt thay | TH-04 | 7 |

### Nhóm 5 – Báo cáo (vòng 8, 9)

Tham số chung: `from`, `to` (kỳ lọc) và `branch_id` (chỉ HQ được chọn; vai trò khác luôn là chi nhánh mình).
Mỗi báo cáo trả kèm phạm vi chi nhánh, kỳ lọc và thời điểm lập.

| Chức năng | Method, đường dẫn | Vai trò | Quy tắc | Vòng |
| --- | --- | --- | --- | --- |
| 5.4 | `GET /reports/low-stock` | QL, KHO | TK-05 | 8 |
| 5.1 | `GET /reports/revenue` | HQ, QL | DT-01 đến DT-05 | 9 |
| 5.2 | `GET /reports/products` | HQ, QL | DT-05 | 9 |
| 5.3 | `GET /reports/stock` | HQ, QL, KHO | TK-01, TK-05 | 9 |
| 5.5 | `GET /reports/staff-sales` | HQ, QL, BH (của mình) | DT-05 | 9 |

## 5. Hàm giao giữa các module

Mỗi kho chỉ do nhóm sở hữu ghi (đặc tả 6.1). Module khác muốn làm thay đổi kho đó thì gọi hàm dưới đây, truyền
`conn` đang nằm trong transaction của mình; hàm được gọi không tự mở transaction ngoài cùng và không commit.
Đây là các luồng 3.0 ↔ 4.0 trong đặc tả 6.2. `lines` là danh sách `(product_id, quantity)`; `at` là `clock.now()`.

| Hàm | Chủ | Ai gọi | Việc làm |
| --- | --- | --- | --- |
| `inventory.check_available(conn, branch_id, lines)` | vòng 4 | 3.1 khi chốt đơn | Trả các dòng thiếu kèm tồn khả dụng (4.1, TK-01). Không giữ hàng |
| `inventory.hold_for_order(conn, order_id, branch_id, lines, at)` | vòng 4 | 3.2 trước khi tạo giao dịch thu | Tạo phiếu `OUT_SALE` `PENDING`; thiếu tồn khả dụng thì ném `INSUFFICIENT_STOCK` (TK-03, TT-03) |
| `inventory.confirm_sale(conn, order_id, at)` | vòng 4 | 3.2 khi thu Thành công | Phiếu `OUT_SALE` sang `POSTED`, trừ tồn |
| `inventory.release_hold(conn, order_id, at)` | vòng 4 | 3.2 khi thu Thất bại | Phiếu `OUT_SALE` sang `CANCELLED` |
| `inventory.receive_return(conn, return_id, branch_id, lines, at)` | vòng 4 | 3.4 khi phiếu trả Đã duyệt | Tạo phiếu `IN_RETURN` `POSTED` cho số lượng tốt, đúng một lần mỗi phiếu trả (TH-05) |
| `orders.mark_completed(conn, order_id, at)` | vòng 5 | 3.2 khi thu Thành công | Đơn `AWAITING_PAYMENT` sang `COMPLETED`, ghi `completed_at` |
| `payments.has_pending_txn(conn, order_id)` | vòng 6 | 3.1 mở lại, 3.4 hủy đơn | Đơn có giao dịch `PENDING` hay không (BH-03, BH-04, BH-05) |

Vòng nào cần một hàm mà chủ của nó chưa viết (ví dụ vòng 5 cần `payments.has_pending_txn`) thì vòng đó tạo hàm
với đúng chữ ký trên, đặt đúng file của chủ, kèm test.

## 6. Cổng thanh toán giả lập (vòng 6, khung)

Ngân hàng/Cổng thanh toán là tác nhân bên ngoài (G-04). Vòng 6 thêm container `bank-mock` để chạy được KT-04, KT-05.

- api gọi cổng: `POST {BANK_URL}/requests` với `txn_id`, `type`, `method`, `amount`. Chỉ gọi SAU khi transaction
  CSDL đã commit; không gọi HTTP bên trong transaction. Gọi lỗi hoặc không phản hồi thì giao dịch vẫn `PENDING`
  (mất phản hồi không tự coi là thất bại, TT-02).
- cổng gọi lại api: `POST /bank/callback`, header `X-Bank-Key`, thân có `txn_id`, `result` (`SUCCESS` hoặc
  `FAILED`), `reference_code`. Phản hồi lặp cho giao dịch đã có kết quả: trả `200`, không đổi gì.
- `bank-mock` có bốn chế độ phản hồi: thành công, thất bại, im lặng, phản hồi lặp.

Chi tiết trường và biến môi trường chốt ở `/plan-task` vòng 6.
