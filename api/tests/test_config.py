import pytest
from pydantic import ValidationError

from app.core.config import Settings

REQUIRED = {
    "DATABASE_URL": "sqlite+pysqlite:///:memory:",
    "JWT_SECRET_KEY": "x",
    "ENCRYPTION_KEY": "y",
}


def make(monkeypatch, **env):
    for k, v in {**REQUIRED, **env}.items():
        monkeypatch.setenv(k, v)
    return Settings(_env_file=None)


def test_cors_origins_parsed_from_comma_list(monkeypatch):
    s = make(monkeypatch, CORS_ORIGINS="http://a.test, http://b.test")
    assert s.cors_origins == ["http://a.test", "http://b.test"]


def test_secrets_are_not_exposed_in_repr(monkeypatch):
    s = make(monkeypatch, JWT_SECRET_KEY="super-secret-value")
    assert "super-secret-value" not in repr(s)
    assert s.jwt_secret_key.get_secret_value() == "super-secret-value"


@pytest.mark.parametrize("missing", sorted(REQUIRED))
def test_required_secrets_must_be_set(monkeypatch, missing):
    for k, v in REQUIRED.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv(missing)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_docs_disabled_in_production(monkeypatch):
    make(monkeypatch, APP_ENV="production")
    from app.core.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    try:
        app = create_app()
        assert app.docs_url is None
        assert app.openapi_url is None
    finally:
        get_settings.cache_clear()


def test_settings_declare_every_env_example_key():
    """config.py must cover every variable in the repo-root .env.example (key names only)."""
    import re
    from pathlib import Path

    example = Path(__file__).resolve().parents[2] / ".env.example"
    if not example.exists():
        pytest.skip(".env.example not found")
    keys = {
        m.group(1).lower()
        for line in example.read_text().splitlines()
        if (m := re.match(r"^([A-Z_][A-Z0-9_]*)=", line))
    }
    missing = sorted(keys - set(Settings.model_fields))
    assert not missing, f"Add these to Settings: {missing}"


def test_empty_optional_values_fall_back_to_defaults(monkeypatch):
    s = make(monkeypatch, SMTP_PORT="", SENTRY_DSN="", APP_ENV="Production")
    assert s.smtp_port == 587
    assert s.sentry_dsn is None
    assert s.is_production


@pytest.mark.parametrize(
    "url",
    ["postgres://u:p@h:5432/d", "postgresql://u:p@h:5432/d", "postgresql+psycopg://u:p@h:5432/d"],
)
def test_hosted_postgres_urls_use_psycopg(monkeypatch, url):
    s = make(monkeypatch, DATABASE_URL=url)
    assert s.database_url.get_secret_value() == "postgresql+psycopg://u:p@h:5432/d"
