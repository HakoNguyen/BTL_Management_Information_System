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

Trường (chốt ở vòng 1). `?` là trường không bắt buộc; ở `PATCH`, trường không gửi thì giữ nguyên.

| Model | Trường |
| --- | --- |
| `Branch` (response) | `branch_id`, `name`, `address` (null được), `phone` (null được), `closing_time` (`HH:MM:SS`, giờ Việt Nam), `status` (`BranchStatus`) |
| `BranchCreate` | `branch_id`, `name`, `address?`, `phone?`, `closing_time` |
| `BranchUpdate` | `name?`, `address?`, `phone?`, `closing_time?`; `name`, `closing_time` không nhận null |
| `Employee` (response) | `employee_id`, `full_name`, `phone`, `role`, `branch_id` (null với HQ), `hired_on` (ngày), `status` (`EmployeeStatus`), `username` (null nếu chưa cấp), `account_status` (`AccountStatus`, null nếu chưa cấp). Không bao giờ trả mật khẩu |
| `EmployeeCreate` | `employee_id`, `full_name`, `phone?`, `hired_on`, `role`, `branch_id?` (vai trò bắt buộc vì mỗi nhân viên có đúng một vai trò, NV-01) |
| `EmployeeUpdate` | `full_name?`, `phone?`, `hired_on?`; vai trò, chi nhánh đổi qua 6.2 |
| `AssignmentRequest` | `role`, `branch_id` (null với HQ) |
| `AccountCreate` | `username` (bỏ khoảng trắng hai đầu) |
| `AccountIssued` (response) | `employee_id`, `username`, `temporary_password` (chỉ trả một lần), `account_status` |

| Endpoint | Request → response | Lỗi nghiệp vụ |
| --- | --- | --- |
| `GET /branches` | → `Branch[]` (cả chi nhánh Ngừng hoạt động) | |
| `POST /branches` | `BranchCreate` → `201 Branch` | `DUPLICATE` NV-04 |
| `PATCH /branches/{branch_id}` | `BranchUpdate` → `Branch` | `NOT_FOUND` |
| `POST /branches/{branch_id}/deactivate` | → `Branch` | `NOT_FOUND`; `INVALID_STATE` (đã ngừng); `RULE_VIOLATION` NV-04, thông báo liệt kê mọi điều kiện chưa đạt |
| `GET /employees` | → `Employee[]` | |
| `POST /employees` | `EmployeeCreate` → `201 Employee` | `DUPLICATE` NV-01; `RULE_VIOLATION` NV-01 (vai trò và chi nhánh không khớp); `NOT_FOUND` (chi nhánh); `RULE_VIOLATION` NV-04 (chi nhánh Ngừng hoạt động) |
| `PATCH /employees/{employee_id}` | `EmployeeUpdate` → `Employee` | `NOT_FOUND` |
| `POST /employees/{employee_id}/leave` | → `Employee` | `NOT_FOUND`; `INVALID_STATE` (đã nghỉ); `RULE_VIOLATION` NV-03 (tài khoản chưa khóa, còn ca chưa chốt) |
| `PUT /employees/{employee_id}/assignment` | `AssignmentRequest` → `Employee` | `NOT_FOUND`; `INVALID_STATE` (đã nghỉ); `RULE_VIOLATION` NV-01, NV-02 (thông báo liệt kê chứng từ đang chặn), NV-04 (chi nhánh Ngừng hoạt động) |
| `POST /employees/{employee_id}/account` | `AccountCreate` → `201 AccountIssued` | `NOT_FOUND`; `INVALID_STATE` NV-03 (đã nghỉ, đã có tài khoản); `DUPLICATE` NV-03 (tên đăng nhập đã dùng, kể cả của người đã nghỉ) |
| `POST /employees/{employee_id}/account/lock`, `…/unlock` | → `Employee` | `NOT_FOUND`; `INVALID_STATE` (chưa cấp, hoặc đã ở trạng thái đích) |

Quyết định của người dùng ở vòng 1 (đặc tả để trống): không tạo, không phân công vào chi nhánh Ngừng hoạt động;
không phân công, không cấp tài khoản cho nhân viên Đã nghỉ; nhân viên chưa từng có tài khoản được chuyển Đã nghỉ;
"phiếu chờ xử lý" của NV-04 gồm phiếu kho `PENDING` của chi nhánh và phiếu trả `PENDING` của đơn thuộc chi nhánh.

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

Trường (chốt ở vòng 2). `?` là trường không bắt buộc; ở `PATCH`, trường không gửi thì giữ nguyên.

