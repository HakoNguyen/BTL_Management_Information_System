# Kế hoạch triển khai

File này cho biết dự án đang ở đâu và việc tiếp theo là gì. Đọc mục 1 trước khi làm bất cứ việc gì.

## 1. Tiến độ

**Vòng tiếp theo: 1 (nhóm 6 – nhân viên và chi nhánh).** Mỗi lần chỉ làm một vòng, theo đúng thứ tự: vòng sau
dùng dữ liệu và hàm của vòng trước.

| Vòng | Module | Nhánh | Chức năng | Quy tắc | Tình huống KT | Trạng thái |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | khung | `base/project-skeleton` | Repo, tài liệu, 18 bảng, đăng nhập, phân quyền, Docker, CI | K-01 | — | **xong** (13/11/2026) |
| 1 | `staff` | `staff/employees-branches-accounts` | 6.1, 6.2, 6.3, 6.4 | NV-01 đến NV-04, K-05 | — | chưa làm |
| 2 | `products` | `products/catalog-pricing` | 1.1, 1.2, 1.3, 1.4 | SP-01 đến SP-04 | — | chưa làm |
| 3 | `customers` | `customers/profiles` | 2.1, 2.2, 2.3 | KH-01 đến KH-03 | — | chưa làm |
| 4 | `inventory` | `inventory/stock-slips` | 4.1, 4.2, 4.3, 4.5 và 5 hàm giao | TK-01 đến TK-05 | KT-12 | chưa làm |
| 5 | `orders` | `orders/create-confirm-cancel` | 3.1; 3.4 phần hủy đơn | BH-01 đến BH-04, SP-03 | KT-02, KT-03 | chưa làm |
| 6 | `shifts`, `payments`, `bank-mock` | `payments/shifts-collection-invoice` | 3.5, 3.2, 3.3 | CA-01 đến CA-04, TT-01 đến TT-04 | KT-01, 04, 05, 06, 11, 16 | chưa làm |
| 7 | `returns`, `customers` | `returns/return-refund` | 3.4 phần phiếu trả và hoàn tiền; 2.4 | TH-01 đến TH-05, KH-04 | KT-08, KT-09 | chưa làm |
| 8 | `workers/closing`, `inventory`, `reports` | `closing/end-of-day-replenishment` | Sự kiện giờ đóng cửa; 4.4; 5.4 | BH-05, TH-03, TK-06 | KT-07, KT-14 | chưa làm |
| 9 | `reports` | `reports/revenue-stock-staff` | 5.1, 5.2, 5.3, 5.5 | DT-01 đến DT-05 | KT-10, 13, 15 | chưa làm |
| 10 | `web` | `web/role-screens` | Giao diện theo 5 vai trò; dữ liệu demo | Ma trận 2.2 | chạy tay luồng P1–P5 | chưa làm |

Xong một vòng thì sửa cột "Trạng thái" ở bảng này, dòng "Vòng tiếp theo" ở trên, và cột "Trạng thái" của các
tình huống KT trong [tests.md](tests.md).

## 2. Cách làm việc

- Một người cùng AI code toàn bộ. Bảng phân vai ở mục 6 chỉ dùng cho báo cáo và để giữ ranh giới giữa các module.
- **Git**: mỗi vòng một nhánh `<nghiệp vụ>/<chức năng>` (cột "Nhánh" ở mục 1), commit message bằng tiếng Anh. AI tạo
  nhánh và commit; trước khi push thì kiểm tra nội dung sẽ đẩy và hỏi người dùng. Chi tiết ở `CLAUDE.md` mục Git.
- Mỗi vòng đi đủ bốn bước bằng lệnh của dự án:
  1. `/plan-task <vòng>`: đọc tài liệu, lập kế hoạch, liệt kê giả định, **dừng chờ duyệt**.
  2. `/test-first <vòng>`: viết test, chạy và xác nhận test đỏ vì thiếu chức năng.
  3. `/implement <vòng>`: viết code tới khi test xanh.
  4. `/self-review`: đối chiếu checklist, báo cáo; không tự sửa ở bước này. Đạt hết thì commit trên nhánh của vòng.
