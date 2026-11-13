"""Tạo dữ liệu demo qua API (không SQL trực tiếp), theo mã cố định ở docs/tests.md mục 2.

Dùng: make seed-demo  (hoặc python scripts/seed-demo.py [.env]); cần hệ thống đang chạy (make up).
Đăng nhập bằng tài khoản trụ sở ADMIN_USERNAME, ADMIN_PASSWORD trong .env. Chạy lại nhiều lần được:
thứ đã có thì bỏ qua. Mật khẩu demo là mật khẩu tạm do API 6.3 sinh ngẫu nhiên, chỉ in ra một
lần lúc cấp, không ghi file.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent

BRANCHES = ["CN1", "CN2"]
# (mã, vai trò, chi nhánh, họ tên) theo docs/tests.md mục 2; tên đăng nhập = mã viết thường
EMPLOYEES = [
    ("NV-TS", "HQ", None, "Trụ sở demo"),
    ("NV-QL1", "MANAGER", "CN1", "Quản lý CN1"),
    ("NV-BH1", "SALES", "CN1", "Bán hàng CN1"),
    ("NV-TN1", "CASHIER", "CN1", "Thu ngân CN1"),
    ("NV-KHO1", "WAREHOUSE", "CN1", "Kho CN1"),
]
GROUP_ID = "NHOM1"
PRODUCTS = {"A": 100_000, "B": 100_000, "C": 100_000, "D": 100_000}
OPENING_QTY = 20
CUSTOMERS = [
    ("Nguyễn Văn An", "0901000001"),
    ("Trần Thị Bình", "0901000002"),
    ("Lê Minh Châu", "0901000003"),
]


def read_env(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep and not line.lstrip().startswith("#"):
            values[key.strip()] = value.strip()
    return values


def check(response: httpx.Response, *ok: int) -> dict:
    if response.status_code not in (ok or (200, 201)):
        sys.exit(f"Loi {response.status_code} {response.request.url.path}: {response.text}")
    return response.json()


def login(api: httpx.Client, username: str, password: str) -> httpx.Client:
    token = check(api.post("/auth/login", json={"username": username, "password": password}))
    return httpx.Client(
        base_url=api.base_url, headers={"Authorization": f"Bearer {token['token']}"}, timeout=30
    )


def main() -> None:
    sys.stdout.reconfigure(errors="replace")  # console Windows không in được mọi ký tự
    env = read_env(Path(sys.argv[1]) if len(sys.argv) > 1 else REPO_ROOT / ".env")
    api = httpx.Client(base_url=f"http://localhost:{env.get('WEB_PORT', '3000')}/api", timeout=30)
    hq = login(api, env["ADMIN_USERNAME"], env["ADMIN_PASSWORD"])

    existing = {b["branch_id"] for b in check(hq.get("/branches"))}
    for branch_id in BRANCHES:
        if branch_id not in existing:
            body = {
                "branch_id": branch_id,
                "name": f"Chi nhánh {branch_id}",
                "closing_time": "22:00",
            }
            check(hq.post("/branches", json=body))
            print(f"Tao chi nhanh {branch_id}")

    employees = {e["employee_id"]: e for e in check(hq.get("/employees"))}
    passwords: dict[str, str] = {}
    for employee_id, role, branch_id, full_name in EMPLOYEES:
        if employee_id not in employees:
            body = {
                "employee_id": employee_id,
                "full_name": full_name,
                "hired_on": date.today().isoformat(),
                "role": role,
                "branch_id": branch_id,
            }
            employees[employee_id] = check(hq.post("/employees", json=body))
            print(f"Tao nhan vien {employee_id} ({role})")
        if employees[employee_id]["username"] is None:
            issued = check(
                hq.post(f"/employees/{employee_id}/account", json={"username": employee_id.lower()})
            )
            passwords[employee_id] = issued["temporary_password"]

    if not any(g["group_id"] == GROUP_ID for g in check(hq.get("/product-groups"))):
        check(hq.post("/product-groups", json={"group_id": GROUP_ID, "name": "Nhóm demo"}))
        print(f"Tao nhom {GROUP_ID}")
    products = {p["product_id"] for p in check(hq.get("/products"))}
    for product_id, price in PRODUCTS.items():
        if product_id not in products:
            body = {
                "product_id": product_id,
                "name": f"Sản phẩm {product_id}",
                "group_id": GROUP_ID,
                "unit": "cái",
                "price": price,
            }
            check(hq.post("/products", json=body))
            print(f"Tao san pham {product_id}")

    # Tồn đầu kỳ và khách cần đăng nhập NV kho, NVBH: chỉ làm ở lần cấp tài khoản (biết mật khẩu).
    # shortcut: lần chạy trước dừng giữa chừng thì phần này bị bỏ qua; làm lại từ đầu: make reset.
    if "NV-KHO1" in passwords:
        warehouse = login(api, "nv-kho1", passwords["NV-KHO1"])
        body = {
            "type": "IN_WAREHOUSE",
            "counterparty": "Kho tổng",
            "delivery_no": "DEMO-TON-DAU-KY",
            "items": [{"product_id": p, "quantity": OPENING_QTY} for p in PRODUCTS],
        }
        # 409 DUPLICATE TK-02: phiếu giao này đã ghi nhập
        check(warehouse.post("/stock-slips/inbound", json=body), 201, 409)
        print(f"Nhap ton dau ky CN1: moi san pham {OPENING_QTY}")
    if "NV-BH1" in passwords:
        sales = login(api, "nv-bh1", passwords["NV-BH1"])
        for full_name, phone in CUSTOMERS:
            # 200 = số đã có hồ sơ, không đổi gì (2.1)
            check(sales.post("/customers", json={"full_name": full_name, "phone": phone}), 200, 201)
        print(f"Tao {len(CUSTOMERS)} khach hang")

    if passwords:
        print("\nMat khau tam (chi in mot lan, hay ghi lai):")
        for employee_id, password in passwords.items():
            print(f"  {employee_id.lower():10} {password}")
    else:
        print("Du lieu demo da co day du; tai khoan da cap tu lan chay truoc.")


if __name__ == "__main__":
    main()
