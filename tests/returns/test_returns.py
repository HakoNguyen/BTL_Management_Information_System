"""Phiếu trả (3.4): lập, xem, duyệt, từ chối – TH-01, TH-02, TH-03, TH-05, K-01, K-02, K-03."""

from __future__ import annotations

from datetime import datetime, timedelta

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
    create_awaiting_order,
    create_return,
    login_as,
    open_shift,
    seed_employee,
    seed_product,
    seed_staff,
    seed_stock,
)

from common import clock
from common.clock import VN_TZ
from common.constants import (
    BranchStatus,
    OrderStatus,
    RefundStatus,
    ReturnStatus,
    Role,
    SlipType,
)

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 13, 10, 0, tzinfo=VN_TZ)
MANAGER_2 = "NV-QL2"
SALES_2 = "NV-BH2"


@pytest.fixture
async def world(client: httpx.AsyncClient, conn: asyncpg.Connection) -> dict:
    """CN1 có A (100.000), B (50.000), tồn 10; đơn Hoàn tất 3 A + 2 B thu tiền mặt lúc NOW."""
    await seed_staff(conn)
    await seed_employee(conn, MANAGER_2, Role.MANAGER, BRANCH_2)
    await seed_employee(conn, SALES_2, Role.SALES, BRANCH_2)
    await seed_product(conn, "A")
    await seed_product(conn, "B", 50_000)
    await seed_product(conn, "C")
    for pid in ("A", "B", "C"):
        await seed_stock(conn, BRANCH_1, pid, 10)
    clock.freeze(NOW)
    users = {
        "bh": await login_as(client, SALES_ID),
        "tn": await login_as(client, CASHIER_ID),
        "ql": await login_as(client, MANAGER_ID),
        "hq": await login_as(client, HQ_ID),
        "ql2": await login_as(client, MANAGER_2),
        "bh2": await login_as(client, SALES_2),
    }
    await open_shift(client, users["tn"])
    users["order_id"] = await complete_order(client, users["bh"], users["tn"], {"A": 3, "B": 2})
    return users


def _error(response: httpx.Response, status: int, code: str, rule: str | None) -> None:
    assert response.status_code == status, response.text
    body = response.json()
    assert body["error_code"] == code
    assert body["details"].get("rule") == rule


async def _decide(
    client: httpx.AsyncClient, headers: dict, return_id: str, action: str, note: str | None = None
) -> httpx.Response:
    return await client.post(
        f"/returns/{return_id}/{action}", json={"decision_note": note}, headers=headers
    )


# ---------------------------------------------------------------- Lập phiếu (TH-01, TH-02)


async def test_create_return(client: httpx.AsyncClient, world: dict) -> None:
    """TH-02: phiếu Chờ duyệt, giá trị = Σ (tốt + lỗi) × đơn giá chốt; hàng vẫn do khách giữ."""
    response = await create_return(
        client, world["bh"], world["order_id"], {"A": (1, 1), "B": (0, 1)}
    )
    assert response.status_code == 201, response.text
    slip = response.json()
    assert slip["return_id"] == "PT000001"
    assert slip["status"] == ReturnStatus.PENDING
    assert slip["branch_id"] == BRANCH_1
    assert slip["created_by"] == SALES_ID
    assert slip["value"] == 250_000
    assert slip["refund_status"] is None
    assert [(i["product_id"], i["unit_price"], i["amount"]) for i in slip["items"]] == [
        ("A", 100_000, 200_000),
        ("B", 50_000, 50_000),
    ]
    stock = (await client.get("/stock", headers=world["ql"])).json()
    assert {s["product_id"]: s["quantity"] for s in stock}["A"] == 7


async def test_manager_can_create(client: httpx.AsyncClient, world: dict) -> None:
    """Ma trận 2.2: QL lập phiếu trả được."""
    response = await create_return(client, world["ql"], world["order_id"], {"A": (1, 0)})
    assert response.status_code == 201, response.text


async def test_create_forbidden_roles(client: httpx.AsyncClient, world: dict) -> None:
    """K-01: thu ngân, trụ sở không lập phiếu trả; NVBH chi nhánh khác không lập cho đơn CN1."""
    for who in ("tn", "hq"):
        response = await create_return(client, world[who], world["order_id"], {"A": (1, 0)})
        _error(response, 403, "FORBIDDEN", "K-01")
    response = await create_return(client, world["bh2"], world["order_id"], {"A": (1, 0)})
    _error(response, 403, "FORBIDDEN", "K-01")