- Hợp đồng đi trước code: tên trường của endpoint mới được ghi vào [api.md](api.md) trong bước `/plan-task`, sau
  khi duyệt mới viết model và code. Đổi nội dung đã chốt trong `docs/` thì dùng `/doc-change`.
- Kết thúc mỗi vòng chạy `make check` và báo kết quả thật, kể cả phần chưa đạt.

## 3. Vòng 0 đã dựng những gì

| Phần | Nội dung |
| --- | --- |
| `docs/` | Đặc tả gốc ([spec.md](spec.md)), thiết kế CSDL ([db.md](db.md)), hợp đồng API ([api.md](api.md)), kiểm thử ([tests.md](tests.md)), kế hoạch này |
| `db/` | `001_schema.sql`: đủ 18 bảng và ràng buộc mục 5.3; `002_seed.sql`: khách lẻ KHLE; `migrate.py`: chạy migration lúc api khởi động và trong test |
| `common/` | `constants.py` (vai trò, trạng thái, loại, mã lỗi), `errors.py` (dạng lỗi chung), `auth.py` (băm mật khẩu, token), `clock.py` (nguồn thời gian), `models.py` (model request/response) |
| `api/` | `main.py`, `deps.py` (`Conn`, `User`, `require_role`), `routers/auth.py`, `services/auth.py`: `/health`, `/auth/login`, `/auth/me`, tài khoản trụ sở đầu tiên |
| `web/` | React + Vite + TypeScript + Ant Design + TanStack Query: trang đăng nhập, khung trang có menu theo vai trò, `api/client.ts` có kiểu sinh từ OpenAPI |
| `infra/` | `compose.yml` với ba container `db`, `api`, `web`; cấu hình nginx |
| `tests/` | `conftest.py`, `fixtures.py` và 40 test nền (xem [tests.md](tests.md) mục 4) |
| Công cụ | `Makefile`, `.github/workflows/ci.yml`, `.claude/` (lệnh và quyền), `CLAUDE.md` các thư mục |

Chưa có dòng code nghiệp vụ nào của 27 chức năng.

## 4. Mẫu cho một vòng API (vòng 1 đến 9)

Mỗi vòng tạo hoặc sửa đúng các chỗ sau, không hơn:

| Việc | Vị trí |
| --- | --- |
| Tên trường request/response của endpoint trong vòng | `docs/api.md` mục 4 (làm ở `/plan-task`) |
| Model Pydantic | `common/models.py` |
| Hằng số mới, nếu đặc tả có | `common/constants.py` |
| SQL và quy tắc nghiệp vụ | `api/services/<module>.py` |
| Endpoint: kiểm tra vai trò, gọi service | `api/routers/<module>.py` |
| Đăng ký router: một dòng `app.include_router(...)` | `api/main.py` |
| Test theo quy tắc và theo tình huống KT | `tests/<module>/` |
| Hàm dựng dữ liệu dùng chung cho test | `tests/fixtures.py` |
| Kiểu TypeScript cho giao diện: chạy `make gen-api` | `web/src/api/schema.d.ts` (file sinh, không sửa tay) |
| Cập nhật tiến độ | `docs/plan.md` mục 1, `docs/tests.md` mục 3 |

Schema đã đủ 18 bảng nên các vòng không tạo bảng mới. Nếu thấy thiếu cột hoặc ràng buộc thì dừng và hỏi; được
duyệt thì thêm file migration mới, không sửa `001_schema.sql`.

## 5. Chi tiết từng vòng

### Vòng 1 – Nhân viên và chi nhánh (`staff`)

