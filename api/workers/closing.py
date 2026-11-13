"""Sự kiện giờ đóng cửa (G-08): 3.4 tự hủy đơn quá hạn (BH-05), tự từ chối phiếu trả (TH-03).

`run_closing` nhận thời điểm để test gọi thẳng với đồng hồ cố định; `loop` chỉ gọi lại hàm
đó định kỳ.
Ghi vào D3 qua hàm của chủ kho (`orders`, `returns`); chạy lại nhiều lần không đổi kết quả.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time, timedelta

import asyncpg
from services import orders, returns

from common import clock
from common.clock import VN_TZ

log = logging.getLogger("api.closing")
CLOSING_INTERVAL_SECONDS = 60


def last_closing(at: datetime, closing_time: time) -> datetime:
    """Lần đóng cửa gần nhất ≤ `at`; giờ đóng cửa là giờ Việt Nam (docs/db.md mục 1)."""
    moment = datetime.combine(at.astimezone(VN_TZ).date(), closing_time, VN_TZ)
    return moment if moment <= at else moment - timedelta(days=1)


async def run_closing(conn: asyncpg.Connection, at: datetime) -> None:
    """Quyết định 9: chứng từ lập sau mốc đóng cửa chờ lần đóng cửa kế tiếp."""
    for branch in await conn.fetch("SELECT branch_id, closing_time FROM branches"):
        closing_at = last_closing(at, branch["closing_time"])
        cancelled = await orders.cancel_overdue(conn, branch["branch_id"], closing_at, at)
        rejected = await returns.reject_overdue(conn, branch["branch_id"], closing_at, at)
        if cancelled or rejected:
            log.info(
                "Đóng cửa %s: hủy đơn %s, từ chối phiếu trả %s",
                branch["branch_id"],
                cancelled,
                rejected,
            )


async def loop(pool: asyncpg.Pool) -> None:
    while True:
        try:
            async with pool.acquire() as conn:
                await run_closing(conn, clock.now())
        except Exception:  # lỗi một lần quét không được dừng tác vụ nền
            log.exception("Quét giờ đóng cửa lỗi")
        await asyncio.sleep(CLOSING_INTERVAL_SECONDS)
