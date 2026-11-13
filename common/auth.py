"""Băm mật khẩu (scrypt) và token phiên đăng nhập ký HMAC-SHA256. Chỉ dùng thư viện chuẩn.

Token chỉ mang mã nhân viên và hạn dùng. Vai trò, chi nhánh, trạng thái tài khoản được đọc lại
từ CSDL ở mỗi request (api/deps.py) để đúng K-01: quyền kiểm tra tại thời điểm thao tác.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets

from common.constants import TOKEN_TTL_SECONDS

_SCRYPT = {"n": 2**14, "r": 8, "p": 1}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_hex, digest_hex = stored.split("$")
        salt, expected = bytes.fromhex(salt_hex), bytes.fromhex(digest_hex)
    except ValueError:
        return False
    if scheme != "scrypt":
        return False
    return hmac.compare_digest(hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT), expected)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(payload: str, secret: str) -> str:
    return _b64(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())


def make_token(
    employee_id: str, secret: str, now_ts: float, ttl: int = TOKEN_TTL_SECONDS
) -> str:
    payload = _b64(json.dumps({"sub": employee_id, "exp": int(now_ts) + ttl}).encode())
    return f"{payload}.{_sign(payload, secret)}"


def read_token(token: str, secret: str, now_ts: float) -> str | None:
    """Trả mã nhân viên nếu token đúng chữ ký và còn hạn; ngược lại None."""
    payload, _, signature = token.partition(".")
    if not signature or not hmac.compare_digest(signature, _sign(payload, secret)):
        return None
    try:
        data = json.loads(_unb64(payload))
        employee_id, expires = data["sub"], data["exp"]
    except (ValueError, KeyError, TypeError):
        return None
    if not isinstance(employee_id, str) or not isinstance(expires, int) or expires <= now_ts:
        return None
    return employee_id
