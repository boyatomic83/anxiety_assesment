"""Test configuration. Tests never touch the real .env: env vars set here take precedence."""

import os

TEST_ENV = {
    "APP_ENV": "test",
    "DATABASE_URL": "sqlite+pysqlite:///:memory:",
    "JWT_SECRET_KEY": "test-jwt-secret-that-is-long-enough-for-hs256",
    "ENCRYPTION_KEY": "dGVzdC1lbmNyeXB0aW9uLWtleS0zMi1ieXRlcy0hISE=",
    "CORS_ORIGINS": "http://localhost:3000",
    "BACKGROUND_JOBS_ENABLED": "false",
}
os.environ.update(TEST_ENV)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core import encryption, ratelimit  # noqa: E402
from app.core.config import Settings, get_settings  # noqa: E402

# Never read the developer's real .env during tests.
Settings.model_config["env_file"] = None
from app.db import _session_factory, get_engine  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Base  # noqa: E402
from app.services import ml  # noqa: E402


def _clear_caches():
    get_settings.cache_clear()
    get_engine.cache_clear()
    _session_factory.cache_clear()
    encryption._fernet.cache_clear()
    ml.load_model.cache_clear()
    ratelimit.reset()


@pytest.fixture
def db_url(tmp_path, monkeypatch):
    url = f"sqlite+pysqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    _clear_caches()
    Base.metadata.create_all(get_engine())
    yield url
    get_engine().dispose()
    _clear_caches()


@pytest.fixture
def db(db_url):
    with _session_factory()() as s:
        yield s


@pytest.fixture
def client(db_url):
    with TestClient(create_app()) as c:
        yield c
