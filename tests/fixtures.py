"""Mã cố định và hàm dựng dữ liệu dùng chung cho test (docs/tests.md mục 2).

Mỗi vòng nghiệp vụ thêm hàm dựng dữ liệu của mình vào đây (sản phẩm, tồn, đơn…), dùng lại các mã này
để test, dữ liệu demo và tài liệu khớp nhau.
"""

from __future__ import annotations

from datetime import date, datetime, time

import asyncpg
import httpx

from common.auth import hash_password
from common.clock import VN_TZ
from common.constants import (
    AccountStatus,
    EmployeeStatus,
    OrderStatus,
    ReturnStatus,
    Role,
    ShiftStatus,
    SlipStatus,
    SlipType,
    TxnMethod,
    TxnStatus,
    TxnType,
)

TEST_SECRET = "khoa-bi-mat-chi-dung-cho-test"
TEST_PASSWORD = "mat-khau-test"
# Băm một lần cho cả phiên test: scrypt cố ý chậm
_TEST_PASSWORD_HASH = hash_password(TEST_PASSWORD)

BRANCH_1 = "CN1"
BRANCH_2 = "CN2"

# Mỗi vai trò một nhân viên mẫu; tên đăng nhập trùng mã nhân viên viết thường
HQ_ID = "NV-TS"
MANAGER_ID = "NV-QL1"
SALES_ID = "NV-BH1"
CASHIER_ID = "NV-TN1"
WAREHOUSE_ID = "NV-KHO1"

GROUP_ID = "NHOM1"


async def seed_branch(
    conn: asyncpg.Connection, branch_id: str = BRANCH_1, closing_time: time = time(22, 0)
) -> str:
    await conn.execute(
        "INSERT INTO branches (branch_id, name, closing_time) VALUES ($1, $2, $3)",
        branch_id,
        f"Chi nhánh {branch_id}",
        closing_time,
    )
    return branch_id


async def seed_employee(
    conn: asyncpg.Connection,
    employee_id: str,
    role: Role,
    branch_id: str | None = None,
    *,
    with_account: bool = True,
    account_status: AccountStatus = AccountStatus.ACTIVE,
    status: EmployeeStatus = EmployeeStatus.WORKING,
) -> str:
    """Tạo nhân viên; có tài khoản thì tên đăng nhập là mã viết thường, mật khẩu TEST_PASSWORD."""
    await conn.execute(
        "INSERT INTO employees (employee_id, full_name, role, branch_id, hired_on, status,"
        " username, password_hash, account_status) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)",
        employee_id,
        f"Nhân viên {employee_id}",
        role,
        branch_id,
        date(2026, 1, 1),
        status,
        employee_id.lower() if with_account else None,
        _TEST_PASSWORD_HASH if with_account else None,
        account_status if with_account else None,
    )
    return employee_id