async def test_order_not_found(client: httpx.AsyncClient, world: dict) -> None:
    response = await create_return(client, world["bh"], "DH999999", {"A": (1, 0)})
    _error(response, 404, "NOT_FOUND", None)


async def test_order_not_completed(client: httpx.AsyncClient, world: dict) -> None:
    """TH-01: chỉ nhận trả cho đơn Hoàn tất hoặc Đã trả một phần."""
    order_id = await create_awaiting_order(client, world["bh"], {"A": 1})
    response = await create_return(client, world["bh"], order_id, {"A": (1, 0)})
    _error(response, 409, "INVALID_STATE", "TH-01")


async def test_return_window(client: httpx.AsyncClient, world: dict) -> None:
    """TH-01: không muộn hơn thời điểm hoàn tất + 7 ngày."""
    clock.freeze(NOW + timedelta(days=7))
    bh = await login_as(client, SALES_ID)  # phiên cũ đã hết hạn sau 12 giờ
    response = await create_return(client, bh, world["order_id"], {"A": (1, 0)})
    assert response.status_code == 201, response.text
    clock.freeze(NOW + timedelta(days=7, seconds=1))
    response = await create_return(client, bh, world["order_id"], {"A": (1, 0)})
    _error(response, 422, "RULE_VIOLATION", "TH-01")


async def test_branch_inactive(
    client: httpx.AsyncClient, conn: asyncpg.Connection, world: dict
) -> None:
    """TH-01: chi nhánh của đơn phải đang Hoạt động."""
    await conn.execute(
        "UPDATE branches SET status = $2 WHERE branch_id = $1", BRANCH_1, BranchStatus.INACTIVE
    )
    response = await create_return(client, world["bh"], world["order_id"], {"A": (1, 0)})
    _error(response, 422, "RULE_VIOLATION", "TH-01")


async def test_product_not_in_order(client: httpx.AsyncClient, world: dict) -> None:
    """TH-02: mỗi dòng là sản phẩm có trong đơn gốc."""
    response = await create_return(client, world["bh"], world["order_id"], {"C": (1, 0)})
    _error(response, 422, "RULE_VIOLATION", "TH-02")
    assert response.json()["details"]["product_ids"] == ["C"]


async def test_line_validation(client: httpx.AsyncClient, world: dict) -> None:
    """TH-02: mỗi sản phẩm một dòng; tốt + lỗi > 0."""
    body = {
        "order_id": world["order_id"],
        "reason": "Lỗi",
        "items": [
            {"product_id": "A", "good_qty": 1, "defective_qty": 0},
            {"product_id": "A", "good_qty": 0, "defective_qty": 1},
        ],
    }
    _error(
        await client.post("/returns", json=body, headers=world["bh"]),
        400,
        "VALIDATION_ERROR",
        "TH-02",
    )
    response = await create_return(client, world["bh"], world["order_id"], {"A": (0, 0)})
    _error(response, 400, "VALIDATION_ERROR", "TH-02")


async def test_quantity_counts_pending_and_approved(client: httpx.AsyncClient, world: dict) -> None:
    """TH-02: lượng trả ≤ lượng mua − đã trả (Đã duyệt) − trên phiếu Chờ duyệt khác."""
    first = (await create_return(client, world["bh"], world["order_id"], {"A": (1, 0)})).json()
    second = await create_return(client, world["bh"], world["order_id"], {"A": (1, 0)})
    assert second.status_code == 201, second.text
    assert (await _decide(client, world["ql"], first["return_id"], "approve")).status_code == 200
    response = await create_return(client, world["bh"], world["order_id"], {"A": (1, 1)})
    _error(response, 422, "RULE_VIOLATION", "TH-02")
    assert response.json()["details"]["lines"] == [
        {"product_id": "A", "requested": 2, "remaining": 1}
    ]
    # phiếu Từ chối không giữ lượng
    assert (
        await _decide(
            client,
            world["ql"],
            second.json()["return_id"],
            "reject",
            "Hàng không phải của cửa hàng",
        )
    ).status_code == 200
    response = await create_return(client, world["bh"], world["order_id"], {"A": (1, 1)})
    assert response.status_code == 201, response.text


# ---------------------------------------------------------------- Xem phiếu


