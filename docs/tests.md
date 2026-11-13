# Kiểm thử

Chuẩn nghiệm thu: một chức năng chỉ coi là xong khi test của nó xanh. Khi kết quả thực tế khác kết quả mong đợi
thì sửa code, không sửa kỳ vọng; kỳ vọng chỉ đổi khi đặc tả đổi (`/doc-change`).

## 1. Quy ước

- Test API chạy trên PostgreSQL thật, CSDL `qlbh_test` trong container `db`. Lý do: phần lớn quy tắc của đặc tả
  được ép bằng ràng buộc, khóa dòng và transaction; giả lập CSDL sẽ không bắt được lỗi ở đúng chỗ đó.
- `tests/conftest.py` lo phần nền:
  - `database`: dựng lại schema một lần mỗi phiên test bằng `db/migrate.py` (cùng đường với API thật).
  - `pool`, `conn`: trước mỗi test xóa sạch dữ liệu, đưa dãy số mã chứng từ về 1, nạp lại `002_seed.sql`.
    Vì vậy mã sinh ra luôn đoán được: đơn đầu tiên của mỗi test là `DH000001`.
  - `app`, `client`: ứng dụng FastAPI dùng `pool` của test và `httpx.AsyncClient` gọi thẳng vào ứng dụng.
  - Đồng hồ tự bỏ cố định sau mỗi test.
- Test cần CSDL đánh dấu `pytestmark = pytest.mark.db`. Máy cá nhân chưa bật container `db` thì các test này bị
  skip; trên CI (biến `CI`) thì không kết nối được là lỗi.
- Ngày giờ: dùng `clock.freeze(datetime(..., tzinfo=VN_TZ))`. Không `sleep`, không phụ thuộc giờ thật.
- Dữ liệu: dùng mã và hàm dựng trong `tests/fixtures.py` (mục 2); vòng nào cần dữ liệu mới thì thêm hàm vào đó.
- Đăng nhập trong test: `headers = await login_as(client, SALES_ID)`.
- Lỗi nghiệp vụ: assert cả `error_code` và `details.rule`, không assert theo câu thông báo.
- Đặt tên:
  - Tình huống trong đặc tả mục 7: `tests/<module>/test_ktXX_<ten_ngan>.py`, mỗi file đúng một tình huống.
    Tiền tố `test_ktXX_` chỉ dành cho các file này.
  - Test theo quy tắc hoặc thành phần: `tests/<module>/test_<thanh_phan>.py`; docstring của mỗi test ghi mã quy tắc
    (ví dụ `"""BH-02."""`).
  - `<module>` trùng tên file trong `api/services/`: `staff`, `products`, `customers`, `inventory`, `orders`,
    `payments`, `returns`, `shifts`, `reports`; cộng `auth`, `common`, `db`.
- Giao diện: `web/src/**/*.test.ts` chạy bằng vitest. Chỉ test logic thuần (gọi API, tính toán, lọc theo vai trò),
  không test hiển thị.

## 2. Mã cố định

Khai báo trong `tests/fixtures.py`; test, dữ liệu demo và tài liệu dùng chung.

| Tên | Giá trị | Ghi chú |
| --- | --- | --- |
| `BRANCH_1`, `BRANCH_2` | `CN1`, `CN2` | `seed_branch` đặt giờ đóng cửa 22:00 (KT-07) |
| `HQ_ID` | `NV-TS` | Trụ sở, không thuộc chi nhánh |
| `MANAGER_ID` | `NV-QL1` | Quản lý cửa hàng CN1 |
| `SALES_ID` | `NV-BH1` | Nhân viên bán hàng CN1 |
| `CASHIER_ID` | `NV-TN1` | Thu ngân CN1 |
| `WAREHOUSE_ID` | `NV-KHO1` | Nhân viên kho CN1 |
| `TEST_PASSWORD` | mật khẩu chung của nhân viên seed | Tên đăng nhập = mã nhân viên viết thường |

Sản phẩm mẫu theo đặc tả mục 7: A giá 100.000; B, C, D thêm khi vòng 2 viết `seed_product`.

## 3. Tình huống KT-01 đến KT-16

Dữ liệu và kết quả mong đợi: nguyên văn ở [spec.md](spec.md) mục 7, không chép lại ở đây để tránh hai bản lệch nhau.
Mỗi test assert đủ mọi ý trong cột "Kết quả kỳ vọng" của tình huống đó.