| Model | Trường |
| --- | --- |
| `ProductGroup` (response) | `group_id`, `name`, `description` (null được) |
| `ProductGroupCreate` | `group_id`, `name`, `description?` |
| `ProductGroupUpdate` | `name?`, `description?`; `name` không nhận null |
| `Product` (response) | `product_id`, `name`, `group_id`, `unit`, `current_price`, `description` (null được), `status` (`ProductStatus`) |
| `ProductCreate` | `product_id`, `name`, `group_id`, `unit`, `description?`, `price` (giá ban đầu) |
| `ProductUpdate` | `name?`, `description?`, `unit?`; `name`, `unit` không nhận null. Mã không đổi (SP-01); nhóm, giá, trạng thái đổi qua endpoint riêng |
| `ProductGroupChange` | `group_id` |
| `PriceChange` | `price` |
| `PriceHistoryEntry` (response) | `effective_at`, `price`, `changed_by` |
| `ProductStatusChange` | `status` (`ProductStatus`) |

| Endpoint | Request → response | Lỗi nghiệp vụ |
| --- | --- | --- |
| `GET /product-groups` | → `ProductGroup[]` | |
| `POST /product-groups` | `ProductGroupCreate` → `201 ProductGroup` | `DUPLICATE` SP-01 |
| `PATCH /product-groups/{group_id}` | `ProductGroupUpdate` → `ProductGroup` | `NOT_FOUND` |
| `DELETE /product-groups/{group_id}` | → `ProductGroup` (nhóm vừa xóa) | `NOT_FOUND`; `RULE_VIOLATION` SP-01 (còn sản phẩm, kể cả Ngừng bán) |
| `PUT /products/{product_id}/group` | `ProductGroupChange` → `Product` | `NOT_FOUND` (sản phẩm, nhóm) |
| `GET /products` | → `Product[]` (cả Ngừng bán) | |
| `GET /products/{product_id}` | → `Product` | `NOT_FOUND` |
| `POST /products` | `ProductCreate` → `201 Product`; ghi bản ghi lịch sử giá đầu tiên trong cùng transaction | `DUPLICATE` SP-01; `NOT_FOUND` (nhóm); `RULE_VIOLATION` SP-02 (giá ≤ 0) |
| `PATCH /products/{product_id}` | `ProductUpdate` → `Product` | `NOT_FOUND`; `RULE_VIOLATION` SP-04 (đổi đơn vị tính khi sản phẩm đã có trên đơn hoặc phiếu kho) |
| `PUT /products/{product_id}/price` | `PriceChange` → `Product`; ghi lịch sử giá (người đổi = người gọi) | `NOT_FOUND`; `RULE_VIOLATION` SP-02 (giá ≤ 0 hoặc bằng giá hiện hành) |
| `GET /products/{product_id}/price-history` | → `PriceHistoryEntry[]`, theo `effective_at` tăng dần | `NOT_FOUND` |
| `PUT /products/{product_id}/status` | `ProductStatusChange` → `Product` | `NOT_FOUND`; `INVALID_STATE` (đã ở trạng thái đích) |

Sản phẩm mới không có dòng `stock` nào, tức tồn 0 tại mọi chi nhánh (SP-04); nhóm 1 không ghi D5.

### Nhóm 2 – Khách hàng (vòng 3; 2.4 ở vòng 7)

| Chức năng | Method, đường dẫn | Vai trò | Quy tắc |
| --- | --- | --- | --- |
| 2.1 | `POST /customers` | BH | KH-01 |
| 2.2 | `PATCH /customers/{customer_id}` | BH | KH-01, KH-03 |
| 2.3 | `GET /customers` (lọc theo `phone` hoặc `customer_id`) | BH | KH-02 |
| 2.4 | `GET /customers/{customer_id}/history` (kèm `phone` để xác minh) | BH | KH-04 |

Trường (chốt ở vòng 3). `?` là trường không bắt buộc; ở `PATCH`, trường không gửi thì giữ nguyên.

| Model | Trường |
| --- | --- |
| `Customer` (response) | `customer_id`, `full_name`, `phone`, `address` (null được), `registered_on` (ngày) |
| `CustomerCreate` | `full_name`, `phone`, `address?` |
| `CustomerUpdate` | `full_name?`, `phone?`, `address?`; `full_name`, `phone` không nhận null. Mã khách không đổi (KH-03) |

Chuẩn hóa số điện thoại (2.1, áp dụng cả khi cập nhật và tra cứu): bỏ khoảng trắng, `.`, `-`, `(`, `)`; đầu `+84`
đổi thành `0`; kết quả phải là `0` theo sau 9 hoặc 10 chữ số, sai thì `VALIDATION_ERROR` `rule` = KH-01. Số lưu
và trả về là số đã chuẩn hóa.

