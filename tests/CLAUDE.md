# tests/

pytest trên PostgreSQL thật. Mục cần đọc: `docs/tests.md`.

- Mỗi module một thư mục: `tests/<module>/`, tên trùng file trong `api/services/`.
- `conftest.py`: fixture nền (`database`, `pool`, `conn`, `app`, `client`). Mỗi test bắt đầu với CSDL trống, chỉ có KHLE;
  mã chứng từ bắt đầu lại từ `…000001`.
- `fixtures.py`: mã cố định và hàm dựng dữ liệu (`seed_branch`, `seed_employee`, `login_as`…). Vòng nào cần dữ liệu mới
  thì thêm hàm ở đây, không chép SQL dựng dữ liệu sang từng file test.
- Test cần CSDL: `pytestmark = pytest.mark.db`.
- File `test_ktXX_<ten>.py` hiện thực đúng một tình huống ở `docs/spec.md` mục 7 và assert đủ mọi ý trong cột
  "Kết quả kỳ vọng". Test khác đặt tên theo thành phần, docstring ghi mã quy tắc.
- Test đi qua API (`client`) như người dùng thật; chỉ chèn SQL trực tiếp để dựng trạng thái mà module sở hữu chưa có API.
- Ngày giờ dùng `clock.freeze(...)`. Không `sleep`.
- Test đỏ thì sửa code, không nới lỏng assert. Kỳ vọng chỉ đổi khi đặc tả đổi.

Quy tắc chung xem CLAUDE.md ở gốc repo.
