"""SQLAlchemy models. Import every model module here so Alembic autogenerate sees it."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


__all__ = ["Base"]
