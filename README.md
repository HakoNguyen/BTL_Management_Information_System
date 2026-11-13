# Hệ thống thông tin quản lý bán hàng cho chuỗi cửa hàng (Nhóm 3)

Ghi nhận bán hàng, thanh toán, đổi trả và tồn kho theo từng chi nhánh; báo cáo cho trụ sở và quản lý cửa hàng.
Đặc tả nghiệp vụ: [docs/spec.md](docs/spec.md). Tiến độ và thứ tự triển khai: [docs/plan.md](docs/plan.md).

## Kiến trúc

| Container | Cổng | Vai trò |
|---|---|---|
| `qlbh-db` | 5432 | PostgreSQL 16 |
| `qlbh-api` | 8000 | FastAPI (Python 3.11, asyncpg, Pydantic v2); tự chạy migration lúc khởi động |
| `qlbh-web` | 3000 | nginx phục vụ giao diện React và chuyển `/api/*` sang api |

```
docs/      đặc tả, thiết kế CSDL, hợp đồng API, kiểm thử, kế hoạch (nguồn sự thật)
db/        migration SQL đánh số, migrate.py
common/    hằng số, lỗi, model, token, đồng hồ
api/       routers/ (mỏng), services/ (SQL và quy tắc nghiệp vụ), workers/
web/       React + Vite + TypeScript + Ant Design
infra/     compose.yml, nginx
tests/     pytest trên PostgreSQL thật
```

## Chạy bằng Docker

Cần Docker Desktop. Chạy trong Git Bash, từ gốc repo.

1. Tạo file cấu hình rồi điền mật khẩu và khóa: `cp .env.example .env`
2. Dựng và chạy: `make up`
3. Mở http://localhost:3000, đăng nhập bằng `ADMIN_USERNAME` và `ADMIN_PASSWORD` trong `.env`.

| Lệnh | Việc làm |
|---|---|
| `make up` | Build và chạy `db`, `api`, `web` |
| `make down` | Dừng, giữ dữ liệu |
| `make reset` | Xóa dữ liệu và dựng lại từ đầu |
| `make ps`, `make logs S=api` | Trạng thái, log |

Không có `make` thì dùng trực tiếp: `docker compose --env-file .env -f infra/compose.yml up -d --build`.
API có trang thử tại http://localhost:8000/docs.

## Phát triển

```bash
python -m venv .venv
source .venv/Scripts/activate        # Linux, macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
(cd web && npm install)
make up                              # test cần container db
make check                           # lint, pytest, sinh kiểu TypeScript, kiểm tra giao diện
```

Chạy giao diện ở chế độ phát triển (tự nạp lại khi sửa): `cd web && npm run dev`, mở http://localhost:5173.

Quy ước code và quy trình làm việc với AI: [CLAUDE.md](CLAUDE.md). Quy ước kiểm thử: [docs/tests.md](docs/tests.md).
