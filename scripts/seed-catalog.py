"""Danh mục mẫu cho cửa hàng phụ kiện công nghệ: nhóm, sản phẩm, giá, tồn từng chi nhánh. Đi qua API.

Dùng: make seed-catalog  (hoặc python scripts/seed-catalog.py [.env]); chạy sau make seed-demo.
Hoặc truyền mật khẩu, không đọc .env: python scripts/seed-catalog.py --login admin=<mk>
  [--login nv-kho1=<mk>] [--login nv-ql1=<mk>]
Chạy lại nhiều lần được: thứ đã có thì bỏ qua.

Tồn chỉ đổi qua phiếu kho (TK-01) và chỉ NV kho lập phiếu nhập (4.2), nên mỗi chi nhánh cần một NV kho:
chi nhánh chưa có thì tạo mới; NV kho không có mật khẩu trong --login thì trụ sở cấp lại mật khẩu tạm
(6.3) để đăng nhập, mật khẩu mới in ra ngay, mật khẩu cũ hết hiệu lực. Có --login nv-ql1 thì đặt ngưỡng
tồn CN1 (4.5, chỉ QL đặt): hàng dưới 300.000 ngưỡng 10, dưới 1.000.000 ngưỡng 4, còn lại 2.
"""

# ruff: noqa: E501 (bảng dữ liệu sản phẩm, mỗi sản phẩm một dòng)
from __future__ import annotations

import argparse
import importlib.util
import sys
from datetime import date
from pathlib import Path

import httpx

# Dùng lại read_env, check, login của seed-demo.py (tên file có gạch ngang nên không import thường được)
_spec = importlib.util.spec_from_file_location(
    "seed_demo", Path(__file__).with_name("seed-demo.py")
)
seed_demo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(seed_demo)
read_env, check, login, REPO_ROOT = (
    seed_demo.read_env,
    seed_demo.check,
    seed_demo.login,
    seed_demo.REPO_ROOT,
)

# Sản phẩm demo A–D giữ mã và giá 100.000 (kịch bản demo dựa vào), chỉ đổi tên cho giống thật
DEMO_GROUP = ("NHOM1", "Đồng giá 100K")
DEMO_NAMES = {
    "A": "Cáp sạc USB-C to USB-C 1m",
    "B": "Ốp lưng dẻo trong suốt (nhiều dòng máy)",
    "C": "Giá đỡ điện thoại để bàn",
    "D": "Kính cường lực camera (nhiều dòng máy)",
}

GROUPS = {
    "OPLUNG": "Ốp lưng",
    "CUONGLUC": "Kính cường lực & dán màn hình",
    "CUSAC": "Củ sạc & sạc không dây",
    "CAP": "Cáp sạc & cáp chuyển",
    "SACDP": "Sạc dự phòng",
    "TAINGHE": "Tai nghe",
    "LOA": "Loa bluetooth",
    "CHUOTPHIM": "Chuột & bàn phím",
    "LUUTRU": "Thẻ nhớ & lưu trữ",
    "DEOTAY": "Đồng hồ & vòng đeo thông minh",
    "PHUKIEN": "Giá đỡ & phụ kiện khác",
}