| Mã | Tình huống | File test | Vòng | Trạng thái |
| --- | --- | --- | --- | --- |
| KT-01 | Bán tiền mặt | `tests/payments/test_kt01_ban_tien_mat.py` | 6 | chưa viết |
| KT-02 | Đổi giá | `tests/orders/test_kt02_doi_gia.py` | 5 (ý hoàn 100.000 bổ sung ở vòng 7) | chưa viết |
| KT-03 | Khách đổi ý | `tests/orders/test_kt03_khach_doi_y.py` | 5 (ý "đang có giao dịch Chờ kết quả" bổ sung ở vòng 6) | chưa viết |
| KT-04 | Thẻ thất bại rồi thành công | `tests/payments/test_kt04_the_that_bai.py` | 6 | chưa viết |
| KT-05 | Mất phản hồi, phản hồi lặp | `tests/payments/test_kt05_mat_phan_hoi.py` | 6 | chưa viết |
| KT-06 | Tranh hàng cuối cùng | `tests/payments/test_kt06_tranh_hang.py` | 6 | chưa viết |
| KT-07 | Cuối ngày | `tests/orders/test_kt07_cuoi_ngay.py` | 8 | chưa viết |
| KT-08 | Trả hàng tốt và lỗi | `tests/returns/test_kt08_tra_hang.py` | 7 | chưa viết |
| KT-09 | Hoàn thẻ thất bại | `tests/returns/test_kt09_hoan_the_that_bai.py` | 7 | chưa viết |
| KT-10 | Bán, trả, hoàn khác ngày | `tests/reports/test_kt10_khac_ngay.py` | 9 | chưa viết |
| KT-11 | Đối soát ca | `tests/shifts/test_kt11_doi_soat_ca.py` | 6 | chưa viết |
| KT-12 | Nhập nhầm và nhập trùng | `tests/inventory/test_kt12_nhap_nham.py` | 4 | chưa viết |
| KT-13 | Ngừng bán và đóng chi nhánh | `tests/staff/test_kt13_dong_chi_nhanh.py` | 9 | chưa viết |
| KT-14 | Ngưỡng và yêu cầu bổ sung | `tests/inventory/test_kt14_nguong.py` | 8 | chưa viết |
| KT-15 | Phê duyệt và lịch sử | `tests/reports/test_kt15_phe_duyet.py` | 9 | chưa viết |
| KT-16 | Thu ngân vắng đột xuất | `tests/shifts/test_kt16_thu_ngan_vang.py` | 6 | chưa viết |

Khi một tình huống xanh, đổi cột "Trạng thái" thành "xanh" trong cùng thay đổi đó.

## 4. Test nền đã có (vòng 0)

| File | Kiểm tra |
| --- | --- |
| `tests/common/test_auth.py` | Băm mật khẩu, token: đúng chữ ký, hết hạn, bị sửa |
| `tests/db/test_schema.py` | Đủ 18 bảng; enum khớp CHECK; ràng buộc NV-01, TK-01, CA-01, TK-02 và mục 5.3 chặn dữ liệu sai; mã chứng từ |
| `tests/auth/test_login.py` | Đăng nhập, dạng lỗi, token hết hạn, khóa tài khoản là mất phiên ngay (K-01), `require_role`, tài khoản trụ sở đầu tiên |
| `web/src/api/client.test.ts` | Gắn token, đổi lỗi API thành `ApiError`, 401 thì xóa token |

## 5. Cách chạy

| Lệnh | Việc làm |
| --- | --- |
| `make up` | Bật `db`, `api`, `web` (test cần `db`) |
| `make test` | Toàn bộ pytest; một thư mục: `make test T=tests/orders` |
| `make lint` | `ruff check .` |
| `make gen-api` | Sinh lại `web/src/api/schema.d.ts` từ OpenAPI |
| `make web-check` | Kiểm tra kiểu và test của giao diện |
| `make check` | Tất cả các bước trên trừ `make up`; chạy trước khi báo xong một vòng |

Không dùng `make` thì chạy trực tiếp: `ruff check .`, `pytest`, `python scripts/export_openapi.py web/openapi.json`,
rồi trong `web/`: `npm run gen:api`, `npm run typecheck`, `npm test`.
