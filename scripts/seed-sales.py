"""Mô phỏng một ngày bán hàng qua API ở ba chi nhánh để báo cáo có số liệu. Chạy sau seed-catalog.

Dùng: python scripts/seed-sales.py --login admin=<mk> --login nv-bh1=<mk> --login nv-tn1=<mk>
      --login nv-ql1=<mk>
Mật khẩu nhận qua tham số, không ghi file. Mỗi lần chạy thêm một lượt đơn mới, thời điểm là lúc chạy
(hệ thống lấy giờ từ clock.now(), không lập chứng từ lùi ngày được).

Mọi bước đi qua API như người dùng thật: NVBH lập, chốt đơn (3.1); thu ngân mở ca (3.5), thu tiền
(3.2; thẻ, chuyển khoản do bank-mock gọi lại); vài đơn hủy kèm lý do (BH-04); vài đơn trả hàng: NVBH
lập phiếu, QL duyệt (CN2, CN3 không có QL dùng được nên trụ sở duyệt thay kèm lý do), thu ngân hoàn
(TH-04).
CN2, CN3 chưa có NVBH, thu ngân thì tạo mới; mật khẩu tạm in ra ngay khi cấp.
"""

from __future__ import annotations

import argparse
import importlib.util
import random
import sys
import time
from datetime import date
from pathlib import Path

import httpx

# Dùng lại read_env, check của seed-demo.py (tên file có gạch ngang nên không import thường được)
_spec = importlib.util.spec_from_file_location(
    "seed_demo", Path(__file__).with_name("seed-demo.py")
)
seed_demo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(seed_demo)
read_env, check, REPO_ROOT = seed_demo.read_env, seed_demo.check, seed_demo.REPO_ROOT

BANK_MOCK = "http://localhost:8001"
# (chi nhánh, số đơn, NVBH, thu ngân, QL duyệt trả hàng hoặc None = trụ sở duyệt thay)
BRANCHES = [
    ("CN1", 32, "nv-bh1", "nv-tn1", "nv-ql1"),
    ("CN2", 20, "nv-bh2", "nv-tn2", None),
    ("CN3", 14, "nv-bh3", "nv-tn3", None),
]
NEW_STAFF = {
    "NV-BH2": ("Nguyễn Thị Lan", "SALES", "CN2"),
    "NV-TN2": ("Trần Quốc Bảo", "CASHIER", "CN2"),
    "NV-BH3": ("Lê Hoàng Nam", "SALES", "CN3"),
    "NV-TN3": ("Đỗ Thu Trang", "CASHIER", "CN3"),
}
CUSTOMERS = [
    ("Phạm Minh Tuấn", "0912345601"),
    ("Hoàng Thu Hà", "0912345602"),
    ("Vũ Đức Anh", "0912345603"),
    ("Đặng Ngọc Mai", "0912345604"),
    ("Bùi Quang Huy", "0912345605"),
    ("Ngô Thanh Hương", "0912345606"),
    ("Dương Văn Khoa", "0912345607"),
    ("Lý Thị Ngọc", "0912345608"),
    ("Trịnh Gia Bảo", "0912345609"),
    ("Mai Phương Thảo", "0912345610"),
    ("Hồ Đức Thắng", "0912345611"),
    ("Tạ Minh Châu", "0912345612"),
]
METHODS = ["CASH"] * 5 + ["TRANSFER"] * 3 + ["CARD"] * 2
CANCEL_RATE, RETURN_RATE, REGISTERED_RATE = 0.06, 0.07, 0.3
CANCEL_REASONS = ["Khách đổi ý không mua", "Khách chê giá cao", "Hết màu khách chọn"]
RETURN_REASONS = [
    ("Không tương thích với máy của khách", False),
    ("Khách đổi ý trong 7 ngày", False),
    ("Sản phẩm lỗi khi dùng thử", True),
]


