"""Test configuration. Tests never touch the real .env: env vars set here take precedence."""

import os

TEST_ENV = {
    "APP_ENV": "test",
    "DATABASE_URL": "sqlite+pysqlite:///:memory:",
    "JWT_SECRET_KEY": "test-jwt-secret",
    "ENCRYPTION_KEY": "dGVzdC1lbmNyeXB0aW9uLWtleS0zMi1ieXRlcy0hISE=",
    "CORS_ORIGINS": "http://localhost:3000",
}
os.environ.update(TEST_ENV)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db import get_engine  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture
def client():
    get_settings.cache_clear()
    get_engine.cache_clear()
    with TestClient(create_app()) as c:
        yield c
    get_engine().dispose()
    get_engine.cache_clear()
