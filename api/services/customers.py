"""Nhóm 2 – Khách hàng (kho D2): chức năng 2.1 đến 2.3.

Mọi lệnh ghi vào `customers` nằm ở file này.
Khách dùng chung toàn chuỗi (G-06) nên không so chi nhánh.
"""

from __future__ import annotations

import re

import asyncpg

from common import clock
from common.clock import VN_TZ
from common.constants import WALK_IN_CUSTOMER_ID, ErrorCode
from common.errors import AppError
from common.models import Customer, CustomerCreate, CustomerUpdate

_COLUMNS = "customer_id, full_name, phone, address, registered_on"
_PHONE = re.compile(r"0\d{9,10}")


def normalize_phone(phone: str) -> str:
    """KH-01: bỏ ký tự phân cách, +84 → 0; kết quả là 0 và 9 hoặc 10 chữ số (docs/api.md nhóm 2)."""
    digits = re.sub(r"[\s.\-()]", "", phone)
    if digits.startswith("+84"):
        digits = "0" + digits[3:]
    if not _PHONE.fullmatch(digits):
        raise AppError(ErrorCode.VALIDATION_ERROR, "Số điện thoại không hợp lệ", rule="KH-01")
    return digits


def _reject_walk_in(customer_id: str) -> None:
    if customer_id == WALK_IN_CUSTOMER_ID:
        raise AppError(
            ErrorCode.RULE_VIOLATION, "Khách lẻ KHLE không có hồ sơ cá nhân", rule="KH-02"
        )


async def _by_phone(conn: asyncpg.Connection, phone: str) -> asyncpg.Record | None:
    return await conn.fetchrow(f"SELECT {_COLUMNS} FROM customers WHERE phone = $1", phone)


# ---------------------------------------------------------------- 2.1 Ghi nhận khách mới


async def create_customer(conn: asyncpg.Connection, body: CustomerCreate) -> tuple[Customer, bool]:
    """Trả (hồ sơ, đã tạo mới?). Số đã có hồ sơ thì trả hồ sơ có sẵn, không đổi gì (2.1)."""
    phone = normalize_phone(body.phone)
    row = await _by_phone(conn, phone)
    if row is not None:
        return Customer(**row), False
    row = await conn.fetchrow(
        "INSERT INTO customers (full_name, phone, address, registered_on) VALUES ($1, $2, $3, $4)"
        f" ON CONFLICT (phone) DO NOTHING RETURNING {_COLUMNS}",
        body.full_name,
        phone,
        body.address,
        clock.now().astimezone(VN_TZ).date(),
    )
    if row is None:  # yêu cầu khác vừa tạo cùng số
        return Customer(**await _by_phone(conn, phone)), False
    return Customer(**row), True


# ---------------------------------------------------------------- 2.2 Cập nhật


async def update_customer(
    conn: asyncpg.Connection, customer_id: str, body: CustomerUpdate
) -> Customer:
    """KH-01: số mới không thuộc hồ sơ khác; KH-03: mã khách không đổi nên đơn cũ giữ nguyên."""
    _reject_walk_in(customer_id)
    changes = body.model_dump(exclude_unset=True)
    if "phone" in changes:
        changes["phone"] = normalize_phone(changes["phone"])
    if changes:
        # tên cột lấy từ trường của model, không từ giá trị gửi lên
        sets = ", ".join(f"{column} = ${i}" for i, column in enumerate(changes, start=2))
        sql = f"UPDATE customers SET {sets} WHERE customer_id = $1 RETURNING {_COLUMNS}"
    else:
        sql = f"SELECT {_COLUMNS} FROM customers WHERE customer_id = $1"
    try:
        row = await conn.fetchrow(sql, customer_id, *changes.values())
    except asyncpg.UniqueViolationError:
        raise AppError(
            ErrorCode.DUPLICATE, "Số điện thoại đã thuộc hồ sơ khách khác", rule="KH-01"
        ) from None
    if row is None:
        raise AppError(ErrorCode.NOT_FOUND, f"Không tìm thấy {customer_id}")
    return Customer(**row)


# ---------------------------------------------------------------- 2.3 Tra cứu


async def search_customers(
    conn: asyncpg.Connection, phone: str | None, customer_id: str | None
) -> list[Customer]:
    """Tra theo đúng một tiêu chí; không khớp thì trả rỗng ("Không tìm thấy")."""
    if (phone is None) == (customer_id is None):
        raise AppError(
            ErrorCode.VALIDATION_ERROR, "Nhập đúng một tiêu chí: số điện thoại hoặc mã khách"
        )
    if customer_id is not None:
        _reject_walk_in(customer_id)
        row = await conn.fetchrow(
            f"SELECT {_COLUMNS} FROM customers WHERE customer_id = $1", customer_id
        )
    else:
        row = await _by_phone(conn, normalize_phone(phone or ""))
    return [] if row is None else [Customer(**row)]