- Chức năng 6.1 đến 6.4, kho D6. Chỉ Trụ sở được gọi các endpoint ghi; `GET /branches` cho mọi vai trò.
- NV-02 và NV-04 cần đọc D3, D4, D5 (ca chưa chốt, đơn dở, phiếu chờ xử lý, tồn, phiếu trả chưa hoàn xong). Các bảng
  này đã có từ vòng 0 nên làm đủ điều kiện ngay trong vòng này; test tự chèn dữ liệu bằng SQL vào các bảng đó.
- 6.3 cấp tài khoản: hệ thống sinh mật khẩu tạm, trả về đúng một lần trong response để trụ sở bàn giao.
- Từ vòng này, mọi câu lệnh ghi vào `branches`, `employees` nằm trong `api/services/staff.py`
  (riêng `ensure_bootstrap_admin` ở `services/auth.py` giữ nguyên).

### Vòng 2 – Sản phẩm (`products`)

- Chức năng 1.1 đến 1.4, kho D1. Trụ sở ghi; mọi vai trò đọc danh mục.
- Tạo sản phẩm ghi luôn bản ghi lịch sử giá đầu tiên trong cùng transaction (SP-02). Đổi giá phải khác giá hiện hành.
- Đơn vị tính chỉ đổi khi sản phẩm chưa có trên chứng từ nào (1.1); không có endpoint xóa sản phẩm (SP-04).

### Vòng 3 – Khách hàng (`customers`)

- Chức năng 2.1 đến 2.3, kho D2. Chỉ NVBH.
- Chuẩn hóa số điện thoại trước khi so trùng; trùng thì trả hồ sơ có sẵn, không tạo mới (2.1).
- Không tra cứu hay sửa KHLE (KH-02). Chức năng 2.4 để vòng 7 vì cần phiếu trả.

### Vòng 4 – Tồn kho (`inventory`)

- Chức năng 4.1, 4.2, 4.3, 4.5 và năm hàm giao ở [api.md](api.md) mục 5. Kho D5.
- `api/services/inventory.py` là nơi duy nhất có lệnh ghi vào `stock`, `stock_slips`, `stock_slip_items`.
- Giữ hàng: khóa dòng `stock` bằng `SELECT … FOR UPDATE` theo thứ tự mã sản phẩm rồi mới tính tồn khả dụng.
  Viết test hai kết nối đồng thời tranh một sản phẩm cuối cùng (nền cho KT-06).
- Nghiệm thu: KT-12.

### Vòng 5 – Đơn hàng (`orders`)

- Chức năng 3.1 và phần hủy đơn của 3.4. Kho D3 (bảng `orders`, `order_items`).
- Chốt đơn gọi `inventory.check_available`, chép giá hiện hành vào `unit_price`; chốt không giữ hàng (BH-02).
- Mở lại và hủy cần biết đơn có giao dịch Chờ kết quả hay không: tạo `payments.has_pending_txn` đúng chữ ký ở
  [api.md](api.md) mục 5, đặt trong `api/services/payments.py`.
- Nghiệm thu: KT-02, KT-03 (các ý cần thu tiền và hoàn tiền bổ sung ở vòng 6, 7).

### Vòng 6 – Ca, thu tiền, hóa đơn (`shifts`, `payments`)

- Chức năng 3.5, 3.2, 3.3. Kho D4. Thêm container `bank-mock` và biến môi trường liên quan vào `infra/compose.yml`,
  `.env.example` theo [api.md](api.md) mục 6.
- Một lần thu Thành công làm ba việc trong **một** transaction: giao dịch sang `SUCCESS`, `inventory.confirm_sale`,
  `orders.mark_completed`, rồi phát hành hóa đơn (TT-03, TT-04).
- Gọi cổng thanh toán sau khi transaction đã commit. Phản hồi lặp không làm đổi gì (TT-02).
- Nghiệm thu: KT-01, KT-04, KT-05, KT-06, KT-11, KT-16.

### Vòng 7 – Trả hàng, hoàn tiền (`returns`) và 2.4

