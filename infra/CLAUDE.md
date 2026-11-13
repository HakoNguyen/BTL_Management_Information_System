# infra/

Docker Compose cho toàn bộ hệ thống trên một máy.

- `compose.yml`: `db` (PostgreSQL 16, cổng 5432), `api` (cổng 8000), `web` (nginx, cổng 3000). Vòng 6 thêm `bank-mock`.
  Tên container cố định: `qlbh-db`, `qlbh-api`, `qlbh-web`.
- Biến lấy từ `.env` ở gốc repo; biến mới phải thêm vào `.env.example` kèm chú thích. Không ghi giá trị bí mật vào
  `compose.yml` hay bất kỳ file nào được commit.
- Build context của mọi image là gốc repo (api cần `common/`, `db/`; web cần `infra/nginx/`).
- Schema do api tự áp dụng lúc khởi động (`db/migrate.py`); không mount file SQL vào `db`.
- `nginx/default.conf`: phục vụ bản build của `web/` và chuyển `/api/*` sang `api`, nên không cần CORS.
- Lệnh: `make up`, `make down`, `make reset` (xóa cả dữ liệu), `make ps`, `make logs S=api`.

Quy tắc chung xem CLAUDE.md ở gốc repo.