| Endpoint | Request → response | Lỗi nghiệp vụ |
| --- | --- | --- |
| `POST /customers` | `CustomerCreate` → `201 Customer` (tạo mới, `registered_on` = ngày hiện tại); số đã có hồ sơ thì `200 Customer` là hồ sơ có sẵn, không đổi gì | `VALIDATION_ERROR` KH-01 |
| `PATCH /customers/{customer_id}` | `CustomerUpdate` → `Customer` | `NOT_FOUND`; `RULE_VIOLATION` KH-02 (KHLE); `DUPLICATE` KH-01 (số thuộc hồ sơ khác); `VALIDATION_ERROR` KH-01 |
| `GET /customers?phone=…` hoặc `?customer_id=…` | → `Customer[]` (0 hoặc 1 phần tử; rỗng = "Không tìm thấy") | `VALIDATION_ERROR` (không gửi hoặc gửi cả hai tham số); `RULE_VIOLATION` KH-02 (tra KHLE); `VALIDATION_ERROR` KH-01 |

Không có endpoint xóa khách (KH-03). Khách dùng chung toàn chuỗi (G-06) nên không so chi nhánh.

Trường 2.4 (chốt ở vòng 7). Lịch sử lấy ở mọi chi nhánh vì khách dùng chung toàn chuỗi.

| Model | Trường |
| --- | --- |
| `CustomerHistory` (response) | `customer` (`Customer`), `orders` (`Order[]`: các đơn từng Hoàn tất – `COMPLETED`, `PARTIALLY_RETURNED`, `FULLY_RETURNED` – mới nhất trước theo `completed_at`), `returns` (`ReturnSlip[]` của các đơn đó, mọi trạng thái, mới nhất trước theo `created_at`) |

| Endpoint | Request → response | Lỗi nghiệp vụ |
| --- | --- | --- |
| `GET /customers/{customer_id}/history?phone=…` | → `CustomerHistory` | `NOT_FOUND`; `RULE_VIOLATION` KH-02 (KHLE); `VALIDATION_ERROR` KH-01 (số sai định dạng); `RULE_VIOLATION` KH-04 (số đã chuẩn hóa không khớp hồ sơ) |

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

Trường (chốt ở vòng 4). `?` là trường không bắt buộc. Chi nhánh luôn là chi nhánh của người gọi; phiếu của chi nhánh
khác trả `FORBIDDEN` `rule` = K-01.

| Model | Trường |
| --- | --- |
| `StockLevel` (response) | `product_id`, `quantity`, `available` (tồn khả dụng, TK-01), `min_level` (null = Chưa thiết lập) |
| `StockSlipItem` | `product_id`, `quantity` (> 0) |
| `StockSlip` (response) | `slip_id`, `branch_id`, `type` (`SlipType`), `status` (`SlipStatus`), `created_at`, `created_by`, `reason`, `counterparty`, `delivery_no`, `order_id`, `return_id`, `adjusts_slip_id`, `approved_by` (người quyết định duyệt hoặc từ chối), `decision_reason`, `finalized_at` (các trường sau `created_at` null được), `items` (`StockSlipItem[]`) |
| `InboundSlipCreate` | `type` (`IN_WAREHOUSE` hoặc `IN_SUPPLIER`), `counterparty`, `delivery_no`, `items` (≥ 1 dòng, mỗi sản phẩm một dòng) |
| `StockSlipCreate` | `type` (`ADJUST_UP`, `OUT_DISPOSAL`, `OUT_TO_WAREHOUSE` hoặc `ADJUST_DOWN`), `reason`, `adjusts_slip_id?` (chỉ phiếu điều chỉnh), `items` (như trên) |
| `StockSlipReject` | `reason` (bắt buộc, K-03) |
| `MinLevelChange` | `min_level` (số nguyên ≥ 0 hoặc null = Chưa thiết lập) |

| Endpoint | Request → response | Lỗi nghiệp vụ |
| --- | --- | --- |
| `GET /stock` | → `StockLevel[]`: mọi sản phẩm, cặp chưa có bản ghi là tồn 0, chưa đặt ngưỡng (TK-01) | |
| `POST /stock-slips/inbound` | `InboundSlipCreate` → `201 StockSlip` `POSTED`, tồn tăng ngay | `RULE_VIOLATION` TK-02 (chi nhánh Ngừng hoạt động); `DUPLICATE` TK-02 (bộ bên giao, số phiếu giao đã ghi ở chi nhánh); `NOT_FOUND` (sản phẩm); `VALIDATION_ERROR` (trùng sản phẩm) |
| `POST /stock-slips` | `StockSlipCreate` → `201 StockSlip` `PENDING`; phiếu xuất giữ hàng | `INSUFFICIENT_STOCK` TK-03 (phiếu xuất vượt tồn khả dụng; `details.lines` gồm `product_id`, `quantity`, `available`); `NOT_FOUND` (sản phẩm, phiếu bị điều chỉnh không thuộc chi nhánh); `VALIDATION_ERROR` TK-04 (`adjusts_slip_id` trên phiếu không phải điều chỉnh) |
| `GET /stock-slips?status=…` | → `StockSlip[]` của chi nhánh, mới nhất trước; `status?` lọc theo `SlipStatus` | |
| `GET /stock-slips/{slip_id}` | → `StockSlip` | `NOT_FOUND`; `FORBIDDEN` K-01 |
| `POST /stock-slips/{slip_id}/approve` | → `StockSlip` `POSTED`; tồn tăng (điều chỉnh tăng) hoặc giảm (phiếu xuất) | `NOT_FOUND`; `FORBIDDEN` K-01; `INVALID_STATE` (không ở `PENDING`, hoặc là phiếu nhập, xuất bán: không qua QL duyệt); `FORBIDDEN` K-02 (người duyệt là người lập) |
| `POST /stock-slips/{slip_id}/reject` | `StockSlipReject` → `StockSlip` `CANCELLED`, nhả hàng giữ | như `approve` |
| `PUT /stock/{product_id}/min-level` | `MinLevelChange` → `StockLevel`; không đổi tồn | `NOT_FOUND`; `VALIDATION_ERROR` TK-05 (âm) |

