"""Năm hàm giao của nhóm 4 cho nhóm 3 (docs/api.md mục 5): kiểm tra, giữ, xuất, nhả, nhập trả."""

from __future__ import annotations

import asyncio
from datetime import datetime

import asyncpg
import pytest
from fixtures import (
    BRANCH_1,
    CASHIER_ID,
    MANAGER_ID,
    SALES_ID,
    seed_order,
    seed_product,
    seed_return_slip,
    seed_staff,
    seed_stock,
)
from services import inventory

from common.clock import VN_TZ
from common.constants import ErrorCode, OrderStatus, ReturnStatus, SlipStatus, SlipType
from common.errors import AppError

pytestmark = pytest.mark.db

AT = datetime(2026, 11, 13, 10, 0, tzinfo=VN_TZ)


@pytest.fixture
async def world(conn: asyncpg.Connection) -> None:
    await seed_staff(conn)
    await seed_product(conn, "A")
    await seed_product(conn, "B")
    await seed_stock(conn, BRANCH_1, "A", 5)


async def _quantity(conn: asyncpg.Connection, product_id: str = "A") -> int | None:
    return await conn.fetchval(
        "SELECT quantity FROM stock WHERE branch_id = $1 AND product_id = $2", BRANCH_1, product_id
    )


async def _slip(conn: asyncpg.Connection, slip_id: str) -> asyncpg.Record:
    return await conn.fetchrow("SELECT * FROM stock_slips WHERE slip_id = $1", slip_id)


async def _order(conn: asyncpg.Connection, status: OrderStatus) -> str:
    return await seed_order(conn, SALES_ID, status=status, completed_at=AT)


async def test_check_available(conn: asyncpg.Connection, world: None) -> None:
    """4.1, TK-01: trả các dòng thiếu kèm tồn khả dụng, không giữ hàng."""
    assert await inventory.check_available(conn, BRANCH_1, [("A", 5)]) == []
    assert await inventory.check_available(conn, BRANCH_1, [("B", 1), ("A", 6)]) == [
        {"product_id": "A", "quantity": 6, "available": 5},
        {"product_id": "B", "quantity": 1, "available": 0},
    ]
    assert await conn.fetchval("SELECT count(*) FROM stock_slips") == 0


async def test_hold_then_confirm_sale(conn: asyncpg.Connection, world: None) -> None:
    """TK-03: giữ hàng tạo phiếu Xuất bán Chờ xử lý; thu Thành công thì Đã ghi nhận, trừ tồn."""
    order_1 = await seed_order(conn, SALES_ID, status=OrderStatus.AWAITING_PAYMENT)
    order_2 = await seed_order(conn, SALES_ID, status=OrderStatus.AWAITING_PAYMENT)
    async with conn.transaction():
        slip_id = await inventory.hold_for_order(conn, order_1, BRANCH_1, [("A", 3)], AT)
    slip = await _slip(conn, slip_id)
    assert (slip["type"], slip["status"]) == (SlipType.OUT_SALE, SlipStatus.PENDING)
    assert (slip["order_id"], slip["created_by"], slip["created_at"]) == (order_1, None, AT)
    assert await _quantity(conn) == 5
    assert await inventory.check_available(conn, BRANCH_1, [("A", 3)]) == [
        {"product_id": "A", "quantity": 3, "available": 2}
    ]
    with pytest.raises(AppError) as error:
        await inventory.hold_for_order(conn, order_2, BRANCH_1, [("A", 3)], AT)
    assert error.value.error_code == ErrorCode.INSUFFICIENT_STOCK
    assert error.value.details["rule"] == "TK-03"

    async with conn.transaction():
        await inventory.confirm_sale(conn, order_1, AT)
    slip = await _slip(conn, slip_id)
    assert (slip["status"], slip["finalized_at"]) == (SlipStatus.POSTED, AT)
    assert await _quantity(conn) == 2
    with pytest.raises(AppError) as error:
        await inventory.confirm_sale(conn, order_1, AT)
    assert error.value.error_code == ErrorCode.INVALID_STATE


async def test_release_hold(conn: asyncpg.Connection, world: None) -> None:
    """TK-03: thu Thất bại thì phiếu Xuất bán Đã hủy, nhả hàng; đơn giữ hàng lại được."""
    order = await seed_order(conn, SALES_ID, status=OrderStatus.AWAITING_PAYMENT)
    slip_id = await inventory.hold_for_order(conn, order, BRANCH_1, [("A", 5)], AT)
    await inventory.release_hold(conn, order, AT)
    slip = await _slip(conn, slip_id)
    assert (slip["status"], slip["finalized_at"]) == (SlipStatus.CANCELLED, AT)
    assert await _quantity(conn) == 5
    assert await inventory.check_available(conn, BRANCH_1, [("A", 5)]) == []
    with pytest.raises(AppError) as error:
        await inventory.release_hold(conn, order, AT)
    assert error.value.error_code == ErrorCode.INVALID_STATE
    assert await inventory.hold_for_order(conn, order, BRANCH_1, [("A", 5)], AT) != slip_id


