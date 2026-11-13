"""Schema khớp docs/db.md: đủ 18 bảng, enum khớp CHECK, ràng buộc mục 5.3 chặn dữ liệu sai."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

import asyncpg
import pytest
from fixtures import BRANCH_1, CASHIER_ID, HQ_ID, SALES_ID, seed_branch, seed_employee

from common import constants as c
from common.clock import VN_TZ
from db.migrate import migrate

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 1, 10, 0, tzinfo=VN_TZ)

BUSINESS_TABLES = {
    "branches", "employees",
    "product_groups", "products", "price_history",
    "customers",
    "orders", "order_items", "return_slips", "return_slip_items",
    "transactions", "invoices", "shifts",
    "stock", "stock_slips", "stock_slip_items",
    "replenishment_requests", "replenishment_request_items",
}  # fmt: skip

# (bảng, cột) -> enum trong common/constants.py; hai bên phải liệt kê đúng cùng tập giá trị
ENUM_COLUMNS: dict[tuple[str, str], type[StrEnum]] = {
    ("branches", "status"): c.BranchStatus,
    ("employees", "role"): c.Role,
    ("employees", "status"): c.EmployeeStatus,
    ("employees", "account_status"): c.AccountStatus,
    ("products", "status"): c.ProductStatus,
    ("orders", "status"): c.OrderStatus,
    ("return_slips", "status"): c.ReturnStatus,
    ("transactions", "type"): c.TxnType,
    ("transactions", "method"): c.TxnMethod,
    ("transactions", "status"): c.TxnStatus,
    ("shifts", "status"): c.ShiftStatus,
    ("stock_slips", "type"): c.SlipType,
    ("stock_slips", "status"): c.SlipStatus,
    ("replenishment_requests", "type"): c.ReplenishType,
}


async def test_has_exactly_the_18_business_tables(conn: asyncpg.Connection) -> None:
    rows = await conn.fetch(
        "SELECT tablename FROM pg_tables"
        " WHERE schemaname = 'public' AND tablename <> 'schema_migrations'"
    )
    assert {row["tablename"] for row in rows} == BUSINESS_TABLES


async def test_migrate_is_idempotent(conn: asyncpg.Connection) -> None:
    assert await migrate(conn) == []


async def test_walk_in_customer_is_seeded(conn: asyncpg.Connection) -> None:
    phone = await conn.fetchval(
        "SELECT phone FROM customers WHERE customer_id = $1", c.WALK_IN_CUSTOMER_ID
    )
    assert phone is None
    assert await conn.fetchval("SELECT count(*) FROM customers") == 1


@pytest.mark.parametrize(("table", "column"), list(ENUM_COLUMNS))
async def test_enum_values_match_check_constraint(
    conn: asyncpg.Connection, table: str, column: str
) -> None:
    """Tập giá trị trong CHECK của cột phải trùng đúng tập giá trị của enum tương ứng."""
    definition = await conn.fetchval(
        "SELECT pg_get_constraintdef(con.oid) FROM pg_constraint con"
        " JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = ANY (con.conkey)"
        " WHERE con.conrelid = $1::regclass AND con.contype = 'c' AND att.attname = $2"
        " AND cardinality(con.conkey) = 1 AND pg_get_constraintdef(con.oid) LIKE '%ARRAY%'",
        table,
        column,
    )
    assert definition is not None, f"{table}.{column} chưa có CHECK liệt kê giá trị"
    # Dạng PostgreSQL trả về: CHECK ((status = ANY (ARRAY['ACTIVE'::text, 'INACTIVE'::text])))
    listed = definition.split("ARRAY[")[1].split("]")[0].replace("::text", "").replace("'", "")
    assert set(listed.split(", ")) == {member.value for member in ENUM_COLUMNS[(table, column)]}


async def _seed_order(conn: asyncpg.Connection) -> str:
    await seed_branch(conn)
    await seed_employee(conn, SALES_ID, c.Role.SALES, BRANCH_1)
    return await conn.fetchval(
        "INSERT INTO orders (branch_id, customer_id, created_by, created_at)"
        " VALUES ($1, $2, $3, $4) RETURNING order_id",
        BRANCH_1,
        c.WALK_IN_CUSTOMER_ID,
        SALES_ID,
        NOW,
    )


async def _seed_shift(conn: asyncpg.Connection) -> str:
    await seed_employee(conn, CASHIER_ID, c.Role.CASHIER, BRANCH_1)
    return await conn.fetchval(
        "INSERT INTO shifts (branch_id, cashier_id, opened_at, opening_cash)"
        " VALUES ($1, $2, $3, 0) RETURNING shift_id",
        BRANCH_1,
        CASHIER_ID,
        NOW,
    )


async def test_document_codes_use_prefix_and_restart_per_test(conn: asyncpg.Connection) -> None:
    assert await _seed_order(conn) == "DH000001"
    assert await _seed_shift(conn) == "CA000001"


async def test_hq_employee_cannot_have_branch(conn: asyncpg.Connection) -> None:
    """NV-01."""
    await seed_branch(conn)
    with pytest.raises(asyncpg.CheckViolationError):
        await seed_employee(conn, HQ_ID, c.Role.HQ, BRANCH_1)
    with pytest.raises(asyncpg.CheckViolationError):
        await seed_employee(conn, SALES_ID, c.Role.SALES, None)


async def test_stock_cannot_go_negative(conn: asyncpg.Connection) -> None:
    """TK-01."""
    await seed_branch(conn)
    await conn.execute("INSERT INTO product_groups (group_id, name) VALUES ('G1', 'Nhóm 1')")
    await conn.execute(
        "INSERT INTO products (product_id, name, group_id, unit, current_price)"
        " VALUES ('A', 'Sản phẩm A', 'G1', 'cái', 100000)"
    )
    await conn.execute(
        "INSERT INTO stock (branch_id, product_id, quantity) VALUES ($1, 'A', 1)", BRANCH_1
    )
    with pytest.raises(asyncpg.CheckViolationError):
        await conn.execute("UPDATE stock SET quantity = quantity - 2 WHERE product_id = 'A'")


async def test_one_open_shift_per_cashier(conn: asyncpg.Connection) -> None:
    """CA-01."""
    await seed_branch(conn)
    await _seed_shift(conn)
    with pytest.raises(asyncpg.UniqueViolationError):
        await conn.execute(
            "INSERT INTO shifts (branch_id, cashier_id, opened_at, opening_cash)"
            " VALUES ($1, $2, $3, 0)",
            BRANCH_1,
            CASHIER_ID,
            NOW,
        )


async def test_one_pending_transaction_per_order(conn: asyncpg.Connection) -> None:
    """Mục 5.3: mỗi đơn tối đa một giao dịch Chờ kết quả; giao dịch Thu không gắn phiếu trả."""
    order_id = await _seed_order(conn)
    shift_id = await _seed_shift(conn)
    insert = (
        "INSERT INTO transactions (order_id, shift_id, type, method, amount, created_at)"
        " VALUES ($1, $2, $3, $4, 200000, $5)"
    )
    args = (order_id, shift_id, c.TxnType.COLLECT, c.TxnMethod.CASH, NOW)
    await conn.execute(insert, *args)
    with pytest.raises(asyncpg.UniqueViolationError):
        await conn.execute(insert, *args)
    with pytest.raises(asyncpg.CheckViolationError):
        await conn.execute(insert, order_id, shift_id, c.TxnType.REFUND, c.TxnMethod.CASH, NOW)


async def test_delivery_note_cannot_be_posted_twice(conn: asyncpg.Connection) -> None:
    """TK-02 (KT-12): bộ (bên giao, số phiếu giao, chi nhánh) không được ghi hai lần."""
    await seed_branch(conn)
    insert = (
        "INSERT INTO stock_slips (branch_id, type, status, created_at, counterparty,"
        " delivery_no, finalized_at) VALUES ($1, $2, $3, $4, 'Kho tổng', 'PG-0815', $4)"
    )
    args = (BRANCH_1, c.SlipType.IN_WAREHOUSE, c.SlipStatus.POSTED, NOW)
    await conn.execute(insert, *args)
    with pytest.raises(asyncpg.UniqueViolationError):
        await conn.execute(insert, *args)