Trường 4.4 (chốt ở vòng 8). Yêu cầu lưu như đã gửi, không đổi tồn, không có trạng thái giao nhận (TK-06); tồn và
ngưỡng hiện tại giao diện lấy từ `GET /stock`.

| Model | Trường |
| --- | --- |
| `ReplenishmentCreate` | `type` (`ReplenishType`), `recipient` (nơi nhận: kho tổng hoặc tên NCC, không rỗng), `items` (`StockSlipItem[]`, ≥ 1 dòng, mỗi sản phẩm một dòng) |
| `ReplenishmentRequest` (response) | `request_id`, `branch_id`, `created_by`, `created_at`, `type`, `recipient`, `items` (`StockSlipItem[]`) |

| Endpoint | Request → response | Lỗi nghiệp vụ |
| --- | --- | --- |
| `POST /replenishment-requests` | `ReplenishmentCreate` → `201 ReplenishmentRequest` | `NOT_FOUND` (sản phẩm); `RULE_VIOLATION` TK-06 (sản phẩm Ngừng bán); `VALIDATION_ERROR` (số lượng ≤ 0, trùng sản phẩm, không có dòng) |
| `GET /replenishment-requests` | → `ReplenishmentRequest[]` của chi nhánh, mới nhất trước | |

Phiếu kho không có duyệt thay (TK-03): HQ không gọi được `approve`, `reject`. Hàm giao ở mục 5 dùng chung cách khóa:
`SELECT … FOR UPDATE` các dòng `stock` theo `product_id` tăng dần rồi mới tính tồn khả dụng. `check_available` trả
danh sách dòng thiếu dạng `{product_id, quantity, available}`; `hold_for_order`, `receive_return` trả `slip_id`
(`receive_return` không có dòng nào thì không tạo phiếu, trả `None`; gọi lần hai cho cùng phiếu trả: `DUPLICATE` TH-05);
`hold_for_order` khi đơn đã có phiếu xuất bán chưa hủy ném `INVALID_STATE` TK-03;
`confirm_sale`, `release_hold` không tìm thấy phiếu xuất bán `PENDING` của đơn thì ném `INVALID_STATE`.

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

Trường đơn hàng (chốt ở vòng 5). Đơn luôn thuộc chi nhánh của người lập (BH-01); đơn của chi nhánh khác trả
`FORBIDDEN` `rule` = K-01. "Đơn mình lập": NVBH chỉ thao tác đơn do mình lập, QL thao tác mọi đơn của chi nhánh;
NVBH thao tác đơn người khác lập trả `FORBIDDEN` với `rule` của endpoint (BH-03, hủy là BH-04).

| Model | Trường |
| --- | --- |
| `OrderItemInput` | `product_id`, `quantity` (> 0) |
| `OrderItem` (response) | `product_id`, `quantity`, `unit_price` (đơn giá chốt; null khi đơn Đang lập) |
| `Order` (response) | `order_id`, `branch_id`, `customer_id`, `created_by`, `created_at`, `status` (`OrderStatus`), `confirmed_at`, `completed_at`, `cancelled_at`, `cancelled_by` (null = Hệ thống), `cancel_reason` (các trường sau `status` null được), `total` (Σ số lượng × đơn giá chốt, dẫn xuất; null khi Đang lập), `items` (`OrderItem[]`) |
| `OrderCreate` | `customer_id` (KHLE cho khách lẻ), `items` (≥ 1 dòng, mỗi sản phẩm một dòng) |
| `OrderItemsChange` | `items` (như trên; thay toàn bộ dòng của đơn) |
| `OrderCancel` | `reason` (bắt buộc, K-03) |