def session(api: httpx.Client, username: str, password: str) -> httpx.Client:
    token = check(api.post("/auth/login", json={"username": username, "password": password}))
    return httpx.Client(
        base_url=api.base_url, headers={"Authorization": f"Bearer {token['token']}"}, timeout=30
    )


def pick_items(rng: random.Random, stock: dict[str, list[int]]) -> dict[str, int]:
    """1–3 dòng, ưu tiên hàng rẻ (phụ kiện bán chạy); không vượt tồn khả dụng còn lại.
    `stock`: mã -> [tồn khả dụng, giá]."""
    ids = [pid for pid, (qty, _) in stock.items() if qty > 0]
    if not ids:
        return {}
    weights = [1 / stock[pid][1] ** 0.5 for pid in ids]
    items: dict[str, int] = {}
    for pid in rng.choices(ids, weights, k=rng.choice([1, 1, 1, 2, 2, 3])):
        wanted = rng.choice([1, 1, 2, 3]) if stock[pid][1] <= 300_000 else 1
        items[pid] = min(stock[pid][0], wanted)
    return items


def wait_completed(client: httpx.Client, order_id: str) -> bool:
    """Thẻ, chuyển khoản: chờ bank-mock gọi lại (thường vài trăm ms)."""
    for _ in range(25):
        if check(client.get(f"/orders/{order_id}"))["status"] == "COMPLETED":
            return True
        time.sleep(0.2)
    return False


def ensure_staff(hq: httpx.Client, passwords: dict[str, str]) -> None:
    employees = {e["employee_id"] for e in check(hq.get("/employees"))}
    for employee_id, (full_name, role, branch_id) in NEW_STAFF.items():
        if employee_id in employees:
            continue
        body = {
            "employee_id": employee_id,
            "full_name": full_name,
            "hired_on": date.today().isoformat(),
            "role": role,
            "branch_id": branch_id,
        }
        check(hq.post("/employees", json=body))
        username = employee_id.lower()
        issued = check(hq.post(f"/employees/{employee_id}/account", json={"username": username}))
        passwords[username] = issued["temporary_password"]
        print(f"Tao {employee_id} ({role}, {branch_id}), mat khau tam: {passwords[username]}")


def run_branch(
    api: httpx.Client,
    hq: httpx.Client,
    passwords: dict[str, str],
    customers: list[str],
    rng: random.Random,
    branch: tuple,
) -> None:
    branch_id, count, sales_user, cashier_user, manager_user = branch
    sales = session(api, sales_user, passwords[sales_user])
    cashier = session(api, cashier_user, passwords[cashier_user])
    approver = session(api, manager_user, passwords[manager_user]) if manager_user else hq
    if check(cashier.get("/shifts/current")) is None:  # null = chưa có ca Đang mở
        check(cashier.post("/shifts", json={"opening_cash": 2_000_000}))
        print(f"{branch_id}: mo ca {cashier_user}")
    # Chỉ bán sản phẩm Đang bán còn tồn khả dụng (BH-02, TK-01)
    prices = {
        p["product_id"]: p["current_price"]
        for p in check(sales.get("/products"))
        if p["status"] == "ON_SALE"
    }
    stock = {
        line["product_id"]: [line["available"], prices[line["product_id"]]]
        for line in check(sales.get("/stock"))
        if line["available"] > 0 and line["product_id"] in prices
    }

    done, cancelled, cash_orders = 0, 0, []
    for _ in range(count):
        items = pick_items(rng, stock)
        if not items:
            break
        customer = rng.choice(customers) if rng.random() < REGISTERED_RATE else "KHLE"
        body = {
            "customer_id": customer,
            "items": [{"product_id": p, "quantity": q} for p, q in items.items()],
        }
        order_id = check(sales.post("/orders", json=body), 201)["order_id"]
        check(sales.post(f"/orders/{order_id}/confirm"))
        if rng.random() < CANCEL_RATE:
            reason = rng.choice(CANCEL_REASONS)
            check(sales.post(f"/orders/{order_id}/cancel", json={"reason": reason}))
            cancelled += 1
            continue
        method = rng.choice(METHODS)
        txn = check(cashier.post(f"/orders/{order_id}/payments", json={"method": method}), 201)
        if method == "CASH":
            check(
                cashier.post(
                    f"/transactions/{txn['txn_id']}/confirm-cash", json={"result": "SUCCESS"}
                )
            )
            cash_orders.append((order_id, items))
        elif not wait_completed(sales, order_id):
            print(f"{branch_id}: {order_id} chua co ket qua tu bank-mock, de thu ngan tra soat")
            continue
        for pid, qty in items.items():
            stock[pid][0] -= qty
        done += 1

    returned = 0
    for order_id, items in cash_orders:
        if rng.random() >= RETURN_RATE:
            continue
        pid = next(iter(items))
        reason, defective = rng.choice(RETURN_REASONS)
        body = {
            "order_id": order_id,
            "reason": reason,
            "invoice_presented": True,
            "items": [
                {
                    "product_id": pid,
                    "good_qty": 0 if defective else 1,
                    "defective_qty": int(defective),
                }
            ],
        }
        return_id = check(sales.post("/returns", json=body), 201)["return_id"]
        note = None if manager_user else f"Trụ sở duyệt thay, {branch_id} chưa có quản lý trực"
        check(approver.post(f"/returns/{return_id}/approve", json={"decision_note": note}))
        refund = check(cashier.post(f"/returns/{return_id}/refunds"), 201)
        check(
            cashier.post(
                f"/transactions/{refund['txn_id']}/confirm-cash", json={"result": "SUCCESS"}
            )
        )
        returned += 1
    print(
        f"{branch_id}: {done} don hoan tat, {cancelled} don huy, {returned} phieu tra da hoan tien"
    )


