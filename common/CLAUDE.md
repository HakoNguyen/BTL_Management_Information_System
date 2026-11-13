# common/

Thư viện dùng chung của API và test. Không chứa logic nghiệp vụ, không chứa SQL.

- `constants.py`: vai trò, trạng thái, loại chứng từ, mã lỗi. Giá trị enum là giá trị lưu trong CSDL và phải khớp CHECK
  trong migration (`tests/db/test_schema.py` kiểm tra). Thêm giá trị mới = thêm cả migration và `docs/db.md` mục 3.
- `errors.py`: `AppError` và handler trả `{error_code, message, details}` (`docs/api.md` mục 2).
- `models.py`: model Pydantic v2 cho mọi request/response. Tên trường theo `docs/api.md`. Sau khi sửa chạy `make gen-api`.
- `auth.py`: băm mật khẩu scrypt, token ký HMAC. Không đổi thuật toán khi chưa được duyệt.
- `clock.py`: `clock.now()` là nguồn thời gian duy nhất; `clock.freeze()` chỉ dùng trong test.

Quy tắc chung xem CLAUDE.md ở gốc repo.
