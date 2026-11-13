"""4.2 Nhập hàng, 4.3 xuất hàng: phiếu kho do NV kho lập, QL duyệt (TK-01 đến TK-04)."""

from __future__ import annotations

from datetime import UTC, datetime

import asyncpg
import httpx
import pytest
from fixtures import (
    BRANCH_1,
    BRANCH_2,
    HQ_ID,
    MANAGER_ID,
    SALES_ID,
    WAREHOUSE_ID,
    login_as,
    seed_employee,
    seed_product,
    seed_staff,
    seed_stock,
    seed_stock_slip,
)

from common import clock
from common.clock import VN_TZ
from common.constants import BranchStatus, ErrorCode, ProductStatus, Role, SlipStatus

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 13, 10, 0, tzinfo=VN_TZ)
ISO_NOW = "2026-11-13T03:00:00Z"  # API trả thời điểm theo UTC
KHO2_ID = "NV-KHO2"
QL2_ID = "NV-QL2"
INBOUND = {
    "type": "IN_SUPPLIER",
    "counterparty": "NCC Minh Phát",
    "delivery_no": "PG-1",
    "items": [{"product_id": "A", "quantity": 5}, {"product_id": "B", "quantity": 2}],
}


def _out(type_: str = "OUT_DISPOSAL", quantity: int = 3, **extra: object) -> dict:
    body = {
        "type": type_,
        "reason": "Hàng hỏng",
        "items": [{"product_id": "A", "quantity": quantity}],
    }
    return body | extra


@pytest.fixture
async def world(conn: asyncpg.Connection) -> None:
    await seed_staff(conn)
    await seed_employee(conn, KHO2_ID, Role.WAREHOUSE, BRANCH_2)
    await seed_employee(conn, QL2_ID, Role.MANAGER, BRANCH_2)
    await seed_product(conn, "A")
    await seed_product(conn, "B")
    await seed_stock(conn, BRANCH_1, "A", 10)
    clock.freeze(NOW)


@pytest.fixture
async def kho(client: httpx.AsyncClient, world: None) -> dict[str, str]:
    return await login_as(client, WAREHOUSE_ID)


@pytest.fixture
async def ql(client: httpx.AsyncClient, world: None) -> dict[str, str]:
    return await login_as(client, MANAGER_ID)


def _error(response: httpx.Response, status: int, code: ErrorCode, rule: str | None) -> None:
    assert response.status_code == status, response.text
    assert response.json()["error_code"] == code
    assert response.json()["details"].get("rule") == rule


async def _stock(client: httpx.AsyncClient, headers: dict[str, str]) -> dict[str, tuple[int, int]]:
    rows = (await client.get("/stock", headers=headers)).json()
    return {row["product_id"]: (row["quantity"], row["available"]) for row in rows}


async def _pending(client: httpx.AsyncClient, kho: dict[str, str], **kw: object) -> str:
    response = await client.post("/stock-slips", json=_out(**kw), headers=kho)
    assert response.status_code == 201, response.text
    return response.json()["slip_id"]


# ---------------------------------------------------------------- 4.2 Nhập từ kho tổng, NCC


async def test_inbound_posts_immediately(client: httpx.AsyncClient, kho: dict[str, str]) -> None:
    """TK-02: ghi bên giao, số phiếu giao, ghi nhận ngay; TK-01: tồn tăng, cặp mới được tạo."""
    response = await client.post("/stock-slips/inbound", json=INBOUND, headers=kho)
    assert response.status_code == 201, response.text
    assert response.json() == {
        "slip_id": "PK000001",
        "branch_id": BRANCH_1,
        "type": "IN_SUPPLIER",
        "status": "POSTED",
        "created_at": ISO_NOW,
        "created_by": WAREHOUSE_ID,
        "reason": None,
        "counterparty": "NCC Minh Phát",
        "delivery_no": "PG-1",
        "order_id": None,
        "return_id": None,
        "adjusts_slip_id": None,
        "approved_by": None,
        "decision_reason": None,
        "finalized_at": ISO_NOW,
        "items": [{"product_id": "A", "quantity": 5}, {"product_id": "B", "quantity": 2}],
    }
    assert await _stock(client, kho) == {"A": (15, 15), "B": (2, 2)}