- Phần phiếu trả và hoàn tiền của 3.4; chức năng 2.4 trong `customers`.
- Duyệt phiếu trả gọi `inventory.receive_return` cho số lượng tốt và cập nhật trạng thái đơn trong cùng transaction (TH-05).
- Hoàn tiền mặt thay thế chỉ sau ít nhất một lần hoàn điện tử Thất bại và có người duyệt (TH-04).
- Nghiệm thu: KT-08, KT-09; bổ sung ý hoàn tiền của KT-02.

### Vòng 8 – Giờ đóng cửa, yêu cầu bổ sung, cảnh báo tồn

- `api/workers/closing.py`: tác vụ nền khởi động trong `lifespan` của `api/main.py`. Tới giờ đóng cửa của từng
  chi nhánh thì tự hủy đơn (BH-05) và tự từ chối phiếu trả (TH-03). Phần xử lý là một hàm nhận `at`, để test gọi
  trực tiếp với đồng hồ cố định; vòng lặp nền chỉ gọi hàm đó.
- 4.4 trong `inventory`; 5.4 trong `api/services/reports.py` (bắt đầu file báo cáo).
- Nghiệm thu: KT-07, KT-14.

### Vòng 9 – Báo cáo (`reports`)

- Chức năng 5.1, 5.2, 5.3, 5.5. Chỉ đọc, không có bảng riêng, không ghi gì.
- Ba mốc thời gian không được trộn (đặc tả 4.5): doanh thu theo `completed_at`, hàng trả theo `decided_at` của
  phiếu Đã duyệt, tiền thu và hoàn theo `resolved_at` của giao dịch Thành công.
- Doanh thu và hàng trả ghi cho chi nhánh và người lập của đơn gốc (DT-05).
- Nghiệm thu: KT-10, KT-13, KT-15.

### Vòng 10 – Giao diện (`web`)

- Mỗi vai trò một nhóm trang trong `web/src/features/<module>/`, đăng ký bằng một dòng trong `web/src/menu.tsx`.
  Chia thành năm lượt: Trụ sở, NVBH, Thu ngân, NV kho, Quản lý cửa hàng. Mỗi lượt vẫn đi qua bốn bước.
- Chỉ gọi API qua `client` trong `web/src/api/client.ts`; nhãn tiếng Việt của mã trạng thái đặt trong `web/src/labels.ts`.
- Thêm `scripts/seed-demo.py` tạo dữ liệu demo theo mã ở [tests.md](tests.md) mục 2.
- Nghiệm thu: chạy tay đủ năm luồng P1 đến P5 của đặc tả mục 3 trên `http://localhost:3000`.

## 6. Phân vai (dùng cho báo cáo)

Chia theo kho dữ liệu, vì đặc tả 6.1 quy định mỗi kho chỉ do một nhóm ghi.

| Vai | Sở hữu | Chức năng và quy tắc | Tình huống KT | Lý thuyết cần nắm |
| --- | --- | --- | --- | --- |
| 1. Nền tảng và tích hợp (trưởng nhóm) | `infra/`, `db/`, `common/`, `docs/`, CI, đăng nhập, khung `web/`; kho D6 | 6.1–6.4; NV-01..04, K-01..05 | KT-13 | Chuyển ERD sang lược đồ quan hệ, ràng buộc toàn vẹn; phân quyền theo vai trò, tách người lập và người duyệt; Docker, CI |
| 2. Danh mục và báo cáo bán hàng | kho D1, D2; `products`, `customers`; báo cáo 5.1, 5.2, 5.5 | 1.1–1.4, 2.1–2.4; SP, KH, DT | KT-10, KT-15 | Dữ liệu danh mục, lịch sử giá, dùng trạng thái thay cho xóa; chỉ tiêu quản trị và ba mốc thời gian của doanh thu |
| 3. Đơn hàng và trả hàng | kho D3; `orders`, `returns`, `workers/closing` | 3.1, 3.4 (hủy đơn, phiếu trả); BH-01..05, TH-01..03, TH-05 | KT-02, 03, 07, 08 | Vòng đời chứng từ dạng máy trạng thái; chốt giá tại thời điểm; quy trình phê duyệt; sự kiện theo thời gian |
| 4. Thanh toán, hóa đơn, ca | kho D4; `payments`, `shifts`, `bank-mock` | 3.2, 3.3, 3.4 (hoàn tiền), 3.5; TT-01..04, TH-04, CA-01..04 | KT-01, 04, 05, 09, 11, 16 | Giao dịch tiền không trùng lặp, tích hợp cổng thanh toán và tra soát; đối soát tiền mặt, kiểm soát nội bộ |
| 5. Tồn kho | kho D5; `inventory`; báo cáo 5.3, 5.4 | 4.1–4.5; TK-01..06 | KT-06, 12, 14 | Sổ kho theo chứng từ, giữ hàng; giao dịch CSDL, khóa và tranh chấp đồng thời |

