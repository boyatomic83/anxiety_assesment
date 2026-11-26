"""SQLAlchemy models (SPEC.md section 8). Portable types so tests can run on SQLite."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="user")  # user|clinician|admin
    locale: Mapped[str] = mapped_column(String(10), default="en")
    reminder_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_reminded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    sessions: Mapped[list["AssessmentSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )


class AssessmentSession(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True
    )
    guest_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="in_progress")
    locale: Mapped[str] = mapped_column(String(10), default="en")
    consent_version: Mapped[str] = mapped_column(String(40))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    flagged: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    context_json_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped[User | None] = relationship(back_populates="sessions")
    responses: Mapped[list["Response"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", passive_deletes=True
    )
    result: Mapped["Result | None"] = relationship(
        back_populates="session", cascade="all, delete-orphan", passive_deletes=True
    )


class Response(Base):
    __tablename__ = "responses"
    __table_args__ = (UniqueConstraint("session_id", "questionnaire_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    questionnaire_id: Mapped[str] = mapped_column(String(40))
    questionnaire_version: Mapped[str] = mapped_column(String(20))
    answers_encrypted: Mapped[str] = mapped_column(Text)
    item_timings_json: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    session: Mapped[AssessmentSession] = relationship(back_populates="responses")


class Result(Base):
    __tablename__ = "results"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), unique=True
    )
    scores_json: Mapped[dict] = mapped_column(JSON)
    ml_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    session: Mapped[AssessmentSession] = relationship(back_populates="result")
    shares: Mapped[list["Share"]] = relationship(
        back_populates="result", cascade="all, delete-orphan", passive_deletes=True
    )


class Share(Base):
    __tablename__ = "shares"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    result_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("results.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    clinician_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    result: Mapped[Result] = relationship(back_populates="shares")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    action: Mapped[str] = mapped_column(String(60))
    target: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )


__all__ = ["AssessmentSession", "AuditLog", "Base", "Response", "Result", "Share", "User"]