def main() -> None:
    sys.stdout.reconfigure(errors="replace")  # console Windows không in được mọi ký tự
    parser = argparse.ArgumentParser()
    parser.add_argument("--login", action="append", default=[], metavar="TEN=MATKHAU")
    parser.add_argument("--env", default=str(REPO_ROOT / ".env"))
    parser.add_argument("--seed", type=int, help="cố định ngẫu nhiên để chạy lại ra cùng kết quả")
    args = parser.parse_args()
    passwords = dict(item.split("=", 1) for item in args.login)
    env = read_env(Path(args.env))
    rng = random.Random(args.seed)
    api = httpx.Client(base_url=f"http://localhost:{env.get('WEB_PORT', '3000')}/api", timeout=30)
    hq = session(api, "admin", passwords["admin"])

    ensure_staff(hq, passwords)
    missing = [u for b in BRANCHES for u in b[2:5] if u and u not in passwords]
    if missing:
        sys.exit(f"Thieu mat khau: {', '.join(missing)} (them --login ten=matkhau)")
    try:  # thẻ, chuyển khoản luôn thành công trong lượt mô phỏng này
        httpx.put(f"{BANK_MOCK}/mode", json={"mode": "SUCCESS"}, timeout=5).raise_for_status()
    except httpx.HTTPError:
        sys.exit("Khong goi duoc bank-mock o cong 8001 (make up)")

    # Khách có hồ sơ dùng chung toàn chuỗi; 200 = số đã có hồ sơ, trả hồ sơ có sẵn (2.1)
    sales = session(api, "nv-bh1", passwords["nv-bh1"])
    customers = [
        check(sales.post("/customers", json={"full_name": name, "phone": phone}), 200, 201)[
            "customer_id"
        ]
        for name, phone in CUSTOMERS
    ]
    try:
        for branch in BRANCHES:
            run_branch(api, hq, passwords, customers, rng, branch)
    finally:  # trả về chế độ mặc định: thu ngân tự bấm kết quả ngân hàng trên giao diện
        httpx.put(f"{BANK_MOCK}/mode", json={"mode": "SILENT"}, timeout=5)


if __name__ == "__main__":
    main()