async def test_inbound_duplicate_delivery_note(
    client: httpx.AsyncClient, kho: dict[str, str]
) -> None:
    """TK-02: cùng bên giao, số phiếu giao, chi nhánh không ghi hai lần; khác bên giao thì được."""
    assert (await client.post("/stock-slips/inbound", json=INBOUND, headers=kho)).status_code == 201
    response = await client.post("/stock-slips/inbound", json=INBOUND, headers=kho)
    _error(response, 409, ErrorCode.DUPLICATE, "TK-02")
    other = INBOUND | {"counterparty": "Kho tổng", "type": "IN_WAREHOUSE"}
    assert (await client.post("/stock-slips/inbound", json=other, headers=kho)).status_code == 201
    assert await _stock(client, kho) == {"A": (20, 20), "B": (4, 4)}


async def test_inbound_same_note_other_branch(
    client: httpx.AsyncClient, kho: dict[str, str]
) -> None:
    """TK-02: bộ trùng tính theo chi nhánh."""
    assert (await client.post("/stock-slips/inbound", json=INBOUND, headers=kho)).status_code == 201
    kho2 = await login_as(client, KHO2_ID)
    response = await client.post("/stock-slips/inbound", json=INBOUND, headers=kho2)
    assert response.status_code == 201, response.text


async def test_inbound_inactive_branch(
    client: httpx.AsyncClient, conn: asyncpg.Connection, kho: dict[str, str]
) -> None:
    """TK-02: chi nhánh Ngừng hoạt động không nhập hàng."""
    await conn.execute(
        "UPDATE branches SET status = $1 WHERE branch_id = $2", BranchStatus.INACTIVE, BRANCH_1
    )
    response = await client.post("/stock-slips/inbound", json=INBOUND, headers=kho)
    _error(response, 422, ErrorCode.RULE_VIOLATION, "TK-02")


async def test_inbound_discontinued_product_allowed(
    client: httpx.AsyncClient, conn: asyncpg.Connection, kho: dict[str, str]
) -> None:
    """TK-02: sản phẩm Ngừng bán vẫn nhập được (docs/plan.md mục 7 ý 13)."""
    await conn.execute(
        "UPDATE products SET status = $1 WHERE product_id = 'A'", ProductStatus.DISCONTINUED
    )
    response = await client.post("/stock-slips/inbound", json=INBOUND, headers=kho)
    assert response.status_code == 201, response.text


async def test_inbound_invalid_lines(client: httpx.AsyncClient, kho: dict[str, str]) -> None:
    """TK-02: số lượng > 0, ít nhất một dòng, mỗi sản phẩm một dòng, có bên giao, số phiếu giao."""
    for items in (
        [{"product_id": "A", "quantity": 0}],
        [],
        [{"product_id": "A", "quantity": 1}, {"product_id": "A", "quantity": 2}],
    ):
        body = INBOUND | {"items": items}
        response = await client.post("/stock-slips/inbound", json=body, headers=kho)
        _error(response, 400, ErrorCode.VALIDATION_ERROR, None)
    for missing in ("counterparty", "delivery_no"):
        body = {k: v for k, v in INBOUND.items() if k != missing}
        response = await client.post("/stock-slips/inbound", json=body, headers=kho)
        _error(response, 400, ErrorCode.VALIDATION_ERROR, None)
    unknown = INBOUND | {"items": [{"product_id": "ZZ", "quantity": 1}]}
    response = await client.post("/stock-slips/inbound", json=unknown, headers=kho)
    _error(response, 404, ErrorCode.NOT_FOUND, None)
    assert await _stock(client, kho) == {"A": (10, 10), "B": (0, 0)}


async def test_inbound_only_warehouse(client: httpx.AsyncClient, world: None) -> None:
    """K-01: chỉ NV kho lập phiếu nhập."""
    for employee_id in (MANAGER_ID, SALES_ID, HQ_ID):
        headers = await login_as(client, employee_id)
        response = await client.post("/stock-slips/inbound", json=INBOUND, headers=headers)
        _error(response, 403, ErrorCode.FORBIDDEN, "K-01")