| Endpoint | Request → response | Lỗi nghiệp vụ |
| --- | --- | --- |
| `POST /orders` | `OrderCreate` → `201 Order` `DRAFT` | `NOT_FOUND` (khách, sản phẩm); `VALIDATION_ERROR` BH-01 (trùng sản phẩm) |
| `GET /orders?status=…` | → `Order[]` của chi nhánh, mới nhất trước; `status?` lọc theo `OrderStatus` | |
| `GET /orders/{order_id}` | → `Order` | `NOT_FOUND`; `FORBIDDEN` K-01 |
| `PUT /orders/{order_id}/items` | `OrderItemsChange` → `Order` | như `POST /orders`; `FORBIDDEN` K-01, BH-03; `INVALID_STATE` BH-03 (không ở `DRAFT`) |
| `POST /orders/{order_id}/confirm` | → `Order` `AWAITING_PAYMENT`, chép giá hiện hành vào `unit_price`, ghi `confirmed_at`; không giữ hàng | `FORBIDDEN` K-01, BH-03; `INVALID_STATE` BH-02 (không ở `DRAFT`); `RULE_VIOLATION` BH-02 (chi nhánh Ngừng hoạt động; sản phẩm Ngừng bán, `details.product_ids`); `INSUFFICIENT_STOCK` BH-02 (`details.lines` như TK-03). Lỗi thì đơn vẫn `DRAFT` |
| `POST /orders/{order_id}/reopen` | → `Order` `DRAFT`, xóa `unit_price`, `confirmed_at` | `FORBIDDEN` K-01, BH-03; `INVALID_STATE` BH-03 (không ở `AWAITING_PAYMENT`, hoặc có giao dịch `PENDING`) |
| `POST /orders/{order_id}/cancel` | `OrderCancel` → `Order` `CANCELLED`, ghi người hủy, thời điểm, lý do; không đổi tồn | `FORBIDDEN` K-01, BH-04; `INVALID_STATE` BH-04 (không ở `DRAFT`/`AWAITING_PAYMENT`, hoặc có giao dịch `PENDING`) |

`orders.mark_completed` không tìm thấy đơn `AWAITING_PAYMENT` thì ném `INVALID_STATE`.

Trường ca, giao dịch, hóa đơn (chốt ở vòng 6). Ca chỉ do thu ngân của ca đóng; ca, giao dịch, hóa đơn của chi nhánh
khác trả `FORBIDDEN` `rule` = K-01.

| Model | Trường |
| --- | --- |
| `ShiftOpen` | `opening_cash` (≥ 0, CA-01) |
| `ShiftClose` | `counted_cash` (≥ 0), `variance_reason` (bắt buộc khi chênh lệch khác 0, CA-02) |
| `ShiftProxyClose` | `counted_cash`, `variance_reason` như `ShiftClose`; `witness_id`, `proxy_reason` (bắt buộc, CA-04) |
| `Shift` (response) | `shift_id`, `branch_id`, `cashier_id`, `status` (`ShiftStatus`), `opened_at`, `closed_at`, `settled_at`, `opening_cash`, `counted_cash`, `variance_reason`, `proxy_closed_by`, `witness_id`, `proxy_reason`, `confirmed_by`; dẫn xuất (CA-02): `expected_cash`, `variance` (null khi chưa kiểm đếm) |
| `ShiftMethodTotal` | `type` (`TxnType`), `method` (`TxnMethod`), `count`, `amount` |
| `ShiftDetail` (response) | các trường của `Shift`; kết quả đối soát (CA-03): `cash_collected`, `cash_refunded` (Σ thu, hoàn tiền mặt Thành công), `electronic` (`ShiftMethodTotal[]`, giao dịch điện tử Thành công theo loại và phương thức), `failed`, `pending` (`Transaction[]`) |
| `Transaction` (response) | `txn_id`, `order_id`, `return_id`, `shift_id`, `type`, `method`, `amount`, `status` (`TxnStatus`), `created_at`, `resolved_at`, `reference_code`, `cash_refund_approved_by`, `cash_refund_reason` |
| `PaymentCreate` | `method` (`TxnMethod`) |
| `CashConfirm` | `result` (`SUCCESS` = đã nhận đủ; `FAILED` = khách không đưa tiền) |
| `Reconcile` | `result` (`SUCCESS`/`FAILED`), `reference_code` (bắt buộc khi `SUCCESS`, TT-02) |
| `BankCallback` | `txn_id`, `result` (`SUCCESS`/`FAILED`), `reference_code` (bắt buộc khi `SUCCESS`) |
| `InvoiceLine` | `product_id`, `name`, `quantity`, `unit_price`, `amount` (= số lượng × đơn giá chốt) |
| `Invoice` (response) | `invoice_no`, `order_id`, `branch_id`, `issued_at`, `print_count`, `method` (phương thức của giao dịch thu Thành công), `total`, `items` (`InvoiceLine[]`) |

