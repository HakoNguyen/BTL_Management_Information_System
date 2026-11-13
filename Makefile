# Lệnh thường dùng. Chạy từ gốc repo, trong Git Bash (Windows) hoặc shell Linux.
# Biến đọc từ .env ở gốc repo; đổi file bằng: make up ENV_FILE=...
ENV_FILE ?= .env
COMPOSE = docker compose --env-file $(ENV_FILE) -f infra/compose.yml
# make logs S=api  (để trống = mọi service); make logs N=200
S ?=
N ?= 100

.PHONY: up down reset ps logs lint test gen-api web-check check seed-demo

# Dựng và chạy cả hệ thống: db, api, web
up:
	$(COMPOSE) up -d --build

# Dừng, giữ dữ liệu
down:
	$(COMPOSE) down

# Xóa cả dữ liệu rồi dựng lại từ đầu (api tự chạy migration, tạo lại tài khoản trụ sở)
reset:
	$(COMPOSE) down -v
	$(COMPOSE) up -d --build

ps:
	@$(COMPOSE) ps -a

logs:
	@$(COMPOSE) logs --tail=$(N) $(S)

lint:
	ruff check .

# Cần container db đang chạy (make up). Một thư mục: make test T=tests/auth
T ?=
test:
	pytest $(T)

# Sinh kiểu TypeScript cho giao diện từ OpenAPI của api. Chạy sau mỗi lần đổi common/models.py
# hoặc thêm/sửa endpoint; commit web/src/api/schema.d.ts cùng thay đổi đó.
gen-api:
	python scripts/export_openapi.py web/openapi.json
	cd web && npm run gen:api

web-check:
	cd web && npm run typecheck && npm test

# Chạy trước khi báo xong một vòng: lint, test API, kiểu và test giao diện
check: lint test gen-api web-check

# Dữ liệu demo qua API (cần make up); in mật khẩu tạm một lần lúc cấp. Chạy lại được.
seed-demo:
	python scripts/seed-demo.py $(ENV_FILE)
