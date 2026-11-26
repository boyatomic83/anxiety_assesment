"""Password hashing (argon2) and JWT tokens (SPEC.md section 10)."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import get_settings

_ph = PasswordHasher()
TokenType = Literal["access", "refresh"]


class TokenError(ValueError):
    pass


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def create_token(user_id: uuid.UUID, role: str, token_type: TokenType) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    ttl = (
        timedelta(minutes=s.access_token_expire_minutes)
        if token_type == "access"  # noqa: S105
        else timedelta(days=s.refresh_token_expire_days)
    )
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": token_type,
        "iat": now,
        "exp": now + ttl,
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, s.jwt_secret_key.get_secret_value(), algorithm=s.jwt_algorithm)


def decode_token(token: str, expected: TokenType) -> dict:
    s = get_settings()
    try:
        payload = jwt.decode(
            token, s.jwt_secret_key.get_secret_value(), algorithms=[s.jwt_algorithm]
        )
    except jwt.PyJWTError as e:
        raise TokenError("invalid or expired token") from e
    if payload.get("type") != expected:
        raise TokenError("wrong token type")
    return payload


def new_secret_token() -> str:
    return secrets.token_urlsafe(32)


def hash_secret(value: str) -> str:
    """Keyed hash for guest tokens and IPs, so raw values are never stored."""
    key = get_settings().jwt_secret_key.get_secret_value().encode()
    return hashlib.blake2b(value.encode(), key=key[:64], digest_size=32).hexdigest()
