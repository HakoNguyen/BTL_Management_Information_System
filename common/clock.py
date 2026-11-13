"""Nguồn thời gian duy nhất của hệ thống.

Mọi mốc thời gian nghiệp vụ (lập, chốt, hoàn tất, duyệt, giờ đóng cửa…) lấy từ `clock.now()` rồi
truyền vào SQL. Không gọi `datetime.now()` hay `now()` của SQL trong code nghiệp vụ, để test đặt
được ngày giờ (KT-07, KT-08, KT-10).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

# Việt Nam cố định UTC+7, không có giờ mùa hè, nên không cần cơ sở dữ liệu múi giờ
VN_TZ = timezone(timedelta(hours=7))

_frozen: datetime | None = None


def now() -> datetime:
    return _frozen or datetime.now(VN_TZ)


def freeze(at: datetime | None) -> None:
    """Chỉ dùng trong test: cố định thời điểm hiện tại; truyền None để bỏ cố định."""
    global _frozen
    if at is not None and at.tzinfo is None:
        raise ValueError("Thời điểm cố định phải có múi giờ (dùng VN_TZ)")
    _frozen = at
