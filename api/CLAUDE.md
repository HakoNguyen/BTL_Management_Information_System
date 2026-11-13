# api/

Một ứng dụng FastAPI cho cả 6 nhóm chức năng, cổng 8000. Mục cần đọc: `docs/api.md`, `docs/db.md`.

- `main.py`: tạo app, pool asyncpg, chạy migration, đăng ký router. Mỗi vòng thêm đúng một dòng `include_router`.
- `deps.py`: `Conn` (kết nối CSDL), `User` (phiên đăng nhập), `require_role(...)` (ma trận phân quyền 2.2).
- `routers/<module>.py`: mỏng. Kiểm tra vai trò, gọi một hàm service, trả model trong `common/models.py`.
- `services/<module>.py`: SQL và quy tắc nghiệp vụ. Hàm nhận `conn` làm tham số đầu; hàm làm nhiều lệnh ghi thì tự
  bọc `async with conn.transaction()`. Hàm giao cho module khác gọi (`docs/api.md` mục 5) chạy trong transaction của
  bên gọi.
- `workers/`: tác vụ nền (giờ đóng cửa, vòng 8). Phần xử lý là hàm nhận thời điểm, để test gọi trực tiếp.
- Tên module: `staff`, `products`, `customers`, `inventory`, `orders`, `payments`, `shifts`, `returns`, `reports`.
- Lệnh ghi vào bảng của kho nào chỉ nằm trong service của nhóm sở hữu kho đó (`docs/db.md` mục 2).

Quy tắc chung xem CLAUDE.md ở gốc repo.