| Endpoint | Request → response | Lỗi nghiệp vụ |
| --- | --- | --- |
| `POST /shifts` | `ShiftOpen` → `201 ShiftDetail` `OPEN` tại chi nhánh của thu ngân | `VALIDATION_ERROR` CA-01 (tiền âm); `RULE_VIOLATION` CA-01 (chi nhánh Ngừng hoạt động); `INVALID_STATE` CA-01 (đã có ca `OPEN`) |
| `GET /shifts/current` | → `ShiftDetail` ca `OPEN` của thu ngân, hoặc `null` | |
| `POST /shifts/{shift_id}/close` | `ShiftClose` → `ShiftDetail` `AWAITING_CONFIRMATION`, ghi `closed_at` | `FORBIDDEN` K-01 (ca của người khác); `INVALID_STATE` CA-02 (không ở `OPEN`); `VALIDATION_ERROR` CA-02 (tiền âm); `RULE_VIOLATION` CA-02 (còn giao dịch tiền mặt `PENDING`; chênh lệch khác 0 mà thiếu lý do) |
| `GET /shifts?status=…` | → `Shift[]` mới nhất trước: HQ mọi chi nhánh, QL chi nhánh mình, TN ca của mình | |
| `GET /shifts/{shift_id}` | → `ShiftDetail` | `NOT_FOUND`; `FORBIDDEN` K-01 |
| `POST /shifts/{shift_id}/proxy-close` | `ShiftProxyClose` → `ShiftDetail` `AWAITING_CONFIRMATION`, ghi `proxy_closed_by`, `witness_id`, `proxy_reason` | như `close` (trừ ca của người khác); `RULE_VIOLATION` CA-04 (người làm chứng không phải nhân viên Đang làm cùng chi nhánh, hoặc trùng QL đóng thay, trùng thu ngân của ca) |
| `POST /shifts/{shift_id}/confirm` | → `ShiftDetail` `SETTLED`, ghi `settled_at`, `confirmed_by`. Ca thu ngân tự đóng: QL chi nhánh xác nhận. Ca QL đóng thay: chỉ HQ xác nhận (CA-04) | `INVALID_STATE` CA-03 (không ở `AWAITING_CONFIRMATION`); `RULE_VIOLATION` CA-03 (còn giao dịch `PENDING`); `FORBIDDEN` CA-04 (QL xác nhận ca đóng thay), K-02 (HQ xác nhận ca thu ngân tự đóng) |
| `POST /orders/{order_id}/payments` | `PaymentCreate` → `201 Transaction` `COLLECT` `PENDING`, số tiền = tổng đơn, gắn ca `OPEN` của thu ngân; giữ hàng trước (TT-03); điện tử thì gọi cổng sau khi commit | `NOT_FOUND`; `FORBIDDEN` K-01; `INVALID_STATE` TT-01 (đơn không ở `AWAITING_PAYMENT`), TT-02 (đơn đang có giao dịch `PENDING`); `RULE_VIOLATION` TT-01 (thu ngân không có ca `OPEN` tại chi nhánh của đơn); `INSUFFICIENT_STOCK` TK-03 (không tạo giao dịch) |
| `POST /transactions/{txn_id}/confirm-cash` | `CashConfirm` → `Transaction` | `NOT_FOUND`; `FORBIDDEN` K-01; `RULE_VIOLATION` TT-02 (không phải tiền mặt); `INVALID_STATE` TT-02 (đã có kết quả) |
| `POST /transactions/{txn_id}/reconcile` | `Reconcile` → `Transaction` | như `confirm-cash` nhưng `RULE_VIOLATION` TT-02 khi là tiền mặt; `VALIDATION_ERROR` TT-02 (thiếu mã tham chiếu); `DUPLICATE` TT-02 (mã tham chiếu đã gắn giao dịch khác) |
| `POST /bank/callback` | header `X-Bank-Key`; `BankCallback` → `Transaction`. Giao dịch đã có kết quả: trả nguyên trạng, không đổi gì | `UNAUTHORIZED` (sai khóa); `NOT_FOUND`; `VALIDATION_ERROR`, `DUPLICATE` TT-02 như `reconcile` |
| `GET /orders/{order_id}/invoice` | → `Invoice` | `NOT_FOUND` (đơn chưa có hóa đơn); `FORBIDDEN` K-01 |
| `POST /invoices/{invoice_no}/print` | → `Invoice` cùng số, `print_count` + 1 (TT-04) | `NOT_FOUND`; `FORBIDDEN` K-01 |

Giao dịch thu có kết quả (qua `confirm-cash`, `reconcile` hoặc `bank/callback`) xử lý trong **một** transaction:
`SUCCESS` → `inventory.confirm_sale`, `orders.mark_completed`, phát hành hóa đơn `print_count` = 0; `FAILED` →
`inventory.release_hold`, đơn vẫn `AWAITING_PAYMENT`.

Trường phiếu trả, hoàn tiền (chốt ở vòng 7). Phiếu trả thuộc chi nhánh của đơn gốc; QL, NVBH, TN thao tác phiếu của
chi nhánh khác trả `FORBIDDEN` `rule` = K-01; HQ xem và quyết định được mọi chi nhánh. Duyệt thay (K-02, quyết định
15 ở [plan.md](plan.md) mục 7): HQ duyệt, từ chối phiếu trả và duyệt hoàn tiền mặt bất cứ lúc nào, luôn kèm lý do.