# ---------------------------------------------------------------- 4.2, 4.3 Phiếu cần duyệt


@pytest.mark.parametrize("type_", ["OUT_DISPOSAL", "OUT_TO_WAREHOUSE", "ADJUST_DOWN"])
async def test_out_slip_holds_stock(
    client: httpx.AsyncClient, kho: dict[str, str], type_: str
) -> None:
    """TK-03: phiếu xuất lập ở Chờ xử lý, giữ hàng (tồn không đổi, tồn khả dụng giảm)."""
    response = await client.post("/stock-slips", json=_out(type_), headers=kho)
    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["type"], body["status"], body["created_by"]) == (type_, "PENDING", WAREHOUSE_ID)
    assert (body["reason"], body["finalized_at"]) == ("Hàng hỏng", None)
    assert (await _stock(client, kho))["A"] == (10, 7)


async def test_out_slip_exceeding_available(client: httpx.AsyncClient, kho: dict[str, str]) -> None:
    """TK-03: vượt tồn khả dụng (kể cả phần đang giữ) thì không lập được phiếu."""
    await _pending(client, kho, quantity=8)
    response = await client.post("/stock-slips", json=_out(quantity=3), headers=kho)
    _error(response, 409, ErrorCode.INSUFFICIENT_STOCK, "TK-03")
    assert response.json()["details"]["lines"] == [
        {"product_id": "A", "quantity": 3, "available": 2}
    ]
    body = _out(items=[{"product_id": "B", "quantity": 1}])
    response = await client.post("/stock-slips", json=body, headers=kho)
    _error(response, 409, ErrorCode.INSUFFICIENT_STOCK, "TK-03")  # cặp chưa có bản ghi = tồn 0
    assert (await _stock(client, kho))["A"] == (10, 2)


async def test_adjust_up_waits_for_approval(
    client: httpx.AsyncClient, kho: dict[str, str], ql: dict[str, str]
) -> None:
    """TK-04: điều chỉnh tăng chờ duyệt không đổi tồn; duyệt thì tồn tăng."""
    slip_id = await _pending(
        client, kho, type_="ADJUST_UP", items=[{"product_id": "B", "quantity": 4}]
    )
    assert (await _stock(client, kho))["B"] == (0, 0)
    response = await client.post(f"/stock-slips/{slip_id}/approve", headers=ql)
    assert response.status_code == 200, response.text
    assert (await _stock(client, kho))["B"] == (4, 4)


async def test_slip_requires_reason(client: httpx.AsyncClient, kho: dict[str, str]) -> None:
    """TK-03, TK-04: phiếu cần duyệt bắt buộc lý do; loại nhập không lập qua endpoint này."""
    for body in (_out(reason=None), _out(reason="  "), _out("IN_SUPPLIER")):
        response = await client.post("/stock-slips", json=body, headers=kho)
        _error(response, 400, ErrorCode.VALIDATION_ERROR, None)


async def test_adjusts_slip_reference(
    client: httpx.AsyncClient, conn: asyncpg.Connection, kho: dict[str, str]
) -> None:
    """TK-04: tham chiếu phải là phiếu của chi nhánh; chỉ phiếu điều chỉnh được tham chiếu."""
    other = await seed_stock_slip(conn, BRANCH_2, KHO2_ID, SlipStatus.POSTED)
    body = _out("ADJUST_DOWN", adjusts_slip_id=other)
    _error(
        await client.post("/stock-slips", json=body, headers=kho), 404, ErrorCode.NOT_FOUND, None
    )
    own = await seed_stock_slip(conn, BRANCH_1, WAREHOUSE_ID, SlipStatus.POSTED)
    body = _out("OUT_DISPOSAL", adjusts_slip_id=own)
    response = await client.post("/stock-slips", json=body, headers=kho)
    _error(response, 400, ErrorCode.VALIDATION_ERROR, "TK-04")
    response = await client.post(
        "/stock-slips", json=_out("ADJUST_DOWN", adjusts_slip_id=own), headers=kho
    )
    assert response.status_code == 201, response.text
    assert response.json()["adjusts_slip_id"] == own