## 7. Quyết định đã chốt

Các điểm đặc tả để trống ở mức triển khai, đã được người dùng duyệt ngày 13/11/2026:

1. Một API FastAPI, một PostgreSQL, giao diện React phục vụ qua nginx. Không Kafka, không CDC.
2. Tên bảng, cột, mã trạng thái bằng tiếng Anh; giao diện hiển thị tiếng Việt ([db.md](db.md) mục 2, 3).
3. Mã chứng từ: tiền tố + 6 chữ số tăng dần ([db.md](db.md) mục 7). Mã sản phẩm, nhóm, nhân viên, chi nhánh do trụ sở nhập.
4. Đăng nhập bằng token ký HMAC; mỗi request đọc lại nhân viên từ CSDL để kiểm tra khóa, vai trò, chi nhánh (K-01).
5. Tài khoản trụ sở đầu tiên lấy từ `.env`, tạo khi api khởi động. Chức năng 6.3 sinh mật khẩu tạm. Không có chức năng
   nhân viên tự đổi mật khẩu vì nằm ngoài 27 chức năng.
6. Cảnh báo 5.4 tính ngay lúc QL hoặc NV kho mở trang; không lưu, không cần lịch chạy mỗi sáng, vì nhóm 5 không có kho riêng.
7. In hóa đơn là trang HTML in từ trình duyệt.
8. Ngân hàng/Cổng thanh toán được giả lập bằng container `bank-mock`.
9. Chứng từ lập sau giờ đóng cửa được quét ở lần đóng cửa kế tiếp.
10. Test chạy trên PostgreSQL thật ([tests.md](tests.md) mục 1).

Giả định của người dựng khung, **chưa được người dùng xác nhận**. Vòng nào chạm tới thì nêu lại ở `/plan-task`:

- Trụ sở duyệt thay (K-02): hệ thống không tự biết QL vắng mặt, nên cho phép Trụ sở duyệt khi có lý do bắt buộc.
- Người làm chứng khi đóng ca thay (CA-04): nhân viên Đang làm cùng chi nhánh, khác QL đóng thay và khác thu ngân của ca.
- Lý do hủy đơn, xuất hủy, điều chỉnh là văn bản tự do; báo cáo gom theo đúng chuỗi lý do; giao diện gợi ý sẵn các lý do thường gặp.
- Nhập hàng từ kho tổng/NCC cho sản phẩm Ngừng bán: đặc tả không nói; tạm cho phép.

## 8. Việc hoãn có chủ đích

| Việc | Lý do | Làm ở |
| --- | --- | --- |
| Container `bank-mock` | Chưa có giao dịch nào để gọi | Vòng 6 |
| Tác vụ nền giờ đóng cửa | Chưa có đơn và phiếu trả để quét | Vòng 8 |
| Dữ liệu demo, kịch bản demo | Cần đủ API và giao diện | Vòng 10 |
| Index phụ cho truy vấn | Chưa có truy vấn thật để đo | Khi báo cáo chậm, bằng migration mới |
| CODEOWNERS, lệnh `/review-pr` | Một người làm, không có PR chéo | Khi có người thứ hai cùng code |