| Model | Trường |
| --- | --- |
| `ReturnItemInput` | `product_id`, `good_qty`, `defective_qty` (nguyên ≥ 0, tổng > 0, TH-02) |
| `ReturnCreate` | `order_id`, `reason` (bắt buộc, TH-02), `items` (≥ 1 dòng, mỗi sản phẩm một dòng) |
| `ReturnItem` (response) | `product_id`, `good_qty`, `defective_qty`, `unit_price` (đơn giá chốt trên đơn gốc), `amount` (= (tốt + lỗi) × đơn giá chốt) |
| `ReturnSlip` (response) | `return_id`, `order_id`, `branch_id` (của đơn gốc), `created_by`, `created_at`, `reason`, `status` (`ReturnStatus`), `decided_by` (null = Hệ thống tự từ chối), `decided_at`, `decision_note`; dẫn xuất: `value` (giá trị phiếu, TH-04), `refund_status` (`RefundStatus`; null khi phiếu chưa `APPROVED`), `items` (`ReturnItem[]`) |
| `RefundStatus` (enum, dẫn xuất, [db.md](db.md) mục 6) | `NOT_REFUNDED` = Chưa hoàn; `PENDING` = Đang chờ kết quả; `REFUNDED` = Đã hoàn |
| `ReturnDecision` | `decision_note?`: QL duyệt thì không bắt buộc; HQ duyệt bắt buộc (K-02); từ chối bắt buộc (K-03) |
| `CashRefundApproval` | `reason` (bắt buộc, TH-04) |

| Endpoint | Request → response | Lỗi nghiệp vụ |
| --- | --- | --- |
| `POST /returns` | `ReturnCreate` → `201 ReturnSlip` `PENDING`; hàng vẫn do khách giữ | `NOT_FOUND` (đơn); `FORBIDDEN` K-01; `INVALID_STATE` TH-01 (đơn không ở `COMPLETED`/`PARTIALLY_RETURNED`); `RULE_VIOLATION` TH-01 (chi nhánh Ngừng hoạt động; quá `completed_at` + 7 ngày); `VALIDATION_ERROR` TH-02 (trùng sản phẩm; dòng có tổng = 0); `RULE_VIOLATION` TH-02 (sản phẩm không có trong đơn, `details.product_ids`; vượt lượng còn được trả, `details.lines` gồm `product_id`, `requested`, `remaining`) |
| `GET /returns?status=…&refund_status=…` | → `ReturnSlip[]` mới nhất trước: HQ mọi chi nhánh, vai trò khác chi nhánh mình. Phiếu Đã duyệt chưa hoàn xong (TH-05): `status=APPROVED` và `refund_status=NOT_REFUNDED` | |
| `GET /returns/{return_id}` | → `ReturnSlip` | `NOT_FOUND`; `FORBIDDEN` K-01 |
| `POST /returns/{return_id}/approve` | `ReturnDecision` → `ReturnSlip` `APPROVED`, ghi `decided_by`, `decided_at`, `decision_note`. Cùng transaction: kiểm tra lại TH-02, `inventory.receive_return` cho số lượng tốt (không có hàng tốt thì không lập phiếu kho), `orders.mark_returned` (TH-05) | `NOT_FOUND`; `FORBIDDEN` K-01, K-02 (người duyệt là người lập); `VALIDATION_ERROR` K-02 (HQ thiếu lý do); `INVALID_STATE` TH-03 (không ở `PENDING`); `RULE_VIOLATION` TH-02 |
| `POST /returns/{return_id}/reject` | `ReturnDecision` → `ReturnSlip` `REJECTED`; không đổi tồn, đơn, tiền | như `approve` (trừ TH-02); `VALIDATION_ERROR` K-03 (thiếu lý do) |
| `POST /returns/{return_id}/refunds` | → `201 Transaction` `REFUND` `PENDING`, số tiền = giá trị phiếu, gắn ca `OPEN` của thu ngân. Phương thức: `CASH` nếu một giao dịch hoàn Thất bại của phiếu đã được duyệt hoàn tiền mặt (chép `cash_refund_approved_by`, `cash_refund_reason` sang giao dịch mới); ngược lại bằng phương thức của giao dịch thu Thành công. Điện tử thì gọi cổng sau khi commit. Kết quả cập nhật qua `confirm-cash`, `reconcile`, `bank/callback` như giao dịch thu, nhưng không đổi tồn, đơn | `NOT_FOUND`; `FORBIDDEN` K-01; `INVALID_STATE` TH-04 (phiếu không ở `APPROVED`, hoặc đã có giao dịch hoàn Thành công), TT-02 (đơn đang có giao dịch `PENDING`); `RULE_VIOLATION` TH-04 (thu ngân không có ca `OPEN` tại chi nhánh của phiếu) |
| `POST /transactions/{txn_id}/approve-cash-refund` | `CashRefundApproval` → `Transaction` (giao dịch hoàn điện tử `FAILED` được ghi `cash_refund_approved_by`, `cash_refund_reason`; trạng thái, số tiền không đổi) | `NOT_FOUND`; `FORBIDDEN` K-01; `RULE_VIOLATION` TH-04 (không phải giao dịch hoàn điện tử `FAILED`); `INVALID_STATE` TH-04 (đã được duyệt, hoặc phiếu đã hoàn xong) |

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