async def login_as(client: httpx.AsyncClient, employee_id: str) -> dict[str, str]:
    """Đăng nhập bằng nhân viên đã seed; trả header Authorization để gắn vào các request sau."""
    response = await client.post(
        "/auth/login", json={"username": employee_id.lower(), "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


async def seed_staff(conn: asyncpg.Connection) -> None:
    """CN1, CN2 và năm nhân viên mẫu (HQ_ID không thuộc chi nhánh; bốn người còn lại ở CN1)."""
    await seed_branch(conn, BRANCH_1)
    await seed_branch(conn, BRANCH_2)
    await seed_employee(conn, HQ_ID, Role.HQ)
    for employee_id, role in (
        (MANAGER_ID, Role.MANAGER),
        (SALES_ID, Role.SALES),
        (CASHIER_ID, Role.CASHIER),
        (WAREHOUSE_ID, Role.WAREHOUSE),
    ):
        await seed_employee(conn, employee_id, role, BRANCH_1)


# Các hàm dưới đây chèn thẳng chứng từ D3, D4, D5 để test vòng 1 dựng trạng thái khi module sở hữu
# chưa có API. shortcut: chỉ điền cột bắt buộc; vòng của module sở hữu viết lại qua API của mình.
SEED_AT = datetime(2026, 1, 1, 9, 0, tzinfo=VN_TZ)


async def seed_product(
    conn: asyncpg.Connection,
    product_id: str = "A",
    price: int = 100_000,
    group_id: str = GROUP_ID,
) -> str:
    """Sản phẩm Đang bán kèm lịch sử giá đầu tiên do HQ_ID lập (SP-02); cần seed_staff trước."""
    await conn.execute(
        "INSERT INTO product_groups (group_id, name) VALUES ($1, $2) ON CONFLICT DO NOTHING",
        group_id,
        f"Nhóm {group_id}",
    )
    await conn.execute(
        "INSERT INTO products (product_id, name, group_id, unit, current_price)"
        " VALUES ($1, $2, $3, 'cái', $4)",
        product_id,
        f"Sản phẩm {product_id}",
        group_id,
        price,
    )
    await conn.execute(
        "INSERT INTO price_history (product_id, effective_at, price, changed_by)"
        " VALUES ($1, $2, $3, $4)",
        product_id,
        SEED_AT,
        price,
        HQ_ID,
    )
    return product_id


async def seed_order_item(
    conn: asyncpg.Connection, order_id: str, product_id: str, quantity: int = 1
) -> None:
    await conn.execute(
        "INSERT INTO order_items (order_id, product_id, quantity) VALUES ($1, $2, $3)",
        order_id,
        product_id,
        quantity,
    )


async def seed_stock_slip_item(
    conn: asyncpg.Connection, slip_id: str, product_id: str, quantity: int = 1
) -> None:
    await conn.execute(
        "INSERT INTO stock_slip_items (slip_id, product_id, quantity) VALUES ($1, $2, $3)",
        slip_id,
        product_id,
        quantity,
    )


async def seed_stock(
    conn: asyncpg.Connection, branch_id: str, product_id: str, quantity: int
) -> None:
    await conn.execute(
        "INSERT INTO stock (branch_id, product_id, quantity) VALUES ($1, $2, $3)",
        branch_id,
        product_id,
        quantity,
    )


async def seed_shift(
    conn: asyncpg.Connection,
    cashier_id: str,
    branch_id: str = BRANCH_1,
    status: ShiftStatus = ShiftStatus.OPEN,
) -> str:
    return await conn.fetchval(
        "INSERT INTO shifts (branch_id, cashier_id, opened_at, opening_cash, status)"
        " VALUES ($1, $2, $3, 0, $4) RETURNING shift_id",
        branch_id,
        cashier_id,
        SEED_AT,
        status,
    )


async def seed_order(
    conn: asyncpg.Connection,
    created_by: str,
    branch_id: str = BRANCH_1,
    status: OrderStatus = OrderStatus.DRAFT,
    completed_at: datetime | None = None,
    customer_id: str = "KHLE",
) -> str:
    cancelled = status == OrderStatus.CANCELLED
    return await conn.fetchval(
        "INSERT INTO orders (branch_id, customer_id, created_by, created_at, completed_at, status,"
        " cancelled_at, cancel_reason) VALUES ($1, $8, $2, $3, $4, $5, $6, $7)"
        " RETURNING order_id",
        branch_id,
        created_by,
        completed_at or SEED_AT,
        completed_at,
        status,
        SEED_AT if cancelled else None,
        "Khách đổi ý" if cancelled else None,
        customer_id,
    )


async def seed_return_slip(
    conn: asyncpg.Connection,
    order_id: str,
    created_by: str,
    status: ReturnStatus = ReturnStatus.PENDING,
    decided_by: str | None = None,
) -> str:
    return await conn.fetchval(
        "INSERT INTO return_slips (order_id, created_by, created_at, reason, status, decided_by,"
        " decided_at) VALUES ($1, $2, $3, 'Lỗi', $4, $5, $6) RETURNING return_id",
        order_id,
        created_by,
        SEED_AT,
        status,
        decided_by,
        None if status == ReturnStatus.PENDING else SEED_AT,
    )


async def seed_stock_slip(
    conn: asyncpg.Connection,
    branch_id: str,
    created_by: str,
    status: SlipStatus = SlipStatus.PENDING,
) -> str:
    return await conn.fetchval(
        "INSERT INTO stock_slips (branch_id, type, status, created_at, created_by, reason,"
        " finalized_at) VALUES ($1, $2, $3, $4, $5, 'Hàng hỏng', $6) RETURNING slip_id",
        branch_id,
        SlipType.ADJUST_DOWN,
        status,
        SEED_AT,
        created_by,
        None if status == SlipStatus.PENDING else SEED_AT,
    )


async def seed_transaction(
    conn: asyncpg.Connection,
    order_id: str,
    shift_id: str,
    status: TxnStatus = TxnStatus.SUCCESS,
    return_id: str | None = None,
    amount: int = 100_000,
    method: TxnMethod = TxnMethod.CASH,
) -> str:
    """Giao dịch tiền mặt 100.000; có `return_id` thì là giao dịch Hoàn của phiếu đó."""
    return await conn.fetchval(
        "INSERT INTO transactions (order_id, return_id, shift_id, type, method, amount, status,"
        " created_at, resolved_at) VALUES ($1, $2, $3, $4, $5, $9, $6, $7, $8)"
        " RETURNING txn_id",
        order_id,
        return_id,
        shift_id,
        TxnType.REFUND if return_id else TxnType.COLLECT,
        method,
        status,
        SEED_AT,
        None if status == TxnStatus.PENDING else SEED_AT,
        amount,
    )


# ---------------------------------------------------------------- Vòng 6: ca, thu tiền qua API

# Khóa X-Bank-Key của test; tests/conftest.py đặt vào BANK_KEY và bỏ BANK_URL cho mọi test
BANK_TEST_KEY = "khoa-cong-thanh-toan-test"


async def create_awaiting_order(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    items: dict[str, int],
    customer_id: str = "KHLE",
) -> str:
    """Lập và chốt đơn (mặc định KHLE) qua API (3.1); trả mã đơn Chờ thanh toán."""
    body = {
        "customer_id": customer_id,
        "items": [{"product_id": pid, "quantity": qty} for pid, qty in items.items()],
    }
    response = await client.post("/orders", json=body, headers=headers)
    assert response.status_code == 201, response.text
    order_id = response.json()["order_id"]
    response = await client.post(f"/orders/{order_id}/confirm", headers=headers)
    assert response.status_code == 200, response.text
    return order_id


async def open_shift(
    client: httpx.AsyncClient, headers: dict[str, str], opening_cash: int = 0
) -> str:
    response = await client.post("/shifts", json={"opening_cash": opening_cash}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["shift_id"]


async def start_payment(
    client: httpx.AsyncClient, headers: dict[str, str], order_id: str, method: TxnMethod
) -> dict:
    """Khởi tạo thu (3.2); trả giao dịch Chờ kết quả."""
    response = await client.post(
        f"/orders/{order_id}/payments", json={"method": method}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


async def bank_callback(
    client: httpx.AsyncClient,
    txn_id: str,
    result: TxnStatus,
    reference_code: str | None = None,
    key: str = BANK_TEST_KEY,
) -> httpx.Response:
    """Cổng thanh toán gọi lại api (docs/api.md mục 6)."""
    return await client.post(
        "/bank/callback",
        json={"txn_id": txn_id, "result": result, "reference_code": reference_code},
        headers={"X-Bank-Key": key},
    )


# ---------------------------------------------------------------- Vòng 7: đơn Hoàn tất, phiếu trả


async def resolve_txn(
    client: httpx.AsyncClient, headers: dict[str, str], txn: dict, result: TxnStatus
) -> dict:
    """Giao dịch Chờ kết quả có kết quả: tiền mặt do thu ngân xác nhận, điện tử do cổng gọi lại."""
    if txn["method"] == TxnMethod.CASH:
        response = await client.post(
            f"/transactions/{txn['txn_id']}/confirm-cash", json={"result": result}, headers=headers
        )
    else:
        reference = f"REF-{txn['txn_id']}" if result == TxnStatus.SUCCESS else None
        response = await bank_callback(client, txn["txn_id"], result, reference)
    assert response.status_code == 200, response.text
    return response.json()


async def complete_order(
    client: httpx.AsyncClient,
    sales: dict[str, str],
    cashier: dict[str, str],
    items: dict[str, int],
    method: TxnMethod = TxnMethod.CASH,
    customer_id: str = "KHLE",
) -> str:
    """Lập, chốt, thu Thành công qua API (thu ngân phải có ca Đang mở); trả mã đơn Hoàn tất."""
    order_id = await create_awaiting_order(client, sales, items, customer_id)
    await resolve_txn(
        client, cashier, await start_payment(client, cashier, order_id, method), TxnStatus.SUCCESS
    )
    return order_id


async def create_return(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    order_id: str,
    items: dict[str, tuple[int, int]],
    reason: str = "Khách không ưng",
    invoice_presented: bool = True,
) -> httpx.Response:
    """Lập phiếu trả (3.4); `items` là {mã SP: (số lượng tốt, số lượng lỗi)}.
    Mặc định khách xuất trình hóa đơn (TH-01)."""
    body = {
        "order_id": order_id,
        "reason": reason,
        "invoice_presented": invoice_presented,
        "items": [
            {"product_id": pid, "good_qty": good, "defective_qty": bad}
            for pid, (good, bad) in items.items()
        ],
    }
    return await client.post("/returns", json=body, headers=headers)