async def test_create_slip_only_warehouse(client: httpx.AsyncClient, world: None) -> None:
    """K-01: chỉ NV kho lập phiếu điều chỉnh, xuất khác."""
    for employee_id in (MANAGER_ID, SALES_ID, HQ_ID):
        headers = await login_as(client, employee_id)
        response = await client.post("/stock-slips", json=_out(), headers=headers)
        _error(response, 403, ErrorCode.FORBIDDEN, "K-01")


# ---------------------------------------------------------------- Duyệt, từ chối


async def test_approve_out_slip(
    client: httpx.AsyncClient, kho: dict[str, str], ql: dict[str, str]
) -> None:
    """TK-03: QL duyệt thì Đã ghi nhận, tồn giảm; K-03: lưu người, thời điểm duyệt."""
    slip_id = await _pending(client, kho)
    later = NOW.replace(hour=11)
    clock.freeze(later)
    response = await client.post(f"/stock-slips/{slip_id}/approve", headers=ql)
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["status"], body["approved_by"]) == ("POSTED", MANAGER_ID)
    assert (body["finalized_at"], body["decision_reason"]) == (
        later.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        None,
    )
    assert (await _stock(client, kho))["A"] == (7, 7)


async def test_reject_releases_hold(
    client: httpx.AsyncClient, kho: dict[str, str], ql: dict[str, str]
) -> None:
    """TK-03: từ chối thì Đã hủy, nhả hàng, tồn không đổi; K-03: lưu người, thời điểm, lý do."""
    slip_id = await _pending(client, kho)
    body = {"reason": "Hàng còn dùng được"}
    response = await client.post(f"/stock-slips/{slip_id}/reject", json=body, headers=ql)
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["status"], body["approved_by"]) == ("CANCELLED", MANAGER_ID)
    assert (body["decision_reason"], body["finalized_at"]) == (
        "Hàng còn dùng được",
        ISO_NOW,
    )
    assert body["reason"] == "Hàng hỏng"
    assert (await _stock(client, kho))["A"] == (10, 10)


async def test_reject_requires_reason(
    client: httpx.AsyncClient, kho: dict[str, str], ql: dict[str, str]
) -> None:
    """K-03: từ chối bắt buộc lý do."""
    slip_id = await _pending(client, kho)
    for body in ({}, {"reason": " "}):
        response = await client.post(f"/stock-slips/{slip_id}/reject", json=body, headers=ql)
        _error(response, 400, ErrorCode.VALIDATION_ERROR, None)


async def test_decided_slip_is_final(
    client: httpx.AsyncClient, kho: dict[str, str], ql: dict[str, str]
) -> None:
    """K-04, trạng thái chỉ đi tới: phiếu đã quyết định không duyệt, từ chối lại được."""
    slip_id = await _pending(client, kho)
    assert (await client.post(f"/stock-slips/{slip_id}/approve", headers=ql)).status_code == 200
    response = await client.post(f"/stock-slips/{slip_id}/approve", headers=ql)
    _error(response, 409, ErrorCode.INVALID_STATE, None)
    response = await client.post(f"/stock-slips/{slip_id}/reject", json={"reason": "x"}, headers=ql)
    _error(response, 409, ErrorCode.INVALID_STATE, None)
    assert (await _stock(client, kho))["A"] == (7, 7)


async def test_inbound_slip_not_approvable(
    client: httpx.AsyncClient, kho: dict[str, str], ql: dict[str, str]
) -> None:
    """TK-02: phiếu nhập đã ghi nhận ngay, không qua duyệt."""
    response = await client.post("/stock-slips/inbound", json=INBOUND, headers=kho)
    slip_id = response.json()["slip_id"]
    response = await client.post(f"/stock-slips/{slip_id}/approve", headers=ql)
    _error(response, 409, ErrorCode.INVALID_STATE, None)