async def test_list_and_get(client: httpx.AsyncClient, world: dict) -> None:
    """K-01: TN xem được phiếu chi nhánh mình; HQ xem mọi chi nhánh; chi nhánh khác bị chặn."""
    slip = (await create_return(client, world["bh"], world["order_id"], {"A": (1, 0)})).json()
    for who in ("bh", "ql", "tn", "hq"):
        listed = (await client.get("/returns", headers=world[who])).json()
        assert [s["return_id"] for s in listed] == [slip["return_id"]]
        response = await client.get(f"/returns/{slip['return_id']}", headers=world[who])
        assert response.status_code == 200, response.text
    assert (await client.get("/returns", headers=world["ql2"])).json() == []
    response = await client.get(f"/returns/{slip['return_id']}", headers=world["ql2"])
    _error(response, 403, "FORBIDDEN", "K-01")
    _error(await client.get("/returns/PT999999", headers=world["ql"]), 404, "NOT_FOUND", None)


async def test_list_filters(client: httpx.AsyncClient, world: dict) -> None:
    """TH-05: QL lọc phiếu Đã duyệt chưa hoàn xong."""
    pending = (await create_return(client, world["bh"], world["order_id"], {"A": (1, 0)})).json()
    approved = (await create_return(client, world["bh"], world["order_id"], {"B": (1, 0)})).json()
    await _decide(client, world["ql"], approved["return_id"], "approve")
    response = await client.get(
        "/returns",
        params={"status": ReturnStatus.APPROVED, "refund_status": RefundStatus.NOT_REFUNDED},
        headers=world["ql"],
    )
    assert [s["return_id"] for s in response.json()] == [approved["return_id"]]
    response = await client.get(
        "/returns", params={"status": ReturnStatus.PENDING}, headers=world["ql"]
    )
    assert [s["return_id"] for s in response.json()] == [pending["return_id"]]


# -------------------------------------------------------- Duyệt, từ chối (TH-03, TH-05, K-02, K-03)


async def test_approve_partial(
    client: httpx.AsyncClient, conn: asyncpg.Connection, world: dict
) -> None:
    """TH-05: hàng tốt nhập lại một lần theo mã phiếu trả; hàng lỗi không vào tồn; đơn Đã trả
    một phần; thời điểm hoàn tất và hóa đơn giữ nguyên."""
    order_before = (await client.get(f"/orders/{world['order_id']}", headers=world["bh"])).json()
    slip = (
        await create_return(client, world["bh"], world["order_id"], {"A": (1, 1), "B": (0, 1)})
    ).json()
    clock.freeze(NOW + timedelta(hours=1))
    response = await _decide(client, world["ql"], slip["return_id"], "approve")
    assert response.status_code == 200, response.text
    decided = response.json()
    assert decided["status"] == ReturnStatus.APPROVED
    assert decided["decided_by"] == MANAGER_ID
    assert datetime.fromisoformat(decided["decided_at"]) == NOW + timedelta(hours=1)
    assert decided["refund_status"] == RefundStatus.NOT_REFUNDED

    slips = await conn.fetch(
        "SELECT s.type, s.status, i.product_id, i.quantity FROM stock_slips s"
        " JOIN stock_slip_items i USING (slip_id) WHERE s.return_id = $1",
        slip["return_id"],
    )
    assert [(r["type"], r["product_id"], r["quantity"]) for r in slips] == [
        (SlipType.IN_RETURN, "A", 1)
    ]
    stock = {
        s["product_id"]: s["quantity"]
        for s in (await client.get("/stock", headers=world["ql"])).json()
    }
    assert stock["A"] == 8 and stock["B"] == 8

    order = (await client.get(f"/orders/{world['order_id']}", headers=world["bh"])).json()
    assert order["status"] == OrderStatus.PARTIALLY_RETURNED
    assert order["completed_at"] == order_before["completed_at"]
    assert order["total"] == order_before["total"]
    invoice = (await client.get(f"/orders/{world['order_id']}/invoice", headers=world["tn"])).json()
    assert invoice["total"] == 400_000


