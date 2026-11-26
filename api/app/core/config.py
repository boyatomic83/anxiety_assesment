"""Application settings.

Every environment variable in the repo-root ``.env.example`` is declared here
(``tests/test_config.py`` enforces this). Secrets come ONLY from the environment / ``.env``,
never hard-code them. Unknown variables are ignored; empty values fall back to the defaults.
"""

from functools import lru_cache
from typing import Annotated

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Repo-root .env when run from api/ locally; in Docker the vars arrive via env_file.
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        case_sensitive=False,
        protected_namespaces=("settings_",),  # allow model_path / model_version
    )

    # --- App ---
    app_env: str = "development"
    app_name: str = "Calma API"
    log_level: str = "INFO"
    app_version: str = "0.1.0"
    api_prefix: str = "/api/v1"

    # --- Database ---
    postgres_user: str = "calma"
    postgres_password: SecretStr | None = None
    postgres_db: str = "calma"
    postgres_host: str = "db"
    postgres_port: int = 5432
    database_url: SecretStr

    # --- Auth (SPEC section 10) ---
    jwt_secret_key: SecretStr
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # --- Encryption at rest (Fernet key) ---
    encryption_key: SecretStr

    # --- Bootstrap admin ---
    admin_email: str = "admin@example.com"
    admin_password: SecretStr | None = None

    # --- CORS ---
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    # --- Web (declared so config documents every variable; used by the Next.js build) ---
    next_public_api_url: str = "http://localhost:8000"

    # --- ML (Phase 5) ---
    model_path: str = "ml/models/model.joblib"
    model_version: str = "0.0.0"

    # --- Email (re-test reminders) ---
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: SecretStr | None = None
    email_from: str | None = None

    # --- Error tracking ---
    sentry_dsn: SecretStr | None = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @field_validator("app_env", mode="after")
    @classmethod
    def _normalise_env(cls, v: str) -> str:
        return v.strip().lower()

    @property
    def is_production(self) -> bool:
        return self.app_env in {"production", "prod"}


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # required fields come from env
