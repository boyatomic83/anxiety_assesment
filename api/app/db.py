"""Database engine and session factory (SQLAlchemy 2)."""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    url = get_settings().database_url.get_secret_value()
    connect_args = {"connect_timeout": 3} if url.startswith("postgresql") else {}
    engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args)
    if url.startswith("sqlite"):
        # Enforce ON DELETE CASCADE / SET NULL like Postgres does.
        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _record):  # pragma: no cover - trivial
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

    return engine


@lru_cache
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = _session_factory()()
    try:
        yield db
    finally:
        db.close()


def check_database() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