async def test_approve_full_return(
    client: httpx.AsyncClient, conn: asyncpg.Connection, world: dict
) -> None:
    """TH-05: trả hết mọi dòng thì đơn Đã trả toàn bộ; phiếu chỉ có hàng lỗi không lập phiếu kho."""
    first = (await create_return(client, world["bh"], world["order_id"], {"A": (0, 3)})).json()
    await _decide(client, world["ql"], first["return_id"], "approve")
    assert (
        await conn.fetchval(
            "SELECT count(*) FROM stock_slips WHERE return_id = $1", first["return_id"]
        )
        == 0
    )
    order = (await client.get(f"/orders/{world['order_id']}", headers=world["bh"])).json()
    assert order["status"] == OrderStatus.PARTIALLY_RETURNED

    second = (await create_return(client, world["bh"], world["order_id"], {"B": (2, 0)})).json()
    await _decide(client, world["ql"], second["return_id"], "approve")
    order = (await client.get(f"/orders/{world['order_id']}", headers=world["bh"])).json()
    assert order["status"] == OrderStatus.FULLY_RETURNED
    response = await create_return(client, world["bh"], world["order_id"], {"A": (1, 0)})
    _error(response, 409, "INVALID_STATE", "TH-01")


async def test_reject(client: httpx.AsyncClient, world: dict) -> None:
    """TH-03, K-03: từ chối bắt buộc lý do; không đổi tồn, đơn."""
    slip = (await create_return(client, world["bh"], world["order_id"], {"A": (1, 0)})).json()
    response = await _decide(client, world["ql"], slip["return_id"], "reject")
    _error(response, 400, "VALIDATION_ERROR", "K-03")
    response = await _decide(
        client, world["ql"], slip["return_id"], "reject", "Hàng đã qua sử dụng"
    )
    assert response.status_code == 200, response.text
    rejected = response.json()
    assert rejected["status"] == ReturnStatus.REJECTED
    assert rejected["decided_by"] == MANAGER_ID
    assert rejected["decision_note"] == "Hàng đã qua sử dụng"
    assert rejected["refund_status"] is None
    stock = {
        s["product_id"]: s["quantity"]
        for s in (await client.get("/stock", headers=world["ql"])).json()
    }
    assert stock["A"] == 7
    order = (await client.get(f"/orders/{world['order_id']}", headers=world["bh"])).json()
    assert order["status"] == OrderStatus.COMPLETED


async def test_decided_slip_is_final(client: httpx.AsyncClient, world: dict) -> None:
    """TH-03: phiếu đã quyết định không quyết định lại."""
    slip = (await create_return(client, world["bh"], world["order_id"], {"A": (1, 0)})).json()
    await _decide(client, world["ql"], slip["return_id"], "approve")
    for action, note in (("approve", None), ("reject", "Đổi ý")):
        response = await _decide(client, world["ql"], slip["return_id"], action, note)
        _error(response, 409, "INVALID_STATE", "TH-03")


async def test_creator_cannot_decide(client: httpx.AsyncClient, world: dict) -> None:
    """K-02: QL không tự duyệt phiếu mình lập; trụ sở duyệt thay, bắt buộc lý do."""
    slip = (await create_return(client, world["ql"], world["order_id"], {"A": (1, 0)})).json()
    for action, note in (("approve", None), ("reject", "Lý do")):
        response = await _decide(client, world["ql"], slip["return_id"], action, note)
        _error(response, 403, "FORBIDDEN", "K-02")
    response = await _decide(client, world["hq"], slip["return_id"], "approve")
    _error(response, 400, "VALIDATION_ERROR", "K-02")
    response = await _decide(client, world["hq"], slip["return_id"], "approve", "QL là người lập")
    assert response.status_code == 200, response.text
    assert response.json()["decided_by"] == HQ_ID
    assert response.json()["decision_note"] == "QL là người lập"


async def test_hq_can_reject(client: httpx.AsyncClient, world: dict) -> None:
    """K-02: trụ sở từ chối thay, kèm lý do."""
    slip = (await create_return(client, world["bh"], world["order_id"], {"A": (1, 0)})).json()
    response = await _decide(client, world["hq"], slip["return_id"], "reject", "QL vắng")
    assert response.status_code == 200, response.text
    assert response.json()["decided_by"] == HQ_ID


async def test_decide_forbidden(client: httpx.AsyncClient, world: dict) -> None:
    """K-01: NVBH, thu ngân không duyệt; QL chi nhánh khác không duyệt phiếu CN1."""
    slip = (await create_return(client, world["bh"], world["order_id"], {"A": (1, 0)})).json()
    for who in ("bh", "tn"):
        response = await _decide(client, world[who], slip["return_id"], "approve")
        _error(response, 403, "FORBIDDEN", "K-01")
    response = await _decide(client, world["ql2"], slip["return_id"], "approve")
    _error(response, 403, "FORBIDDEN", "K-01")
    _error(await _decide(client, world["ql"], "PT999999", "approve"), 404, "NOT_FOUND", None)
