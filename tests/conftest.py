"""Conftest gốc: đường dẫn import, CSDL test, đồng hồ, ứng dụng và HTTP client cho test.

Test chạy trên PostgreSQL thật (CSDL có tên kết thúc bằng `_test`), vì phần lớn quy tắc của đặc tả
được ép bằng ràng buộc và transaction của CSDL. Xem docs/tests.md mục 1.
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import asyncpg
import httpx
import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent

for _p in (str(REPO_ROOT), str(REPO_ROOT / "api"), str(TESTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fixtures import BANK_TEST_KEY, TEST_SECRET  # noqa: E402
from main import create_app  # noqa: E402

from common import clock  # noqa: E402
from common.constants import ENV_BANK_KEY, ENV_BANK_URL  # noqa: E402
from db.migrate import MIGRATIONS_DIR, migrate  # noqa: E402


def _dotenv() -> dict[str, str]:
    path = REPO_ROOT / ".env"
    if not path.exists():
        return {}
    pairs = (
        line.split("=", 1)
        for line in path.read_text(encoding="utf-8").splitlines()
        if "=" in line and not line.lstrip().startswith("#")
    )
    return {key.strip(): value.strip() for key, value in pairs}


def _test_db_url() -> str:
    """TEST_DB_URL nếu có (CI); không thì ghép từ .env, trỏ vào container db đang chạy."""
    if url := os.environ.get("TEST_DB_URL"):
        return url
    env = _dotenv()
    password = env.get("POSTGRES_PASSWORD", "postgres")
    return f"postgresql://postgres:{password}@localhost:{env.get('DB_PORT', '5432')}/qlbh_test"


TEST_DB_URL = _test_db_url()


async def _prepare_database(url: str) -> None:
    base, _, name = url.rpartition("/")
    # Chặn xóa nhầm dữ liệu thật: chỉ dựng lại schema trên CSDL có tên kết thúc bằng _test
    if not name.endswith("_test"):
        raise RuntimeError(f"TEST_DB_URL phải trỏ vào CSDL có tên kết thúc bằng _test: {name}")
    admin = await asyncpg.connect(f"{base}/postgres", timeout=5)
    try:
        if not await admin.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", name):
            await admin.execute(f'CREATE DATABASE "{name}"')
    finally:
        await admin.close()
    conn = await asyncpg.connect(url, timeout=5)
    try:
        await conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        await migrate(conn)
    finally:
        await conn.close()


@pytest.fixture(scope="session")
def database() -> str:
    """Dựng lại schema một lần mỗi phiên test.

    Không kết nối được CSDL: skip ở máy cá nhân, báo lỗi trên CI.
    """
    try:
        asyncio.run(_prepare_database(TEST_DB_URL))
    except (TimeoutError, OSError, asyncpg.PostgresError) as exc:
        if os.environ.get("CI"):
            raise
        pytest.skip(f"Không kết nối được CSDL test (chạy `make up` trước): {exc!r}")
    return TEST_DB_URL


async def reset_data(conn: asyncpg.Connection) -> None:
    """Xóa sạch dữ liệu, đưa các dãy số mã chứng từ về 1, nạp lại dữ liệu tham chiếu."""
    tables = await conn.fetch(
        "SELECT tablename FROM pg_tables"
        " WHERE schemaname = 'public' AND tablename <> 'schema_migrations'"
    )
    names = ", ".join(f'"{row["tablename"]}"' for row in tables)
    await conn.execute(f"TRUNCATE {names} RESTART IDENTITY CASCADE")
    await conn.execute((MIGRATIONS_DIR / "002_seed.sql").read_text(encoding="utf-8"))


@pytest.fixture
async def pool(database: str) -> AsyncIterator[asyncpg.Pool]:
    pool = await asyncpg.create_pool(database, min_size=1, max_size=5)
    async with pool.acquire() as conn:
        await reset_data(conn)
    yield pool
    await pool.close()


@pytest.fixture
async def conn(pool: asyncpg.Pool) -> AsyncIterator[asyncpg.Connection]:
    async with pool.acquire() as connection:
        yield connection


@pytest.fixture(autouse=True)
def _unfreeze_clock() -> Iterator[None]:
    yield
    clock.freeze(None)


@pytest.fixture(autouse=True)
def _bank_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Không test nào gọi cổng thật: bỏ BANK_URL; test đóng vai cổng bằng khóa BANK_TEST_KEY."""
    monkeypatch.delenv(ENV_BANK_URL, raising=False)
    monkeypatch.setenv(ENV_BANK_KEY, BANK_TEST_KEY)


@pytest.fixture
def app(pool: asyncpg.Pool):  # type: ignore[no-untyped-def]
    """Ứng dụng dùng pool của test; không chạy lifespan nên không migrate hay tạo admin."""
    application = create_app()
    application.state.pool = pool
    application.state.secret_key = TEST_SECRET
    return application


@pytest.fixture
async def client(app) -> AsyncIterator[httpx.AsyncClient]:  # type: ignore[no-untyped-def]
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
