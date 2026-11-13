# CLAUDE.md – Quy tắc cho AI trong repo QLBH

Đọc file này ở đầu mọi phiên làm việc. Các quy tắc dưới đây là bắt buộc.

## Dự án
Hệ thống thông tin quản lý bán hàng cho chuỗi cửa hàng (Nhóm 3): bán hàng, thanh toán, đổi trả, tồn kho theo
chi nhánh và báo cáo. 6 nhóm chức năng, 27 chức năng con, 18 bảng. Một API FastAPI + một PostgreSQL + giao diện
React, chạy bằng Docker Compose.

## Bắt đầu từ đâu
- `docs/plan.md` mục 1 cho biết vòng đang làm. Mỗi lần chỉ làm **một** vòng, đúng thứ tự.
- Quy trình bốn bước, dùng lệnh dự án: `/plan-task` → `/test-first` → `/implement` → `/self-review`.
  `/plan-task` kết thúc bằng việc dừng lại chờ người dùng duyệt.

## Nguồn sự thật
- `docs/spec.md` (đặc tả nghiệp vụ) là chuẩn cao nhất, rồi `docs/db.md`, rồi `docs/api.md`.
  `docs/tests.md`: kết quả phải đạt. `docs/plan.md`: thứ tự làm và các quyết định đã chốt.
- Không tự đặt tên bảng, cột, endpoint, mã lỗi, mã trạng thái, biến môi trường. Tên đã có trong `docs/` thì dùng
  đúng; chưa có thì đề xuất ở `/plan-task` và ghi vào `docs/` trước khi code.
- Đặc tả thiếu hoặc mâu thuẫn thì DỪNG và hỏi, không đoán. Các giả định chưa được xác nhận nằm ở `docs/plan.md` mục 7.
- Không thêm thư viện. Python: fastapi, uvicorn, asyncpg, pydantic (v2), httpx; test: pytest, pytest-asyncio; lint: ruff.
  Giao diện: react, react-dom, react-router-dom, antd, @tanstack/react-query, openapi-fetch; công cụ: vite,
  typescript, vitest, openapi-typescript. Cần thêm thì dừng và hỏi.

## Bản đồ repo
| Thư mục | Nội dung | Mục cần đọc |
|---|---|---|
| `docs/` | Đặc tả, thiết kế CSDL, hợp đồng API, kiểm thử, kế hoạch | `docs/README.md` |
| `db/` | Migration SQL đánh số, `migrate.py` | `docs/db.md` |
| `common/` | Hằng số, lỗi, model, băm mật khẩu và token, đồng hồ | `docs/db.md` mục 3, `docs/api.md` mục 2 |
| `api/` | FastAPI: `routers/` (mỏng), `services/` (SQL và quy tắc), `workers/` (tác vụ nền) | `docs/api.md` |
| `web/` | React + TypeScript; trang theo module trong `src/features/` | `web/CLAUDE.md` |
| `infra/` | Docker Compose, nginx | `infra/CLAUDE.md` |
| `tests/` | pytest trên PostgreSQL thật | `docs/tests.md` |

Mỗi thư mục có `CLAUDE.md` riêng; đọc file của thư mục sắp sửa.

## Phạm vi sửa
- Chỉ sửa file đã liệt kê trong kế hoạch được duyệt. Cần sửa chỗ khác thì dừng và nêu đề xuất.
- Không sửa file trong `db/migrations/` đã có; đổi schema = file migration mới, đánh số tiếp theo, và phải được duyệt.
- `docs/spec.md` không sửa tay. Thay đổi nội dung đã chốt trong `docs/` dùng lệnh `/doc-change`.
- `web/src/api/schema.d.ts` là file sinh ra: không sửa tay, chạy `make gen-api`.
- Không thêm tính năng, tùy chọn hay lớp trừu tượng mà đặc tả không yêu cầu.

## Quy tắc nghiệp vụ không được vi phạm
- **Mỗi kho một chủ** (đặc tả 6.1): lệnh ghi vào bảng của kho nào chỉ nằm trong service của nhóm sở hữu kho đó
  (`docs/db.md` mục 2). Module khác gọi hàm giao ở `docs/api.md` mục 5, trong cùng transaction. Ví dụ: `payments`
  không viết `UPDATE stock`, mà gọi `inventory.confirm_sale`.
- **Tồn chỉ đổi qua phiếu kho** (TK-01): không có lệnh sửa `stock.quantity` nào ngoài `api/services/inventory.py`.
  Trước khi tính tồn khả dụng để giữ hàng, khóa dòng `stock` bằng `SELECT … FOR UPDATE` theo thứ tự mã sản phẩm.
