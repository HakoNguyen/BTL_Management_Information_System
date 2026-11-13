"""5.1, 5.2, 5.3, 5.5: báo cáo chỉ đọc (DT-01 đến DT-05, TK-01, TK-05, K-01)."""

from __future__ import annotations

from datetime import datetime

import asyncpg
import httpx
import pytest
from fixtures import (
    BRANCH_1,
    BRANCH_2,
    CASHIER_ID,
    HQ_ID,
    MANAGER_ID,
    SALES_ID,
    WAREHOUSE_ID,
    complete_order,
    create_awaiting_order,
    create_return,
    login_as,
    open_shift,
    resolve_txn,
    seed_employee,
    seed_product,
    seed_staff,
    seed_stock,
    start_payment,
)

from common import clock
from common.clock import VN_TZ
from common.constants import (
    ErrorCode,
    LevelStatus,
    ProductStatus,
    RankBy,
    Role,
    SlipType,
    TxnMethod,
    TxnStatus,
    TxnType,
)

pytestmark = pytest.mark.db

DAY = {"from": "2026-11-03", "to": "2026-11-03"}


def _at(day: int, hour: int = 10) -> datetime:
    return datetime(2026, 11, day, hour, 0, tzinfo=VN_TZ)


async def _get(client: httpx.AsyncClient, path: str, headers: dict, **params: str) -> dict:
    response = await client.get(path, params={**DAY, **params}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _error(response: httpx.Response, status: int, code: ErrorCode, rule: str | None) -> None:
    assert response.status_code == status, response.text
    body = response.json()
    assert body["error_code"] == code
    assert body["details"].get("rule") == rule


async def test_report_access(client: httpx.AsyncClient, conn: asyncpg.Connection) -> None:
    """K-01: đúng vai trò; vai trò chi nhánh chỉ xem chi nhánh mình; kỳ hợp lệ."""
    await seed_staff(conn)
    ql = await login_as(client, MANAGER_ID)
    kho = await login_as(client, WAREHOUSE_ID)
    bh = await login_as(client, SALES_ID)
    tn = await login_as(client, CASHIER_ID)
    for path, denied in (
        ("/reports/revenue", (kho, bh, tn)),
        ("/reports/products", (kho, bh, tn)),
        ("/reports/stock", (bh, tn)),
        ("/reports/staff-sales", (kho, tn)),
    ):
        for headers in denied:
            response = await client.get(path, params=DAY, headers=headers)
            _error(response, 403, ErrorCode.FORBIDDEN, "K-01")
    for path, headers in (("/reports/revenue", ql), ("/reports/stock", kho)):
        response = await client.get(path, params={**DAY, "branch_id": BRANCH_2}, headers=headers)
        _error(response, 403, ErrorCode.FORBIDDEN, "K-01")
        assert (
            await client.get(path, params={**DAY, "branch_id": BRANCH_1}, headers=headers)
        ).is_success
    bad = {"from": "2026-11-04", "to": "2026-11-03"}
    _error(
        await client.get("/reports/revenue", params=bad, headers=ql),
        400,
        ErrorCode.VALIDATION_ERROR,
        None,
    )
    _error(
        await client.get("/reports/revenue", params={"to": "2026-11-03"}, headers=ql),
        400,
        ErrorCode.VALIDATION_ERROR,
        None,
    )


async def _sell_registered(
    client: httpx.AsyncClient, sales: dict, cashier: dict, items: dict[str, int]
) -> str:
    response = await client.post(
        "/customers", json={"full_name": "Khách Bình", "phone": "0912345678"}, headers=sales
    )
    assert response.status_code in (200, 201), response.text
    body = {
        "customer_id": response.json()["customer_id"],
        "items": [{"product_id": pid, "quantity": qty} for pid, qty in items.items()],
    }
    response = await client.post("/orders", json=body, headers=sales)
    order_id = response.json()["order_id"]
    assert (await client.post(f"/orders/{order_id}/confirm", headers=sales)).is_success
    txn = await start_payment(client, cashier, order_id, TxnMethod.CASH)
    await resolve_txn(client, cashier, txn, TxnStatus.SUCCESS)
    return order_id


async def test_revenue_and_staff_totals(
    client: httpx.AsyncClient, conn: asyncpg.Connection
) -> None:
    """DT-01, DT-04, DT-05: theo chi nhánh; theo nhân viên = theo chi nhánh = toàn chuỗi."""
    await seed_staff(conn)
    await seed_employee(conn, "NV-BH2", Role.SALES, BRANCH_2)
    await seed_employee(conn, "NV-TN2", Role.CASHIER, BRANCH_2)
    await seed_product(conn, "A")
    await seed_stock(conn, BRANCH_1, "A", 20)
    await seed_stock(conn, BRANCH_2, "A", 20)
    clock.freeze(_at(3))
    hq = await login_as(client, HQ_ID)
    ql = await login_as(client, MANAGER_ID)
    bh = await login_as(client, SALES_ID)
    tn = await login_as(client, CASHIER_ID)
    bh2 = await login_as(client, "NV-BH2")
    tn2 = await login_as(client, "NV-TN2")
    shift_id = await open_shift(client, tn)
    await open_shift(client, tn2)

    await _sell_registered(client, bh, tn, {"A": 3})  # CN1, NVBH, khách có hồ sơ 300.000
    await complete_order(client, ql, tn, {"A": 1})  # CN1, QL, KHLE 100.000
    await complete_order(client, bh2, tn2, {"A": 2}, TxnMethod.CARD)  # CN2 200.000
    cancelled = await create_awaiting_order(client, bh, {"A": 1})
    response = await client.post(
        f"/orders/{cancelled}/cancel", json={"reason": "Khách đổi ý"}, headers=bh
    )
    assert response.status_code == 200, response.text
    response = await client.post(
        f"/shifts/{shift_id}/close",
        json={"counted_cash": 390_000, "variance_reason": "Thiếu tiền lẻ"},
        headers=tn,
    )
    assert response.status_code == 200, response.text

    report = await _get(client, "/reports/revenue", hq)
    assert (report["branch_id"], report["from_date"], report["to_date"]) == (
        None,
        "2026-11-03",
        "2026-11-03",
    )
    branches = {line["branch_id"]: line for line in report["branches"]}
    cn1, cn2, total = branches[BRANCH_1], branches[BRANCH_2], report["total"]
    assert (cn1["order_count"], cn1["gross_revenue"], cn1["average_order_value"]) == (
        2,
        400_000,
        200_000,
    )
    assert (cn1["registered_revenue"], cn1["walk_in_revenue"]) == (300_000, 100_000)
    assert cn1["cancellations"] == [{"reason": "Khách đổi ý", "count": 1}]
    assert cn1["shift_variance"] == -10_000
    assert cn1["payments"] == [
        {"type": TxnType.COLLECT, "method": TxnMethod.CASH, "amount": 400_000}
    ]
    assert cn2["payments"] == [
        {"type": TxnType.COLLECT, "method": TxnMethod.CARD, "amount": 200_000}
    ]
    assert (total["branch_id"], total["order_count"], total["gross_revenue"]) == (None, 3, 600_000)
    assert total["net_revenue"] == cn1["net_revenue"] + cn2["net_revenue"]
    assert report["previous"]["order_count"] == 0
    assert report["previous"]["average_order_value"] is None

    # QL chỉ thấy chi nhánh mình
    mine = await _get(client, "/reports/revenue", ql)
    assert mine["branch_id"] == BRANCH_1
    assert [line["branch_id"] for line in mine["branches"]] == [BRANCH_1]

    # Theo nhân viên: xếp hạng trong chi nhánh, cộng lại bằng toàn chuỗi
    lines = (await _get(client, "/reports/staff-sales", hq))["lines"]
    assert [(x["branch_id"], x["employee_id"], x["rank"]) for x in lines] == [
        (BRANCH_1, SALES_ID, 1),
        (BRANCH_1, MANAGER_ID, 2),
        (BRANCH_2, "NV-BH2", 1),
    ]
    assert sum(x["gross_revenue"] for x in lines) == total["gross_revenue"]
    assert [x["cancelled_count"] for x in lines] == [1, 0, 0]

    # NVBH chỉ thấy dòng của mình
    own = (await _get(client, "/reports/staff-sales", bh))["lines"]
    assert [(x["employee_id"], x["gross_revenue"], x["rank"]) for x in own] == [
        (SALES_ID, 300_000, 1)
    ]


async def test_product_sales(client: httpx.AsyncClient, conn: asyncpg.Connection) -> None:
    """DT-02, DT-05: lượng bán gộp, trả, thuần theo sản phẩm, nhóm; thứ hạng kỳ trước; chậm bán."""
    await seed_staff(conn)
    for product_id in "ABCD":
        await seed_product(conn, product_id)
        await seed_stock(conn, BRANCH_1, product_id, 20)
    clock.freeze(_at(2))
    hq = await login_as(client, HQ_ID)
    ql = await login_as(client, MANAGER_ID)
    bh = await login_as(client, SALES_ID)
    tn = await login_as(client, CASHIER_ID)
    await open_shift(client, tn)
    response = await client.put(
        "/products/D/status", json={"status": ProductStatus.DISCONTINUED}, headers=hq
    )
    assert response.status_code == 200, response.text

    # Kỳ trước (02/11): A 3, B 1
    old = await complete_order(client, bh, tn, {"A": 3, "B": 1})
    # Kỳ này (03/11): B 5; trả 1 A của đơn kỳ trước
    clock.freeze(_at(3))
    bh, tn, ql = [await login_as(client, x) for x in (SALES_ID, CASHIER_ID, MANAGER_ID)]
    await complete_order(client, bh, tn, {"B": 5})
    return_id = (await create_return(client, bh, old, {"A": (0, 1)})).json()["return_id"]
    assert (await client.post(f"/returns/{return_id}/approve", json={}, headers=ql)).is_success

    report = await _get(client, "/reports/products", ql)
    assert report["rank_by"] == RankBy.QUANTITY
    assert [
        (x["product_id"], x["sold_qty"], x["returned_qty"], x["net_qty"], x["net_value"])
        for x in report["products"]
    ] == [("B", 5, 0, 5, 500_000), ("A", 0, 1, -1, -100_000)]
    assert [(x["rank"], x["previous_rank"]) for x in report["products"]] == [(1, 2), (2, 1)]
    assert report["products"][0]["group_id"] == "NHOM1"
    assert [(g["group_id"], g["net_qty"], g["net_value"]) for g in report["groups"]] == [
        ("NHOM1", 4, 400_000)
    ]
    # Chậm bán: Đang bán, còn tồn, không bán trong kỳ (A, C); D Ngừng bán bỏ qua
    assert [(x["branch_id"], x["product_id"]) for x in report["slow_moving"]] == [
        (BRANCH_1, "A"),
        (BRANCH_1, "C"),
    ]

    by_value = await _get(client, "/reports/products", ql, rank_by=RankBy.VALUE)
    assert by_value["rank_by"] == RankBy.VALUE
    assert [x["product_id"] for x in by_value["products"]] == ["B", "A"]


async def test_stock_report(client: httpx.AsyncClient, conn: asyncpg.Connection) -> None:
    """TK-01, TK-05: tồn, khả dụng, so ngưỡng; điều chỉnh, xuất hủy trong kỳ theo lý do."""
    await seed_staff(conn)
    for product_id in "ABC":
        await seed_product(conn, product_id)
    await seed_stock(conn, BRANCH_1, "A", 5)
    await seed_stock(conn, BRANCH_1, "B", 10)
    clock.freeze(_at(3))
    ql = await login_as(client, MANAGER_ID)
    kho = await login_as(client, WAREHOUSE_ID)
    for product_id in "AB":
        response = await client.put(
            f"/stock/{product_id}/min-level", json={"min_level": 10}, headers=ql
        )
        assert response.status_code == 200, response.text

    async def slip(type_: SlipType, product_id: str, quantity: int, reason: str) -> str:
        body = {
            "type": type_,
            "reason": reason,
            "items": [{"product_id": product_id, "quantity": quantity}],
        }
        response = await client.post("/stock-slips", json=body, headers=kho)
        assert response.status_code == 201, response.text
        return response.json()["slip_id"]

    for product_id, reason in (("B", "Kiểm kê thừa"), ("A", "Kiểm kê thừa")):
        slip_id = await slip(SlipType.ADJUST_UP, product_id, 2, reason)
        assert (await client.post(f"/stock-slips/{slip_id}/approve", headers=ql)).is_success
    await slip(SlipType.OUT_DISPOSAL, "B", 3, "Hàng hỏng")  # Chờ xử lý: giữ hàng, chưa tính

    report = await _get(client, "/reports/stock", kho)
    assert report["branch_id"] == BRANCH_1
    assert [
        (x["product_id"], x["quantity"], x["available"], x["min_level"], x["level_status"])
        for x in report["lines"]
    ] == [
        ("A", 7, 7, 10, LevelStatus.BELOW_MIN),
        ("B", 12, 9, 10, LevelStatus.OK),
        ("C", 0, 0, None, LevelStatus.NOT_SET),
    ]
    assert [
        (m["type"], m["reason"], m["product_id"], m["quantity"]) for m in report["movements"]
    ] == [
        (SlipType.ADJUST_UP, "Kiểm kê thừa", "A", 2),
        (SlipType.ADJUST_UP, "Kiểm kê thừa", "B", 2),
    ]
    # Kỳ khác: không có biến động, tồn vẫn là tại thời điểm lập
    other = await _get(client, "/reports/stock", kho, **{"from": "2026-11-01", "to": "2026-11-02"})
    assert other["movements"] == []
    assert len(other["lines"]) == 3
