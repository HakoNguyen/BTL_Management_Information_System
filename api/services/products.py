"""Nhóm 1 – Sản phẩm (kho D1): chức năng 1.1 đến 1.4.

Mọi lệnh ghi vào `product_groups`, `products`, `price_history` nằm ở file này.
Đọc `order_items`, `stock_slip_items` chỉ để kiểm tra điều kiện đổi đơn vị tính (1.1).
"""

from __future__ import annotations

from typing import Any

import asyncpg

from common import clock
from common.constants import ErrorCode, ProductStatus
from common.errors import AppError
from common.models import (
    PriceHistoryEntry,
    Product,
    ProductCreate,
    ProductGroup,
    ProductGroupCreate,
    ProductGroupUpdate,
    ProductUpdate,
)

_GROUP_COLUMNS = "group_id, name, description"
_PRODUCT_COLUMNS = "product_id, name, group_id, unit, current_price, description, status"


def _not_found(code: str) -> AppError:
    return AppError(ErrorCode.NOT_FOUND, f"Không tìm thấy {code}")


def _require_positive(price: int) -> None:
    if price <= 0:
        raise AppError(ErrorCode.RULE_VIOLATION, "Giá bán phải lớn hơn 0", rule="SP-02")


async def _update(
    conn: asyncpg.Connection, table: str, key: str, key_value: str, changes: dict[str, Any]
) -> asyncpg.Record:
    """UPDATE các cột trong `changes`; tên cột lấy từ trường của model, không từ giá trị gửi lên."""
    columns = _GROUP_COLUMNS if table == "product_groups" else _PRODUCT_COLUMNS
    if changes:
        sets = ", ".join(f"{column} = ${i}" for i, column in enumerate(changes, start=2))
        sql = f"UPDATE {table} SET {sets} WHERE {key} = $1 RETURNING {columns}"
    else:
        sql = f"SELECT {columns} FROM {table} WHERE {key} = $1"
    row = await conn.fetchrow(sql, key_value, *changes.values())
    if row is None:
        raise _not_found(key_value)
    return row


# ---------------------------------------------------------------- 1.2 Nhóm sản phẩm


async def list_groups(conn: asyncpg.Connection) -> list[ProductGroup]:
    rows = await conn.fetch(f"SELECT {_GROUP_COLUMNS} FROM product_groups ORDER BY group_id")
    return [ProductGroup(**row) for row in rows]


async def create_group(conn: asyncpg.Connection, body: ProductGroupCreate) -> ProductGroup:
    row = await conn.fetchrow(
        "INSERT INTO product_groups (group_id, name, description) VALUES ($1, $2, $3)"
        f" ON CONFLICT (group_id) DO NOTHING RETURNING {_GROUP_COLUMNS}",
        body.group_id,
        body.name,
        body.description,
    )
    if row is None:
        raise AppError(ErrorCode.DUPLICATE, f"Mã nhóm {body.group_id} đã có", rule="SP-01")
    return ProductGroup(**row)


async def update_group(
    conn: asyncpg.Connection, group_id: str, body: ProductGroupUpdate
) -> ProductGroup:
    changes = body.model_dump(exclude_unset=True)
    return ProductGroup(**await _update(conn, "product_groups", "group_id", group_id, changes))


async def delete_group(conn: asyncpg.Connection, group_id: str) -> ProductGroup:
    """SP-01: không xóa nhóm còn sản phẩm; khóa ngoại của `products` là chốt chặn khi tranh chấp."""
    try:
        row = await conn.fetchrow(
            f"DELETE FROM product_groups WHERE group_id = $1 RETURNING {_GROUP_COLUMNS}", group_id
        )
    except asyncpg.ForeignKeyViolationError:
        raise AppError(
            ErrorCode.RULE_VIOLATION, f"Nhóm {group_id} còn sản phẩm", rule="SP-01"
        ) from None
    if row is None:
        raise _not_found(group_id)
    return ProductGroup(**row)


async def change_group(conn: asyncpg.Connection, product_id: str, group_id: str) -> Product:
    try:
        row = await _update(conn, "products", "product_id", product_id, {"group_id": group_id})
    except asyncpg.ForeignKeyViolationError:
        raise _not_found(group_id) from None
    return Product(**row)


# ---------------------------------------------------------------- 1.1 Sản phẩm


async def list_products(conn: asyncpg.Connection) -> list[Product]:
    rows = await conn.fetch(f"SELECT {_PRODUCT_COLUMNS} FROM products ORDER BY product_id")
    return [Product(**row) for row in rows]


async def get_product(conn: asyncpg.Connection, product_id: str) -> Product:
    return Product(**await _update(conn, "products", "product_id", product_id, {}))