- **Trạng thái chỉ đi tới**: `UPDATE … WHERE status = <trạng thái liền trước>`, rồi kiểm tra số dòng bị ảnh hưởng.
- **Không sửa, xóa chứng từ đã có hiệu lực** (K-04) và không xóa danh mục đã phát sinh nghiệp vụ (K-05). Sai sót xử lý
  bằng chứng từ mới có duyệt.
- **Người duyệt khác người lập** (K-02). Mọi quyết định duyệt, hủy, từ chối lưu người, thời điểm, lý do (K-03).
- **Chứng từ giữ chi nhánh và nhân viên lúc phát sinh** (K-05): chép mã vào chứng từ, không suy lại từ hồ sơ hiện tại.
- **Quyền kiểm tra tại thời điểm thao tác** (K-01): endpoint nào cũng qua `require_role`; service so chi nhánh của
  người dùng với chi nhánh của chứng từ.
- **Dữ liệu dẫn xuất không lưu thành cột** (`docs/db.md` mục 6): tổng tiền đơn, tồn khả dụng, giá trị phiếu trả,
  tiền mặt kỳ vọng, chỉ tiêu doanh thu luôn tính bằng truy vấn.
- **Một nguồn thời gian**: mốc thời gian nghiệp vụ lấy từ `clock.now()` rồi truyền vào SQL. Không dùng
  `datetime.now()` hay `now()` của SQL trong code nghiệp vụ.
- **Không gọi HTTP bên trong transaction CSDL** (cổng thanh toán gọi sau khi commit).
- **Tiền và số lượng là số nguyên** (G-07): `int` trong Python, `bigint`/`integer` trong SQL; không dùng `float`.

## Cách làm
- Python 3.11, async, có type hint, định dạng theo ruff (line-length 100).
- Router mỏng: kiểm tra vai trò, gọi một hàm service, trả model. SQL thuần bằng asyncpg, tham số hóa (`$1`, `$2`);
  không ghép chuỗi giá trị vào SQL.
- Dùng enum trong `common/constants.py`; không viết chuỗi trực tiếp như `"PENDING"`.
- Lỗi nghiệp vụ: `raise AppError(ErrorCode.X, "thông báo tiếng Việt", rule="BH-02")`. Service kiểm tra trước để lỗi
  ràng buộc CSDL không lọt ra thành lỗi 500.
- Mỗi vòng API đi theo mẫu ở `docs/plan.md` mục 4; router đăng ký bằng một dòng trong `api/main.py`.
- Giao diện gọi API chỉ qua `client` và `unwrap` trong `web/src/api/client.ts`; trang mới đăng ký bằng một dòng
  trong `web/src/menu.tsx`; nhãn tiếng Việt đặt trong `web/src/labels.ts`.
- Test: quy ước ở `docs/tests.md`. Tiền tố `test_ktXX_` chỉ dành cho test hiện thực đúng một tình huống KT.
- Comment và thông báo lỗi viết tiếng Việt; tên trong code viết tiếng Anh. File `requirements*.txt` chỉ viết ASCII.
- Kết thúc mỗi việc: chạy `make check`, báo kết quả thật (kể cả phần chưa đạt), liệt kê giả định còn mở, cập nhật
  tiến độ trong `docs/plan.md` và `docs/tests.md`.

## Git
- Remote `origin`: https://github.com/HakoNguyen/BTL_Management_Information_System.git
- Mỗi vòng một nhánh, đặt tên `<nghiệp vụ>/<chức năng>` bằng tiếng Anh viết thường, nối bằng gạch ngang. Tên nhánh
  của từng vòng ở `docs/plan.md` mục 1. Tách từ `main` mới nhất; vòng trước chưa được merge vào `main` thì tách từ
  nhánh của vòng trước. Không commit thẳng vào `main`.
- Commit message viết bằng tiếng Anh, dạng `<type>(<module>): <summary>` (type: feat, fix, test, docs, refactor,
  chore, build, ci), câu mệnh lệnh, dòng đầu tối đa 72 ký tự. Thân ghi mã chức năng, mã quy tắc và tình huống KT
  liên quan.
- Chỉ commit khi `make check` xanh và `/self-review` không còn ý KHÔNG ĐẠT. Không bao giờ commit `.env`.
- Trước khi push: liệt kê commit và file sẽ được đẩy (`git log --oneline`, `git status`), kiểm tra không có bí mật,
  rồi hỏi người dùng; chỉ push khi được đồng ý. Không `--force`, không push vào `main`, không tạo pull request khi
  chưa được yêu cầu.