Trường 5.4 (chốt ở vòng 8). Ảnh chụp tình trạng hiện tại nên không có `from`, `to`; luôn là chi nhánh của người gọi;
tính lúc gọi, không lưu (quyết định 6 ở [plan.md](plan.md) mục 7). Chỉ xét sản phẩm Đang bán; "dưới ngưỡng" là
`quantity` < `min_level` (TK-05), sắp theo `product_id`.

| Model | Trường |
| --- | --- |
| `LowStockLine` | `product_id`, `name`, `quantity` (tồn, cặp chưa có bản ghi là 0), `min_level` (null ở danh sách Chưa thiết lập) |
| `LowStockReport` (response của `GET /reports/low-stock`) | `branch_id`, `generated_at`, `below_min` (`LowStockLine[]`: đã đặt ngưỡng và tồn < ngưỡng), `not_set` (`LowStockLine[]`: Chưa thiết lập ngưỡng) |

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
| `orders.mark_returned(conn, order_id, fully)` | vòng 7 | 3.4 khi phiếu trả Đã duyệt | Đơn `COMPLETED`/`PARTIALLY_RETURNED` sang `FULLY_RETURNED` nếu `fully`, ngược lại `PARTIALLY_RETURNED`; giữ `completed_at` (TH-05) |

Sự kiện giờ đóng cửa (vòng 8): `api/workers/closing.py` có `run_closing(conn, at)`. Với mỗi chi nhánh, mốc đóng cửa
là lần `closing_time` (giờ Việt Nam) gần nhất ≤ `at`; chứng từ lập sau mốc đó chờ lần đóng cửa kế tiếp (quyết định 9).
Hàm gọi hai hàm của chủ kho D3, mỗi hàm một transaction, chạy lại nhiều lần không đổi kết quả:

| Hàm | Chủ | Việc làm |
| --- | --- | --- |
| `orders.cancel_overdue(conn, branch_id, closing_at, at)` | vòng 8 | Đơn `DRAFT`/`AWAITING_PAYMENT` lập ≤ `closing_at`, không có giao dịch `PENDING` (`payments.has_pending_txn`): sang `CANCELLED`, `cancelled_by` NULL (Hệ thống), `cancel_reason` = `OVERDUE_CANCEL_REASON` (BH-05). Trả mã đơn đã hủy |
| `returns.reject_overdue(conn, branch_id, closing_at, at)` | vòng 8 | Phiếu trả `PENDING` lập ≤ `closing_at` của đơn thuộc chi nhánh: sang `REJECTED`, `decided_by` NULL, `decision_note` = `OVERDUE_REJECT_REASON` (TH-03). Trả mã phiếu |

Vòng lặp nền khởi động trong `lifespan`, gọi `run_closing(conn, clock.now())` mỗi 60 giây.

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

Chốt ở vòng 6. Mã nguồn `infra/bank-mock/` (dùng lại fastapi, httpx, uvicorn), cổng 8001 trong mạng compose.

| Biến môi trường | Dùng ở | Nghĩa |
| --- | --- | --- |
| `BANK_URL` | api | Địa chỉ cổng, ví dụ `http://bank-mock:8001`. Để trống thì api không gọi cổng (giao dịch giữ `PENDING`) |
| `BANK_KEY` | api, bank-mock | Khóa bí mật gửi trong header `X-Bank-Key` của callback; để trống thì api từ chối mọi callback |
| `BANK_CALLBACK_URL` | bank-mock | Địa chỉ callback của api, ví dụ `http://api:8000/bank/callback` |
| `BANK_MOCK_MODE` | bank-mock | Chế độ ban đầu: `SUCCESS`, `FAILED`, `SILENT`, `DUPLICATE` (mặc định `SUCCESS`) |
| `BANK_PORT` | compose | Cổng bank-mock mở ra máy host để gọi `PUT /mode` (mặc định 8001) |

`bank-mock` có `POST /requests` (nhận yêu cầu từ api) và `PUT /mode` (thân `{"mode": …}`, đổi chế độ lúc demo).
Mã tham chiếu cổng sinh là `REF-<txn_id>`; chế độ `DUPLICATE` gửi cùng một callback `SUCCESS` hai lần.