# (mã, tên, nhóm, đơn vị, giá, (tồn CN1, CN2, CN3)); hàng rẻ bán chạy tồn nhiều, hàng đắt tồn ít.
# Giữ mỗi sản phẩm một dòng cho dễ đọc như bảng.
# fmt: off
PRODUCTS = [
    ("OP-001", "Ốp lưng MagSafe trong suốt iPhone 16 Pro Max", "OPLUNG", "cái", 390_000, (25, 18, 12)),
    ("OP-002", "Ốp lưng MagSafe trong suốt iPhone 16 Pro", "OPLUNG", "cái", 390_000, (22, 15, 10)),
    ("OP-003", "Ốp lưng silicon MagSafe iPhone 15", "OPLUNG", "cái", 290_000, (30, 20, 14)),
    ("OP-004", "Ốp lưng chống sốc Galaxy S25 Ultra", "OPLUNG", "cái", 350_000, (12, 8, 6)),
    ("OP-005", "Ốp lưng da Galaxy Z Fold6", "OPLUNG", "cái", 690_000, (4, 2, 0)),
    ("OP-006", "Ốp lưng nhám chống vân tay Xiaomi 14T", "OPLUNG", "cái", 190_000, (15, 10, 8)),
    ("OP-007", "Ốp lưng dẻo trong OPPO Reno12", "OPLUNG", "cái", 120_000, (20, 14, 9)),
    ("OP-008", "Bao da iPad Air 11 inch kèm khay bút", "OPLUNG", "cái", 450_000, (6, 4, 3)),
    ("CL-001", "Kính cường lực full màn iPhone 16 Pro Max", "CUONGLUC", "miếng", 250_000, (40, 30, 20)),
    ("CL-002", "Kính cường lực chống nhìn trộm iPhone 16 Pro", "CUONGLUC", "miếng", 290_000, (35, 22, 18)),
    ("CL-003", "Kính cường lực dán UV Galaxy S25 Ultra", "CUONGLUC", "miếng", 320_000, (10, 8, 5)),
    ("CL-004", "Bộ dán bảo vệ camera iPhone 16 Pro", "CUONGLUC", "bộ", 150_000, (30, 25, 15)),
    ("CL-005", "Dán màn hình PPF iPad Pro 13 inch", "CUONGLUC", "miếng", 350_000, (5, 3, 0)),
    ("CL-006", "Kính cường lực Redmi Note 14", "CUONGLUC", "miếng", 90_000, (45, 30, 25)),
    ("CS-001", "Củ sạc Apple USB-C 20W", "CUSAC", "cái", 490_000, (20, 15, 10)),
    ("CS-002", "Củ sạc Anker Nano 30W GaN", "CUSAC", "cái", 450_000, (18, 12, 8)),
    ("CS-003", "Củ sạc Ugreen Nexode 65W 3 cổng GaN", "CUSAC", "cái", 890_000, (8, 6, 4)),
    ("CS-004", "Củ sạc Baseus 100W 4 cổng GaN", "CUSAC", "cái", 1_290_000, (4, 3, 2)),
    ("CS-005", "Củ sạc Samsung 25W Super Fast Charging", "CUSAC", "cái", 390_000, (15, 10, 7)),
    ("CS-006", "Củ sạc Xiaomi 67W kèm cáp USB-C", "CUSAC", "bộ", 590_000, (10, 6, 5)),
    ("CS-007", "Sạc không dây MagSafe Apple 15W", "CUSAC", "cái", 1_090_000, (5, 3, 2)),
    ("CP-001", "Cáp Apple USB-C to Lightning 1m", "CAP", "sợi", 490_000, (25, 15, 10)),
    ("CP-002", "Cáp Apple USB-C 240W 2m bện dù", "CAP", "sợi", 690_000, (12, 8, 5)),
    ("CP-003", "Cáp Anker PowerLine III USB-C 1.8m", "CAP", "sợi", 290_000, (30, 20, 15)),
    ("CP-004", "Cáp Ugreen USB-A to USB-C 3A 1m", "CAP", "sợi", 120_000, (50, 35, 30)),
    ("CP-005", "Cáp Baseus 3 đầu Lightning/Micro/Type-C 1.2m", "CAP", "sợi", 150_000, (40, 25, 20)),
    ("CP-006", "Cáp chuyển Ugreen USB-C sang HDMI 4K", "CAP", "sợi", 390_000, (8, 5, 3)),
    ("CP-007", "Hub chuyển Ugreen USB-C 6 trong 1", "CAP", "cái", 790_000, (6, 4, 2)),
    ("DP-001", "Sạc dự phòng Anker 10000mAh 22.5W", "SACDP", "cái", 590_000, (15, 10, 8)),
    ("DP-002", "Sạc dự phòng Xiaomi 20000mAh 33W", "SACDP", "cái", 650_000, (12, 9, 6)),
    ("DP-003", "Sạc dự phòng MagSafe Baseus 10000mAh 20W", "SACDP", "cái", 890_000, (8, 5, 4)),
    ("DP-004", "Sạc dự phòng Anker Prime 26250mAh 300W", "SACDP", "cái", 3_290_000, (2, 1, 0)),
    ("DP-005", "Sạc dự phòng Samsung 10000mAh 25W", "SACDP", "cái", 790_000, (6, 4, 3)),
    ("TN-001", "Tai nghe Apple AirPods 4", "TAINGHE", "cái", 3_290_000, (6, 4, 3)),
    ("TN-002", "Tai nghe Apple AirPods Pro 2 USB-C", "TAINGHE", "cái", 5_990_000, (4, 2, 2)),
    ("TN-003", "Tai nghe Samsung Galaxy Buds3 Pro", "TAINGHE", "cái", 4_490_000, (3, 2, 1)),
    ("TN-004", "Tai nghe Sony WF-1000XM5", "TAINGHE", "cái", 5_490_000, (2, 1, 0)),
    ("TN-005", "Tai nghe Soundpeats Air4", "TAINGHE", "cái", 890_000, (10, 8, 6)),
    ("TN-006", "Tai nghe Xiaomi Redmi Buds 6 Active", "TAINGHE", "cái", 390_000, (20, 15, 12)),
    ("TN-007", "Tai nghe chụp tai Sony WH-1000XM5", "TAINGHE", "cái", 7_490_000, (2, 1, 1)),
    ("TN-008", "Tai nghe có dây Apple EarPods USB-C", "TAINGHE", "cái", 590_000, (15, 10, 8)),
    ("LO-001", "Loa bluetooth JBL Flip 6", "LOA", "cái", 2_690_000, (4, 3, 2)),
    ("LO-002", "Loa bluetooth JBL Go 4", "LOA", "cái", 1_090_000, (8, 6, 4)),
    ("LO-003", "Loa bluetooth Marshall Emberton II", "LOA", "cái", 3_990_000, (2, 1, 1)),
    ("LO-004", "Loa bluetooth Xiaomi Portable 16W", "LOA", "cái", 690_000, (6, 4, 3)),
    ("LO-005", "Loa bluetooth Tronsmart T7 Lite", "LOA", "cái", 790_000, (5, 3, 2)),
    ("CB-001", "Chuột không dây Logitech M331 Silent", "CHUOTPHIM", "cái", 350_000, (15, 10, 8)),
    ("CB-002", "Chuột Logitech MX Master 3S", "CHUOTPHIM", "cái", 2_490_000, (3, 2, 1)),
    ("CB-003", "Bàn phím bluetooth Logitech K380", "CHUOTPHIM", "cái", 790_000, (8, 5, 4)),
    ("CB-004", "Bàn phím cơ không dây Akko 3068B Plus", "CHUOTPHIM", "cái", 1_690_000, (3, 2, 0)),
    ("CB-005", "Lót chuột cỡ lớn 80x30cm", "CHUOTPHIM", "cái", 150_000, (20, 12, 10)),
    ("LT-001", "Thẻ nhớ microSD SanDisk Ultra 64GB", "LUUTRU", "cái", 190_000, (30, 20, 15)),
    ("LT-002", "Thẻ nhớ microSD Samsung EVO Plus 128GB", "LUUTRU", "cái", 320_000, (25, 15, 10)),
    ("LT-003", "USB SanDisk Ultra Flair 64GB USB 3.0", "LUUTRU", "cái", 220_000, (20, 12, 10)),
    ("LT-004", "Ổ cứng SSD di động Samsung T7 1TB", "LUUTRU", "cái", 2_690_000, (3, 2, 1)),
    ("LT-005", "Đầu đọc thẻ Ugreen USB-C 2 khe", "LUUTRU", "cái", 190_000, (10, 6, 5)),
    ("DH-001", "Apple Watch SE 2024 GPS 40mm", "DEOTAY", "chiếc", 6_290_000, (2, 1, 1)),
    ("DH-002", "Vòng đeo tay Xiaomi Smart Band 9", "DEOTAY", "chiếc", 890_000, (10, 6, 5)),
    ("DH-003", "Samsung Galaxy Watch7 40mm", "DEOTAY", "chiếc", 5_490_000, (2, 1, 0)),
    ("DH-004", "Dây đeo silicon Apple Watch 41mm", "DEOTAY", "cái", 190_000, (20, 15, 10)),
    ("DH-005", "Huawei Watch Fit 3", "DEOTAY", "chiếc", 2_990_000, (3, 2, 1)),
    ("PK-001", "Giá đỡ điện thoại ô tô kẹp cửa gió Baseus", "PHUKIEN", "cái", 290_000, (12, 8, 6)),
    ("PK-002", "Gậy chụp ảnh tripod bluetooth Xiaomi", "PHUKIEN", "cái", 450_000, (8, 5, 4)),
    ("PK-003", "Đèn livestream vòng 26cm kèm chân", "PHUKIEN", "bộ", 390_000, (5, 3, 2)),
    ("PK-004", "Giá đỡ laptop nhôm gấp gọn", "PHUKIEN", "cái", 350_000, (6, 4, 3)),
    ("PK-005", "Bút cảm ứng Apple Pencil (USB-C)", "PHUKIEN", "cái", 2_190_000, (3, 2, 1)),
    ("PK-006", "Thiết bị định vị Apple AirTag", "PHUKIEN", "cái", 790_000, (8, 5, 4)),
    ("PK-007", "Túi chống sốc laptop 14 inch", "PHUKIEN", "cái", 250_000, (10, 7, 5)),
]
# fmt: on
BRANCHES = ["CN1", "CN2", "CN3"]
# Tồn của 4 sản phẩm demo A–D (đồng giá 100.000) theo CN1, CN2, CN3
DEMO_STOCK = (20, 15, 10)
# NV kho tạo mới cho chi nhánh chưa có: (mã, họ tên, chi nhánh)
NEW_WAREHOUSE = [("NV-KHO2", "Phạm Văn Đức", "CN2"), ("NV-KHO3", "Võ Thị Hà", "CN3")]