async def test_receive_return(conn: asyncpg.Connection, world: None) -> None:
    """TK-02, TH-05: phiếu Nhập hàng trả ghi nhận ngay, đúng một lần mỗi phiếu trả."""
    order = await _order(conn, OrderStatus.COMPLETED)
    return_id = await seed_return_slip(conn, order, SALES_ID, ReturnStatus.APPROVED, MANAGER_ID)
    lines = [("A", 1), ("B", 2)]
    async with conn.transaction():
        slip_id = await inventory.receive_return(conn, return_id, BRANCH_1, lines, AT)
    slip = await _slip(conn, slip_id)
    assert (slip["type"], slip["status"]) == (SlipType.IN_RETURN, SlipStatus.POSTED)
    assert (slip["return_id"], slip["finalized_at"]) == (return_id, AT)
    assert (await _quantity(conn), await _quantity(conn, "B")) == (6, 2)
    with pytest.raises(AppError) as error:
        await inventory.receive_return(conn, return_id, BRANCH_1, [("A", 1)], AT)
    assert error.value.error_code == ErrorCode.DUPLICATE
    assert error.value.details["rule"] == "TH-05"
    assert await _quantity(conn) == 6


async def test_receive_return_without_good_items(conn: asyncpg.Connection, world: None) -> None:
    """Phiếu trả chỉ có hàng lỗi: không tạo phiếu nhập."""
    order = await _order(conn, OrderStatus.COMPLETED)
    return_id = await seed_return_slip(conn, order, SALES_ID, ReturnStatus.APPROVED, MANAGER_ID)
    assert await inventory.receive_return(conn, return_id, BRANCH_1, [], AT) is None
    assert await conn.fetchval("SELECT count(*) FROM stock_slips") == 0


async def test_two_connections_compete_for_last_unit(
    pool: asyncpg.Pool, conn: asyncpg.Connection, world: None
) -> None:
    """TK-03 (nền cho KT-06): hai giao dịch tranh sản phẩm cuối cùng, chỉ một giữ được hàng."""
    await conn.execute("UPDATE stock SET quantity = 1 WHERE product_id = 'A'")
    order_1 = await seed_order(conn, CASHIER_ID, status=OrderStatus.AWAITING_PAYMENT)
    order_2 = await seed_order(conn, CASHIER_ID, status=OrderStatus.AWAITING_PAYMENT)
    async with pool.acquire() as first, pool.acquire() as second:
        tx_1 = first.transaction()
        await tx_1.start()
        await inventory.hold_for_order(first, order_1, BRANCH_1, [("A", 1)], AT)

        async def hold_second() -> None:
            async with second.transaction():
                await inventory.hold_for_order(second, order_2, BRANCH_1, [("A", 1)], AT)

        task = asyncio.create_task(hold_second())
        # chờ tới khi giao dịch thứ hai bị chặn ở khóa dòng stock, rồi mới commit giao dịch đầu
        pid = second.get_server_pid()
        sql = "SELECT wait_event_type = 'Lock' FROM pg_stat_activity WHERE pid = $1"
        async with asyncio.timeout(5):
            while not await conn.fetchval(sql, pid):  # noqa: ASYNC110 - trạng thái nằm ở CSDL
                await asyncio.sleep(0.01)
        await tx_1.commit()
        with pytest.raises(AppError) as error:
            await task
    assert error.value.error_code == ErrorCode.INSUFFICIENT_STOCK
    pending = "SELECT order_id FROM stock_slips WHERE status = $1"
    assert [r["order_id"] for r in await conn.fetch(pending, SlipStatus.PENDING)] == [order_1]


async def test_hold_twice_for_same_order(conn: asyncpg.Connection, world: None) -> None:
    """TK-03: mỗi đơn tối đa một phiếu xuất bán chưa hủy."""
    order = await seed_order(conn, SALES_ID, status=OrderStatus.AWAITING_PAYMENT)
    await inventory.hold_for_order(conn, order, BRANCH_1, [("A", 1)], AT)
    with pytest.raises(AppError) as error:
        async with conn.transaction():
            await inventory.hold_for_order(conn, order, BRANCH_1, [("A", 1)], AT)
    assert (error.value.error_code, error.value.details["rule"]) == (
        ErrorCode.INVALID_STATE,
        "TK-03",
    )
