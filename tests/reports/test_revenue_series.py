"""Biểu đồ doanh thu theo thời gian (tính năng thêm, docs/api.md nhóm 5): DT-01 đến DT-03, DT-05."""

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
    complete_order,
    create_return,
    login_as,
    open_shift,
    seed_product,
    seed_staff,
    seed_stock,
)

from common import clock
from common.clock import VN_TZ
from common.constants import ErrorCode

pytestmark = pytest.mark.db

GROUP_2 = "NHOM2"


def _at(day: int, hour: int = 10) -> datetime:
    return datetime(2026, 11, day, hour, 0, tzinfo=VN_TZ)


async def _series(client: httpx.AsyncClient, headers: dict[str, str], **params: str) -> dict:
    response = await client.get("/reports/revenue/series", params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _values(body: dict) -> list[tuple]:
    return [
        (
            p["period_start"],
            p["order_count"],
            p["gross_revenue"],
            p["returns_value"],
            p["net_revenue"],
        )
        for p in body["points"]
    ]


@pytest.fixture
async def sales(client: httpx.AsyncClient, conn: asyncpg.Connection) -> dict[str, str]:
    """10/11: đơn A×10 = 1.000.000. 12/11: trả A×2 = 200.000 (đã duyệt).
    13/11 00:30 giờ VN (= 17:30 ngày 12 UTC): đơn B×1 = 100.000 nhóm 2; phải rơi vào ngày 13."""
    await seed_staff(conn)
    await seed_product(conn, "A")
    await seed_product(conn, "B", group_id=GROUP_2)
    await seed_stock(conn, BRANCH_1, "A", 20)
    await seed_stock(conn, BRANCH_1, "B", 20)
    clock.freeze(_at(10))
    bh, tn = await login_as(client, SALES_ID), await login_as(client, CASHIER_ID)
    await open_shift(client, tn)
    order_id = await complete_order(client, bh, tn, {"A": 10})

    clock.freeze(_at(12))
    bh, ql = await login_as(client, SALES_ID), await login_as(client, MANAGER_ID)
    return_id = (await create_return(client, bh, order_id, {"A": (2, 0)})).json()["return_id"]
    response = await client.post(f"/returns/{return_id}/approve", json={}, headers=ql)
    assert response.status_code == 200, response.text

    clock.freeze(_at(13, 0).replace(minute=30))  # 00:30 ngày 13 giờ VN = 17:30 ngày 12 UTC
    bh, tn = await login_as(client, SALES_ID), await login_as(client, CASHIER_ID)
    await complete_order(client, bh, tn, {"B": 1})
    return await login_as(client, HQ_ID)


async def test_series_by_day_matches_revenue_report(
    client: httpx.AsyncClient, sales: dict[str, str]
) -> None:
    """DT-01..DT-03 theo ngày giờ Việt Nam; mốc không phát sinh có số 0; Σ các mốc = tổng 5.1."""
    body = await _series(client, sales, **{"from": "2026-11-09", "to": "2026-11-13"}, period="DAY")
    assert (body["period"], body["group_id"], body["branch_id"]) == ("DAY", None, None)
    assert _values(body) == [
        ("2026-11-09", 0, 0, 0, 0),
        ("2026-11-10", 1, 1_000_000, 0, 1_000_000),
        ("2026-11-11", 0, 0, 0, 0),
        ("2026-11-12", 0, 0, 200_000, -200_000),
        ("2026-11-13", 1, 100_000, 0, 100_000),
    ]
    report = await client.get(
        "/reports/revenue", params={"from": "2026-11-09", "to": "2026-11-13"}, headers=sales
    )
    total = report.json()["total"]
    for field in ("order_count", "gross_revenue", "returns_value", "net_revenue"):
        assert sum(p[field] for p in body["points"]) == total[field]


async def test_series_by_month_and_group(client: httpx.AsyncClient, sales: dict[str, str]) -> None:
    """Mốc tháng bắt đầu ngày 1 dù kỳ bắt đầu giữa tháng; lọc nhóm chỉ tính dòng của nhóm, DT-05."""
    span = {"from": "2026-11-05", "to": "2026-12-20"}
    body = await _series(client, sales, **span)
    assert body["period"] == "MONTH"
    assert _values(body) == [
        ("2026-11-01", 2, 1_100_000, 200_000, 900_000),
        ("2026-12-01", 0, 0, 0, 0),
    ]
    group = await _series(client, sales, **span, group_id=GROUP_2)
    assert group["group_id"] == GROUP_2
    assert _values(group)[0] == ("2026-11-01", 1, 100_000, 0, 100_000)


@pytest.mark.parametrize(
    ("period", "span", "starts"),
    [
        (
            "QUARTER",
            ("2026-02-15", "2026-11-16"),
            ["2026-01-01", "2026-04-01", "2026-07-01", "2026-10-01"],
        ),
        ("YEAR", ("2025-06-01", "2026-11-16"), ["2025-01-01", "2026-01-01"]),
        ("MONTH", ("2025-12-31", "2026-01-01"), ["2025-12-01", "2026-01-01"]),
    ],
)
async def test_series_buckets(
    client: httpx.AsyncClient, sales: dict[str, str], period: str, span: tuple, starts: list
) -> None:
    body = await _series(client, sales, **{"from": span[0], "to": span[1]}, period=period)
    assert [p["period_start"] for p in body["points"]] == starts
    assert sum(p["gross_revenue"] for p in body["points"]) == (
        1_100_000 if period != "MONTH" else 0
    )


async def test_series_invalid(client: httpx.AsyncClient, sales: dict[str, str]) -> None:
    too_long = await client.get(
        "/reports/revenue/series",
        params={"from": "2026-01-01", "to": "2026-04-03", "period": "DAY"},  # 93 ngày
        headers=sales,
    )
    assert too_long.status_code == 400
    assert too_long.json()["error_code"] == ErrorCode.VALIDATION_ERROR
    ok = await client.get(
        "/reports/revenue/series",
        params={"from": "2026-01-01", "to": "2026-04-02", "period": "DAY"},  # đúng 92 ngày
        headers=sales,
    )
    assert ok.status_code == 200
    missing = await client.get(
        "/reports/revenue/series",
        params={"from": "2026-11-01", "to": "2026-11-30", "group_id": "KHONG-CO"},
        headers=sales,
    )
    assert missing.status_code == 404


async def test_series_permissions(client: httpx.AsyncClient, sales: dict[str, str]) -> None:
    """K-01: QL chỉ xem chi nhánh mình; NVBH không xem doanh thu (ma trận 2.2)."""
    span = {"from": "2026-11-01", "to": "2026-11-30"}
    ql = await login_as(client, MANAGER_ID)
    own = await _series(client, ql, **span)
    assert own["branch_id"] == BRANCH_1
    other = await client.get(
        "/reports/revenue/series", params={**span, "branch_id": BRANCH_2}, headers=ql
    )
    assert other.status_code == 403
    assert other.json()["details"]["rule"] == "K-01"
    bh = await login_as(client, SALES_ID)
    denied = await client.get("/reports/revenue/series", params=span, headers=bh)
    assert denied.status_code == 403
