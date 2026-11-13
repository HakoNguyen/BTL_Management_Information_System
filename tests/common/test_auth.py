"""common/auth.py: băm mật khẩu và token phiên đăng nhập."""

from __future__ import annotations

from common.auth import hash_password, make_token, read_token, verify_password

SECRET = "khoa-a"
NOW = 1_800_000_000.0


def test_password_roundtrip() -> None:
    stored = hash_password("mat-khau")
    assert verify_password("mat-khau", stored)
    assert not verify_password("mat-khau-khac", stored)
    # Muối ngẫu nhiên: cùng mật khẩu cho hai chuỗi băm khác nhau
    assert stored != hash_password("mat-khau")


def test_verify_password_rejects_malformed_hash() -> None:
    assert not verify_password("x", "khong-phai-chuoi-bam")
    assert not verify_password("x", "md5$00$00")


def test_token_roundtrip() -> None:
    token = make_token("NV001", SECRET, NOW, ttl=60)
    assert read_token(token, SECRET, NOW + 59) == "NV001"


def test_token_expires() -> None:
    token = make_token("NV001", SECRET, NOW, ttl=60)
    assert read_token(token, SECRET, NOW + 60) is None


def test_token_rejects_tampering_and_wrong_secret() -> None:
    token = make_token("NV001", SECRET, NOW)
    other = make_token("NV002", SECRET, NOW)
    # Ghép payload của người khác với chữ ký của mình
    forged = other.split(".")[0] + "." + token.split(".")[1]
    assert read_token(forged, SECRET, NOW) is None
    assert read_token(token, "khoa-b", NOW) is None
    assert read_token("rac", SECRET, NOW) is None
    assert read_token("", SECRET, NOW) is None