async def create_product(conn: asyncpg.Connection, body: ProductCreate, user_id: str) -> Product:
    """SP-02: sản phẩm Đang bán kèm bản ghi lịch sử giá đầu tiên trong cùng transaction."""
    _require_positive(body.price)
    async with conn.transaction():
        try:
            row = await conn.fetchrow(
                "INSERT INTO products"
                " (product_id, name, group_id, unit, current_price, description)"
                " VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT (product_id) DO NOTHING"
                f" RETURNING {_PRODUCT_COLUMNS}",
                body.product_id,
                body.name,
                body.group_id,
                body.unit,
                body.price,
                body.description,
            )
        except asyncpg.ForeignKeyViolationError:
            raise AppError(ErrorCode.NOT_FOUND, f"Không tìm thấy nhóm {body.group_id}") from None
        if row is None:
            raise AppError(
                ErrorCode.DUPLICATE, f"Mã sản phẩm {body.product_id} đã có", rule="SP-01"
            )
        await conn.execute(
            "INSERT INTO price_history (product_id, effective_at, price, changed_by)"
            " VALUES ($1, $2, $3, $4)",
            body.product_id,
            clock.now(),
            body.price,
            user_id,
        )
        return Product(**row)


async def update_product(conn: asyncpg.Connection, product_id: str, body: ProductUpdate) -> Product:
    """1.1: đơn vị tính chỉ đổi khi sản phẩm chưa có trên đơn hoặc phiếu kho (SP-04)."""
    changes = body.model_dump(exclude_unset=True)
    async with conn.transaction():
        # FOR UPDATE chặn đơn, phiếu kho mới chèn dòng tham chiếu sản phẩm này cho tới khi commit
        unit = await conn.fetchval(
            "SELECT unit FROM products WHERE product_id = $1 FOR UPDATE", product_id
        )
        if unit is None:
            raise _not_found(product_id)
        if changes.get("unit", unit) != unit and await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM order_items WHERE product_id = $1)"
            " OR EXISTS (SELECT 1 FROM stock_slip_items WHERE product_id = $1)",
            product_id,
        ):
            raise AppError(
                ErrorCode.RULE_VIOLATION,
                "Sản phẩm đã có trên đơn hoặc phiếu kho, không đổi được đơn vị tính",
                rule="SP-04",
            )
        return Product(**await _update(conn, "products", "product_id", product_id, changes))


# ---------------------------------------------------------------- 1.3 Giá bán


async def change_price(
    conn: asyncpg.Connection, product_id: str, price: int, user_id: str
) -> Product:
    """SP-02: giá > 0, khác giá hiện hành, hiệu lực ngay; ghi lịch sử giá."""
    _require_positive(price)
    async with conn.transaction():
        current = await conn.fetchval(
            "SELECT current_price FROM products WHERE product_id = $1 FOR UPDATE", product_id
        )
        if current is None:
            raise _not_found(product_id)
        if current == price:
            raise AppError(
                ErrorCode.RULE_VIOLATION, "Giá mới phải khác giá hiện hành", rule="SP-02"
            )
        await conn.execute(
            "INSERT INTO price_history (product_id, effective_at, price, changed_by)"
            " VALUES ($1, $2, $3, $4)",
            product_id,
            clock.now(),
            price,
            user_id,
        )
        row = await _update(conn, "products", "product_id", product_id, {"current_price": price})
        return Product(**row)


async def price_history(conn: asyncpg.Connection, product_id: str) -> list[PriceHistoryEntry]:
    rows = await conn.fetch(
        "SELECT effective_at, price, changed_by FROM price_history WHERE product_id = $1"
        " ORDER BY effective_at",
        product_id,
    )
    if not rows:  # mọi sản phẩm có ít nhất một bản ghi (SP-02)
        raise _not_found(product_id)
    return [PriceHistoryEntry(**row) for row in rows]


# ---------------------------------------------------------------- 1.4 Trạng thái kinh doanh


async def set_status(conn: asyncpg.Connection, product_id: str, target: ProductStatus) -> Product:
    """Đang bán ↔ Ngừng bán (SP-04)."""
    current = (
        ProductStatus.ON_SALE
        if target == ProductStatus.DISCONTINUED
        else ProductStatus.DISCONTINUED
    )
    row = await conn.fetchrow(
        f"UPDATE products SET status = $2 WHERE product_id = $1 AND status = $3"
        f" RETURNING {_PRODUCT_COLUMNS}",
        product_id,
        target,
        current,
    )
    if row is not None:
        return Product(**row)
    if await conn.fetchval("SELECT 1 FROM products WHERE product_id = $1", product_id):
        raise AppError(ErrorCode.INVALID_STATE, "Sản phẩm đã ở trạng thái này")
    raise _not_found(product_id)