def min_level(price: int) -> int:
    """Ngưỡng tồn mẫu theo giá: hàng rẻ bán nhanh cần dự trữ nhiều hơn."""
    return 10 if price < 300_000 else 4 if price < 1_000_000 else 2


def main() -> None:
    sys.stdout.reconfigure(errors="replace")  # console Windows không in được mọi ký tự
    parser = argparse.ArgumentParser()
    parser.add_argument("env", nargs="?", default=str(REPO_ROOT / ".env"))
    parser.add_argument("--login", action="append", default=[], metavar="TEN=MATKHAU")
    args = parser.parse_args()
    passwords = dict(item.split("=", 1) for item in args.login)
    if "admin" in passwords:
        env = {"ADMIN_USERNAME": "admin", "ADMIN_PASSWORD": passwords["admin"]}
    else:
        env = read_env(Path(args.env))
    api = httpx.Client(base_url=f"http://localhost:{env.get('WEB_PORT', '3000')}/api", timeout=30)
    hq = login(api, env["ADMIN_USERNAME"], env["ADMIN_PASSWORD"])

    groups = {g["group_id"]: g for g in check(hq.get("/product-groups"))}
    if DEMO_GROUP[0] in groups and groups[DEMO_GROUP[0]]["name"] != DEMO_GROUP[1]:
        check(hq.patch(f"/product-groups/{DEMO_GROUP[0]}", json={"name": DEMO_GROUP[1]}))
        print(f"Doi ten nhom {DEMO_GROUP[0]}")
    for group_id, name in GROUPS.items():
        if group_id not in groups:
            check(hq.post("/product-groups", json={"group_id": group_id, "name": name}))
    products = {p["product_id"]: p for p in check(hq.get("/products"))}
    for product_id, name in DEMO_NAMES.items():
        if product_id in products and products[product_id]["name"] != name:
            check(hq.patch(f"/products/{product_id}", json={"name": name}))
    created = 0
    for product_id, name, group_id, unit, price, _ in PRODUCTS:
        if product_id not in products:
            body = {
                "product_id": product_id,
                "name": name,
                "group_id": group_id,
                "unit": unit,
                "price": price,
            }
            check(hq.post("/products", json=body))
            created += 1
    print(f"Danh muc: {len(GROUPS)} nhom, {len(PRODUCTS)} san pham (tao moi {created})")

    # Chi nhánh đã có tồn hàng mẫu thì bỏ qua (xem qua báo cáo tồn của trụ sở)
    today = date.today().isoformat()
    active = {b["branch_id"] for b in check(hq.get("/branches")) if b["status"] == "ACTIVE"}
    pending = []
    for branch_id in BRANCHES:
        if branch_id not in active:
            print(f"Bo qua {branch_id}: chua co hoac ngung hoat dong")
            continue
        report = check(
            hq.get("/reports/stock", params={"from": today, "to": today, "branch_id": branch_id})
        )
        mock_ids = {p[0] for p in PRODUCTS}
        if any(line["product_id"] in mock_ids and line["quantity"] for line in report["lines"]):
            print(f"{branch_id} da co ton hang mau")
        else:
            pending.append(branch_id)

    employees = check(hq.get("/employees"))
    for employee_id, full_name, branch_id in NEW_WAREHOUSE:
        if branch_id in pending and not any(e["employee_id"] == employee_id for e in employees):
            body = {
                "employee_id": employee_id,
                "full_name": full_name,
                "hired_on": today,
                "role": "WAREHOUSE",
                "branch_id": branch_id,
            }
            employees.append(check(hq.post("/employees", json=body)))
            print(f"Tao NV kho {employee_id} ({branch_id})")

    for index, branch_id in enumerate(BRANCHES):
        if branch_id not in pending:
            continue
        keeper = next(
            (
                e
                for e in employees
                if e["branch_id"] == branch_id
                and e["role"] == "WAREHOUSE"
                and e["status"] == "WORKING"
            ),
            None,
        )
        if keeper is None:
            print(f"Bo qua {branch_id}: khong co NV kho")
            continue
        employee_id = keeper["employee_id"]
        if keeper["username"] in passwords:  # đã có mật khẩu: giữ nguyên tài khoản
            warehouse = login(api, keeper["username"], passwords[keeper["username"]])
        else:
            if keeper["username"] is None:
                path, body = f"/employees/{employee_id}/account", {"username": employee_id.lower()}
            else:
                path, body = f"/employees/{employee_id}/account/reset-password", None
            issued = check(hq.post(path, json=body))
            # In ngay: bước sau lỗi thì script dừng, mật khẩu chưa in là mất
            print(f"Mat khau tam moi {issued['username']}: {issued['temporary_password']}")
            if issued["account_status"] != "ACTIVE":
                print(f"Bo qua {branch_id}: tai khoan {employee_id} dang bi khoa")
                continue
            warehouse = login(api, issued["username"], issued["temporary_password"])
        items = [{"product_id": p[0], "quantity": p[5][index]} for p in PRODUCTS if p[5][index] > 0]
        items += [{"product_id": pid, "quantity": DEMO_STOCK[index]} for pid in DEMO_NAMES]
        slip = {
            "type": "IN_WAREHOUSE",
            "counterparty": "Kho tổng Hà Nội",
            "delivery_no": f"MOCK-NHAP-{branch_id}",
            "items": items,
        }
        # 409 DUPLICATE TK-02: phiếu giao này đã ghi nhập
        check(warehouse.post("/stock-slips/inbound", json=slip), 201, 409)
        units = sum(item["quantity"] for item in items)
        print(f"Nhap ton {branch_id}: {len(items)} ma, {units} san pham")

    if "nv-ql1" in passwords:  # ngưỡng tồn CN1 để trang Cảnh báo tồn có số liệu (TK-05)
        manager = login(api, "nv-ql1", passwords["nv-ql1"])
        prices = {p[0]: p[4] for p in PRODUCTS} | dict.fromkeys(DEMO_NAMES, 100_000)
        for product_id, price in prices.items():
            body = {"min_level": min_level(price)}
            check(manager.put(f"/stock/{product_id}/min-level", json=body))
        print(f"Dat nguong ton CN1 cho {len(prices)} ma")
    print("Mat khau tam o tren chi in mot lan; mat khau cu cua cac tai khoan do het hieu luc.")


if __name__ == "__main__":
    main()
