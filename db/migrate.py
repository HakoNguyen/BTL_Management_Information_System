"""Chạy các file db/migrations/*.sql chưa áp dụng, theo thứ tự tên file.

Dùng chung cho API lúc khởi động (api/main.py) và cho test (tests/conftest.py), để CSDL thật và
CSDL test luôn có cùng schema. Bảng schema_migrations là bảng kỹ thuật, không thuộc 18 bảng
nghiệp vụ.
"""

from __future__ import annotations

from pathlib import Path

import asyncpg

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


async def migrate(conn: asyncpg.Connection) -> list[str]:
    """Trả danh sách file vừa áp dụng. Mỗi file chạy trong một transaction."""
    # shortcut: không khóa chống hai tiến trình cùng migrate, vì chỉ có một container api;
    # chạy nhiều bản api thì bọc bằng pg_advisory_lock.
    await conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        " filename text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
    )
    rows = await conn.fetch("SELECT filename FROM schema_migrations")
    applied = {row["filename"] for row in rows}
    done: list[str] = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if path.name in applied:
            continue
        async with conn.transaction():
            await conn.execute(path.read_text(encoding="utf-8"))
            await conn.execute("INSERT INTO schema_migrations (filename) VALUES ($1)", path.name)
        done.append(path.name)
    return done