async def test_approver_differs_from_creator(
    client: httpx.AsyncClient, conn: asyncpg.Connection, ql: dict[str, str]
) -> None:
    """K-02: QL không duyệt, từ chối phiếu do chính mình lập."""
    slip_id = await seed_stock_slip(conn, BRANCH_1, MANAGER_ID)
    response = await client.post(f"/stock-slips/{slip_id}/approve", headers=ql)
    _error(response, 403, ErrorCode.FORBIDDEN, "K-02")
    response = await client.post(f"/stock-slips/{slip_id}/reject", json={"reason": "x"}, headers=ql)
    _error(response, 403, ErrorCode.FORBIDDEN, "K-02")


async def test_other_branch_forbidden(client: httpx.AsyncClient, kho: dict[str, str]) -> None:
    """K-01: QL chi nhánh khác không xem, duyệt, từ chối được phiếu của chi nhánh này."""
    slip_id = await _pending(client, kho)
    ql2 = await login_as(client, QL2_ID)
    response = await client.post(f"/stock-slips/{slip_id}/approve", headers=ql2)
    _error(response, 403, ErrorCode.FORBIDDEN, "K-01")
    response = await client.post(
        f"/stock-slips/{slip_id}/reject", json={"reason": "x"}, headers=ql2
    )
    _error(response, 403, ErrorCode.FORBIDDEN, "K-01")
    response = await client.get(f"/stock-slips/{slip_id}", headers=ql2)
    _error(response, 403, ErrorCode.FORBIDDEN, "K-01")


async def test_no_proxy_approval(client: httpx.AsyncClient, kho: dict[str, str]) -> None:
    """TK-03: phiếu kho không có duyệt thay; chỉ QL duyệt, từ chối."""
    slip_id = await _pending(client, kho)
    for employee_id in (HQ_ID, WAREHOUSE_ID, SALES_ID):
        headers = await login_as(client, employee_id)
        response = await client.post(f"/stock-slips/{slip_id}/approve", headers=headers)
        _error(response, 403, ErrorCode.FORBIDDEN, "K-01")
        body = {"reason": "x"}
        response = await client.post(f"/stock-slips/{slip_id}/reject", json=body, headers=headers)
        _error(response, 403, ErrorCode.FORBIDDEN, "K-01")


async def test_decide_unknown_slip(client: httpx.AsyncClient, ql: dict[str, str]) -> None:
    response = await client.post("/stock-slips/PK999999/approve", headers=ql)
    _error(response, 404, ErrorCode.NOT_FOUND, None)


# ---------------------------------------------------------------- Xem phiếu


async def test_list_and_get_slips(
    client: httpx.AsyncClient, kho: dict[str, str], ql: dict[str, str]
) -> None:
    """Danh sách phiếu của chi nhánh mình, mới nhất trước, lọc theo trạng thái."""
    first = (await client.post("/stock-slips/inbound", json=INBOUND, headers=kho)).json()
    clock.freeze(NOW.replace(hour=11))
    second = await _pending(client, kho)
    kho2 = await login_as(client, KHO2_ID)
    assert (
        await client.post("/stock-slips/inbound", json=INBOUND, headers=kho2)
    ).status_code == 201

    for headers in (kho, ql):
        response = await client.get("/stock-slips", headers=headers)
        assert response.status_code == 200, response.text
        assert [s["slip_id"] for s in response.json()] == [second, first["slip_id"]]
    response = await client.get("/stock-slips", params={"status": "PENDING"}, headers=ql)
    assert [s["slip_id"] for s in response.json()] == [second]
    response = await client.get(f"/stock-slips/{first['slip_id']}", headers=ql)
    assert response.json() == first
    response = await client.get("/stock-slips/PK999999", headers=ql)
    _error(response, 404, ErrorCode.NOT_FOUND, None)


async def test_view_slips_roles(client: httpx.AsyncClient, world: None) -> None:
    """K-01: chỉ QL, NV kho xem phiếu kho."""
    for employee_id in (SALES_ID, HQ_ID):
        headers = await login_as(client, employee_id)
        response = await client.get("/stock-slips", headers=headers)
        _error(response, 403, ErrorCode.FORBIDDEN, "K-01")
