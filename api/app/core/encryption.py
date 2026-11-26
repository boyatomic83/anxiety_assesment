"""Fernet encryption at rest for answers, context and free text (SPEC.md section 8)."""

import json
from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


class DecryptionError(ValueError):
    pass


@lru_cache
def _fernet() -> Fernet:
    return Fernet(get_settings().encryption_key.get_secret_value().encode())


def encrypt_json(value: Any) -> str:
    return _fernet().encrypt(json.dumps(value, ensure_ascii=False).encode()).decode()


def decrypt_json(token: str | None) -> Any:
    if token is None:
        return None
    try:
        return json.loads(_fernet().decrypt(token.encode()))
    except InvalidToken as e:
        raise DecryptionError("could not decrypt stored data") from e
