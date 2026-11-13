# db/

Schema PostgreSQL 16. Mục cần đọc: `docs/db.md` toàn bộ.

- `migrations/001_schema.sql`, `002_seed.sql`, … đánh số tăng dần. KHÔNG sửa file đã có; đổi schema = file mới và phải
  được người dùng duyệt, kèm cập nhật `docs/db.md`.
- Tên bảng, cột, kiểu, ràng buộc đúng `docs/db.md`. Giá trị trong CHECK khớp enum ở `common/constants.py`.
- `migrate.py`: chạy các file chưa áp dụng, ghi vào bảng kỹ thuật `schema_migrations`. API gọi lúc khởi động, test gọi
  lúc dựng CSDL test, nên không có đường nào khác để tạo schema.
- File seed phải chạy lại được nhiều lần (`ON CONFLICT DO NOTHING`): test nạp lại sau mỗi lần xóa dữ liệu.

Quy tắc chung xem CLAUDE.md ở gốc repo.
